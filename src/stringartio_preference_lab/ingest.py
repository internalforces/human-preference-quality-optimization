from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

from .config import LabConfig
from .generation_quality_contract import (
    app_ready_allowed_quality_modes,
    app_ready_line_count_limit,
    app_ready_max_pin_count,
    app_ready_runtime_target_ms,
    forbidden_truthy_config_fields,
    load_generation_quality_contract,
)
from .schema import Candidate, WarningRecord
from .svg_diagnostics import rendered_svg_diagnostics
from .utils import (
    check_path_exists,
    first_int,
    first_number,
    read_json,
    resolve_project_path,
    sha256_file,
    stable_id,
    utc_now_iso,
    write_json,
)


RESULT_FILENAMES = {
    "results.json",
    "summary.json",
    "artwork-quality-summary.json",
    "best-config.json",
    "preference-lab-handoff.json",
    "promotion-preview.json",
    "manifest.json",
}


def discover_run_dirs(experiments_path: Path) -> List[Path]:
    run_dirs: Set[Path] = set()
    if not experiments_path.exists():
        return []
    for filename in RESULT_FILENAMES:
        for file_path in experiments_path.rglob(filename):
            if "node_modules" in file_path.parts:
                continue
            run_dirs.add(file_path.parent)
    return sorted(run_dirs)


def select_run_dirs(
    experiments_path: Path,
    run_id: Optional[str],
    warnings: List[WarningRecord],
) -> List[Path]:
    if run_id is None:
        return discover_run_dirs(experiments_path)

    run_dir = resolve_requested_run_dir(experiments_path, run_id, warnings)
    if run_dir is None:
        return []
    if not run_dir.exists():
        warnings.append(WarningRecord("Requested runId not found", str(run_dir)))
        return []
    if not run_dir.is_dir():
        warnings.append(WarningRecord("Requested runId path is not a directory", str(run_dir)))
        return []
    if not contains_result_file(run_dir):
        warnings.append(WarningRecord("Requested runId has no readable experiment files", str(run_dir)))
        return []
    return [run_dir]


def resolve_requested_run_dir(
    experiments_path: Path,
    run_id: str,
    warnings: List[WarningRecord],
) -> Optional[Path]:
    safe_run_id = safe_run_id_segment(run_id, warnings)
    if safe_run_id is None:
        return None

    experiments_root = experiments_root_for_run_selection(experiments_path)
    try:
        resolved_root = experiments_root.resolve()
        resolved_run_dir = (experiments_root / "local-runs" / safe_run_id).resolve()
    except OSError as exc:
        warnings.append(WarningRecord(f"Could not resolve requested runId path: {exc}", str(experiments_path)))
        return None

    try:
        resolved_run_dir.relative_to(resolved_root)
    except ValueError:
        warnings.append(WarningRecord("Requested runId resolves outside the experiments path", str(resolved_run_dir)))
        return None
    return resolved_run_dir


def experiments_root_for_run_selection(experiments_path: Path) -> Path:
    resolved = experiments_path.resolve()
    if resolved.name == "local-runs":
        return resolved.parent
    if len(resolved.parts) >= 2 and resolved.parent.name == "local-runs":
        return resolved.parent.parent
    return resolved


def safe_run_id_segment(run_id: str, warnings: List[WarningRecord]) -> Optional[str]:
    value = str(run_id).strip()
    if not value:
        warnings.append(WarningRecord("Requested runId is empty"))
        return None
    path = Path(value)
    if path.is_absolute() or path.name != value or value in {".", ".."} or "\\" in value:
        warnings.append(WarningRecord("Requested runId must be a single path segment", value))
        return None
    return value


def contains_result_file(run_dir: Path) -> bool:
    return any((run_dir / filename).is_file() for filename in RESULT_FILENAMES)


def ingest_experiments(
    config: LabConfig,
    dry_run: bool = False,
    limit_runs: Optional[int] = None,
    run_id: Optional[str] = None,
) -> Dict[str, Any]:
    warnings: List[WarningRecord] = []
    config_warnings = config.validate(create_dirs=not dry_run)
    warnings.extend(config_warnings)

    stringartio_root = Path(config.stringartio_root)
    experiments_path = Path(config.experiments_path)
    generation_quality_contract = load_generation_quality_contract(config, warnings)
    source_hashes = load_source_hashes(stringartio_root, experiments_path, warnings)
    run_dirs = select_run_dirs(experiments_path, run_id, warnings)
    if limit_runs is not None:
        run_dirs = run_dirs[: max(0, limit_runs)]

    candidates: List[Candidate] = []
    seen_keys: Set[str] = set()
    for run_dir in run_dirs:
        run_candidates = ingest_run_dir(
            run_dir,
            stringartio_root,
            source_hashes,
            warnings,
            seen_keys,
            generation_quality_contract,
        )
        candidates.extend(run_candidates)

    manifest = {
        "schema_version": 1,
        "created_at": utc_now_iso(),
        "source": {
            "stringartio_root": str(stringartio_root.resolve()),
            "experiments_path": str(experiments_path.resolve()),
            "run_dir_count": len(run_dirs),
            "source_count": len(source_hashes),
            **({"requested_run_id": run_id} if run_id is not None else {}),
        },
        "candidate_count": len(candidates),
        "candidates": [candidate.to_dict() for candidate in candidates],
        "warnings": [warning.to_dict() for warning in warnings],
    }
    write_json(Path(config.manifest_path), manifest, dry_run=dry_run)
    return manifest


def load_candidate_manifest(path: str) -> List[Candidate]:
    data = read_json(Path(path), required=False) or {}
    return [Candidate.from_dict(raw) for raw in data.get("candidates", [])]


def load_source_hashes(
    stringartio_root: Path,
    experiments_path: Path,
    warnings: List[WarningRecord],
) -> Dict[str, str]:
    dataset_paths = [
        experiments_path / "rl-training" / "dataset.json",
        stringartio_root / "experiments" / "rl-training" / "dataset.json",
    ]
    dataset = None
    dataset_path = None
    for candidate_path in dataset_paths:
        dataset = read_json(candidate_path, warnings)
        if dataset:
            dataset_path = candidate_path
            break

    hashes: Dict[str, str] = {}
    if not dataset:
        warnings.append(WarningRecord("No rl-training dataset found for source hashes"))
        return hashes

    base_dir = dataset_path.parent if dataset_path else experiments_path / "rl-training"
    for pair in dataset.get("pairs", []):
        source_id = str(pair.get("id") or "")
        source_path = pair.get("source")
        if not source_id or not source_path:
            warnings.append(WarningRecord("Dataset pair is missing id or source", str(dataset_path)))
            continue
        resolved = (base_dir / str(source_path)).resolve()
        digest = sha256_file(resolved, warnings)
        if digest:
            hashes[source_id] = digest
    return hashes


def ingest_run_dir(
    run_dir: Path,
    stringartio_root: Path,
    source_hashes: Dict[str, str],
    warnings: List[WarningRecord],
    seen_keys: Set[str],
    generation_quality_contract: Dict[str, Any],
) -> List[Candidate]:
    files = {
        "summary": read_json(run_dir / "summary.json", warnings),
        "results": read_json(run_dir / "results.json", warnings),
        "artwork": read_json(run_dir / "artwork-quality-summary.json", warnings),
        "best": read_json(run_dir / "best-config.json", warnings),
        "handoff": read_json(run_dir / "preference-lab-handoff.json", warnings),
        "promotion": read_json(run_dir / "promotion-preview.json", warnings),
        "manifest": read_json(run_dir / "manifest.json", warnings),
    }

    if not any(files.values()):
        warnings.append(WarningRecord("No readable experiment files found", str(run_dir)))
        return []

    context = create_run_context(run_dir, files, generation_quality_contract)
    candidates: List[Candidate] = []
    candidates.extend(
        extract_artwork_candidates(
            context,
            files.get("artwork") or {},
            files.get("promotion") or {},
            stringartio_root,
            source_hashes,
            warnings,
            seen_keys,
        )
    )
    candidates.extend(
        extract_best_config_candidates(
            context,
            files.get("best") or {},
            stringartio_root,
            source_hashes,
            warnings,
            seen_keys,
        )
    )
    candidates.extend(
        extract_result_episode_candidates(
            context,
            files.get("results") or {},
            stringartio_root,
            source_hashes,
            warnings,
            seen_keys,
        )
    )

    if not candidates:
        warnings.append(WarningRecord("Run directory produced no source-level candidates", str(run_dir)))
    return candidates


def create_run_context(
    run_dir: Path,
    files: Dict[str, Any],
    generation_quality_contract: Dict[str, Any],
) -> Dict[str, Any]:
    run_id = (
        lookup(files, "summary", "runId")
        or lookup(files, "artwork", "runId")
        or lookup(files, "promotion", "runId")
        or lookup(files, "manifest", "runId")
        or run_dir.name
    )
    preset = (
        lookup(files, "summary", "preset")
        or lookup(files, "artwork", "preset")
        or lookup(files, "manifest", "preset")
    )
    score_lanes = lookup(files, "manifest", "scoreLanes") or []
    return {
        "run_dir": run_dir,
        "run_id": str(run_id),
        "preset": preset,
        "score_lanes": score_lanes,
        "generation_quality_contract": generation_quality_contract,
        "preference_lab_by_episode": create_preference_lab_handoff_lookup(
            files.get("handoff") or {}
        ),
    }


def lookup(container: Dict[str, Any], *keys: str) -> Any:
    current: Any = container
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def create_preference_lab_handoff_lookup(handoff: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    by_episode: Dict[str, Dict[str, Any]] = {}
    for suggestion in handoff.get("suggestions", []) or []:
        suggestion_id = suggestion.get("suggestionId") or suggestion.get("suggestion_id")
        if not suggestion_id:
            continue
        metadata = {
            "suggestion_id": suggestion_id,
            "expected_preference_score": suggestion.get("expectedPreferenceScore"),
            "phase_id": suggestion.get("phaseId"),
            "source_run_id": suggestion.get("sourceRunId"),
            "nearest_observed_candidate": suggestion.get("nearestObservedCandidate"),
            "handoff_run_id": handoff.get("runId"),
        }
        for episode in suggestion.get("regenerated", []) or []:
            run_id = episode.get("runId")
            episode_number = episode.get("episode")
            if not run_id or episode_number is None:
                continue
            by_episode[episode_key(run_id, episode_number)] = metadata
    return by_episode


def episode_key(run_id: Any, episode_number: Any) -> str:
    return f"{run_id}:{episode_number}"


def preference_lab_metadata_for_episode(
    context: Dict[str, Any],
    run_id: Any,
    episode_number: Any,
) -> Dict[str, Any]:
    metadata = context.get("preference_lab_by_episode", {}).get(
        episode_key(run_id, episode_number)
    )
    return {"preference_lab": metadata} if metadata else {}


def extract_artwork_candidates(
    context: Dict[str, Any],
    artwork: Dict[str, Any],
    promotion: Dict[str, Any],
    stringartio_root: Path,
    source_hashes: Dict[str, str],
    warnings: List[WarningRecord],
    seen_keys: Set[str],
) -> List[Candidate]:
    output: List[Candidate] = []
    proposed_group = lookup(promotion, "proposed", "source", "groupId")
    for item in artwork.get("candidates", []) or []:
        artifacts = item.get("artifacts") or []
        if not artifacts:
            warnings.append(
                WarningRecord(
                    "Artwork candidate has no source-level artifacts",
                    str(context["run_dir"] / "artwork-quality-summary.json"),
                )
            )
            continue
        group_id = str(
            item.get("candidateId")
            or lookup(item, "source", "groupId")
            or stable_id(context["run_id"], item.get("config"), item.get("metrics"))
        )
        origin_lanes = item.get("originLanes") or []
        lane = origin_lanes[0] if origin_lanes else "artwork-primary"
        for artifact in artifacts:
            source_id = str(artifact.get("inputId") or artifact.get("sourceId") or "")
            if not source_id:
                warnings.append(WarningRecord("Artwork artifact is missing inputId", str(context["run_dir"])))
                continue
            artifact_paths = create_artifact_paths(artifact, stringartio_root)
            candidate_id = concrete_candidate_id(
                f"{context['run_id']}:{group_id}",
                source_id,
                artifact,
                artifact_paths,
            )
            dedupe_key = dedupe_key_for(candidate_id, artifact_paths)
            if dedupe_key in seen_keys:
                continue
            seen_keys.add(dedupe_key)
            warn_missing_artifacts(candidate_id, artifact_paths, warnings)
            rendered_svg = rendered_svg_metadata(candidate_id, artifact_paths, warnings)
            app_ready, app_ready_reason = resolve_app_ready(
                config=item.get("config") or {},
                metrics=item.get("metrics") or {},
                generation_quality_contract=context["generation_quality_contract"],
                lane=lane,
                explicit_ready=bool(item.get("eligible")) and any(str(value).startswith("app-ready") for value in origin_lanes),
                proposed_group=proposed_group,
                group_id=group_id,
                string_art_patch=lookup(item, "stringArtSettingsPatch"),
            )
            runtime_ms = candidate_runtime_ms(
                lookup(item, "metrics", "totalMs"),
                lookup(item, "geometry", "signals", "runtimeMs"),
                artifact_count=len(artifacts),
            )
            output.append(
                Candidate(
                    run_id=context["run_id"],
                    candidate_id=candidate_id,
                    source_id=source_id,
                    source_hash=candidate_source_hash(context, source_id, artifact_paths, source_hashes, warnings),
                    config=dict(item.get("config") or {}),
                    metrics=merge_source_metric(item.get("metrics") or {}, artifact),
                    artifact_paths=artifact_paths,
                    runtime_ms=runtime_ms,
                    line_count=first_int(
                        lookup(item, "geometry", "lineCount"),
                        lookup(item, "metrics", "finalLineCount"),
                        lookup(item, "config", "finalLineCap"),
                        lookup(item, "config", "threadCount"),
                    ),
                    preset=context.get("preset"),
                    lane=lane,
                    app_ready=app_ready,
                    app_ready_reason=app_ready_reason,
                    score=first_number(item.get("artworkPrimary"), item.get("score"), item.get("sourceScore")),
                    profile=item.get("profileKey"),
                    metadata={
                        "source_kind": "artwork-quality-summary",
                        "origin_lanes": origin_lanes,
                        "group_id": group_id,
                        "dimensions": item.get("dimensions") or {},
                        "geometry": item.get("geometry") or {},
                        "quality": {
                            "independentQuality": item.get("independentQuality"),
                            "perceptualQuality": item.get("perceptualQuality"),
                            "targetSimilarity": item.get("targetSimilarity"),
                            "visualFailurePenalty": item.get("visualFailurePenalty"),
                        },
                        "rendered_svg": rendered_svg,
                        **preference_lab_metadata_for_episode(
                            context,
                            lookup(item, "source", "runId"),
                            lookup(item, "source", "episode"),
                        ),
                    },
                )
            )
    return output


def extract_best_config_candidates(
    context: Dict[str, Any],
    best: Dict[str, Any],
    stringartio_root: Path,
    source_hashes: Dict[str, str],
    warnings: List[WarningRecord],
    seen_keys: Set[str],
) -> List[Candidate]:
    output: List[Candidate] = []
    slots = [
        ("bestAppReady", best.get("bestAppReady")),
        ("bestAppRepresentable", best.get("bestAppRepresentable")),
        ("bestQuality", best.get("bestQuality")),
        ("best", best.get("best")),
    ]
    for slot_name, item in slots:
        if not isinstance(item, dict):
            continue
        artifacts = item.get("artifacts") or []
        for artifact in artifacts:
            source_id = str(artifact.get("inputId") or "")
            if not source_id:
                continue
            group_id = str(lookup(item, "source", "groupId") or lookup(item, "source", "signature") or slot_name)
            artifact_paths = create_artifact_paths(artifact, stringartio_root)
            candidate_id = concrete_candidate_id(
                f"{context['run_id']}:{slot_name}:{stable_id(group_id, item.get('config'))}",
                source_id,
                artifact,
                artifact_paths,
            )
            dedupe_key = dedupe_key_for(candidate_id, artifact_paths)
            if dedupe_key in seen_keys:
                continue
            seen_keys.add(dedupe_key)
            warn_missing_artifacts(candidate_id, artifact_paths, warnings)
            rendered_svg = rendered_svg_metadata(candidate_id, artifact_paths, warnings)
            patch = item.get("stringArtSettingsPatch")
            explicit_ready = bool(lookup(patch or {}, "ready")) or slot_name in {"bestAppReady", "bestAppRepresentable"}
            app_ready, app_ready_reason = resolve_app_ready(
                config=item.get("config") or {},
                metrics=item.get("metrics") or {},
                generation_quality_contract=context["generation_quality_contract"],
                lane=slot_name,
                explicit_ready=explicit_ready,
                string_art_patch=patch,
            )
            runtime_ms = candidate_runtime_ms(
                lookup(item, "metrics", "totalMs"),
                artifact_count=len(artifacts),
            )
            output.append(
                Candidate(
                    run_id=context["run_id"],
                    candidate_id=candidate_id,
                    source_id=source_id,
                    source_hash=candidate_source_hash(context, source_id, artifact_paths, source_hashes, warnings),
                    config=dict(item.get("config") or {}),
                    metrics=merge_source_metric(item.get("metrics") or {}, artifact),
                    artifact_paths=artifact_paths,
                    runtime_ms=runtime_ms,
                    line_count=first_int(
                        lookup(item, "metrics", "finalLineCount"),
                        lookup(item, "config", "finalLineCap"),
                        lookup(item, "config", "threadCount"),
                    ),
                    preset=context.get("preset"),
                    lane=slot_name,
                    app_ready=app_ready,
                    app_ready_reason=app_ready_reason,
                    score=first_number(item.get("score"), item.get("loggedScore"), item.get("visualQualityScore")),
                    profile=item.get("profileKey"),
                    metadata={
                        "source_kind": "best-config",
                        "slot": slot_name,
                        "rendered_svg": rendered_svg,
                        **preference_lab_metadata_for_episode(
                            context,
                            lookup(item, "source", "runId") or item.get("runId"),
                            lookup(item, "source", "episode") or item.get("episode"),
                        ),
                    },
                )
            )
    return output


def extract_result_episode_candidates(
    context: Dict[str, Any],
    results: Dict[str, Any],
    stringartio_root: Path,
    source_hashes: Dict[str, str],
    warnings: List[WarningRecord],
    seen_keys: Set[str],
) -> List[Candidate]:
    output: List[Candidate] = []
    for episode in results.get("episodes", []) or []:
        if not isinstance(episode, dict):
            continue
        if episode.get("failed"):
            continue
        artifacts = episode.get("artifacts") or []
        if not artifacts:
            continue
        signature = episode.get("signature") or stable_id(episode.get("config"), episode.get("metrics"))
        group_id = f"{episode.get('profileKey') or 'profile'}:{episode.get('episode') or 'episode'}:{stable_id(signature)}"
        for artifact in artifacts:
            source_id = str(artifact.get("inputId") or "")
            if not source_id:
                warnings.append(WarningRecord("Result artifact is missing inputId", str(context["run_dir"])))
                continue
            artifact_paths = create_artifact_paths(artifact, stringartio_root)
            candidate_id = concrete_candidate_id(
                f"{context['run_id']}:episode-{episode.get('episode', 'unknown')}:{stable_id(signature)}",
                source_id,
                artifact,
                artifact_paths,
            )
            dedupe_key = dedupe_key_for(candidate_id, artifact_paths)
            if dedupe_key in seen_keys:
                continue
            seen_keys.add(dedupe_key)
            warn_missing_artifacts(candidate_id, artifact_paths, warnings)
            rendered_svg = rendered_svg_metadata(candidate_id, artifact_paths, warnings)
            config = dict(episode.get("config") or lookup(episode, "state", "settings") or {})
            metrics = merge_source_metric(episode.get("metrics") or {}, artifact)
            lane = str(episode.get("objective") or episode.get("profileKey") or "episode")
            app_ready, app_ready_reason = resolve_app_ready(
                config=config,
                metrics=metrics,
                generation_quality_contract=context["generation_quality_contract"],
                lane=lane,
                explicit_ready=False,
                string_art_patch=episode.get("stringArtSettingsPatch"),
            )
            runtime_ms = candidate_runtime_ms(
                lookup(episode, "metrics", "totalMs"),
                lookup(episode, "runtime", "episodeWallMs"),
                artifact_count=len(artifacts),
            )
            output.append(
                Candidate(
                    run_id=context["run_id"],
                    candidate_id=candidate_id,
                    source_id=source_id,
                    source_hash=candidate_source_hash(context, source_id, artifact_paths, source_hashes, warnings),
                    config=config,
                    metrics=metrics,
                    artifact_paths=artifact_paths,
                    runtime_ms=runtime_ms,
                    line_count=first_int(
                        lookup(episode, "metrics", "finalLineCount"),
                        lookup(episode, "config", "finalLineCap"),
                        lookup(episode, "config", "threadCount"),
                    ),
                    preset=context.get("preset"),
                    lane=lane,
                    app_ready=app_ready,
                    app_ready_reason=app_ready_reason,
                    score=first_number(episode.get("score"), episode.get("finalScore"), artifact.get("score")),
                    profile=episode.get("profileKey"),
                    metadata={
                        "source_kind": "results-episode",
                        "episode": episode.get("episode"),
                        "action": episode.get("action") or {},
                        "group_id": group_id,
                        "generation_run_id": episode.get("runId"),
                        "rendered_svg": rendered_svg,
                        **preference_lab_metadata_for_episode(
                            context,
                            episode.get("runId"),
                            episode.get("episode"),
                        ),
                    },
                )
            )
    return output


def create_artifact_paths(artifact: Dict[str, Any], stringartio_root: Path) -> Dict[str, Optional[str]]:
    return {
        "source": resolve_project_path(artifact.get("sourcePath"), stringartio_root),
        "target": resolve_project_path(artifact.get("targetPath"), stringartio_root),
        "output": resolve_project_path(artifact.get("outputPath"), stringartio_root),
        "comparison": resolve_project_path(artifact.get("comparisonPath"), stringartio_root),
        "raw_pattern": resolve_project_path(artifact.get("rawPatternPath"), stringartio_root),
    }


def warn_missing_artifacts(
    candidate_id: str,
    artifact_paths: Dict[str, Optional[str]],
    warnings: List[WarningRecord],
) -> None:
    for label, path in artifact_paths.items():
        if label == "raw_pattern":
            continue
        check_path_exists(f"{candidate_id}:{label}", path, warnings)


def candidate_source_hash(
    context: Dict[str, Any],
    source_id: str,
    artifact_paths: Dict[str, Optional[str]],
    source_hashes: Dict[str, str],
    warnings: List[WarningRecord],
) -> Optional[str]:
    source_path = artifact_paths.get("source")
    if source_path and Path(source_path).exists():
        cache = context.setdefault("source_hash_cache", {})
        if source_path not in cache:
            digest = sha256_file(Path(source_path), warnings)
            if digest:
                cache[source_path] = digest
        return cache.get(source_path)
    return source_hashes.get(source_id)


def rendered_svg_metadata(
    candidate_id: str,
    artifact_paths: Dict[str, Optional[str]],
    warnings: List[WarningRecord],
) -> Dict[str, Any]:
    output_path = artifact_paths.get("output")
    diagnostics = rendered_svg_diagnostics(output_path)
    for message in diagnostics.get("warnings", []):
        if message.startswith(("invalid_svg", "svg_read_error")):
            warnings.append(
                WarningRecord(
                    f"Rendered SVG diagnostic warning for {candidate_id}: {message}",
                    output_path,
                )
            )
    return diagnostics


def dedupe_key_for(candidate_id: str, artifact_paths: Dict[str, Optional[str]]) -> str:
    return artifact_paths.get("output") or candidate_id


def concrete_candidate_id(
    base_id: str,
    source_id: str,
    artifact: Dict[str, Any],
    artifact_paths: Dict[str, Optional[str]],
) -> str:
    repeat = artifact.get("repeat")
    path_hash = stable_id(artifact_paths.get("output"), artifact_paths.get("comparison"), artifact.get("score"), length=10)
    if repeat is not None:
        suffix = f"r{repeat}-{path_hash}"
    else:
        suffix = path_hash
    return f"{base_id}::{source_id}::{suffix}"


def merge_source_metric(metrics: Dict[str, Any], artifact: Dict[str, Any]) -> Dict[str, Any]:
    merged = dict(metrics)
    if "score" in artifact:
        merged["sourceArtifactScore"] = artifact.get("score")
    if "repeat" in artifact:
        merged["repeat"] = artifact.get("repeat")
    if "comparisonHash" in artifact:
        merged["comparisonHashPresent"] = True
    return merged


def candidate_runtime_ms(*values: Any, artifact_count: int = 1) -> Optional[float]:
    runtime = first_number(*values)
    if runtime is None:
        return None
    count = max(1, int(artifact_count or 1))
    return runtime / count


def resolve_app_ready(
    config: Dict[str, Any],
    metrics: Dict[str, Any],
    lane: Optional[str],
    generation_quality_contract: Optional[Dict[str, Any]] = None,
    explicit_ready: bool = False,
    proposed_group: Optional[str] = None,
    group_id: Optional[str] = None,
    string_art_patch: Optional[Dict[str, Any]] = None,
) -> Tuple[bool, str]:
    if explicit_ready:
        return True, "runner-app-ready-lane"
    if proposed_group and group_id and proposed_group == group_id:
        return True, "promotion-preview-proposed"
    if isinstance(string_art_patch, dict) and string_art_patch.get("ready") is True:
        return True, str(string_art_patch.get("reason") or "string-art-settings-patch-ready")
    if lane and str(lane).startswith("app-ready"):
        return True, "app-ready-lane"
    if is_app_ready_by_limits(config, metrics, generation_quality_contract):
        return True, "heuristic-app-limits"
    return False, "not-marked-app-ready"


def is_app_ready_by_limits(
    config: Dict[str, Any],
    metrics: Dict[str, Any],
    generation_quality_contract: Optional[Dict[str, Any]] = None,
) -> bool:
    contract = generation_quality_contract or {}
    pin_count = first_int(config.get("pinCount"))
    thread_count = first_int(config.get("threadCount"))
    line_count = first_int(metrics.get("finalLineCount"), config.get("finalLineCap"), thread_count)
    runtime = first_number(metrics.get("totalMs"), metrics.get("runtimeMs"))
    if pin_count is None or thread_count is None:
        return False
    if pin_count > app_ready_max_pin_count(contract) or thread_count > app_ready_line_count_limit(contract):
        return False
    if line_count is not None and line_count > app_ready_line_count_limit(contract):
        return False
    if runtime is not None and runtime > app_ready_runtime_target_ms(contract):
        return False
    if str(config.get("qualityModeKey") or "clean") not in set(app_ready_allowed_quality_modes(contract)):
        return False
    if has_target_aware_logic(config, forbidden_truthy_config_fields(contract)):
        return False
    return True


def has_target_aware_logic(config: Dict[str, Any], active_keys: Optional[Iterable[str]] = None) -> bool:
    active_keys = tuple(active_keys or (
        "targetAwareLineReweighting",
        "targetGuidanceStrength",
        "targetAwarePruneRatio",
        "targetAwareSoftPruneRatio",
        "sourcePseudoTargetStrength",
    ))
    for key in active_keys:
        if is_truthy_or_nonzero(config.get(key)):
            return True
    return False


def is_truthy_or_nonzero(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return float(value) != 0.0
    if isinstance(value, str):
        return value.strip().lower() not in {"", "0", "false", "none", "null"}
    return False


def candidates_by_source(candidates: Iterable[Candidate]) -> Dict[str, List[Candidate]]:
    grouped: Dict[str, List[Candidate]] = {}
    for candidate in candidates:
        grouped.setdefault(candidate.source_id, []).append(candidate)
    return grouped
