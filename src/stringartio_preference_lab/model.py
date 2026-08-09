import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .config import LabConfig
from .preferences import load_preferences
from .schema import Preference, WarningRecord
from .utils import first_number, read_csv, write_json


IDENTIFIER_COLUMNS = {
    "candidate_id",
    "source_id",
    "source_hash",
    "run_id",
    "preset",
    "lane",
    "profile",
    "artifact_output",
    "artifact_comparison",
    "artifact_source",
    "artifact_target",
}

BOTH_BAD_FAILURE_PENALTY_FRACTION = 0.05
PAIRWISE_EXAMPLE_WEIGHT = 1.0
TIE_EXAMPLE_WEIGHT = 0.25
BOTH_BAD_FAILURE_EXAMPLE_WEIGHT = 1.0
REASON_FLAG_EXAMPLE_WEIGHT = 0.5

REASON_FLAG_FEATURE_TARGETS = {
    "sharper_face": (
        "metric_face_detail_score",
        "metric_localized_detail_score",
        "metric_detail_score",
        "metric_edge_similarity",
    ),
    "better_hair": (
        "metric_localized_detail_score",
        "metric_detail_score",
        "metric_edge_similarity",
    ),
    "better_outline": (
        "metric_edge_similarity",
        "metric_ssim",
        "metric_coverage_rate",
    ),
    "better_contrast": (
        "metric_contrast_score",
        "config_contrast",
        "config_gamma",
    ),
    "cleaner": (
        "metric_visual_quality_score",
        "metric_line_clump_penalty",
        "metric_overdraw_rate",
        "metric_mae",
        "metric_mse",
    ),
    "less_blurry": (
        "metric_ssim",
        "metric_detail_score",
        "metric_edge_similarity",
        "metric_mae",
        "metric_mse",
    ),
    "less_clumping": (
        "metric_line_clump_penalty",
        "metric_overdraw_rate",
    ),
    "better_visibility": (
        "rendered_svg_stroke_opacity_mean",
        "rendered_svg_stroke_width_mean",
        "derived_visible_ink_score",
        "config_visual_opacity_scale",
        "config_visual_width_scale",
        "config_line_ink",
        "metric_contrast_score",
        "config_contrast",
        "config_gamma",
    ),
}


def train_preference_model(
    config: LabConfig,
    learning_rate: float = 0.05,
    epochs: int = 600,
    l2: float = 0.001,
    dry_run: bool = False,
) -> Dict[str, Any]:
    warnings: List[WarningRecord] = []
    rows = read_csv(Path(config.feature_table_path))
    preferences = load_preferences(config.preference_path, warnings)
    diagnostic_policy = diagnostic_feature_policy(rows)
    feature_names = select_feature_columns(rows)
    matrix, candidate_ids, means, stds = standardize_rows(rows, feature_names)
    row_by_id = {candidate_id: index for index, candidate_id in enumerate(candidate_ids)}
    pairwise_examples = create_pairwise_training_examples(preferences, row_by_id, matrix, warnings)
    tie_examples = create_tie_training_examples(preferences, row_by_id, matrix, warnings)
    failure_examples = create_both_bad_training_examples(preferences, row_by_id, matrix, warnings)
    reason_flag_examples, reason_flag_signal = create_reason_flag_training_examples(
        preferences,
        row_by_id,
        matrix,
        feature_names,
        warnings,
    )
    examples = pairwise_examples + tie_examples + failure_examples + reason_flag_examples

    if not rows:
        result = neutral_model_result("empty-feature-table", warnings, diagnostic_policy)
    elif not feature_names:
        result = neutral_model_result("no-numeric-features", warnings, diagnostic_policy)
    elif not examples:
        result = fallback_score_model(rows, warnings, "no-labeled-pairwise-preferences", diagnostic_policy)
    else:
        weights, loss = fit_pairwise_logistic(examples, len(feature_names), learning_rate, epochs, l2)
        candidate_scores = score_candidates(matrix, candidate_ids, weights, preferences)
        result = {
            "schema_version": 1,
            "trained": True,
            "method": "bradley-terry-logistic-pairwise",
            "feature_names": feature_names,
            "weights": weights,
            "feature_means": means,
            "feature_stds": stds,
            "training_examples": len(examples),
            "pairwise_training_examples": len(pairwise_examples),
            "tie_training_examples": len(tie_examples),
            "failure_training_examples": len(failure_examples),
            "reason_flag_training_examples": len(reason_flag_examples),
            "loss": loss,
            "candidate_scores": candidate_scores,
            "tie_signal": {
                "tie_as_equal_preference_loss": True,
                "training_weight": TIE_EXAMPLE_WEIGHT,
            },
            "failure_signal": {
                "both_bad_as_neutral_loss": True,
                "training_weight": BOTH_BAD_FAILURE_EXAMPLE_WEIGHT,
                "score_penalty_fraction": BOTH_BAD_FAILURE_PENALTY_FRACTION,
            },
            "reason_flag_signal": reason_flag_signal,
            "diagnostic_feature_policy": diagnostic_policy,
            "warnings": [warning.to_dict() for warning in warnings],
        }

    write_json(Path(config.model_path), result, dry_run=dry_run)
    return result


def select_feature_columns(rows: Sequence[Dict[str, str]]) -> List[str]:
    if not rows:
        return []
    columns = list(rows[0].keys())
    selected = []
    for column in columns:
        if column in IDENTIFIER_COLUMNS or column.startswith("preference_lab_"):
            continue
        if is_diagnostic_only_feature(column):
            continue
        numeric_count = 0
        for row in rows:
            if parse_float(row.get(column)) is not None:
                numeric_count += 1
        if numeric_count:
            selected.append(column)
    return selected


def diagnostic_feature_policy(rows: Sequence[Dict[str, str]]) -> Dict[str, Any]:
    columns = sorted({column for row in rows for column in row.keys()})
    excluded = [column for column in columns if is_diagnostic_only_feature(column)]
    return {
        "residual_metrics_exported_to_features": True,
        "residual_metrics_train_by_default": False,
        "excluded_feature_columns": excluded,
        "reason": "Residual metrics are diagnostic-only until ablation against human labels is reviewed.",
    }


def is_diagnostic_only_feature(column: str) -> bool:
    return column.startswith("metric_") and "residual" in column


def standardize_rows(
    rows: Sequence[Dict[str, str]],
    feature_names: Sequence[str],
) -> Tuple[List[List[float]], List[str], Dict[str, float], Dict[str, float]]:
    raw_matrix: List[List[float]] = []
    candidate_ids: List[str] = []
    for row in rows:
        candidate_ids.append(row.get("candidate_id", ""))
        raw_matrix.append([parse_float(row.get(feature)) or 0.0 for feature in feature_names])

    means: Dict[str, float] = {}
    stds: Dict[str, float] = {}
    matrix: List[List[float]] = []
    for index, feature in enumerate(feature_names):
        values = [row[index] for row in raw_matrix]
        mean = sum(values) / len(values) if values else 0.0
        variance = sum((value - mean) ** 2 for value in values) / len(values) if values else 0.0
        std = math.sqrt(variance) or 1.0
        means[feature] = mean
        stds[feature] = std
    for row in raw_matrix:
        matrix.append(
            [
                (value - means[feature_names[index]]) / stds[feature_names[index]]
                for index, value in enumerate(row)
            ]
        )
    return matrix, candidate_ids, means, stds


def create_pairwise_training_examples(
    preferences: Sequence[Preference],
    row_by_id: Dict[str, int],
    matrix: Sequence[Sequence[float]],
    warnings: List[WarningRecord],
) -> List[Tuple[List[float], float, float]]:
    examples: List[Tuple[List[float], float, float]] = []
    for preference in preferences:
        if preference.winner in {"tie", "both_bad"}:
            continue
        index_a = row_by_id.get(preference.candidate_a)
        index_b = row_by_id.get(preference.candidate_b)
        if index_a is None or index_b is None:
            warnings.append(
                WarningRecord(f"Skipping preference with missing feature row: {preference.preference_id}")
            )
            continue
        diff = [a - b for a, b in zip(matrix[index_a], matrix[index_b])]
        label = 1.0 if preference.winner == "A" else 0.0
        examples.append((diff, label, PAIRWISE_EXAMPLE_WEIGHT))
    return examples


def create_tie_training_examples(
    preferences: Sequence[Preference],
    row_by_id: Dict[str, int],
    matrix: Sequence[Sequence[float]],
    warnings: List[WarningRecord],
) -> List[Tuple[List[float], float, float]]:
    examples: List[Tuple[List[float], float, float]] = []
    for preference in preferences:
        if preference.winner != "tie":
            continue
        index_a = row_by_id.get(preference.candidate_a)
        index_b = row_by_id.get(preference.candidate_b)
        if index_a is None or index_b is None:
            warnings.append(
                WarningRecord(f"Skipping tie with missing feature row: {preference.preference_id}")
            )
            continue
        diff = [a - b for a, b in zip(matrix[index_a], matrix[index_b])]
        examples.append((diff, 0.5, TIE_EXAMPLE_WEIGHT))
    return examples


def create_both_bad_training_examples(
    preferences: Sequence[Preference],
    row_by_id: Dict[str, int],
    matrix: Sequence[Sequence[float]],
    warnings: List[WarningRecord],
) -> List[Tuple[List[float], float, float]]:
    examples: List[Tuple[List[float], float, float]] = []
    seen_candidates = set()
    for preference in preferences:
        if preference.winner != "both_bad":
            continue
        candidate_fields = (("candidate_a", preference.candidate_a), ("candidate_b", preference.candidate_b))
        for field, candidate_id in candidate_fields:
            if candidate_id in seen_candidates:
                continue
            index = row_by_id.get(candidate_id)
            if index is None:
                warnings.append(
                    WarningRecord(
                        f"Skipping both_bad {field} with missing feature row: {preference.preference_id}"
                    )
                )
                continue
            seen_candidates.add(candidate_id)
            examples.append((list(matrix[index]), 0.0, BOTH_BAD_FAILURE_EXAMPLE_WEIGHT))
    return examples


def create_reason_flag_training_examples(
    preferences: Sequence[Preference],
    row_by_id: Dict[str, int],
    matrix: Sequence[Sequence[float]],
    feature_names: Sequence[str],
    warnings: List[WarningRecord],
) -> Tuple[List[Tuple[List[float], float, float]], Dict[str, Any]]:
    examples: List[Tuple[List[float], float, float]] = []
    feature_index = {feature: index for index, feature in enumerate(feature_names)}
    used_flags: Dict[str, int] = {}
    used_features: Dict[str, List[str]] = {}
    skipped_flags: Dict[str, int] = {}

    for preference in preferences:
        if not preference.reason_flags:
            continue
        target_indices = reason_flag_feature_indices(preference.reason_flags, feature_index)
        if not target_indices:
            for flag in preference.reason_flags:
                skipped_flags[flag] = skipped_flags.get(flag, 0) + 1
            warnings.append(
                WarningRecord(
                    "Skipping reason_flags with no matching numeric feature columns: "
                    f"{preference.preference_id}"
                )
            )
            continue
        for flag in preference.reason_flags:
            flag_features = [
                feature
                for feature in REASON_FLAG_FEATURE_TARGETS.get(flag, ())
                if feature in feature_index
            ]
            if flag_features:
                used_flags[flag] = used_flags.get(flag, 0) + 1
                used_features[flag] = flag_features

        if preference.winner == "both_bad":
            append_reason_flag_failure_examples(
                preference,
                row_by_id,
                matrix,
                target_indices,
                examples,
                warnings,
            )
            continue

        index_a = row_by_id.get(preference.candidate_a)
        index_b = row_by_id.get(preference.candidate_b)
        if index_a is None or index_b is None:
            warnings.append(
                WarningRecord(f"Skipping reason_flags with missing feature row: {preference.preference_id}")
            )
            continue
        diff = masked_difference(matrix[index_a], matrix[index_b], target_indices)
        if preference.winner == "tie":
            examples.append((diff, 0.5, TIE_EXAMPLE_WEIGHT * REASON_FLAG_EXAMPLE_WEIGHT))
        else:
            label = 1.0 if preference.winner == "A" else 0.0
            examples.append((diff, label, REASON_FLAG_EXAMPLE_WEIGHT))

    signal = reason_flag_signal_result(True)
    signal["used_flags"] = dict(sorted(used_flags.items()))
    signal["used_features"] = {
        flag: features
        for flag, features in sorted(used_features.items())
    }
    signal["skipped_flags"] = dict(sorted(skipped_flags.items()))
    return examples, signal


def reason_flag_feature_indices(
    reason_flags: Sequence[str],
    feature_index: Dict[str, int],
) -> List[int]:
    indices = {
        feature_index[feature]
        for flag in reason_flags
        for feature in REASON_FLAG_FEATURE_TARGETS.get(flag, ())
        if feature in feature_index
    }
    return sorted(indices)


def append_reason_flag_failure_examples(
    preference: Preference,
    row_by_id: Dict[str, int],
    matrix: Sequence[Sequence[float]],
    target_indices: Sequence[int],
    examples: List[Tuple[List[float], float, float]],
    warnings: List[WarningRecord],
) -> None:
    candidate_fields = (("candidate_a", preference.candidate_a), ("candidate_b", preference.candidate_b))
    for field, candidate_id in candidate_fields:
        index = row_by_id.get(candidate_id)
        if index is None:
            warnings.append(
                WarningRecord(
                    f"Skipping both_bad reason_flags {field} with missing feature row: "
                    f"{preference.preference_id}"
                )
            )
            continue
        examples.append(
            (
                masked_row(matrix[index], target_indices),
                0.0,
                BOTH_BAD_FAILURE_EXAMPLE_WEIGHT * REASON_FLAG_EXAMPLE_WEIGHT,
            )
        )


def masked_difference(
    left: Sequence[float],
    right: Sequence[float],
    indices: Sequence[int],
) -> List[float]:
    output = [0.0] * len(left)
    for index in indices:
        output[index] = left[index] - right[index]
    return output


def masked_row(row: Sequence[float], indices: Sequence[int]) -> List[float]:
    output = [0.0] * len(row)
    for index in indices:
        output[index] = row[index]
    return output


def reason_flag_signal_result(enabled: bool) -> Dict[str, Any]:
    return {
        "reason_flags_as_auxiliary_feature_loss": enabled,
        "training_weight": REASON_FLAG_EXAMPLE_WEIGHT,
        "flag_feature_targets": {
            flag: list(features)
            for flag, features in sorted(REASON_FLAG_FEATURE_TARGETS.items())
        },
        "used_flags": {},
        "used_features": {},
        "skipped_flags": {},
    }


def fit_pairwise_logistic(
    examples: Sequence[Tuple[Sequence[float], float, float]],
    feature_count: int,
    learning_rate: float,
    epochs: int,
    l2: float,
) -> Tuple[List[float], float]:
    weights = [0.0] * feature_count
    loss = 0.0
    total_weight = sum(example_weight for _, _, example_weight in examples) or 1.0
    for _ in range(max(1, epochs)):
        gradients = [l2 * weight for weight in weights]
        loss = 0.0
        for diff, label, example_weight in examples:
            score = dot(weights, diff)
            probability = sigmoid(score)
            error = probability - label
            loss += example_weight * logistic_loss(probability, label)
            for index, value in enumerate(diff):
                gradients[index] += example_weight * error * value
        scale = 1.0 / total_weight
        for index in range(feature_count):
            weights[index] -= learning_rate * gradients[index] * scale
    return weights, loss / total_weight


def score_candidates(
    matrix: Sequence[Sequence[float]],
    candidate_ids: Sequence[str],
    weights: Sequence[float],
    preferences: Sequence[Preference],
) -> Dict[str, Dict[str, float]]:
    observation_counts = preference_observation_counts(preferences)
    failure_counts = both_bad_observation_counts(preferences)
    raw_scores = [dot(weights, row) for row in matrix]
    if raw_scores:
        minimum = min(raw_scores)
        maximum = max(raw_scores)
    else:
        minimum = maximum = 0.0
    penalty_unit = max(1.0, (maximum - minimum) * BOTH_BAD_FAILURE_PENALTY_FRACTION)
    adjusted_scores = [
        score - penalty_unit * math.sqrt(failure_counts.get(candidate_id, 0))
        for candidate_id, score in zip(candidate_ids, raw_scores)
    ]
    if adjusted_scores:
        adjusted_minimum = min(adjusted_scores)
        adjusted_maximum = max(adjusted_scores)
    else:
        adjusted_minimum = adjusted_maximum = 0.0
    output: Dict[str, Dict[str, float]] = {}
    for candidate_id, raw_score, adjusted_score in zip(candidate_ids, raw_scores, adjusted_scores):
        failure_count = failure_counts.get(candidate_id, 0)
        failure_penalty = penalty_unit * math.sqrt(failure_count)
        probability_like = (
            0.5
            if adjusted_maximum == adjusted_minimum
            else (adjusted_score - adjusted_minimum) / (adjusted_maximum - adjusted_minimum)
        )
        count = observation_counts.get(candidate_id, 0)
        output[candidate_id] = {
            "preference_score": round(adjusted_score, 6),
            "raw_preference_score": round(raw_score, 6),
            "failure_penalty": round(failure_penalty, 6),
            "both_bad_count": float(failure_count),
            "win_probability": round(probability_like, 6),
            "uncertainty": round(1.0 / math.sqrt(count + 1.0), 6),
            "observation_count": float(count),
        }
    return output


def preference_observation_counts(preferences: Sequence[Preference]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for preference in preferences:
        counts[preference.candidate_a] = counts.get(preference.candidate_a, 0) + 1
        counts[preference.candidate_b] = counts.get(preference.candidate_b, 0) + 1
    return counts


def both_bad_observation_counts(preferences: Sequence[Preference]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for preference in preferences:
        if preference.winner != "both_bad":
            continue
        counts[preference.candidate_a] = counts.get(preference.candidate_a, 0) + 1
        counts[preference.candidate_b] = counts.get(preference.candidate_b, 0) + 1
    return counts


def fallback_score_model(
    rows: Sequence[Dict[str, str]],
    warnings: List[WarningRecord],
    reason: str,
    diagnostic_policy: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    warnings.append(WarningRecord(f"Using metric fallback model: {reason}"))
    scores = []
    for row in rows:
        score = first_number(
            parse_float(row.get("score")),
            parse_float(row.get("metric_visual_quality_score")),
            parse_float(row.get("metric_target_score")),
            parse_float(row.get("metric_ssim")),
        )
        scores.append(score if score is not None else 0.0)
    minimum = min(scores) if scores else 0.0
    maximum = max(scores) if scores else 0.0
    candidate_scores = {}
    for row, score in zip(rows, scores):
        probability_like = 0.5 if maximum == minimum else (score - minimum) / (maximum - minimum)
        candidate_scores[row.get("candidate_id", "")] = {
            "preference_score": round(score, 6),
            "win_probability": round(probability_like, 6),
            "uncertainty": 1.0,
            "observation_count": 0.0,
        }
    return {
        "schema_version": 1,
        "trained": False,
        "method": "metric-fallback",
        "reason": reason,
        "feature_names": [],
        "weights": [],
        "feature_means": {},
        "feature_stds": {},
        "training_examples": 0,
        "pairwise_training_examples": 0,
        "tie_training_examples": 0,
        "failure_training_examples": 0,
        "reason_flag_training_examples": 0,
        "candidate_scores": candidate_scores,
        "reason_flag_signal": reason_flag_signal_result(False),
        "diagnostic_feature_policy": diagnostic_policy or diagnostic_feature_policy(rows),
        "warnings": [warning.to_dict() for warning in warnings],
    }


def neutral_model_result(
    reason: str,
    warnings: List[WarningRecord],
    diagnostic_policy: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    warnings.append(WarningRecord(f"Preference model is neutral: {reason}"))
    return {
        "schema_version": 1,
        "trained": False,
        "method": "neutral",
        "reason": reason,
        "feature_names": [],
        "weights": [],
        "feature_means": {},
        "feature_stds": {},
        "training_examples": 0,
        "pairwise_training_examples": 0,
        "tie_training_examples": 0,
        "failure_training_examples": 0,
        "reason_flag_training_examples": 0,
        "candidate_scores": {},
        "reason_flag_signal": reason_flag_signal_result(False),
        "diagnostic_feature_policy": diagnostic_policy or {
            "residual_metrics_exported_to_features": True,
            "residual_metrics_train_by_default": False,
            "excluded_feature_columns": [],
            "reason": "Residual metrics are diagnostic-only until ablation against human labels is reviewed.",
        },
        "warnings": [warning.to_dict() for warning in warnings],
    }


def parse_float(value: Any) -> Optional[float]:
    if value in {None, ""}:
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(parsed):
        return None
    return parsed


def sigmoid(value: float) -> float:
    if value >= 0:
        z = math.exp(-value)
        return 1.0 / (1.0 + z)
    z = math.exp(value)
    return z / (1.0 + z)


def logistic_loss(probability: float, label: float) -> float:
    epsilon = 1e-9
    probability = min(1.0 - epsilon, max(epsilon, probability))
    return -(label * math.log(probability) + (1.0 - label) * math.log(1.0 - probability))


def dot(left: Sequence[float], right: Sequence[float]) -> float:
    return sum(a * b for a, b in zip(left, right))
