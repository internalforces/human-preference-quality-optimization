import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from .schema import WarningRecord
from .utils import project_root, read_json, write_json


@dataclass
class LabConfig:
    stringartio_root: str
    experiments_path: str
    output_path: str
    preference_path: str
    feature_table_path: str
    review_queue_path: str
    manifest_path: str
    model_path: str
    suggestions_path: str

    @classmethod
    def default(cls) -> "LabConfig":
        root = project_root()
        default_stringartio = Path(os.environ.get("STRINGARTIO_ROOT", root.parent / "stringartio"))
        output_path = root / "data" / "processed"
        preference_path = root / "data" / "preferences" / "preferences.jsonl"
        return cls(
            stringartio_root=str(default_stringartio.resolve()),
            experiments_path=str((default_stringartio / "experiments").resolve()),
            output_path=str(output_path.resolve()),
            preference_path=str(preference_path.resolve()),
            feature_table_path=str((output_path / "features.csv").resolve()),
            review_queue_path=str((root / "data" / "review_queue" / "review_queue.jsonl").resolve()),
            manifest_path=str((output_path / "candidate_manifest.json").resolve()),
            model_path=str((output_path / "preference_model.json").resolve()),
            suggestions_path=str((root / "data" / "suggestions" / "suggested-configs.json").resolve()),
        )

    @classmethod
    def from_dict(cls, value: Dict[str, Any]) -> "LabConfig":
        base = cls.default()
        merged = asdict(base)
        merged.update({key: str(raw) for key, raw in value.items() if raw is not None})
        return cls(**merged)

    @classmethod
    def load(cls, path: Optional[str] = None) -> "LabConfig":
        config_path = Path(path) if path else project_root() / "lab-config.json"
        if config_path.exists():
            data = read_json(config_path, required=True) or {}
            return cls.from_dict(data)
        return cls.default()

    def to_dict(self) -> Dict[str, str]:
        return asdict(self)

    def write(self, path: str, dry_run: bool = False) -> None:
        write_json(Path(path), self.to_dict(), dry_run=dry_run)

    def validate(self, create_dirs: bool = False) -> List[WarningRecord]:
        warnings: List[WarningRecord] = []
        stringartio_root = Path(self.stringartio_root)
        experiments_path = Path(self.experiments_path)

        if not stringartio_root.exists():
            warnings.append(WarningRecord("StringArtio root does not exist", str(stringartio_root)))
        if not experiments_path.exists():
            warnings.append(WarningRecord("Experiments path does not exist", str(experiments_path)))
        if stringartio_root.exists() and experiments_path.exists():
            try:
                experiments_path.relative_to(stringartio_root)
            except ValueError:
                warnings.append(
                    WarningRecord(
                        "Experiments path is outside the configured StringArtio root",
                        str(experiments_path),
                    )
                )

        for field_name in [
            "output_path",
            "preference_path",
            "feature_table_path",
            "review_queue_path",
            "manifest_path",
            "model_path",
            "suggestions_path",
        ]:
            raw_path = getattr(self, field_name)
            if not raw_path:
                warnings.append(WarningRecord(f"Config field {field_name} is empty"))
                continue
            path = Path(raw_path)
            directory = path if field_name == "output_path" else path.parent
            if create_dirs:
                directory.mkdir(parents=True, exist_ok=True)

        return warnings


def create_example_config(path: str, stringartio_root: Optional[str] = None, dry_run: bool = False) -> LabConfig:
    config = LabConfig.default()
    if stringartio_root:
        root = Path(stringartio_root).resolve()
        config.stringartio_root = str(root)
        config.experiments_path = str((root / "experiments").resolve())
    config.write(path, dry_run=dry_run)
    return config
