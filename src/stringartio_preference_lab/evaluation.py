import math
import random
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple

from .config import LabConfig
from .generation_quality_contract import (
    app_ready_line_count_limit,
    app_ready_runtime_target_ms,
    forbidden_truthy_config_fields,
    load_generation_quality_contract,
    visibility_value,
)
from .ingest import load_candidate_manifest
from .model import (
    create_both_bad_training_examples,
    create_pairwise_training_examples,
    create_reason_flag_training_examples,
    create_tie_training_examples,
    fit_pairwise_logistic,
    parse_float,
    select_feature_columns,
    sigmoid,
)
from .optimizer import (
    candidate_constraint_failures,
    preference_lab_regenerated_constraint_failures,
)
from .preferences import load_preferences
from .schema import Candidate, Preference, WarningRecord
from .utils import read_csv, utc_now_iso, write_json


MODEL_VARIANTS = (
    ("metric_baseline", False, False, False),
    ("pairwise_only", True, False, False),
    ("pairwise_plus_ties_both_bad", True, True, False),
    ("full_reason_flags", True, True, True),
)

MIN_RECOMMENDED_LABELED_SOURCES = 10
MIN_RECOMMENDED_REVIEWERS = 2
SOURCE_BOOTSTRAP_ITERATIONS = 2000
SOURCE_BOOTSTRAP_SEED = 20260809


def evaluate_preference_model(
    config: LabConfig,
    output_path: Optional[str] = None,
    learning_rate: float = 0.05,
    epochs: int = 600,
    l2: float = 0.001,
    min_run_test_pairs: int = 3,
    dry_run: bool = False,
) -> Dict[str, Any]:
    warnings: List[WarningRecord] = []
    rows = read_csv(Path(config.feature_table_path))
    preferences = load_preferences(config.preference_path, warnings)
    candidates = load_candidate_manifest(config.manifest_path)
    candidate_by_id = {candidate.candidate_id: candidate for candidate in candidates}
    row_by_id = {str(row.get("candidate_id") or ""): row for row in rows}
    usable = [
        preference
        for preference in preferences
        if preference.candidate_a in row_by_id and preference.candidate_b in row_by_id
    ]

    source_folds = grouped_folds(
        usable,
        group_value=lambda preference: preference.source_id,
        train_filter=lambda preference, held: preference.source_id != held,
        test_filter=lambda preference, held: preference.source_id == held,
    )
    run_folds = build_run_folds(usable, candidate_by_id, min_run_test_pairs)
    agreement = reviewer_agreement(preferences)
    readiness = evaluation_readiness(preferences, agreement)
    for message in readiness["warnings"]:
        warnings.append(WarningRecord(message))
    report = {
        "schema_version": 1,
        "created_at": utc_now_iso(),
        "data": data_summary(candidates, preferences, usable),
        "constraints": constraint_summary(config, candidates, warnings),
        "human_outcomes": human_outcome_summary(preferences, candidate_by_id),
        "reviewer_agreement": agreement,
        "evaluation_readiness": readiness,
        "holdout": {
            "source": evaluate_folds(
                source_folds,
                row_by_id,
                learning_rate,
                epochs,
                l2,
                bootstrap_unit="source_id",
            ),
            "run": evaluate_folds(
                run_folds,
                row_by_id,
                learning_rate,
                epochs,
                l2,
            ),
        },
        "methodology": {
            "primary_metric": "pairwise_accuracy_on_A_or_B_labels",
            "secondary_metric": "binary_log_loss",
            "tie_and_both_bad_in_test_metric": False,
            "source_holdout": "leave one complete source_id out",
            "source_bootstrap_ci": (
                "95% percentile interval from deterministic resampling of complete source folds"
            ),
            "reviewer_agreement": (
                "pooled exact agreement and chance-corrected kappa on repeated unordered "
                "candidate pairs after canonicalizing A/B orientation"
            ),
            "run_holdout": (
                "leave one run_id out; training excludes every comparison touching the run, "
                "and testing uses same-run A/B comparisons only"
            ),
            "normalization": "training-candidate means and standard deviations only",
            "metric_baseline": (
                "candidate score, then visualQualityScore, targetScore, or SSIM; "
                "probability is sigmoid(8 * score_difference)"
            ),
        },
        "warnings": [warning.to_dict() for warning in warnings],
    }
    if output_path:
        write_json(Path(output_path), report, dry_run=dry_run)
    return report


def data_summary(
    candidates: Sequence[Candidate],
    preferences: Sequence[Preference],
    usable: Sequence[Preference],
) -> Dict[str, Any]:
    winners = Counter(preference.winner for preference in preferences)
    return {
        "candidate_count": len(candidates),
        "preference_count": len(preferences),
        "usable_preference_count": len(usable),
        "source_count": len({candidate.source_id for candidate in candidates if candidate.source_id}),
        "run_count": len({candidate.run_id for candidate in candidates if candidate.run_id}),
        "labeled_source_count": len(
            {preference.source_id for preference in preferences if preference.source_id}
        ),
        "reviewer_identifier_count": len(
            {preference.reviewer for preference in preferences if preference.reviewer}
        ),
        "winner_counts": dict(sorted(winners.items())),
    }


def constraint_summary(
    config: LabConfig,
    candidates: Sequence[Candidate],
    warnings: List[WarningRecord],
) -> Dict[str, Any]:
    contract = load_generation_quality_contract(config, warnings)
    runtime_limit_ms = app_ready_runtime_target_ms(contract)
    line_count_limit = app_ready_line_count_limit(contract)
    core_eligible: List[Candidate] = []
    eligible: List[Candidate] = []
    core_failure_counts: Counter = Counter()
    failure_counts: Counter = Counter()
    regenerated_failures = preference_lab_regenerated_constraint_failures(
        list(candidates),
        runtime_limit_ms,
        line_count_limit,
        forbidden_truthy_config_fields(contract),
    )
    for candidate in candidates:
        core_failures = candidate_constraint_failures(
            candidate,
            runtime_limit_ms,
            line_count_limit,
            0.0,
            0.0,
            0.0,
            0.0,
        )
        failures = candidate_constraint_failures(
            candidate,
            runtime_limit_ms,
            line_count_limit,
            visibility_value(contract, "minVisualOpacityScale", 0.6),
            visibility_value(contract, "minVisualWidthScale", 0.8),
            visibility_value(contract, "minLineInk", 0.0085),
            visibility_value(contract, "minVisibleInk", 0.004),
            regenerated_failures,
            forbidden_truthy_config_fields(contract),
        )
        if core_failures:
            core_failure_counts.update(core_failures)
        else:
            core_eligible.append(candidate)
        if failures:
            failure_counts.update(failures)
        else:
            eligible.append(candidate)
    runtimes = sorted(
        float(candidate.runtime_ms)
        for candidate in candidates
        if candidate.runtime_ms is not None
    )
    eligible_runtimes = sorted(
        float(candidate.runtime_ms)
        for candidate in eligible
        if candidate.runtime_ms is not None
    )
    return {
        "runtime_limit_ms": runtime_limit_ms,
        "line_count_limit": line_count_limit,
        "candidate_count": len(candidates),
        "core_passing_candidate_count": len(core_eligible),
        "core_pass_rate": ratio(len(core_eligible), len(candidates)),
        "core_failure_counts": dict(sorted(core_failure_counts.items())),
        "suggestion_anchor_passing_candidate_count": len(eligible),
        "suggestion_anchor_pass_rate": ratio(len(eligible), len(candidates)),
        "failure_counts": dict(sorted(failure_counts.items())),
        "runtime_ms": distribution(runtimes),
        "passing_runtime_ms": distribution(eligible_runtimes),
        "note": (
            "Core pass checks app_ready, runtime, line count, and no target-aware logic. "
            "Suggestion-anchor pass also checks visibility floors and observed regenerated failures."
        ),
    }


def human_outcome_summary(
    preferences: Sequence[Preference],
    candidate_by_id: Dict[str, Candidate],
) -> Dict[str, Any]:
    by_source: Dict[str, Counter] = defaultdict(Counter)
    by_run_matchup: Dict[Tuple[str, str], Counter] = defaultdict(Counter)
    for preference in preferences:
        by_source[preference.source_id][preference.winner] += 1
        candidate_a = candidate_by_id.get(preference.candidate_a)
        candidate_b = candidate_by_id.get(preference.candidate_b)
        if not candidate_a or not candidate_b or candidate_a.run_id == candidate_b.run_id:
            continue
        left, right = sorted((candidate_a.run_id, candidate_b.run_id))
        if preference.winner in {"tie", "both_bad"}:
            outcome = preference.winner
        else:
            winning_run = candidate_a.run_id if preference.winner == "A" else candidate_b.run_id
            outcome = "left_win" if winning_run == left else "right_win"
        by_run_matchup[(left, right)][outcome] += 1

    overall = outcome_rates(Counter(preference.winner for preference in preferences))
    overall["source_bootstrap_95_ci"] = source_outcome_bootstrap_ci(by_source)
    return {
        "overall": overall,
        "by_source": {
            source_id: outcome_rates(counts)
            for source_id, counts in sorted(by_source.items())
        },
        "cross_run_matchups": [
            {
                "left_run": left,
                "right_run": right,
                **matchup_rates(counts),
            }
            for (left, right), counts in sorted(
                by_run_matchup.items(),
                key=lambda item: (-sum(item[1].values()), item[0]),
            )
        ],
    }


def outcome_rates(counts: Counter) -> Dict[str, Any]:
    total = sum(counts.values())
    decisive = counts["A"] + counts["B"]
    return {
        "review_count": total,
        "counts": {winner: counts[winner] for winner in ("A", "B", "tie", "both_bad")},
        "a_win_rate_decisive": ratio(counts["A"], decisive),
        "both_bad_rate": ratio(counts["both_bad"], total),
    }


def evaluation_readiness(
    preferences: Sequence[Preference],
    agreement: Dict[str, Any],
) -> Dict[str, Any]:
    labeled_source_count = len(
        {preference.source_id for preference in preferences if preference.source_id}
    )
    reviewer_count = len(
        {preference.reviewer for preference in preferences if preference.reviewer}
    )
    overlap_pair_count = int(agreement["overlap_pair_count"])
    warnings = []
    if labeled_source_count < MIN_RECOMMENDED_LABELED_SOURCES:
        warnings.append(
            f"Only {labeled_source_count} labeled sources are available; collect at least "
            f"{MIN_RECOMMENDED_LABELED_SOURCES} before treating source-level intervals as stable."
        )
    if reviewer_count < MIN_RECOMMENDED_REVIEWERS:
        warnings.append(
            f"Only {reviewer_count} reviewer identifiers are available; collect at least "
            f"{MIN_RECOMMENDED_REVIEWERS}."
        )
    if overlap_pair_count == 0:
        warnings.append(
            "No candidate pair has ratings from multiple reviewer identifiers; reviewer "
            "agreement cannot be estimated."
        )
    return {
        "recommended_labeled_source_count": MIN_RECOMMENDED_LABELED_SOURCES,
        "labeled_source_count": labeled_source_count,
        "source_target_met": labeled_source_count >= MIN_RECOMMENDED_LABELED_SOURCES,
        "recommended_reviewer_count": MIN_RECOMMENDED_REVIEWERS,
        "reviewer_identifier_count": reviewer_count,
        "reviewer_identifier_target_met": reviewer_count >= MIN_RECOMMENDED_REVIEWERS,
        "independent_reviewer_target_met": None,
        "overlap_pair_count": overlap_pair_count,
        "agreement_estimable": overlap_pair_count > 0,
        "warnings": warnings,
    }


def reviewer_agreement(preferences: Sequence[Preference]) -> Dict[str, Any]:
    ratings_by_pair: Dict[Tuple[str, str, str], Dict[str, str]] = defaultdict(dict)
    reviewer_ids = set()
    for preference in preferences:
        reviewer = str(preference.reviewer or "").strip()
        if not reviewer:
            continue
        reviewer_ids.add(reviewer)
        left, right = sorted((preference.candidate_a, preference.candidate_b))
        outcome = canonical_outcome(preference, left)
        ratings_by_pair[(preference.source_id, left, right)][reviewer] = outcome

    comparisons: List[Tuple[str, str]] = []
    overlap_pair_count = 0
    for ratings in ratings_by_pair.values():
        if len(ratings) < 2:
            continue
        overlap_pair_count += 1
        comparisons.extend(
            (left[1], right[1])
            for left, right in combinations(sorted(ratings.items()), 2)
        )

    agreement_count = sum(left == right for left, right in comparisons)
    observed = ratio(agreement_count, len(comparisons))
    marginals = Counter(outcome for comparison in comparisons for outcome in comparison)
    marginal_total = sum(marginals.values())
    expected = (
        sum((count / marginal_total) ** 2 for count in marginals.values())
        if marginal_total
        else None
    )
    kappa = None
    if observed is not None and expected is not None and expected < 1.0:
        kappa = round((observed - expected) / (1.0 - expected), 6)
    return {
        "reviewer_identifier_count": len(reviewer_ids),
        "overlap_pair_count": overlap_pair_count,
        "rating_pair_count": len(comparisons),
        "agreement_count": agreement_count,
        "exact_agreement_rate": observed,
        "expected_agreement_rate": round(expected, 6) if expected is not None else None,
        "chance_corrected_kappa": kappa,
        "outcome_categories": ["left", "right", "tie", "both_bad"],
        "method": "pooled pairwise agreement on repeated unordered candidate pairs",
        "identity_note": (
            "Reviewer field values are treated as identifiers; the collection protocol must "
            "separately confirm that they represent independent people."
        ),
    }


def canonical_outcome(preference: Preference, left_candidate: str) -> str:
    if preference.winner in {"tie", "both_bad"}:
        return preference.winner
    winning_candidate = (
        preference.candidate_a if preference.winner == "A" else preference.candidate_b
    )
    return "left" if winning_candidate == left_candidate else "right"


def source_outcome_bootstrap_ci(
    by_source: Dict[str, Counter],
    iterations: int = SOURCE_BOOTSTRAP_ITERATIONS,
    seed: int = SOURCE_BOOTSTRAP_SEED,
) -> Dict[str, Any]:
    source_counts = [by_source[source] for source in sorted(by_source)]
    return {
        "unit": "source_id",
        "source_count": len(source_counts),
        "iterations": iterations,
        "seed": seed,
        "a_win_rate_decisive": bootstrap_counter_rate(
            source_counts,
            lambda counts: ratio(counts["A"], counts["A"] + counts["B"]),
            iterations,
            seed,
        ),
        "both_bad_rate": bootstrap_counter_rate(
            source_counts,
            lambda counts: ratio(counts["both_bad"], sum(counts.values())),
            iterations,
            seed + 1,
        ),
    }


def bootstrap_counter_rate(
    counters: Sequence[Counter],
    statistic: Callable[[Counter], Optional[float]],
    iterations: int,
    seed: int,
) -> Optional[Dict[str, float]]:
    if len(counters) < 2:
        return None
    rng = random.Random(seed)
    estimates = []
    for _ in range(iterations):
        combined = Counter()
        for _ in counters:
            combined.update(counters[rng.randrange(len(counters))])
        estimate = statistic(combined)
        if estimate is not None:
            estimates.append(estimate)
    return percentile_interval(estimates)


def matchup_rates(counts: Counter) -> Dict[str, Any]:
    total = sum(counts.values())
    decisive = counts["left_win"] + counts["right_win"]
    return {
        "review_count": total,
        "counts": dict(sorted(counts.items())),
        "left_win_rate_decisive": ratio(counts["left_win"], decisive),
        "right_win_rate_decisive": ratio(counts["right_win"], decisive),
        "both_bad_rate": ratio(counts["both_bad"], total),
    }


def grouped_folds(
    preferences: Sequence[Preference],
    group_value: Callable[[Preference], str],
    train_filter: Callable[[Preference, str], bool],
    test_filter: Callable[[Preference, str], bool],
) -> List[Dict[str, Any]]:
    groups = sorted({group_value(preference) for preference in preferences})
    return [
        {
            "group": group,
            "train": [preference for preference in preferences if train_filter(preference, group)],
            "test": [preference for preference in preferences if test_filter(preference, group)],
        }
        for group in groups
    ]


def build_run_folds(
    preferences: Sequence[Preference],
    candidate_by_id: Dict[str, Candidate],
    min_test_pairs: int,
) -> List[Dict[str, Any]]:
    runs = sorted({candidate.run_id for candidate in candidate_by_id.values() if candidate.run_id})
    folds: List[Dict[str, Any]] = []
    for run_id in runs:
        test = []
        train = []
        for preference in preferences:
            candidate_a = candidate_by_id.get(preference.candidate_a)
            candidate_b = candidate_by_id.get(preference.candidate_b)
            if not candidate_a or not candidate_b:
                continue
            touches = run_id in {candidate_a.run_id, candidate_b.run_id}
            if candidate_a.run_id == run_id and candidate_b.run_id == run_id:
                test.append(preference)
            elif not touches:
                train.append(preference)
        decisive_count = sum(preference.winner in {"A", "B"} for preference in test)
        if decisive_count >= min_test_pairs:
            folds.append({"group": run_id, "train": train, "test": test})
    return folds


def evaluate_folds(
    folds: Sequence[Dict[str, Any]],
    row_by_id: Dict[str, Dict[str, str]],
    learning_rate: float,
    epochs: int,
    l2: float,
    bootstrap_unit: Optional[str] = None,
) -> Dict[str, Any]:
    variant_results: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for fold in folds:
        for name, trained, auxiliary, reason_flags in MODEL_VARIANTS:
            result = evaluate_variant(
                fold["train"],
                fold["test"],
                row_by_id,
                trained,
                auxiliary,
                reason_flags,
                learning_rate,
                epochs,
                l2,
            )
            result["group"] = fold["group"]
            variant_results[name].append(result)
    return {
        "fold_count": len(folds),
        "models": {
            name: aggregate_fold_results(results, bootstrap_unit=bootstrap_unit)
            for name, results in variant_results.items()
        },
    }


def evaluate_variant(
    training: Sequence[Preference],
    testing: Sequence[Preference],
    row_by_id: Dict[str, Dict[str, str]],
    trained: bool,
    auxiliary: bool,
    reason_flags: bool,
    learning_rate: float,
    epochs: int,
    l2: float,
) -> Dict[str, Any]:
    decisive_test = [preference for preference in testing if preference.winner in {"A", "B"}]
    if not trained:
        probabilities = [metric_probability(preference, row_by_id) for preference in decisive_test]
    else:
        feature_names = select_feature_columns(list(row_by_id.values()))
        train_ids = sorted(
            {
                candidate_id
                for preference in training
                for candidate_id in (preference.candidate_a, preference.candidate_b)
                if candidate_id in row_by_id
            }
        )
        matrix_by_id = training_standardized_matrix(row_by_id, feature_names, train_ids)
        index_by_id = {candidate_id: index for index, candidate_id in enumerate(matrix_by_id)}
        matrix = [matrix_by_id[candidate_id] for candidate_id in index_by_id]
        local_warnings: List[WarningRecord] = []
        examples = create_pairwise_training_examples(training, index_by_id, matrix, local_warnings)
        if auxiliary:
            examples += create_tie_training_examples(training, index_by_id, matrix, local_warnings)
            examples += create_both_bad_training_examples(training, index_by_id, matrix, local_warnings)
        if reason_flags:
            reason_examples, _ = create_reason_flag_training_examples(
                training,
                index_by_id,
                matrix,
                feature_names,
                local_warnings,
            )
            examples += reason_examples
        weights, _ = fit_pairwise_logistic(
            examples,
            len(feature_names),
            learning_rate,
            epochs,
            l2,
        )
        probabilities = []
        for preference in decisive_test:
            left = matrix_by_id.get(preference.candidate_a)
            right = matrix_by_id.get(preference.candidate_b)
            if left is None or right is None:
                probabilities.append(0.5)
                continue
            probabilities.append(sigmoid(sum(weight * (a - b) for weight, a, b in zip(weights, left, right))))
    labels = [1.0 if preference.winner == "A" else 0.0 for preference in decisive_test]
    correct = sum((probability >= 0.5) == bool(label) for probability, label in zip(probabilities, labels))
    log_loss = sum(binary_log_loss(probability, label) for probability, label in zip(probabilities, labels))
    return {
        "test_pair_count": len(labels),
        "correct_count": correct,
        "accuracy": ratio(correct, len(labels)),
        "log_loss_sum": log_loss,
        "log_loss": ratio(log_loss, len(labels)),
    }


def training_standardized_matrix(
    row_by_id: Dict[str, Dict[str, str]],
    feature_names: Sequence[str],
    train_ids: Sequence[str],
) -> Dict[str, List[float]]:
    means: List[float] = []
    stds: List[float] = []
    for feature in feature_names:
        values = [parse_float(row_by_id[candidate_id].get(feature)) or 0.0 for candidate_id in train_ids]
        mean = sum(values) / len(values) if values else 0.0
        variance = sum((value - mean) ** 2 for value in values) / len(values) if values else 0.0
        means.append(mean)
        stds.append(math.sqrt(variance) or 1.0)
    return {
        candidate_id: [
            ((parse_float(row.get(feature)) or 0.0) - means[index]) / stds[index]
            for index, feature in enumerate(feature_names)
        ]
        for candidate_id, row in row_by_id.items()
    }


def metric_probability(
    preference: Preference,
    row_by_id: Dict[str, Dict[str, str]],
) -> float:
    score_a = metric_score(row_by_id.get(preference.candidate_a, {}))
    score_b = metric_score(row_by_id.get(preference.candidate_b, {}))
    return sigmoid((score_a - score_b) * 8.0)


def metric_score(row: Dict[str, str]) -> float:
    for field in ("score", "metric_visual_quality_score", "metric_target_score", "metric_ssim"):
        value = parse_float(row.get(field))
        if value is not None:
            return value
    return 0.0


def aggregate_fold_results(
    results: Sequence[Dict[str, Any]],
    bootstrap_unit: Optional[str] = None,
) -> Dict[str, Any]:
    count = sum(result["test_pair_count"] for result in results)
    correct = sum(result["correct_count"] for result in results)
    loss = sum(result["log_loss_sum"] for result in results)
    output = {
        "test_pair_count": count,
        "accuracy": ratio(correct, count),
        "log_loss": ratio(loss, count),
        "macro_accuracy": mean_available(result["accuracy"] for result in results),
        "macro_log_loss": mean_available(result["log_loss"] for result in results),
        "folds": [
            {
                "group": result["group"],
                "test_pair_count": result["test_pair_count"],
                "accuracy": result["accuracy"],
                "log_loss": result["log_loss"],
            }
            for result in results
        ],
    }
    if bootstrap_unit:
        output["source_bootstrap_95_ci"] = {
            "unit": bootstrap_unit,
            "source_count": len(results),
            "iterations": SOURCE_BOOTSTRAP_ITERATIONS,
            "seed": SOURCE_BOOTSTRAP_SEED,
            "accuracy": bootstrap_fold_metric(
                results,
                "correct_count",
                "test_pair_count",
                SOURCE_BOOTSTRAP_ITERATIONS,
                SOURCE_BOOTSTRAP_SEED,
            ),
            "log_loss": bootstrap_fold_metric(
                results,
                "log_loss_sum",
                "test_pair_count",
                SOURCE_BOOTSTRAP_ITERATIONS,
                SOURCE_BOOTSTRAP_SEED + 1,
            ),
        }
    return output


def mean_available(values: Iterable[Optional[float]]) -> Optional[float]:
    available = [float(value) for value in values if value is not None]
    return round(sum(available) / len(available), 6) if available else None


def bootstrap_fold_metric(
    results: Sequence[Dict[str, Any]],
    numerator_field: str,
    denominator_field: str,
    iterations: int,
    seed: int,
) -> Optional[Dict[str, float]]:
    if len(results) < 2:
        return None
    rng = random.Random(seed)
    estimates = []
    for _ in range(iterations):
        sample = [results[rng.randrange(len(results))] for _ in results]
        numerator = sum(float(result[numerator_field]) for result in sample)
        denominator = sum(float(result[denominator_field]) for result in sample)
        estimate = ratio(numerator, denominator)
        if estimate is not None:
            estimates.append(estimate)
    return percentile_interval(estimates)


def percentile_interval(values: Sequence[float]) -> Optional[Dict[str, float]]:
    if not values:
        return None
    ordered = sorted(values)
    return {
        "lower": round(percentile(ordered, 0.025), 6),
        "upper": round(percentile(ordered, 0.975), 6),
    }


def binary_log_loss(probability: float, label: float) -> float:
    probability = min(max(probability, 1e-12), 1.0 - 1e-12)
    return -(label * math.log(probability) + (1.0 - label) * math.log(1.0 - probability))


def distribution(values: Sequence[float]) -> Dict[str, Optional[float]]:
    if not values:
        return {"count": 0, "min": None, "median": None, "p95": None, "max": None}
    return {
        "count": len(values),
        "min": round(values[0], 3),
        "median": round(percentile(values, 0.5), 3),
        "p95": round(percentile(values, 0.95), 3),
        "max": round(values[-1], 3),
    }


def percentile(values: Sequence[float], fraction: float) -> float:
    if len(values) == 1:
        return values[0]
    position = (len(values) - 1) * fraction
    lower = int(math.floor(position))
    upper = int(math.ceil(position))
    if lower == upper:
        return values[lower]
    return values[lower] + (values[upper] - values[lower]) * (position - lower)


def ratio(numerator: float, denominator: float) -> Optional[float]:
    if not denominator:
        return None
    return round(numerator / denominator, 6)
