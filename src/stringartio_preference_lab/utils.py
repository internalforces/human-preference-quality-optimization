import csv
import hashlib
import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

from .schema import WarningRecord


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def read_json(path: Path, warnings: Optional[List[WarningRecord]] = None, required: bool = False) -> Any:
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except FileNotFoundError:
        if warnings is not None and required:
            warnings.append(WarningRecord(f"Missing JSON file: {path}", str(path)))
    except json.JSONDecodeError as exc:
        if warnings is not None:
            warnings.append(WarningRecord(f"Invalid JSON in {path}: {exc}", str(path)))
    except OSError as exc:
        if warnings is not None:
            warnings.append(WarningRecord(f"Could not read {path}: {exc}", str(path)))
    return None


def write_json(path: Path, value: Any, dry_run: bool = False) -> None:
    if dry_run:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with tmp_path.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True)
        handle.write("\n")
    tmp_path.replace(path)


def read_jsonl(path: Path, warnings: Optional[List[WarningRecord]] = None) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    if not path.exists():
        return records
    try:
        with path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    records.append(json.loads(stripped))
                except json.JSONDecodeError as exc:
                    if warnings is not None:
                        warnings.append(
                            WarningRecord(
                                f"Invalid JSONL record at line {line_number}: {exc}",
                                str(path),
                            )
                        )
    except OSError as exc:
        if warnings is not None:
            warnings.append(WarningRecord(f"Could not read JSONL file {path}: {exc}", str(path)))
    return records


def write_jsonl(path: Path, records: Iterable[Dict[str, Any]], dry_run: bool = False) -> None:
    if dry_run:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with tmp_path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, sort_keys=True))
            handle.write("\n")
    tmp_path.replace(path)


def write_csv(path: Path, rows: Sequence[Dict[str, Any]], dry_run: bool = False) -> List[str]:
    fieldnames: List[str] = []
    seen = set()
    for row in rows:
        for key in row.keys():
            if key not in seen:
                seen.add(key)
                fieldnames.append(key)
    if dry_run:
        return fieldnames
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    return fieldnames


def read_csv(path: Path) -> List[Dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def sha256_file(path: Path, warnings: Optional[List[WarningRecord]] = None) -> Optional[str]:
    try:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
    except FileNotFoundError:
        if warnings is not None:
            warnings.append(WarningRecord(f"Missing file for hashing: {path}", str(path)))
    except OSError as exc:
        if warnings is not None:
            warnings.append(WarningRecord(f"Could not hash {path}: {exc}", str(path)))
    return None


def stable_id(*parts: Any, length: int = 16) -> str:
    raw = "\x1f".join(str(part) for part in parts if part is not None)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:length]


def resolve_project_path(raw_path: Any, stringartio_root: Path) -> Optional[str]:
    if not raw_path:
        return None
    path = Path(str(raw_path))
    if not path.is_absolute():
        path = stringartio_root / path
    return str(path.resolve())


def check_path_exists(label: str, raw_path: Optional[str], warnings: List[WarningRecord]) -> None:
    if not raw_path:
        return
    if not Path(raw_path).exists():
        warnings.append(WarningRecord(f"Missing artifact path for {label}: {raw_path}", raw_path))


def numeric_or_none(value: Any) -> Optional[float]:
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if math.isfinite(float(value)):
            return float(value)
    return None


def int_or_none(value: Any) -> Optional[int]:
    numeric = numeric_or_none(value)
    if numeric is None:
        return None
    return int(round(numeric))


def first_number(*values: Any) -> Optional[float]:
    for value in values:
        numeric = numeric_or_none(value)
        if numeric is not None:
            return numeric
    return None


def first_int(*values: Any) -> Optional[int]:
    for value in values:
        integer = int_or_none(value)
        if integer is not None:
            return integer
    return None


def snake_case(value: str) -> str:
    value = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", value)
    value = re.sub(r"[^A-Za-z0-9]+", "_", value)
    return value.strip("_").lower()


def flatten_numeric(prefix: str, value: Any) -> Dict[str, float]:
    output: Dict[str, float] = {}
    if isinstance(value, dict):
        for key, nested in value.items():
            nested_prefix = f"{prefix}_{snake_case(str(key))}" if prefix else snake_case(str(key))
            output.update(flatten_numeric(nested_prefix, nested))
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            output.update(flatten_numeric(f"{prefix}_{index}", nested))
    else:
        numeric = numeric_or_none(value)
        if numeric is not None and prefix:
            output[prefix] = numeric
    return output


def safe_divide(numerator: float, denominator: float, default: float = 0.0) -> float:
    if denominator == 0:
        return default
    return numerator / denominator
