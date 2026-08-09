import itertools
import math
import random
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from .config import LabConfig
from .ingest import candidates_by_source, load_candidate_manifest
from .preferences import labeled_pair_keys, load_preferences, preference_pair_key
from .schema import Candidate, WarningRecord
from .svg_diagnostics import rendered_svg_visibility_risk
from .utils import first_number, read_json, stable_id, utc_now_iso, write_jsonl


ANCHOR_PAIR_TARGET_FRACTION = 0.4
DOUBLE_FAILURE_RISK_THRESHOLD = 0.65
MAX_ANCHORS_PER_SOURCE = 12


def generate_review_queue(
    config: LabConfig,
    limit: int = 100,
    seed: int = 20260626,
    dry_run: bool = False,
    max_pairs_per_source: Optional[int] = None,
) -> Dict[str, Any]:
    warnings: List[WarningRecord] = []
    candidates = load_candidate_manifest(config.manifest_path)
    preferences = load_preferences(config.preference_path, warnings)
    model = read_json(Path(config.model_path), warnings) or {}
    score_map = model.get("candidate_scores") if isinstance(model, dict) else {}
    if not isinstance(score_map, dict):
        score_map = {}
    labeled = labeled_pair_keys(preferences)
    rng = random.Random(seed)
    rows: List[Dict[str, Any]] = []

    pair_cap = max_pairs_per_source or max(1000, limit * 50)
    for source_id, source_candidates in sorted(candidates_by_source(candidates).items()):
        usable = [candidate for candidate in source_candidates if candidate.artifact_paths.get("output")]
        if len(usable) < 2:
            continue
        for candidate_a, candidate_b in bounded_candidate_pairs(usable, rng, pair_cap, score_map):
            pair_key = preference_pair_key(source_id, candidate_a.candidate_id, candidate_b.candidate_id)
            if pair_key in labeled:
                continue
            rows.append(create_queue_record(source_id, candidate_a, candidate_b, rng, score_map))

    rows.sort(key=lambda row: row["priority"], reverse=True)
    selected = select_review_rows(rows, max(0, limit))
    write_jsonl(Path(config.review_queue_path), selected, dry_run=dry_run)
    return {
        "path": config.review_queue_path,
        "candidate_count": len(candidates),
        "preference_count": len(preferences),
        "pair_count": len(rows),
        "written_count": len(selected),
        "dry_run": dry_run,
        "selection_strategy": queue_strategy_summary(rows, selected, max(0, limit)),
        "warnings": [warning.to_dict() for warning in warnings],
    }


def bounded_candidate_pairs(
    candidates: List[Candidate],
    rng: random.Random,
    max_pairs: int,
    score_map: Optional[Dict[str, Any]] = None,
) -> List[Tuple[Candidate, Candidate]]:
    if len(candidates) < 2:
        return []
    all_pair_count = len(candidates) * (len(candidates) - 1) // 2
    if all_pair_count <= max_pairs:
        return list(itertools.combinations(candidates, 2))

    score_map = score_map or {}
    pairs: List[Tuple[Candidate, Candidate]] = []
    seen: Set[Tuple[str, str]] = set()

    def add_pair(left: Candidate, right: Candidate) -> None:
        if left.candidate_id == right.candidate_id:
            return
        key = tuple(sorted([left.candidate_id, right.candidate_id]))
        if key in seen:
            return
        seen.add(key)
        pairs.append((left, right))

    anchors = select_anchor_candidates(candidates, score_map)
    challengers = sorted(
        candidates,
        key=lambda candidate: candidate_review_need(candidate, score_map),
        reverse=True,
    )
    target_anchor_pairs = max(1, int(max_pairs * ANCHOR_PAIR_TARGET_FRACTION))
    for challenger in challengers:
        for anchor in anchors:
            add_pair(anchor, challenger)
            if len(pairs) >= target_anchor_pairs:
                break
        if len(pairs) >= target_anchor_pairs:
            break
    if len(pairs) >= max_pairs:
        return pairs[:max_pairs]

    by_score = sorted(candidates, key=lambda candidate: candidate_review_score(candidate, score_map) or 0.0)
    for left, right in zip(by_score, by_score[1:]):
        if pair_double_failure_risk(left, right, score_map) >= DOUBLE_FAILURE_RISK_THRESHOLD:
            continue
        add_pair(left, right)
        if len(pairs) >= max_pairs:
            return pairs

    risky = sorted(
        candidates,
        key=lambda candidate: candidate_failure_risk(candidate, score_map),
        reverse=True,
    )[: min(100, len(candidates))]
    partner_pool = anchors or candidates
    for left in risky:
        for right in rng.sample(partner_pool, k=min(8, len(partner_pool))):
            add_pair(left, right)
            if len(pairs) >= max_pairs:
                return pairs

    attempts = 0
    while len(pairs) < max_pairs and attempts < max_pairs * 20:
        attempts += 1
        left, right = rng.sample(candidates, 2)
        if (
            pair_double_failure_risk(left, right, score_map) >= DOUBLE_FAILURE_RISK_THRESHOLD
            and len(pairs) < int(max_pairs * 0.9)
        ):
            continue
        add_pair(left, right)
        if len(seen) >= all_pair_count:
            break
    return pairs


def create_queue_record(
    source_id: str,
    candidate_a: Candidate,
    candidate_b: Candidate,
    rng: random.Random,
    score_map: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    score_map = score_map or {}
    score_a = candidate_review_score(candidate_a, score_map)
    score_b = candidate_review_score(candidate_b, score_map)
    uncertainty = pair_uncertainty(score_a, score_b)
    risk_a = visual_risk(candidate_a)
    risk_b = visual_risk(candidate_b)
    risk = max(risk_a, risk_b)
    anchor_pair = pair_anchor_signal(candidate_a, candidate_b, score_map)
    double_failure_risk = pair_double_failure_risk(candidate_a, candidate_b, score_map)
    score_gap = 0.0 if score_a is None or score_b is None else min(1.0, abs(score_a - score_b) / 0.25)
    exploration = rng.random()
    priority = (
        0.3 * uncertainty
        + 0.25 * anchor_pair
        + 0.15 * risk
        + 0.15 * exploration
        + 0.15 * score_gap
        - 0.45 * double_failure_risk
    )
    queue_id = "queue-" + stable_id(source_id, candidate_a.candidate_id, candidate_b.candidate_id)
    return {
        "queue_id": queue_id,
        "created_at": utc_now_iso(),
        "source_id": source_id,
        "candidate_a": candidate_a.candidate_id,
        "candidate_b": candidate_b.candidate_id,
        "priority": round(priority, 6),
        "selection_reasons": {
            "uncertainty": round(uncertainty, 6),
            "visual_risk": round(risk, 6),
            "anchor_pair": round(anchor_pair, 6),
            "double_failure_risk": round(double_failure_risk, 6),
            "model_score_gap": round(score_gap, 6),
            "candidate_a_anchor_strength": round(candidate_anchor_strength(candidate_a, score_map), 6),
            "candidate_b_anchor_strength": round(candidate_anchor_strength(candidate_b, score_map), 6),
            "candidate_a_failure_risk": round(candidate_failure_risk(candidate_a, score_map), 6),
            "candidate_b_failure_risk": round(candidate_failure_risk(candidate_b, score_map), 6),
            "random_exploration": round(exploration, 6),
        },
        "blind_artifacts": {
            "A": candidate_a.artifact_paths.get("output"),
            "B": candidate_b.artifact_paths.get("output"),
        },
        "diagnostic_artifacts": {
            "A": candidate_a.artifact_paths.get("comparison"),
            "B": candidate_b.artifact_paths.get("comparison"),
        },
        "review_state": "pending",
    }


def select_review_rows(rows: List[Dict[str, Any]], limit: int) -> List[Dict[str, Any]]:
    if limit <= 0:
        return []
    safe_rows = [
        row
        for row in rows
        if row["selection_reasons"].get("double_failure_risk", 0.0) < DOUBLE_FAILURE_RISK_THRESHOLD
    ]
    pool = safe_rows or rows
    selected: List[Dict[str, Any]] = []
    selected_ids: Set[str] = set()

    def append(row: Dict[str, Any]) -> None:
        if row["queue_id"] in selected_ids:
            return
        selected_ids.add(row["queue_id"])
        selected.append(row)

    target_anchor_count = min(limit, int(math.ceil(limit * ANCHOR_PAIR_TARGET_FRACTION)))
    anchor_rows = [
        row
        for row in pool
        if row["selection_reasons"].get("anchor_pair", 0.0) > 0.0
    ]
    for row in source_diverse_rows(anchor_rows)[:target_anchor_count]:
        append(row)
        if len(selected) >= limit:
            break

    for row in source_diverse_rows(pool):
        append(row)
        if len(selected) >= limit:
            break

    if len(selected) < limit and pool is not rows:
        for row in source_diverse_rows(rows):
            append(row)
            if len(selected) >= limit:
                break

    selected.sort(key=lambda row: row["priority"], reverse=True)
    return selected


def queue_strategy_summary(
    rows: List[Dict[str, Any]],
    selected: List[Dict[str, Any]],
    limit: int,
) -> Dict[str, Any]:
    target_anchor_count = int(math.ceil(limit * ANCHOR_PAIR_TARGET_FRACTION)) if limit else 0
    return {
        "name": "source-balanced-anchor-mixed-failure-aware",
        "anchor_pair_target_fraction": ANCHOR_PAIR_TARGET_FRACTION,
        "anchor_pair_target_count": target_anchor_count,
        "available_anchor_pair_count": count_anchor_pairs(rows),
        "selected_anchor_pair_count": count_anchor_pairs(selected),
        "available_double_failure_risk_pair_count": count_double_failure_pairs(rows),
        "selected_double_failure_risk_pair_count": count_double_failure_pairs(selected),
        "available_source_count": count_sources(rows),
        "selected_source_count": count_sources(selected),
        "double_failure_risk_threshold": DOUBLE_FAILURE_RISK_THRESHOLD,
        "goal": "reduce both_bad-vs-both_bad reviews while keeping labels spread across source images",
    }


def count_anchor_pairs(rows: List[Dict[str, Any]]) -> int:
    return sum(1 for row in rows if row["selection_reasons"].get("anchor_pair", 0.0) > 0.0)


def count_double_failure_pairs(rows: List[Dict[str, Any]]) -> int:
    return sum(
        1
        for row in rows
        if row["selection_reasons"].get("double_failure_risk", 0.0) >= DOUBLE_FAILURE_RISK_THRESHOLD
    )


def count_sources(rows: List[Dict[str, Any]]) -> int:
    return len({row.get("source_id") for row in rows if row.get("source_id")})


def source_diverse_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if len(rows) < 2:
        return rows
    by_source: Dict[str, List[Dict[str, Any]]] = {}
    source_order: List[str] = []
    for row in rows:
        source_id = str(row.get("source_id") or "")
        if source_id not in by_source:
            by_source[source_id] = []
            source_order.append(source_id)
        by_source[source_id].append(row)

    ranked: List[Dict[str, Any]] = []
    while len(ranked) < len(rows):
        appended = False
        for source_id in source_order:
            source_rows = by_source[source_id]
            if not source_rows:
                continue
            ranked.append(source_rows.pop(0))
            appended = True
        if not appended:
            break
    return ranked


def select_anchor_candidates(
    candidates: List[Candidate],
    score_map: Dict[str, Any],
    limit: int = MAX_ANCHORS_PER_SOURCE,
) -> List[Candidate]:
    ranked = sorted(
        candidates,
        key=lambda candidate: candidate_anchor_strength(candidate, score_map),
        reverse=True,
    )
    anchors = [
        candidate
        for candidate in ranked
        if candidate.app_ready
        and candidate_anchor_strength(candidate, score_map) >= 0.55
        and candidate_failure_risk(candidate, score_map) < DOUBLE_FAILURE_RISK_THRESHOLD
    ]
    if not anchors:
        anchors = [
            candidate
            for candidate in ranked
            if candidate_failure_risk(candidate, score_map) < DOUBLE_FAILURE_RISK_THRESHOLD
        ]
    return anchors[: min(limit, len(anchors))]


def candidate_review_need(candidate: Candidate, score_map: Dict[str, Any]) -> float:
    uncertainty = candidate_model_uncertainty(candidate, score_map)
    return clamp01(
        0.45 * uncertainty
        + 0.35 * candidate_failure_risk(candidate, score_map)
        + 0.2 * (1.0 - candidate_anchor_strength(candidate, score_map))
    )


def candidate_review_score(candidate: Candidate, score_map: Dict[str, Any]) -> Optional[float]:
    model_score = candidate_model_record(candidate, score_map)
    score = first_number(model_score.get("win_probability"))
    if score is not None:
        return clamp01(score)
    return candidate_preference_proxy(candidate)


def candidate_anchor_strength(candidate: Candidate, score_map: Dict[str, Any]) -> float:
    score = candidate_review_score(candidate, score_map)
    preference = clamp01(score if score is not None else 0.0)
    stability = 1.0 - visual_risk(candidate)
    observation = 1.0 - min(1.0, candidate_model_uncertainty(candidate, score_map))
    app_ready = 1.0 if candidate.app_ready else 0.0
    failure_penalty = min(1.0, candidate_both_bad_count(candidate, score_map) / 2.0)
    return clamp01(
        0.5 * preference
        + 0.25 * stability
        + 0.15 * app_ready
        + 0.1 * observation
        - 0.5 * failure_penalty
    )


def candidate_failure_risk(candidate: Candidate, score_map: Dict[str, Any]) -> float:
    score = candidate_review_score(candidate, score_map)
    low_score = 0.5 if score is None else 1.0 - clamp01(score)
    observed_failure = min(1.0, candidate_both_bad_count(candidate, score_map) / 2.0)
    proxy_failure = 0.6 * visual_risk(candidate) + 0.4 * low_score
    return clamp01(max(observed_failure, proxy_failure))


def pair_anchor_signal(candidate_a: Candidate, candidate_b: Candidate, score_map: Dict[str, Any]) -> float:
    anchor_a = candidate_anchor_strength(candidate_a, score_map)
    anchor_b = candidate_anchor_strength(candidate_b, score_map)
    failure_a = candidate_failure_risk(candidate_a, score_map)
    failure_b = candidate_failure_risk(candidate_b, score_map)
    if anchor_a >= anchor_b:
        anchor_strength = anchor_a
        partner_failure = failure_b
    else:
        anchor_strength = anchor_b
        partner_failure = failure_a
    if anchor_strength < 0.55:
        return 0.0
    return clamp01(anchor_strength * (0.5 + 0.5 * partner_failure))


def pair_double_failure_risk(candidate_a: Candidate, candidate_b: Candidate, score_map: Dict[str, Any]) -> float:
    shared_failure = min(
        candidate_failure_risk(candidate_a, score_map),
        candidate_failure_risk(candidate_b, score_map),
    )
    strongest_anchor = max(
        candidate_anchor_strength(candidate_a, score_map),
        candidate_anchor_strength(candidate_b, score_map),
    )
    return clamp01(shared_failure * (1.0 - strongest_anchor))


def candidate_model_record(candidate: Candidate, score_map: Dict[str, Any]) -> Dict[str, Any]:
    record = score_map.get(candidate.candidate_id) or {}
    return record if isinstance(record, dict) else {}


def candidate_model_uncertainty(candidate: Candidate, score_map: Dict[str, Any]) -> float:
    uncertainty = first_number(candidate_model_record(candidate, score_map).get("uncertainty"))
    return clamp01(uncertainty if uncertainty is not None else 1.0)


def candidate_both_bad_count(candidate: Candidate, score_map: Dict[str, Any]) -> float:
    count = first_number(candidate_model_record(candidate, score_map).get("both_bad_count"))
    return max(0.0, count or 0.0)


def clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def candidate_preference_proxy(candidate: Candidate) -> Optional[float]:
    return first_number(
        candidate.score,
        candidate.metrics.get("visualQualityScore"),
        candidate.metrics.get("targetScore"),
        candidate.metrics.get("sourceArtifactScore"),
        candidate.metrics.get("ssim"),
    )


def pair_uncertainty(score_a: Optional[float], score_b: Optional[float]) -> float:
    if score_a is None or score_b is None:
        return 0.85
    return max(0.0, 1.0 - min(1.0, abs(score_a - score_b) / 0.25))


def visual_risk(candidate: Candidate) -> float:
    visual_quality = first_number(candidate.metrics.get("visualQualityScore"), candidate.score)
    clump = first_number(candidate.metrics.get("lineClumpPenalty")) or 0.0
    overdraw = first_number(candidate.metrics.get("overdrawRate")) or 0.0
    runtime = first_number(candidate.runtime_ms, candidate.metrics.get("totalMs")) or 0.0
    line_count = first_number(candidate.line_count, candidate.metrics.get("finalLineCount")) or 0.0
    rendered_visibility = rendered_svg_visibility_risk(candidate.metadata.get("rendered_svg"))
    low_quality = 0.5 if visual_quality is None else max(0.0, min(1.0, 0.8 - visual_quality))
    runtime_risk = max(0.0, min(1.0, (runtime - 30000.0) / 120000.0))
    line_risk = max(0.0, min(1.0, (line_count - 4800.0) / 2400.0))
    return max(
        0.0,
        min(
            1.0,
            low_quality
            + 0.3 * clump
            + 0.25 * overdraw
            + 0.2 * runtime_risk
            + 0.1 * line_risk
            + 0.35 * rendered_visibility,
        ),
    )
