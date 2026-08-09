from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

from .config import LabConfig
from .ingest import load_candidate_manifest
from .schema import ALLOWED_WINNERS, REASON_FLAGS, Preference, WarningRecord
from .utils import read_jsonl


def preference_pair_key(source_id: str, candidate_a: str, candidate_b: str) -> Tuple[str, str, str]:
    left, right = sorted([candidate_a, candidate_b])
    return (source_id, left, right)


def load_preferences(path: str, warnings: Optional[List[WarningRecord]] = None) -> List[Preference]:
    output: List[Preference] = []
    for raw in read_jsonl(Path(path), warnings):
        preference, record_warnings = parse_preference(raw)
        if warnings is not None:
            warnings.extend(record_warnings)
        if preference:
            output.append(preference)
    return output


def labeled_pair_keys(preferences: Iterable[Preference]) -> Set[Tuple[str, str, str]]:
    return {
        preference_pair_key(preference.source_id, preference.candidate_a, preference.candidate_b)
        for preference in preferences
    }


def parse_preference(raw: Dict[str, Any]) -> Tuple[Optional[Preference], List[WarningRecord]]:
    warnings: List[WarningRecord] = []
    required = ["preference_id", "source_id", "candidate_a", "candidate_b", "winner"]
    for field in required:
        if not raw.get(field):
            warnings.append(WarningRecord(f"Preference record is missing required field: {field}"))
    winner = raw.get("winner")
    if winner and winner not in ALLOWED_WINNERS:
        warnings.append(WarningRecord(f"Preference winner must be one of {sorted(ALLOWED_WINNERS)}"))
    reason_flags = raw.get("reason_flags") or []
    if not isinstance(reason_flags, list):
        warnings.append(WarningRecord("Preference reason_flags must be a list"))
        reason_flags = []
    unknown_flags = [flag for flag in reason_flags if flag not in REASON_FLAGS]
    for flag in unknown_flags:
        warnings.append(WarningRecord(f"Unknown preference reason flag: {flag}"))
    if raw.get("candidate_a") == raw.get("candidate_b"):
        warnings.append(WarningRecord("Preference candidates must be different"))

    if warnings:
        return None, warnings
    return (
        Preference(
            preference_id=str(raw["preference_id"]),
            source_id=str(raw["source_id"]),
            candidate_a=str(raw["candidate_a"]),
            candidate_b=str(raw["candidate_b"]),
            winner=str(raw["winner"]),
            reviewer=raw.get("reviewer"),
            timestamp=raw.get("timestamp"),
            reason_flags=list(reason_flags),
            notes=raw.get("notes"),
        ),
        warnings,
    )


def validate_preferences(config: LabConfig) -> Dict[str, Any]:
    warnings: List[WarningRecord] = []
    preferences = load_preferences(config.preference_path, warnings)
    candidates = {candidate.candidate_id: candidate for candidate in load_candidate_manifest(config.manifest_path)}

    for preference in preferences:
        candidate_a = candidates.get(preference.candidate_a)
        candidate_b = candidates.get(preference.candidate_b)
        if candidate_a is None:
            warnings.append(WarningRecord(f"Preference references unknown candidate_a: {preference.candidate_a}"))
        if candidate_b is None:
            warnings.append(WarningRecord(f"Preference references unknown candidate_b: {preference.candidate_b}"))
        if candidate_a and candidate_a.source_id != preference.source_id:
            warnings.append(WarningRecord(f"candidate_a source does not match preference source: {preference.preference_id}"))
        if candidate_b and candidate_b.source_id != preference.source_id:
            warnings.append(WarningRecord(f"candidate_b source does not match preference source: {preference.preference_id}"))
        if candidate_a and candidate_b and candidate_a.source_id != candidate_b.source_id:
            warnings.append(WarningRecord(f"Preference candidates must share a source: {preference.preference_id}"))

    return {
        "path": config.preference_path,
        "preference_count": len(preferences),
        "warning_count": len(warnings),
        "warnings": [warning.to_dict() for warning in warnings],
    }
