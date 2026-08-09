#!/usr/bin/env python3
"""Export a deterministic, minimal, anonymized subset of real review data."""

import argparse
import csv
import json
import shutil
from collections import defaultdict
from pathlib import Path


FEATURE_COLUMNS = (
    "candidate_id",
    "source_id",
    "run_id",
    "score",
    "app_ready",
    "runtime_ms",
    "line_count",
    "derived_visible_ink_score",
    "metric_visual_quality_score",
    "metric_ssim",
    "metric_detail_score",
    "metric_contrast_score",
    "metric_edge_similarity",
    "metric_line_clump_penalty",
    "metric_overdraw_rate",
    "config_line_ink",
    "config_thread_count",
    "config_final_line_cap",
    "config_visual_opacity_scale",
    "config_visual_width_scale",
    "config_contrast",
    "config_gamma",
)


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--preferences", default="data/preferences/preferences.jsonl")
    parser.add_argument("--features", default="data/processed/features.csv")
    parser.add_argument(
        "--output",
        default="build/public-fixture-export",
        help="Export destination; defaults outside the tracked fixture to avoid accidental overwrite.",
    )
    parser.add_argument("--per-source-reviewer", type=int, default=1)
    parser.add_argument("--max-sources", type=int, default=3)
    return parser.parse_args()


def main():
    args = parse_args()
    preference_rows = read_jsonl(Path(args.preferences))
    feature_rows = read_csv(Path(args.features))
    feature_by_candidate = {row["candidate_id"]: row for row in feature_rows}
    eligible = [
        row
        for row in preference_rows
        if row.get("candidate_a") in feature_by_candidate
        and row.get("candidate_b") in feature_by_candidate
    ]
    selected = balanced_selection(eligible, args.per_source_reviewer, args.max_sources)
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    export(selected, feature_by_candidate, output)
    print(
        json.dumps(
            {
                "output": str(output),
                "preference_count": len(selected),
                "source_count": len({row["source_id"] for row in selected}),
                "candidate_count": len(
                    {
                        candidate
                        for row in selected
                        for candidate in (row["candidate_a"], row["candidate_b"])
                    }
                ),
            },
            sort_keys=True,
        )
    )


def balanced_selection(rows, per_source_reviewer, max_sources):
    allowed_sources = sorted({str(row.get("source_id") or "") for row in rows})[
        : max(0, max_sources)
    ]
    groups = defaultdict(list)
    for row in rows:
        if str(row.get("source_id") or "") not in allowed_sources:
            continue
        key = (str(row.get("source_id") or ""), str(row.get("reviewer") or "unassigned"))
        groups[key].append(row)
    selected = []
    for key in sorted(groups):
        ordered = sorted(groups[key], key=lambda row: str(row.get("preference_id") or ""))
        selected.extend(ordered[:per_source_reviewer])
    return sorted(
        selected,
        key=lambda row: (
            str(row.get("source_id") or ""),
            str(row.get("reviewer") or ""),
            str(row.get("preference_id") or ""),
        ),
    )


def export(preferences, feature_by_candidate, output):
    source_map = sequential_map(sorted({row["source_id"] for row in preferences}), "source")
    reviewer_map = sequential_map(
        sorted({str(row.get("reviewer") or "unassigned") for row in preferences}),
        "reviewer-alias",
    )
    candidate_ids = sorted(
        {
            candidate
            for row in preferences
            for candidate in (row["candidate_a"], row["candidate_b"])
        }
    )
    candidate_map = sequential_map(candidate_ids, "candidate", width=4)
    run_ids = sorted(
        {
            feature_by_candidate[candidate].get("run_id", "")
            for candidate in candidate_ids
        }
    )
    run_map = sequential_map(run_ids, "run")

    public_preferences = []
    for index, row in enumerate(preferences, start=1):
        public_preferences.append(
            {
                "preference_id": f"public-pref-{index:03d}",
                "source_id": source_map[row["source_id"]],
                "candidate_a": candidate_map[row["candidate_a"]],
                "candidate_b": candidate_map[row["candidate_b"]],
                "winner": row["winner"],
                "reviewer": reviewer_map[str(row.get("reviewer") or "unassigned")],
                "reason_flags": list(row.get("reason_flags") or []),
            }
        )

    public_features = []
    manifest_candidates = []
    artifact_dir = output / "artifacts"
    if artifact_dir.exists():
        shutil.rmtree(artifact_dir)
    artifact_dir.mkdir(parents=True)
    for original_id in candidate_ids:
        source = feature_by_candidate[original_id]
        row = {column: source.get(column, "") for column in FEATURE_COLUMNS}
        row["candidate_id"] = candidate_map[original_id]
        row["source_id"] = source_map[source["source_id"]]
        row["run_id"] = run_map[source.get("run_id", "")]
        public_features.append(row)
        artifact_path = copy_public_artifact(
            source.get("artifact_output"),
            artifact_dir,
            row["candidate_id"],
        )
        manifest_candidates.append(candidate_manifest_row(row, artifact_path))

    write_jsonl(output / "preferences.jsonl", public_preferences)
    write_csv(output / "features.csv", public_features, FEATURE_COLUMNS)
    write_json(
        output / "candidate_manifest.json",
        {
            "schema_version": 1,
            "candidate_count": len(manifest_candidates),
            "candidates": manifest_candidates,
            "warnings": [],
        },
    )
    write_json(
        output / "fixture-manifest.json",
        {
            "schema_version": 1,
            "provenance": "deterministic anonymized subset of real human review records",
            "selection": "up to four records per source and reviewer-field alias",
            "anonymized_fields": [
                "preference_id",
                "source_id",
                "candidate_id",
                "run_id",
                "reviewer",
            ],
            "removed_fields": [
                "timestamp",
                "notes",
                "private source/comparison artifact paths",
                "source hashes",
            ],
            "public_artifact_policy": (
                "Generated SVG outputs only; original and diagnostic source images are excluded"
            ),
            "public_asset_license": "Source-photo terms are listed in portfolio/assets/ATTRIBUTION.md",
            "preference_count": len(public_preferences),
            "candidate_count": len(public_features),
            "labeled_source_count": len(source_map),
            "reviewer_alias_count": len(reviewer_map),
            "independent_reviewer_identity_confirmed": False,
            "repeated_pair_count": 0,
        },
    )


def copy_public_artifact(raw_path, artifact_dir, candidate_id):
    source = Path(str(raw_path or ""))
    if not source.is_absolute():
        source = Path.cwd() / source
    if not source.is_file() or source.suffix.lower() != ".svg":
        raise FileNotFoundError(f"Missing public SVG artifact for {candidate_id}: {source}")
    destination = artifact_dir / f"{candidate_id}.svg"
    shutil.copyfile(source, destination)
    return f"fixtures/public/artifacts/{destination.name}"


def candidate_manifest_row(row, artifact_path):
    return {
        "run_id": row["run_id"],
        "candidate_id": row["candidate_id"],
        "source_id": row["source_id"],
        "source_hash": None,
        "config": {
            "lineInk": number(row.get("config_line_ink")),
            "threadCount": integer(row.get("config_thread_count")),
            "finalLineCap": integer(row.get("config_final_line_cap")),
            "visualOpacityScale": number(row.get("config_visual_opacity_scale")),
            "visualWidthScale": number(row.get("config_visual_width_scale")),
            "contrast": number(row.get("config_contrast")),
            "gamma": number(row.get("config_gamma")),
        },
        "metrics": {
            "visualQualityScore": number(row.get("metric_visual_quality_score")),
            "ssim": number(row.get("metric_ssim")),
        },
        "artifact_paths": {
            "output": artifact_path,
            "comparison": None,
        },
        "runtime_ms": number(row.get("runtime_ms")),
        "line_count": integer(row.get("line_count")),
        "app_ready": truthy(row.get("app_ready")),
        "score": number(row.get("score")),
    }


def sequential_map(values, prefix, width=2):
    return {value: f"{prefix}-{index:0{width}d}" for index, value in enumerate(values, 1)}


def number(value):
    try:
        return float(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


def integer(value):
    value = number(value)
    return int(round(value)) if value is not None else None


def truthy(value):
    return str(value).strip().lower() in {"1", "true", "yes"}


def read_jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def read_csv(path):
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_jsonl(path, rows):
    path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def write_csv(path, rows, columns):
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
