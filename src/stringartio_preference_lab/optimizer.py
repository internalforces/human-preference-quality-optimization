import random
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from .config import LabConfig
from .generation_quality_contract import (
    DEFAULT_GENERATION_QUALITY_CONTRACT,
    app_ready_line_count_limit,
    app_ready_runtime_target_ms,
    forbidden_truthy_config_fields,
    generation_quality_contract_reference,
    load_generation_quality_contract,
    preferred_line_count_max as contract_preferred_line_count_max,
    preferred_line_count_min as contract_preferred_line_count_min,
    visibility_value,
)
from .ingest import has_target_aware_logic, load_candidate_manifest
from .schema import Candidate, WarningRecord
from .svg_diagnostics import rendered_svg_diagnostic_summary, rendered_svg_visibility_risk
from .utils import first_int, first_number, read_json, stable_id, utc_now_iso, write_json


DEFAULT_RUNTIME_LIMIT_MS = app_ready_runtime_target_ms(DEFAULT_GENERATION_QUALITY_CONTRACT)
DEFAULT_LINE_COUNT_LIMIT = app_ready_line_count_limit(DEFAULT_GENERATION_QUALITY_CONTRACT)
DEFAULT_MIN_VISUAL_OPACITY_SCALE = visibility_value(
    DEFAULT_GENERATION_QUALITY_CONTRACT, "minVisualOpacityScale", 0.6
)
DEFAULT_MIN_VISUAL_WIDTH_SCALE = visibility_value(
    DEFAULT_GENERATION_QUALITY_CONTRACT, "minVisualWidthScale", 0.8
)
DEFAULT_MIN_LINE_INK = visibility_value(DEFAULT_GENERATION_QUALITY_CONTRACT, "minLineInk", 0.0085)
DEFAULT_MIN_VISIBLE_INK = visibility_value(DEFAULT_GENERATION_QUALITY_CONTRACT, "minVisibleInk", 0.004)
DEFAULT_TARGET_VISUAL_OPACITY_SCALE = visibility_value(
    DEFAULT_GENERATION_QUALITY_CONTRACT, "targetVisualOpacityScale", 0.7
)
DEFAULT_TARGET_VISUAL_WIDTH_SCALE = visibility_value(
    DEFAULT_GENERATION_QUALITY_CONTRACT, "targetVisualWidthScale", 0.9
)
DEFAULT_TARGET_LINE_INK = visibility_value(DEFAULT_GENERATION_QUALITY_CONTRACT, "targetLineInk", 0.009)
DEFAULT_TARGET_VISIBLE_INK = visibility_value(DEFAULT_GENERATION_QUALITY_CONTRACT, "targetVisibleInk", 0.0055)
DEFAULT_PREFERRED_LINE_COUNT_MIN = contract_preferred_line_count_min(DEFAULT_GENERATION_QUALITY_CONTRACT)
DEFAULT_PREFERRED_LINE_COUNT_MAX = contract_preferred_line_count_max(DEFAULT_GENERATION_QUALITY_CONTRACT)
SUGGESTION_VISUAL_RISK_PENALTY = 0.25


def suggest_configurations(
    config: LabConfig,
    limit: int = 10,
    runtime_limit_ms: Optional[int] = None,
    line_count_limit: Optional[int] = None,
    min_visual_opacity_scale: Optional[float] = None,
    min_visual_width_scale: Optional[float] = None,
    min_line_ink: Optional[float] = None,
    min_visible_ink: Optional[float] = None,
    target_visual_opacity_scale: Optional[float] = None,
    target_visual_width_scale: Optional[float] = None,
    target_line_ink: Optional[float] = None,
    target_visible_ink: Optional[float] = None,
    preferred_line_count_min: Optional[int] = None,
    preferred_line_count_max: Optional[int] = None,
    seed: int = 20260626,
    dry_run: bool = False,
) -> Dict[str, Any]:
    warnings: List[WarningRecord] = []
    contract = load_generation_quality_contract(config, warnings)
    runtime_limit_ms = int(runtime_limit_ms or app_ready_runtime_target_ms(contract))
    line_count_limit = int(line_count_limit or app_ready_line_count_limit(contract))
    min_visual_opacity_scale = float(
        min_visual_opacity_scale
        if min_visual_opacity_scale is not None
        else visibility_value(contract, "minVisualOpacityScale", DEFAULT_MIN_VISUAL_OPACITY_SCALE)
    )
    min_visual_width_scale = float(
        min_visual_width_scale
        if min_visual_width_scale is not None
        else visibility_value(contract, "minVisualWidthScale", DEFAULT_MIN_VISUAL_WIDTH_SCALE)
    )
    min_line_ink = float(
        min_line_ink if min_line_ink is not None else visibility_value(contract, "minLineInk", DEFAULT_MIN_LINE_INK)
    )
    min_visible_ink = float(
        min_visible_ink
        if min_visible_ink is not None
        else visibility_value(contract, "minVisibleInk", DEFAULT_MIN_VISIBLE_INK)
    )
    target_visual_opacity_scale = float(
        target_visual_opacity_scale
        if target_visual_opacity_scale is not None
        else visibility_value(contract, "targetVisualOpacityScale", DEFAULT_TARGET_VISUAL_OPACITY_SCALE)
    )
    target_visual_width_scale = float(
        target_visual_width_scale
        if target_visual_width_scale is not None
        else visibility_value(contract, "targetVisualWidthScale", DEFAULT_TARGET_VISUAL_WIDTH_SCALE)
    )
    target_line_ink = float(
        target_line_ink
        if target_line_ink is not None
        else visibility_value(contract, "targetLineInk", DEFAULT_TARGET_LINE_INK)
    )
    target_visible_ink = float(
        target_visible_ink
        if target_visible_ink is not None
        else visibility_value(contract, "targetVisibleInk", DEFAULT_TARGET_VISIBLE_INK)
    )
    preferred_line_count_min = int(
        preferred_line_count_min
        if preferred_line_count_min is not None
        else contract_preferred_line_count_min(contract)
    )
    preferred_line_count_max = int(
        preferred_line_count_max
        if preferred_line_count_max is not None
        else contract_preferred_line_count_max(contract)
    )
    forbidden_fields = forbidden_truthy_config_fields(contract)
    (
        target_visual_opacity_scale,
        target_visual_width_scale,
        target_line_ink,
        target_visible_ink,
    ) = effective_visibility_targets(
        min_visual_opacity_scale,
        min_visual_width_scale,
        min_line_ink,
        min_visible_ink,
        target_visual_opacity_scale,
        target_visual_width_scale,
        target_line_ink,
        target_visible_ink,
    )
    preferred_line_count_min, preferred_line_count_max = normalized_preferred_line_count_range(
        preferred_line_count_min,
        preferred_line_count_max,
        line_count_limit,
    )
    candidates = load_candidate_manifest(config.manifest_path)
    model = read_json(Path(config.model_path), warnings) or {}
    score_map = model.get("candidate_scores") or {}
    preference_lab_failures_by_suggestion, preference_lab_failures_by_candidate = (
        preference_lab_regenerated_constraint_failures(
            candidates,
            runtime_limit_ms,
            line_count_limit,
            forbidden_truthy_config_fields(contract),
        )
    )
    preference_lab_failures = (
        preference_lab_failures_by_suggestion,
        preference_lab_failures_by_candidate,
    )
    rejection_counts: Dict[str, int] = {}
    eligible: List[Candidate] = []
    for candidate in candidates:
        failures = candidate_constraint_failures(
            candidate,
            runtime_limit_ms,
            line_count_limit,
            min_visual_opacity_scale,
            min_visual_width_scale,
            min_line_ink,
            min_visible_ink,
            preference_lab_failures,
            forbidden_fields,
        )
        if failures:
            for failure in failures:
                rejection_counts[failure] = rejection_counts.get(failure, 0) + 1
        else:
            eligible.append(candidate)
    if not eligible:
        warnings.append(WarningRecord("No candidates satisfy optimizer constraints"))
    rendered_svg_summary = {
        "all_candidates": rendered_svg_diagnostic_summary(candidates),
        "eligible_candidates": rendered_svg_diagnostic_summary(eligible),
    }

    ranked_all = sorted(
        eligible,
        key=lambda candidate: suggestion_base_score(
            candidate,
            score_map,
            runtime_limit_ms,
            preferred_line_count_min,
            preferred_line_count_max,
        ),
        reverse=True,
    )
    stable_ranked = [
        candidate
        for candidate in ranked_all
        if model_candidate_both_bad_count(candidate, score_map) <= 0.0
    ]
    stable_ids = {candidate.candidate_id for candidate in stable_ranked}
    failure_observed_ranked = [
        candidate
        for candidate in ranked_all
        if candidate.candidate_id not in stable_ids
    ]
    ranked = source_diverse_rank(stable_ranked) + source_diverse_rank(failure_observed_ranked)
    observed_ranges = numeric_config_ranges(eligible or candidates)
    rng = random.Random(seed)
    suggestions: List[Dict[str, Any]] = []
    attempts = 0
    while ranked and len(suggestions) < limit and attempts < limit * 40:
        attempts += 1
        base = ranked[(attempts - 1) % len(ranked)]
        proposed = sanitize_target_aware_config(perturb_config(base.config, observed_ranges, rng))
        proposed = enforce_visibility_floors(
            proposed,
            min_visual_opacity_scale,
            min_visual_width_scale,
            min_line_ink,
            min_visible_ink,
        )
        proposed = enforce_visibility_floors(
            proposed,
            target_visual_opacity_scale,
            target_visual_width_scale,
            target_line_ink,
            target_visible_ink,
        )
        proposed = steer_line_count_to_preferred_band(
            proposed,
            line_count_limit,
            preferred_line_count_min,
            preferred_line_count_max,
        )
        proposed_line_count = first_int(proposed.get("finalLineCap"), proposed.get("threadCount"), base.line_count)
        if proposed_line_count and proposed_line_count > line_count_limit:
            proposed["finalLineCap"] = line_count_limit
            proposed["threadCount"] = min(first_int(proposed.get("threadCount")) or line_count_limit, line_count_limit)
        suggestion_id = "suggestion-" + stable_id(base.candidate_id, proposed, attempts)
        if any(existing["config"] == proposed for existing in suggestions):
            continue
        posterior_mean = model_candidate_score(base, score_map)
        uncertainty = suggestion_uncertainty(base, score_map, proposed, observed_ranges)
        base_failure_penalty = model_candidate_failure_penalty(base, score_map)
        acquisition = posterior_mean + 0.2 * uncertainty - base_failure_penalty
        suggestions.append(
            {
                "suggestion_id": suggestion_id,
                "created_at": utc_now_iso(),
                "experiment_intent": "preference_tuning_suggestion",
                "config": proposed,
                "expected_preference_score": round(posterior_mean, 6),
                "preference_score": round(posterior_mean, 6),
                "uncertainty": round(uncertainty, 6),
                "acquisition": round(acquisition, 6),
                "acquisition_score": round(acquisition, 6),
                "nearest_observed_candidate": base.candidate_id,
                "base_candidate_id": base.candidate_id,
                "source_id": base.source_id,
                "source_run_id": base.run_id,
                "base_model_signal": {
                    "both_bad_count": round(model_candidate_both_bad_count(base, score_map), 6),
                    "failure_penalty": round(base_failure_penalty, 6),
                    "stable_anchor_base": model_candidate_both_bad_count(base, score_map) <= 0.0,
                },
                "constraints": {
                    "app_ready": True,
                    "runtime_limit_ms": runtime_limit_ms,
                    "line_count_limit": line_count_limit,
                    "no_target_aware_logic": True,
                    "generation_quality_contract": generation_quality_contract_reference(contract),
                    "visibility": visibility_constraints(
                        min_visual_opacity_scale,
                        min_visual_width_scale,
                        min_line_ink,
                        min_visible_ink,
                        target_visual_opacity_scale,
                        target_visual_width_scale,
                        target_line_ink,
                        target_visible_ink,
                    ),
                    "preferred_line_count_range": line_count_preference_constraints(
                        preferred_line_count_min,
                        preferred_line_count_max,
                    ),
                    "auto_execute_js_experiments": False,
                },
                "provenance": {
                    "optimizer": "constrained-preference-guided-search-v1",
                    "surrogate": model.get("method") or "unknown",
                    "acquisition": "posterior_mean_plus_uncertainty_minus_failure_penalty",
                    "bayesian_optimization": False,
                    "base_candidate_diagnostics": base_candidate_diagnostics(base),
                    "supported_handoff_intents": [
                        "render_model_calibration",
                        "bounded_add_remove_local_search",
                        "conservative_auto_color",
                    ],
                    "note": "Suggestion only. This tool never runs StringArtio JS experiments.",
                },
                "status": "not_executed",
            }
        )

    output = {
        "schema_version": 1,
        "created_at": utc_now_iso(),
        "method": "constrained-preference-guided-search",
        "bayesian_optimization": False,
        "constraints": {
            "app_ready": True,
            "runtime_limit_ms": runtime_limit_ms,
            "line_count_limit": line_count_limit,
            "no_target_aware_logic": True,
            "target_aware": False,
            "generation_quality_contract": generation_quality_contract_reference(contract),
            "visibility": visibility_constraints(
                min_visual_opacity_scale,
                min_visual_width_scale,
                min_line_ink,
                min_visible_ink,
                target_visual_opacity_scale,
                target_visual_width_scale,
                target_line_ink,
                target_visible_ink,
            ),
            "preferred_line_count_range": line_count_preference_constraints(
                preferred_line_count_min,
                preferred_line_count_max,
            ),
            "auto_execute_js_experiments": False,
        },
        "input": {
            "candidate_count": len(candidates),
            "eligible_candidate_count": len(eligible),
            "source_count": distinct_source_count(candidates),
            "eligible_source_count": distinct_source_count(eligible),
            "stable_base_source_count": distinct_source_count(stable_ranked),
            "stable_base_candidate_count": len(stable_ranked),
            "failure_observed_candidate_count": sum(
                1
                for candidate in eligible
                if model_candidate_both_bad_count(candidate, score_map) > 0.0
            ),
            "constraint_rejection_counts": dict(sorted(rejection_counts.items())),
            "rendered_svg_diagnostics": rendered_svg_summary,
            "source_diversity_strategy": {
                "name": "stable-source-interleaving",
                "goal": "avoid anchoring suggestions to only the highest-scoring source image",
            },
            "model_path": config.model_path,
        },
        "suggestions": suggestions,
        "warnings": [warning.to_dict() for warning in warnings],
    }
    write_json(Path(config.suggestions_path), output, dry_run=dry_run)
    return output


def satisfies_constraints(
    candidate: Candidate,
    runtime_limit_ms: int,
    line_count_limit: int,
    min_visual_opacity_scale: float = DEFAULT_MIN_VISUAL_OPACITY_SCALE,
    min_visual_width_scale: float = DEFAULT_MIN_VISUAL_WIDTH_SCALE,
    min_line_ink: float = DEFAULT_MIN_LINE_INK,
    min_visible_ink: float = DEFAULT_MIN_VISIBLE_INK,
) -> bool:
    return not candidate_constraint_failures(
        candidate,
        runtime_limit_ms,
        line_count_limit,
        min_visual_opacity_scale,
        min_visual_width_scale,
        min_line_ink,
        min_visible_ink,
    )


def candidate_constraint_failures(
    candidate: Candidate,
    runtime_limit_ms: int,
    line_count_limit: int,
    min_visual_opacity_scale: float,
    min_visual_width_scale: float,
    min_line_ink: float,
    min_visible_ink: float,
    preference_lab_failures: Optional[Tuple[Dict[str, Set[str]], Dict[str, Set[str]]]] = None,
    forbidden_config_fields: Optional[List[str]] = None,
) -> List[str]:
    failures: List[str] = []
    if not candidate.app_ready:
        failures.append("app_ready")
    if has_target_aware_logic(candidate.config, forbidden_config_fields):
        failures.append("target_aware_logic")
    runtime = first_number(candidate.runtime_ms, candidate.metrics.get("totalMs"))
    if runtime is not None and runtime > runtime_limit_ms:
        failures.append("runtime_limit_ms")
    line_count = first_int(
        candidate.line_count,
        candidate.metrics.get("finalLineCount"),
        candidate.config.get("threadCount"),
    )
    if line_count is not None and line_count > line_count_limit:
        failures.append("line_count_limit")
    failures.extend(
        visibility_constraint_failures(
            candidate.config,
            min_visual_opacity_scale,
            min_visual_width_scale,
            min_line_ink,
            min_visible_ink,
        )
    )
    if preference_lab_failures:
        suggestion_failures, candidate_failures = preference_lab_failures
        linked_failures: Set[str] = set()
        suggestion_id = preference_lab_suggestion_id(candidate)
        if suggestion_id:
            linked_failures.update(suggestion_failures.get(suggestion_id, set()))
        linked_failures.update(candidate_failures.get(candidate.candidate_id, set()))
        failures.extend(sorted(linked_failures))
    return failures


def preference_lab_regenerated_constraint_failures(
    candidates: List[Candidate],
    runtime_limit_ms: int,
    line_count_limit: int,
    forbidden_config_fields: Optional[List[str]] = None,
) -> Tuple[Dict[str, Set[str]], Dict[str, Set[str]]]:
    failures_by_suggestion: Dict[str, Set[str]] = {}
    failures_by_candidate: Dict[str, Set[str]] = {}
    candidate_ids_by_family: Dict[str, Set[str]] = {}
    for candidate in candidates:
        candidate_ids_by_family.setdefault(
            preference_lab_candidate_family_id(candidate.candidate_id),
            set(),
        ).add(candidate.candidate_id)
    for candidate in candidates:
        suggestion_id = preference_lab_suggestion_id(candidate)
        if not suggestion_id:
            continue
        observed_failures: Set[str] = set()
        runtime = first_number(candidate.runtime_ms, candidate.metrics.get("totalMs"))
        line_count = first_int(
            candidate.line_count,
            candidate.metrics.get("finalLineCount"),
            candidate.config.get("threadCount"),
        )
        if runtime is not None and runtime > runtime_limit_ms:
            observed_failures.add("preference_lab_regenerated_runtime_limit_ms")
        if line_count is not None and line_count > line_count_limit:
            observed_failures.add("preference_lab_regenerated_line_count_limit")
        if has_target_aware_logic(candidate.config, forbidden_config_fields):
            observed_failures.add("preference_lab_regenerated_target_aware_logic")
        if not observed_failures:
            continue
        failures_by_suggestion.setdefault(suggestion_id, set()).update(observed_failures)
        linked_candidate_ids = {candidate.candidate_id}
        nearest_observed_candidate = preference_lab_nearest_observed_candidate(candidate)
        if nearest_observed_candidate:
            linked_candidate_ids.add(nearest_observed_candidate)
        for candidate_id in linked_candidate_ids:
            candidate_family = preference_lab_candidate_family_id(candidate_id)
            family_candidate_ids = candidate_ids_by_family.get(candidate_family) or {candidate_id}
            for family_candidate_id in family_candidate_ids:
                failures_by_candidate.setdefault(family_candidate_id, set()).update(observed_failures)
    return failures_by_suggestion, failures_by_candidate


def preference_lab_suggestion_id(candidate: Candidate) -> str:
    preference_lab = candidate.metadata.get("preference_lab") or {}
    return str(preference_lab.get("suggestion_id") or "")


def preference_lab_nearest_observed_candidate(candidate: Candidate) -> str:
    preference_lab = candidate.metadata.get("preference_lab") or {}
    return str(preference_lab.get("nearest_observed_candidate") or "")


def preference_lab_candidate_family_id(candidate_id: str) -> str:
    return str(candidate_id).split("::pair-", 1)[0]


def visibility_constraint_failures(
    config: Dict[str, Any],
    min_visual_opacity_scale: float,
    min_visual_width_scale: float,
    min_line_ink: float,
    min_visible_ink: float,
) -> List[str]:
    failures: List[str] = []
    opacity = first_number(config.get("visualOpacityScale"))
    width = first_number(config.get("visualWidthScale"))
    line_ink = first_number(config.get("lineInk"))
    if opacity is not None and opacity < min_visual_opacity_scale:
        failures.append("visual_opacity_scale_floor")
    if width is not None and width < min_visual_width_scale:
        failures.append("visual_width_scale_floor")
    if line_ink is not None and line_ink < min_line_ink:
        failures.append("line_ink_floor")
    visible_ink = visible_ink_score(config)
    if visible_ink is not None and visible_ink < min_visible_ink:
        failures.append("visible_ink_floor")
    return failures


def visibility_constraints(
    min_visual_opacity_scale: float,
    min_visual_width_scale: float,
    min_line_ink: float,
    min_visible_ink: float,
    target_visual_opacity_scale: float,
    target_visual_width_scale: float,
    target_line_ink: float,
    target_visible_ink: float,
) -> Dict[str, Any]:
    return {
        "policy": "minimum_floor_plus_app_upload_target",
        "min_visual_opacity_scale": min_visual_opacity_scale,
        "min_visual_width_scale": min_visual_width_scale,
        "min_line_ink": min_line_ink,
        "min_visible_ink": min_visible_ink,
        "target_visual_opacity_scale": target_visual_opacity_scale,
        "target_visual_width_scale": target_visual_width_scale,
        "target_line_ink": target_line_ink,
        "target_visible_ink": target_visible_ink,
    }


def line_count_preference_constraints(preferred_min: int, preferred_max: int) -> Dict[str, int]:
    return {
        "preferred_min": preferred_min,
        "preferred_max": preferred_max,
    }


def effective_visibility_targets(
    min_visual_opacity_scale: float,
    min_visual_width_scale: float,
    min_line_ink: float,
    min_visible_ink: float,
    target_visual_opacity_scale: float,
    target_visual_width_scale: float,
    target_line_ink: float,
    target_visible_ink: float,
) -> Tuple[float, float, float, float]:
    return (
        max(min_visual_opacity_scale, target_visual_opacity_scale),
        max(min_visual_width_scale, target_visual_width_scale),
        max(min_line_ink, target_line_ink),
        max(min_visible_ink, target_visible_ink),
    )


def visible_ink_score(config: Dict[str, Any]) -> Optional[float]:
    line_ink = first_number(config.get("lineInk"))
    opacity = first_number(config.get("visualOpacityScale"))
    width = first_number(config.get("visualWidthScale"))
    if line_ink is None or opacity is None or width is None:
        return None
    return line_ink * opacity * width


def base_candidate_diagnostics(candidate: Candidate) -> Dict[str, Any]:
    diagnostics: Dict[str, Any] = {
        "config_visible_ink_score": rounded_or_none(visible_ink_score(candidate.config)),
    }
    rendered_svg = rendered_svg_provenance(candidate)
    if rendered_svg:
        diagnostics["rendered_svg"] = rendered_svg
    return diagnostics


def rendered_svg_provenance(candidate: Candidate) -> Dict[str, Any]:
    rendered_svg = candidate.metadata.get("rendered_svg") or {}
    output: Dict[str, Any] = {}
    for key in [
        "valid",
        "line_count",
        "stroke_opacity_min",
        "stroke_opacity_mean",
        "stroke_opacity_max",
        "stroke_width_min",
        "stroke_width_mean",
        "stroke_width_max",
        "warning_count",
    ]:
        if key in rendered_svg:
            output[key] = rendered_svg[key]
    return output


def rounded_or_none(value: Optional[float]) -> Optional[float]:
    if value is None:
        return None
    return round(value, 6)


def enforce_visibility_floors(
    config: Dict[str, Any],
    min_visual_opacity_scale: float,
    min_visual_width_scale: float,
    min_line_ink: float,
    min_visible_ink: float,
) -> Dict[str, Any]:
    floored = dict(config)
    floor_numeric_key(floored, "visualOpacityScale", min_visual_opacity_scale)
    floor_numeric_key(floored, "visualWidthScale", min_visual_width_scale)
    floor_numeric_key(floored, "lineInk", min_line_ink)
    visible_ink = visible_ink_score(floored)
    if visible_ink is not None and visible_ink < min_visible_ink:
        opacity = first_number(floored.get("visualOpacityScale")) or min_visual_opacity_scale
        width = first_number(floored.get("visualWidthScale")) or min_visual_width_scale
        required_line_ink = min_visible_ink / max(opacity * width, 1e-12)
        floor_numeric_key(floored, "lineInk", required_line_ink)
    return floored


def normalized_preferred_line_count_range(
    preferred_min: int,
    preferred_max: int,
    line_count_limit: int,
) -> Tuple[int, int]:
    lower = max(0, min(int(preferred_min), int(preferred_max)))
    upper = max(lower, max(int(preferred_min), int(preferred_max)))
    upper = min(upper, max(0, int(line_count_limit)))
    lower = min(lower, upper)
    return lower, upper


def steer_line_count_to_preferred_band(
    config: Dict[str, Any],
    line_count_limit: int,
    preferred_min: int,
    preferred_max: int,
) -> Dict[str, Any]:
    steered = dict(config)
    if "finalLineCap" not in steered and "threadCount" not in steered:
        return steered
    preferred_min, preferred_max = normalized_preferred_line_count_range(
        preferred_min,
        preferred_max,
        line_count_limit,
    )
    current = first_int(steered.get("finalLineCap"), steered.get("threadCount"))
    if current is None:
        return steered
    target = current
    if current < preferred_min:
        target = preferred_min
    elif current > preferred_max:
        target = preferred_max
    target = min(target, line_count_limit)
    steered["finalLineCap"] = target
    steered["threadCount"] = target
    return steered


def floor_numeric_key(config: Dict[str, Any], key: str, minimum: float) -> None:
    current = first_number(config.get(key))
    if current is None:
        config[key] = round(minimum, 6)
    elif current < minimum:
        config[key] = round(minimum, 6)


def model_candidate_score(candidate: Candidate, score_map: Dict[str, Any]) -> float:
    model_score = score_map.get(candidate.candidate_id) or {}
    score = first_number(
        model_score.get("preference_score"),
        candidate.score,
        candidate.metrics.get("visualQualityScore"),
        candidate.metrics.get("targetScore"),
        candidate.metrics.get("ssim"),
    )
    return score if score is not None else 0.0


def suggestion_base_score(
    candidate: Candidate,
    score_map: Dict[str, Any],
    runtime_limit_ms: int = DEFAULT_RUNTIME_LIMIT_MS,
    preferred_line_count_min: int = DEFAULT_PREFERRED_LINE_COUNT_MIN,
    preferred_line_count_max: int = DEFAULT_PREFERRED_LINE_COUNT_MAX,
) -> float:
    return (
        model_candidate_score(candidate, score_map)
        - model_candidate_failure_penalty(candidate, score_map)
        - SUGGESTION_VISUAL_RISK_PENALTY
        * suggestion_visual_risk(
            candidate,
            runtime_limit_ms,
            preferred_line_count_min,
            preferred_line_count_max,
        )
    )


def model_candidate_both_bad_count(candidate: Candidate, score_map: Dict[str, Any]) -> float:
    model_score = score_map.get(candidate.candidate_id) or {}
    count = first_number(model_score.get("both_bad_count"))
    return max(0.0, count or 0.0)


def model_candidate_failure_penalty(candidate: Candidate, score_map: Dict[str, Any]) -> float:
    model_score = score_map.get(candidate.candidate_id) or {}
    penalty = first_number(model_score.get("failure_penalty"))
    if penalty is not None:
        return max(0.0, penalty)
    return model_candidate_both_bad_count(candidate, score_map) ** 0.5


def suggestion_visual_risk(
    candidate: Candidate,
    runtime_limit_ms: int = DEFAULT_RUNTIME_LIMIT_MS,
    preferred_line_count_min: int = DEFAULT_PREFERRED_LINE_COUNT_MIN,
    preferred_line_count_max: int = DEFAULT_PREFERRED_LINE_COUNT_MAX,
) -> float:
    visual_quality = first_number(candidate.metrics.get("visualQualityScore"), candidate.score)
    clump = first_number(candidate.metrics.get("lineClumpPenalty")) or 0.0
    overdraw = first_number(candidate.metrics.get("overdrawRate")) or 0.0
    runtime = first_number(candidate.runtime_ms, candidate.metrics.get("totalMs")) or 0.0
    line_count = first_number(candidate.line_count, candidate.metrics.get("finalLineCount")) or 0.0
    rendered_visibility = rendered_svg_visibility_risk(candidate.metadata.get("rendered_svg"))
    low_quality = 0.5 if visual_quality is None else max(0.0, min(1.0, 0.8 - visual_quality))
    runtime_risk = max(0.0, min(1.0, (runtime - runtime_limit_ms) / 120000.0))
    density_risk = suggestion_line_density_risk(
        line_count,
        preferred_line_count_min,
        preferred_line_count_max,
    )
    return max(
        0.0,
        min(
            1.0,
            low_quality
            + 0.3 * clump
            + 0.25 * overdraw
            + 0.2 * runtime_risk
            + 0.15 * density_risk
            + 0.35 * rendered_visibility,
        ),
    )


def suggestion_line_density_risk(
    line_count: float,
    preferred_line_count_min: int = DEFAULT_PREFERRED_LINE_COUNT_MIN,
    preferred_line_count_max: int = DEFAULT_PREFERRED_LINE_COUNT_MAX,
) -> float:
    if line_count <= 0:
        return 0.0
    if line_count < preferred_line_count_min:
        return min(1.0, (preferred_line_count_min - line_count) / 1200.0)
    if line_count > preferred_line_count_max:
        return min(1.0, (line_count - preferred_line_count_max) / 400.0)
    return 0.0


def source_diverse_rank(candidates: List[Candidate]) -> List[Candidate]:
    if len(candidates) < 2:
        return candidates
    by_source: Dict[str, List[Candidate]] = {}
    source_order: List[str] = []
    for candidate in candidates:
        source_id = candidate.source_id or ""
        if source_id not in by_source:
            by_source[source_id] = []
            source_order.append(source_id)
        by_source[source_id].append(candidate)

    ranked: List[Candidate] = []
    while len(ranked) < len(candidates):
        appended = False
        for source_id in source_order:
            source_candidates = by_source[source_id]
            if not source_candidates:
                continue
            ranked.append(source_candidates.pop(0))
            appended = True
        if not appended:
            break
    return ranked


def distinct_source_count(candidates: List[Candidate]) -> int:
    return len({candidate.source_id for candidate in candidates if candidate.source_id})


def numeric_config_ranges(candidates: List[Candidate]) -> Dict[str, Tuple[float, float]]:
    ranges: Dict[str, Tuple[float, float]] = {}
    values: Dict[str, List[float]] = {}
    for candidate in candidates:
        for key, value in candidate.config.items():
            if isinstance(value, bool):
                continue
            numeric = first_number(value)
            if numeric is None:
                continue
            if is_target_aware_key(key):
                continue
            values.setdefault(key, []).append(numeric)
    for key, key_values in values.items():
        ranges[key] = (min(key_values), max(key_values))
    return ranges


def perturb_config(
    base_config: Dict[str, Any],
    observed_ranges: Dict[str, Tuple[float, float]],
    rng: random.Random,
) -> Dict[str, Any]:
    proposed = dict(base_config)
    tunable_keys = [key for key in observed_ranges.keys() if key in proposed and not is_target_aware_key(key)]
    rng.shuffle(tunable_keys)
    mutation_count = min(len(tunable_keys), rng.randint(1, 4) if tunable_keys else 0)
    for key in tunable_keys[:mutation_count]:
        if isinstance(proposed.get(key), bool):
            continue
        minimum, maximum = observed_ranges[key]
        current = first_number(proposed.get(key))
        if current is None:
            continue
        width = max(maximum - minimum, abs(current) * 0.1, 1e-6)
        proposed_value = current + rng.uniform(-0.15, 0.15) * width
        proposed_value = min(maximum, max(minimum, proposed_value))
        if isinstance(proposed.get(key), int) and not isinstance(proposed.get(key), bool):
            proposed[key] = int(round(proposed_value))
        else:
            proposed[key] = round(proposed_value, 6)
    return proposed


def sanitize_target_aware_config(config: Dict[str, Any]) -> Dict[str, Any]:
    sanitized = dict(config)
    for key, value in list(sanitized.items()):
        if not is_target_aware_key(key):
            continue
        if isinstance(value, bool):
            sanitized[key] = False
        elif isinstance(value, (int, float)):
            sanitized[key] = 0
        else:
            sanitized[key] = None
    return sanitized


def is_target_aware_key(key: str) -> bool:
    normalized = key.lower()
    return "targetaware" in normalized or "targetguidance" in normalized or "pseudotarget" in normalized


def suggestion_uncertainty(
    base: Candidate,
    score_map: Dict[str, Any],
    proposed: Dict[str, Any],
    observed_ranges: Dict[str, Tuple[float, float]],
) -> float:
    model_score = score_map.get(base.candidate_id) or {}
    observed_uncertainty = first_number(model_score.get("uncertainty")) or 1.0
    novelty = config_distance(base.config, proposed, observed_ranges)
    return min(1.0, 0.7 * observed_uncertainty + 0.3 * novelty)


def config_distance(
    left: Dict[str, Any],
    right: Dict[str, Any],
    observed_ranges: Dict[str, Tuple[float, float]],
) -> float:
    distances: List[float] = []
    for key, (minimum, maximum) in observed_ranges.items():
        left_value = first_number(left.get(key))
        right_value = first_number(right.get(key))
        if left_value is None or right_value is None:
            continue
        width = maximum - minimum or 1.0
        distances.append(abs(left_value - right_value) / width)
    if not distances:
        return 0.0
    return min(1.0, sum(distances) / len(distances))
