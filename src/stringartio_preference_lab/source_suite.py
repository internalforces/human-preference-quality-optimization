import ssl
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .schema import WarningRecord
from .utils import project_root, read_json, sha256_file, utc_now_iso, write_json


DEFAULT_THUMB_WIDTH = 1280
USER_AGENT = "stringartio-preference-lab/1.0"
RUNNER_ROBUSTNESS_RELATIVE_DIR = Path("experiments") / "rl-training" / "robustness"
RUNNER_ROBUSTNESS_EXPECTED_PAIR_IDS = tuple(f"pair-{index}" for index in range(1, 10))
RUNNER_ROBUSTNESS_PROXY_PAIRS = ("pair-2", "pair-4")
RUNNER_ROBUSTNESS_IMAGE_DIMENSIONS = {"width": 1000, "height": 1000}
RUNNER_ROBUSTNESS_IMAGE_FORMAT = "jpeg"

ROBUSTNESS_SOURCE_SPECS: List[Dict[str, Any]] = [
    {
        "id": "robust-face-portrait",
        "category": "face",
        "title": "Face portrait",
        "filename": "face-portrait-boy-venezuela.jpg",
        "commons_title": "File:Boy Face from Venezuela.jpg",
        "download_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/e/e7/Boy_Face_from_Venezuela.jpg/1280px-Boy_Face_from_Venezuela.jpg",
        "fallback_download_urls": ["https://upload.wikimedia.org/wikipedia/commons/e/e7/Boy_Face_from_Venezuela.jpg"],
        "source_url": "https://commons.wikimedia.org/wiki/File:Boy_Face_from_Venezuela.jpg",
        "license": "CC0",
        "license_url": "http://creativecommons.org/publicdomain/zero/1.0/deed.en",
        "attribution": "Wilfredor",
        "tags": ["face", "portrait", "skin-tone", "centered-subject"],
    },
    {
        "id": "robust-pet-cat",
        "category": "pet",
        "title": "Pet cat",
        "filename": "pet-cat-tabby.jpg",
        "commons_title": "File:Cat November 2010-1a.jpg",
        "download_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/4/4d/Cat_November_2010-1a.jpg/1280px-Cat_November_2010-1a.jpg",
        "fallback_download_urls": ["https://upload.wikimedia.org/wikipedia/commons/4/4d/Cat_November_2010-1a.jpg"],
        "source_url": "https://commons.wikimedia.org/wiki/File:Cat_November_2010-1a.jpg",
        "license": "CC BY-SA 3.0",
        "license_url": "https://creativecommons.org/licenses/by-sa/3.0",
        "attribution": "Alvesgaspar",
        "tags": ["pet", "fur", "animal", "soft-detail"],
    },
    {
        "id": "robust-object-camera",
        "category": "object",
        "title": "Object camera",
        "filename": "object-camera-zenit.jpg",
        "commons_title": "File:Cameras Zenit 11.jpg",
        "download_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/4/44/Cameras_Zenit_11.jpg/1280px-Cameras_Zenit_11.jpg",
        "fallback_download_urls": ["https://upload.wikimedia.org/wikipedia/commons/4/44/Cameras_Zenit_11.jpg"],
        "source_url": "https://commons.wikimedia.org/wiki/File:Cameras_Zenit_11.jpg",
        "license": "CC BY-SA 4.0",
        "license_url": "https://creativecommons.org/licenses/by-sa/4.0",
        "attribution": "Dmitry Makeev",
        "tags": ["object", "hard-edge", "metal", "fine-detail"],
    },
    {
        "id": "robust-low-contrast-fog",
        "category": "low_contrast",
        "title": "Low contrast fog",
        "filename": "low-contrast-fog-valley.jpg",
        "commons_title": "File:Beilstein - Schmidbachtal - Ansicht von SW im Herbst mit Nebel (1).jpg",
        "download_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/f/fe/Beilstein_-_Schmidbachtal_-_Ansicht_von_SW_im_Herbst_mit_Nebel_%281%29.jpg/1280px-Beilstein_-_Schmidbachtal_-_Ansicht_von_SW_im_Herbst_mit_Nebel_%281%29.jpg",
        "fallback_download_urls": [
            "https://upload.wikimedia.org/wikipedia/commons/f/fe/Beilstein_-_Schmidbachtal_-_Ansicht_von_SW_im_Herbst_mit_Nebel_%281%29.jpg"
        ],
        "source_url": "https://commons.wikimedia.org/wiki/File:Beilstein_-_Schmidbachtal_-_Ansicht_von_SW_im_Herbst_mit_Nebel_(1).jpg",
        "license": "CC BY-SA 4.0",
        "license_url": "https://creativecommons.org/licenses/by-sa/4.0",
        "attribution": "Roman Eisele",
        "tags": ["low-contrast", "fog", "landscape", "soft-background"],
    },
    {
        "id": "robust-backlit-silhouette",
        "category": "backlight",
        "title": "Backlit silhouette",
        "filename": "backlit-qutub-minar.jpg",
        "commons_title": "File:Backlit QUTUB MINAR.jpg",
        "download_url": "https://upload.wikimedia.org/wikipedia/commons/3/32/Backlit_QUTUB_MINAR.jpg",
        "fallback_download_urls": [],
        "source_url": "https://commons.wikimedia.org/wiki/File:Backlit_QUTUB_MINAR.jpg",
        "license": "CC BY-SA 3.0",
        "license_url": "https://creativecommons.org/licenses/by-sa/3.0",
        "attribution": "Sau123mahajan",
        "tags": ["backlight", "silhouette", "high-dynamic-range", "architecture"],
    },
    {
        "id": "robust-complex-background",
        "category": "complex_background",
        "title": "Complex background",
        "filename": "complex-background-golden-temple.jpg",
        "commons_title": "File:Sikh pilgrim at the Golden Temple (Harmandir Sahib) in Amritsar, India.jpg",
        "download_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/4/41/Sikh_pilgrim_at_the_Golden_Temple_%28Harmandir_Sahib%29_in_Amritsar%2C_India.jpg/1280px-Sikh_pilgrim_at_the_Golden_Temple_%28Harmandir_Sahib%29_in_Amritsar%2C_India.jpg",
        "fallback_download_urls": [
            "https://upload.wikimedia.org/wikipedia/commons/4/41/Sikh_pilgrim_at_the_Golden_Temple_%28Harmandir_Sahib%29_in_Amritsar%2C_India.jpg"
        ],
        "source_url": "https://commons.wikimedia.org/wiki/File:Sikh_pilgrim_at_the_Golden_Temple_(Harmandir_Sahib)_in_Amritsar,_India.jpg",
        "license": "CC BY-SA 4.0",
        "license_url": "https://creativecommons.org/licenses/by-sa/4.0",
        "attribution": "Paulrudd",
        "tags": ["complex-background", "person", "water", "architecture"],
    },
    {
        "id": "robust-dark-background",
        "category": "dark_background",
        "title": "Dark background",
        "filename": "dark-background-candles.jpg",
        "commons_title": "File:Candles with a dark background.jpg",
        "download_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/6/67/Candles_with_a_dark_background.jpg/1280px-Candles_with_a_dark_background.jpg",
        "fallback_download_urls": ["https://upload.wikimedia.org/wikipedia/commons/6/67/Candles_with_a_dark_background.jpg"],
        "source_url": "https://commons.wikimedia.org/wiki/File:Candles_with_a_dark_background.jpg",
        "license": "CC BY-SA 4.0",
        "license_url": "https://creativecommons.org/licenses/by-sa/4.0",
        "attribution": "Jygle",
        "tags": ["dark-background", "small-highlights", "glow", "low-key"],
    },
    {
        "id": "robust-bright-background",
        "category": "bright_background",
        "title": "Bright snow background",
        "filename": "bright-background-snow-evergreen.jpg",
        "commons_title": "File:Blue, White, and Evergreen.jpg",
        "download_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/c/cf/Blue%2C_White%2C_and_Evergreen.jpg/1280px-Blue%2C_White%2C_and_Evergreen.jpg",
        "fallback_download_urls": ["https://upload.wikimedia.org/wikipedia/commons/c/cf/Blue%2C_White%2C_and_Evergreen.jpg"],
        "source_url": "https://commons.wikimedia.org/wiki/File:Blue,_White,_and_Evergreen.jpg",
        "license": "CC0",
        "license_url": "http://creativecommons.org/publicdomain/zero/1.0/deed.en",
        "attribution": "Peter Cooper Jr.",
        "tags": ["bright-background", "snow", "high-key", "thin-detail"],
    },
    {
        "id": "robust-small-offcenter-subject",
        "category": "small_offcenter_subject",
        "title": "Small off-center subject",
        "filename": "small-offcenter-subject-fox.jpg",
        "commons_title": "File:A Tiny Fox In a Big World (3928b631-1dd8-b71c-072c-166e896c3992).jpg",
        "download_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/5/55/A_Tiny_Fox_In_a_Big_World_%283928b631-1dd8-b71c-072c-166e896c3992%29.jpg/1280px-A_Tiny_Fox_In_a_Big_World_%283928b631-1dd8-b71c-072c-166e896c3992%29.jpg",
        "fallback_download_urls": [
            "https://upload.wikimedia.org/wikipedia/commons/5/55/A_Tiny_Fox_In_a_Big_World_%283928b631-1dd8-b71c-072c-166e896c3992%29.jpg"
        ],
        "source_url": "https://commons.wikimedia.org/wiki/File:A_Tiny_Fox_In_a_Big_World_(3928b631-1dd8-b71c-072c-166e896c3992).jpg",
        "license": "Public domain",
        "license_url": "",
        "attribution": "NPS Photo",
        "tags": ["small-subject", "off-center", "animal", "large-background"],
    },
]


def default_source_suite_dir() -> Path:
    return project_root() / "data" / "source_suite" / "robustness"


def build_source_suite(
    output_dir: Optional[str] = None,
    download: bool = True,
    force: bool = False,
    dry_run: bool = False,
) -> Dict[str, Any]:
    suite_dir = Path(output_dir).resolve() if output_dir else default_source_suite_dir()
    image_dir = suite_dir / "images"
    warnings: List[WarningRecord] = []
    records: List[Dict[str, Any]] = []

    for spec in ROBUSTNESS_SOURCE_SPECS:
        local_path = image_dir / spec["filename"]
        if download:
            download_image(download_urls(spec), local_path, force=force, dry_run=dry_run, warnings=warnings)
        records.append(source_record(spec, local_path))

    manifest = {
        "schema_version": 1,
        "created_at": utc_now_iso(),
        "name": "stringartio-robustness-source-suite",
        "description": (
            "Diverse open-license source images for checking whether StringArtio "
            "settings generalize beyond one overfit source image."
        ),
        "source_count": len(records),
        "category_coverage": category_coverage(records),
        "downloaded_count": sum(1 for record in records if record["exists"]),
        "thumb_width": DEFAULT_THUMB_WIDTH,
        "sources": records,
        "dataset_path": str(suite_dir / "dataset.json"),
        "warnings": [warning.to_dict() for warning in warnings],
        "dry_run": dry_run,
    }
    dataset = {
        "name": "stringartio-robustness-source-suite",
        "description": (
            "StringArtio-compatible dataset template. Source and target point to "
            "the same downloaded image so generator experiments can be run manually."
        ),
        "pairs": [dataset_pair(record, suite_dir) for record in records],
    }

    write_json(suite_dir / "manifest.json", manifest, dry_run=dry_run)
    write_json(suite_dir / "dataset.json", dataset, dry_run=dry_run)
    return manifest


def validate_runner_robustness_dataset(
    dataset_dir: Optional[str] = None,
    stringartio_root: Optional[str] = None,
) -> Dict[str, Any]:
    warnings: List[WarningRecord] = []
    base_dir = resolve_runner_robustness_dir(dataset_dir, stringartio_root)
    dataset_path = base_dir / "dataset.json"
    manifest_path = base_dir / "manifest.json"
    dataset = read_json(dataset_path, warnings, required=True) or {}
    manifest = read_json(manifest_path, warnings, required=True) or {}
    pairs = dataset.get("pairs") if isinstance(dataset.get("pairs"), list) else []

    if len(pairs) != len(RUNNER_ROBUSTNESS_EXPECTED_PAIR_IDS):
        warnings.append(
            WarningRecord(
                "Runner robustness dataset should contain exactly 9 pairs",
                str(dataset_path),
            )
        )

    pair_ids = [str(pair.get("id") or "") for pair in pairs if isinstance(pair, dict)]
    duplicate_pair_ids = sorted({pair_id for pair_id in pair_ids if pair_ids.count(pair_id) > 1})
    missing_pair_ids = [pair_id for pair_id in RUNNER_ROBUSTNESS_EXPECTED_PAIR_IDS if pair_id not in pair_ids]
    extra_pair_ids = [pair_id for pair_id in pair_ids if pair_id not in RUNNER_ROBUSTNESS_EXPECTED_PAIR_IDS]
    missing_proxy_pairs = [pair_id for pair_id in RUNNER_ROBUSTNESS_PROXY_PAIRS if pair_id not in pair_ids]

    for message, values in [
        ("Runner robustness dataset has duplicate pair ids", duplicate_pair_ids),
        ("Runner robustness dataset is missing expected pair ids", missing_pair_ids),
        ("Runner robustness dataset has unexpected pair ids", extra_pair_ids),
        ("Runner robustness dataset is missing proxy pair ids", missing_proxy_pairs),
    ]:
        if values:
            warnings.append(WarningRecord(f"{message}: {', '.join(values)}", str(dataset_path)))

    if manifest.get("sourceCount") is not None and manifest.get("sourceCount") != len(pairs):
        warnings.append(
            WarningRecord(
                "Robustness manifest sourceCount does not match dataset pair count",
                str(manifest_path),
            )
        )

    pair_reports = []
    source_target_jpeg_count = 0
    source_target_dimension_count = 0
    all_source_targets_exist = True
    all_source_targets_1000_square = True
    for pair in pairs:
        if not isinstance(pair, dict):
            warnings.append(WarningRecord("Dataset pair is not an object", str(dataset_path)))
            continue
        pair_report = {
            "id": pair.get("id"),
            "source": validate_runner_dataset_asset(
                base_dir,
                pair,
                "source",
                warnings,
                dataset_path,
            ),
            "target": validate_runner_dataset_asset(
                base_dir,
                pair,
                "target",
                warnings,
                dataset_path,
            ),
            "source_category": pair.get("sourceCategory"),
            "source_suite_id": pair.get("sourceSuiteId"),
        }
        for label in ("source", "target"):
            asset = pair_report[label]
            all_source_targets_exist = all_source_targets_exist and bool(asset["exists"])
            if asset["format"] == RUNNER_ROBUSTNESS_IMAGE_FORMAT:
                source_target_jpeg_count += 1
            if asset["dimensions"] == RUNNER_ROBUSTNESS_IMAGE_DIMENSIONS:
                source_target_dimension_count += 1
            else:
                all_source_targets_1000_square = False
        pair_reports.append(pair_report)

    original_count = count_files(base_dir / "originals")
    source_count = count_files(base_dir / "sources")
    target_count = count_files(base_dir / "targets")

    return {
        "dataset_path": str(dataset_path),
        "manifest_path": str(manifest_path),
        "name": dataset.get("name") or manifest.get("name"),
        "description": dataset.get("description") or manifest.get("description"),
        "pair_count": len(pairs),
        "expected_pair_ids": list(RUNNER_ROBUSTNESS_EXPECTED_PAIR_IDS),
        "pair_ids": pair_ids,
        "missing_pair_ids": missing_pair_ids,
        "extra_pair_ids": extra_pair_ids,
        "duplicate_pair_ids": duplicate_pair_ids,
        "proxy_pairs": list(RUNNER_ROBUSTNESS_PROXY_PAIRS),
        "missing_proxy_pairs": missing_proxy_pairs,
        "image_counts": {
            "originals": original_count,
            "sources": source_count,
            "targets": target_count,
        },
        "source_target_jpeg_count": source_target_jpeg_count,
        "source_target_1000_square_count": source_target_dimension_count,
        "source_target_expected_count": len(pairs) * 2,
        "all_source_targets_exist": all_source_targets_exist,
        "all_source_targets_1000_square": all_source_targets_1000_square,
        "pairs": pair_reports,
        "valid": not warnings,
        "warning_count": len(warnings),
        "warnings": [warning.to_dict() for warning in warnings],
    }


def resolve_runner_robustness_dir(
    dataset_dir: Optional[str],
    stringartio_root: Optional[str],
) -> Path:
    if dataset_dir:
        return Path(dataset_dir).expanduser().resolve()
    root = Path(stringartio_root).expanduser() if stringartio_root else project_root().parent / "stringartio"
    return (root / RUNNER_ROBUSTNESS_RELATIVE_DIR).resolve()


def validate_runner_dataset_asset(
    base_dir: Path,
    pair: Dict[str, Any],
    label: str,
    warnings: List[WarningRecord],
    dataset_path: Path,
) -> Dict[str, Any]:
    raw_path = pair.get(label)
    if not raw_path:
        warnings.append(WarningRecord(f"Dataset pair {pair.get('id')} is missing {label}", str(dataset_path)))
        return {"path": None, "exists": False, "dimensions": None, "declared_dimensions": None}
    path = Path(str(raw_path))
    if not path.is_absolute():
        path = base_dir / path
    path = path.resolve()
    exists = path.exists()
    image_type = image_file_format(path) if exists else None
    dimensions = image_dimensions(path) if exists else None
    declared_dimensions = pair.get(f"{label}Dimensions")
    if not exists:
        warnings.append(WarningRecord(f"Dataset pair {pair.get('id')} is missing {label} file", str(path)))
    elif image_type != RUNNER_ROBUSTNESS_IMAGE_FORMAT:
        warnings.append(
            WarningRecord(
                f"Dataset pair {pair.get('id')} {label} is not a JPEG image",
                str(path),
            )
        )
    elif dimensions != RUNNER_ROBUSTNESS_IMAGE_DIMENSIONS:
        warnings.append(
            WarningRecord(
                f"Dataset pair {pair.get('id')} {label} is not 1000x1000",
                str(path),
            )
        )
    if declared_dimensions and dimensions and declared_dimensions != dimensions:
        warnings.append(
            WarningRecord(
                f"Dataset pair {pair.get('id')} declared {label} dimensions do not match the file",
                str(path),
            )
        )
    return {
        "path": str(path),
        "exists": exists,
        "format": image_type,
        "dimensions": dimensions,
        "declared_dimensions": declared_dimensions,
    }


def count_files(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(1 for child in path.iterdir() if child.is_file())


def source_record(spec: Dict[str, Any], local_path: Path) -> Dict[str, Any]:
    exists = local_path.exists()
    dimensions = image_dimensions(local_path) if exists else None
    return {
        "id": spec["id"],
        "category": spec["category"],
        "title": spec["title"],
        "tags": list(spec["tags"]),
        "commons_title": spec["commons_title"],
        "source_url": spec["source_url"],
        "download_url": spec["download_url"],
        "fallback_download_urls": list(spec.get("fallback_download_urls") or []),
        "license": spec["license"],
        "license_url": spec["license_url"],
        "attribution": spec["attribution"],
        "local_path": str(local_path),
        "exists": exists,
        "sha256": sha256_file(local_path) if exists else None,
        "dimensions": dimensions,
    }


def dataset_pair(record: Dict[str, Any], suite_dir: Path) -> Dict[str, Any]:
    local_path = Path(record["local_path"])
    try:
        relative_path = local_path.relative_to(suite_dir)
    except ValueError:
        relative_path = local_path
    dimensions = record.get("dimensions") or {}
    return {
        "id": record["id"],
        "source": str(relative_path),
        "target": str(relative_path),
        "sourceDimensions": dimensions,
        "targetDimensions": dimensions,
        "sourceCategory": record["category"],
        "tags": record["tags"],
        "license": record["license"],
        "sourceUrl": record["source_url"],
        "attribution": record["attribution"],
    }


def category_coverage(records: List[Dict[str, Any]]) -> Dict[str, int]:
    coverage: Dict[str, int] = {}
    for record in records:
        coverage[record["category"]] = coverage.get(record["category"], 0) + 1
    return dict(sorted(coverage.items()))


def download_urls(spec: Dict[str, Any]) -> List[str]:
    urls = [str(spec["download_url"])]
    urls.extend(str(url) for url in spec.get("fallback_download_urls") or [])
    deduped: List[str] = []
    for url in urls:
        if url not in deduped:
            deduped.append(url)
    return deduped


def download_image(
    urls: List[str],
    path: Path,
    force: bool,
    dry_run: bool,
    warnings: List[WarningRecord],
) -> None:
    if dry_run:
        return
    if path.exists() and not force:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    failed_messages: List[str] = []
    for url in urls:
        if try_download_image_url(url, tmp_path, warnings):
            tmp_path.replace(path)
            return
        failed_messages.append(url)
    warnings.append(WarningRecord("All source-suite download URLs failed", ", ".join(failed_messages)))


def try_download_image_url(url: str, tmp_path: Path, warnings: List[WarningRecord]) -> bool:
    try:
        download_url(url, tmp_path)
        return True
    except urllib.error.URLError as exc:
        if "CERTIFICATE_VERIFY_FAILED" not in str(exc):
            warnings.append(WarningRecord(f"Download failed: {exc}", url))
            return False
        warnings.append(
            WarningRecord(
                "TLS certificate verification failed; retried source-suite image download with an unverified context",
                url,
            )
        )
        try:
            download_url(url, tmp_path, context=ssl._create_unverified_context())
            return True
        except urllib.error.URLError as retry_exc:
            warnings.append(WarningRecord(f"Download failed after TLS retry: {retry_exc}", url))
            return False
    except OSError as exc:
        warnings.append(WarningRecord(f"Could not write downloaded image: {exc}", str(tmp_path)))
        return False


def download_url(url: str, path: Path, context: Optional[ssl.SSLContext] = None) -> None:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=60, context=context or default_ssl_context()) as response:
        with path.open("wb") as handle:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                handle.write(chunk)


def default_ssl_context() -> Optional[ssl.SSLContext]:
    try:
        import certifi  # type: ignore

        return ssl.create_default_context(cafile=certifi.where())
    except (ImportError, OSError):
        return None


def image_file_format(path: Path) -> Optional[str]:
    try:
        with path.open("rb") as handle:
            header = handle.read(12)
    except OSError:
        return None
    if header.startswith(b"\xff\xd8"):
        return "jpeg"
    if header.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    return "unknown"


def image_dimensions(path: Path) -> Optional[Dict[str, int]]:
    try:
        with path.open("rb") as handle:
            header = handle.read(32)
            if header.startswith(b"\x89PNG\r\n\x1a\n") and len(header) >= 24:
                return {"width": int.from_bytes(header[16:20], "big"), "height": int.from_bytes(header[20:24], "big")}
            if header.startswith(b"\xff\xd8"):
                handle.seek(0)
                width, height = jpeg_dimensions(handle.read())
                if width and height:
                    return {"width": width, "height": height}
    except OSError:
        return None
    return None


def jpeg_dimensions(data: bytes) -> Tuple[Optional[int], Optional[int]]:
    index = 2
    while index < len(data):
        if data[index] != 0xFF:
            index += 1
            continue
        while index < len(data) and data[index] == 0xFF:
            index += 1
        if index >= len(data):
            break
        marker = data[index]
        index += 1
        if marker in {0xD8, 0xD9}:
            continue
        if index + 2 > len(data):
            break
        segment_length = int.from_bytes(data[index : index + 2], "big")
        if segment_length < 2:
            break
        segment_start = index + 2
        segment_end = index + segment_length
        if marker in {
            0xC0,
            0xC1,
            0xC2,
            0xC3,
            0xC5,
            0xC6,
            0xC7,
            0xC9,
            0xCA,
            0xCB,
            0xCD,
            0xCE,
            0xCF,
        }:
            if segment_start + 5 > len(data):
                break
            height = int.from_bytes(data[segment_start + 1 : segment_start + 3], "big")
            width = int.from_bytes(data[segment_start + 3 : segment_start + 5], "big")
            return width, height
        index = segment_end
    return None, None
