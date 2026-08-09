from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


ALLOWED_WINNERS = {"A", "B", "tie", "both_bad"}

REASON_FLAGS = {
    "sharper_face",
    "better_hair",
    "better_outline",
    "better_contrast",
    "cleaner",
    "less_blurry",
    "less_clumping",
    "better_visibility",
}


@dataclass
class WarningRecord:
    message: str
    path: Optional[str] = None
    level: str = "warning"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Candidate:
    run_id: str
    candidate_id: str
    source_id: str
    source_hash: Optional[str]
    config: Dict[str, Any] = field(default_factory=dict)
    metrics: Dict[str, Any] = field(default_factory=dict)
    artifact_paths: Dict[str, Optional[str]] = field(default_factory=dict)
    runtime_ms: Optional[float] = None
    line_count: Optional[int] = None
    preset: Optional[str] = None
    lane: Optional[str] = None
    app_ready: bool = False
    app_ready_reason: Optional[str] = None
    score: Optional[float] = None
    profile: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: Dict[str, Any]) -> "Candidate":
        return cls(
            run_id=str(value.get("run_id", "")),
            candidate_id=str(value.get("candidate_id", "")),
            source_id=str(value.get("source_id", "")),
            source_hash=value.get("source_hash"),
            config=dict(value.get("config") or {}),
            metrics=dict(value.get("metrics") or {}),
            artifact_paths=dict(value.get("artifact_paths") or {}),
            runtime_ms=value.get("runtime_ms"),
            line_count=value.get("line_count"),
            preset=value.get("preset"),
            lane=value.get("lane"),
            app_ready=bool(value.get("app_ready")),
            app_ready_reason=value.get("app_ready_reason"),
            score=value.get("score"),
            profile=value.get("profile"),
            metadata=dict(value.get("metadata") or {}),
        )


@dataclass
class Preference:
    preference_id: str
    source_id: str
    candidate_a: str
    candidate_b: str
    winner: str
    reviewer: Optional[str] = None
    timestamp: Optional[str] = None
    reason_flags: List[str] = field(default_factory=list)
    notes: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
