import copy
import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from .config import LabConfig
from .schema import WarningRecord


DEFAULT_GENERATION_QUALITY_CONTRACT: Dict[str, Any] = {
    "schemaVersion": 1,
    "contractId": "stringartio-generation-quality-contract",
    "version": "fallback",
    "appReady": {
        "allowedQualityModeKeys": ["clean", "accurate"],
        "humanReviewRequired": True,
        "lineCountLimit": 6000,
        "maxPinCount": 768,
        "preferredLineCountRange": {"min": 5200, "max": 5800},
        "promotionProfileKey": "clean",
        "runtimeTargetMs": 30000,
    },
    "forbiddenConfigFields": {
        "truthyOrNonzero": [
            "targetAwareLineReweighting",
            "targetGuidanceStrength",
            "targetAwarePruneRatio",
            "targetAwareSoftPruneRatio",
            "sourcePseudoTargetStrength",
        ]
    },
    "preferenceLabSuggestion": {
        "comparisonSize": 192,
        "repeatCount": 5,
        "runtimeTargetMs": 30000,
        "sampleSize": 192,
    },
    "qualityModel": {
        "name": "perceptual-string-art-v2",
    },
    "visibility": {
        "minLineInk": 0.0085,
        "minVisibleInk": 0.004,
        "minVisualOpacityScale": 0.6,
        "minVisualWidthScale": 0.8,
        "policy": "minimum_floor_plus_app_upload_target",
        "targetLineInk": 0.009,
        "targetVisibleInk": 0.0055,
        "targetVisualOpacityScale": 0.7,
        "targetVisualWidthScale": 0.9,
    },
}


def contract_path_for_root(stringartio_root: str) -> Path:
    return Path(stringartio_root) / "docs" / "string-art" / "generation-quality-contract.json"


def load_generation_quality_contract(
    config: LabConfig,
    warnings: Optional[List[WarningRecord]] = None,
) -> Dict[str, Any]:
    path = contract_path_for_root(config.stringartio_root)
    try:
        raw = path.read_text(encoding="utf-8")
        parsed = json.loads(raw)
        contract = merge_contract_defaults(parsed)
        contract["hash"] = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        contract["sourcePath"] = portable_contract_path(path, Path(config.stringartio_root))
        contract["fallback"] = False
        return contract
    except FileNotFoundError:
        if warnings is not None:
            warnings.append(WarningRecord("Generation quality contract missing; using Preference Lab fallback defaults", str(path)))
    except json.JSONDecodeError as exc:
        if warnings is not None:
            warnings.append(WarningRecord(f"Generation quality contract is invalid JSON; using fallback defaults: {exc}", str(path)))
    except OSError as exc:
        if warnings is not None:
            warnings.append(WarningRecord(f"Could not read generation quality contract; using fallback defaults: {exc}", str(path)))

    contract = merge_contract_defaults({})
    contract["hash"] = None
    contract["sourcePath"] = portable_contract_path(path, Path(config.stringartio_root))
    contract["fallback"] = True
    return contract


def portable_contract_path(path: Path, stringartio_root: Path) -> str:
    try:
        return path.resolve().relative_to(stringartio_root.resolve()).as_posix()
    except ValueError:
        return path.name


def merge_contract_defaults(value: Dict[str, Any]) -> Dict[str, Any]:
    merged = copy.deepcopy(DEFAULT_GENERATION_QUALITY_CONTRACT)
    deep_merge(merged, value or {})
    return merged


def deep_merge(target: Dict[str, Any], source: Dict[str, Any]) -> None:
    for key, value in source.items():
        if isinstance(value, dict) and isinstance(target.get(key), dict):
            deep_merge(target[key], value)
        else:
            target[key] = copy.deepcopy(value)


def generation_quality_contract_reference(contract: Dict[str, Any]) -> Dict[str, Any]:
    quality_model = contract.get("qualityModel") or {}
    return {
        "contract_id": contract.get("contractId"),
        "fallback": bool(contract.get("fallback")),
        "hash": contract.get("hash"),
        "quality_model_name": quality_model.get("name"),
        "schema_version": contract.get("schemaVersion"),
        "source_path": contract.get("sourcePath"),
        "version": contract.get("version"),
    }


def app_ready_runtime_target_ms(contract: Dict[str, Any]) -> int:
    return int((contract.get("appReady") or {}).get("runtimeTargetMs") or 30000)


def app_ready_line_count_limit(contract: Dict[str, Any]) -> int:
    return int((contract.get("appReady") or {}).get("lineCountLimit") or 6000)


def app_ready_max_pin_count(contract: Dict[str, Any]) -> int:
    return int((contract.get("appReady") or {}).get("maxPinCount") or 768)


def app_ready_allowed_quality_modes(contract: Dict[str, Any]) -> List[str]:
    values = (contract.get("appReady") or {}).get("allowedQualityModeKeys") or ["clean", "accurate"]
    return [str(value) for value in values]


def preferred_line_count_min(contract: Dict[str, Any]) -> int:
    preferred = (contract.get("appReady") or {}).get("preferredLineCountRange") or {}
    return int(preferred.get("min") or 5200)


def preferred_line_count_max(contract: Dict[str, Any]) -> int:
    preferred = (contract.get("appReady") or {}).get("preferredLineCountRange") or {}
    return int(preferred.get("max") or 5800)


def visibility_value(contract: Dict[str, Any], key: str, fallback: float) -> float:
    value = (contract.get("visibility") or {}).get(key)
    return float(value if value is not None else fallback)


def forbidden_truthy_config_fields(contract: Dict[str, Any]) -> List[str]:
    fields = ((contract.get("forbiddenConfigFields") or {}).get("truthyOrNonzero") or [])
    return [str(field) for field in fields]
