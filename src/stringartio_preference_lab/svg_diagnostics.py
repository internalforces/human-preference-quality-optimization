import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Dict, List, Optional

from .utils import first_number


DEFAULT_RENDERED_STROKE_OPACITY_FLOOR = 0.0055
DEFAULT_RENDERED_STROKE_WIDTH_FLOOR = 0.8

STROKE_SHAPE_TAGS = {
    "circle",
    "ellipse",
    "line",
    "path",
    "polygon",
    "polyline",
    "rect",
}

NUMBER_RE = re.compile(r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?")


def rendered_svg_diagnostics(raw_path: Optional[str]) -> Dict[str, Any]:
    diagnostics: Dict[str, Any] = {
        "path_present": bool(raw_path),
        "path_exists": False,
        "valid": False,
        "line_count": 0,
        "stroke_element_count": 0,
        "missing_stroke_opacity_count": 0,
        "missing_stroke_width_count": 0,
        "warning_count": 0,
        "warnings": [],
    }
    if not raw_path:
        add_warning(diagnostics, "missing_svg_path")
        return diagnostics

    path = Path(raw_path)
    if path.suffix.lower() != ".svg":
        add_warning(diagnostics, "output_artifact_is_not_svg")
        return diagnostics
    if not path.exists():
        add_warning(diagnostics, "missing_svg_file")
        return diagnostics

    diagnostics["path_exists"] = True
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError as exc:
        add_warning(diagnostics, f"invalid_svg: {exc}")
        return diagnostics
    except OSError as exc:
        add_warning(diagnostics, f"svg_read_error: {exc}")
        return diagnostics

    diagnostics["valid"] = True
    stats = {
        "opacities": [],
        "widths": [],
        "missing_opacity": 0,
        "missing_width": 0,
    }
    walk_svg(root, initial_svg_state(), stats, diagnostics)

    opacities = stats["opacities"]
    widths = stats["widths"]
    diagnostics["line_count"] = len(opacities)
    diagnostics["stroke_element_count"] = len(opacities)
    diagnostics["missing_stroke_opacity_count"] = stats["missing_opacity"]
    diagnostics["missing_stroke_width_count"] = stats["missing_width"]
    if opacities:
        diagnostics.update(numeric_summary("stroke_opacity", opacities))
        diagnostics.update(numeric_summary("stroke_width", widths))
    else:
        add_warning(diagnostics, "no_stroked_svg_elements")
    return diagnostics


def rendered_svg_visibility_risk(rendered_svg: Optional[Dict[str, Any]]) -> float:
    if not rendered_svg:
        return 0.0
    if not rendered_svg.get("path_present"):
        return 0.0

    opacity = first_number(rendered_svg.get("stroke_opacity_mean"))
    width = first_number(rendered_svg.get("stroke_width_mean"))
    opacity_risk = floor_risk(opacity, DEFAULT_RENDERED_STROKE_OPACITY_FLOOR)
    width_risk = floor_risk(width, DEFAULT_RENDERED_STROKE_WIDTH_FLOOR)
    warning_count = first_number(rendered_svg.get("warning_count")) or 0.0
    warning_risk = min(0.4, 0.12 * warning_count)
    if rendered_svg.get("valid") is False and rendered_svg.get("path_exists"):
        warning_risk = max(warning_risk, 0.5)
    return clamp01(0.5 * opacity_risk + 0.4 * width_risk + 0.1 * warning_risk)


def rendered_svg_diagnostic_summary(candidates: List[Any]) -> Dict[str, Any]:
    total = 0
    warning_candidates = 0
    total_warnings = 0
    low_opacity = 0
    low_width = 0
    invalid = 0
    missing = 0
    for candidate in candidates:
        rendered_svg = getattr(candidate, "metadata", {}).get("rendered_svg") or {}
        if not rendered_svg:
            continue
        total += 1
        warning_count = int(first_number(rendered_svg.get("warning_count")) or 0)
        total_warnings += warning_count
        if warning_count:
            warning_candidates += 1
        if rendered_svg.get("valid") is False and rendered_svg.get("path_exists"):
            invalid += 1
        if rendered_svg.get("path_present") and not rendered_svg.get("path_exists"):
            missing += 1
        opacity = first_number(rendered_svg.get("stroke_opacity_mean"))
        width = first_number(rendered_svg.get("stroke_width_mean"))
        if opacity is not None and opacity < DEFAULT_RENDERED_STROKE_OPACITY_FLOOR:
            low_opacity += 1
        if width is not None and width < DEFAULT_RENDERED_STROKE_WIDTH_FLOOR:
            low_width += 1
    return {
        "candidate_count": total,
        "warning_candidate_count": warning_candidates,
        "total_warning_count": total_warnings,
        "invalid_svg_candidate_count": invalid,
        "missing_svg_candidate_count": missing,
        "low_opacity_candidate_count": low_opacity,
        "low_width_candidate_count": low_width,
        "opacity_floor": DEFAULT_RENDERED_STROKE_OPACITY_FLOOR,
        "width_floor": DEFAULT_RENDERED_STROKE_WIDTH_FLOOR,
    }


def walk_svg(
    element: ET.Element,
    inherited: Dict[str, Any],
    stats: Dict[str, Any],
    diagnostics: Dict[str, Any],
) -> None:
    state = inherited_svg_state(element, inherited, diagnostics)
    if state["hidden"]:
        return

    if local_name(element.tag) in STROKE_SHAPE_TAGS and draws_stroke(state.get("stroke")):
        effective_opacity = state["opacity_multiplier"] * state["stroke_opacity"]
        if is_transparent_stroke(state.get("stroke")):
            effective_opacity = 0.0
        stats["opacities"].append(clamp01(effective_opacity))
        stats["widths"].append(max(0.0, state["stroke_width"]))
        if not state["stroke_opacity_explicit"]:
            stats["missing_opacity"] += 1
        if not state["stroke_width_explicit"]:
            stats["missing_width"] += 1

    for child in list(element):
        walk_svg(child, state, stats, diagnostics)


def inherited_svg_state(
    element: ET.Element,
    inherited: Dict[str, Any],
    diagnostics: Dict[str, Any],
) -> Dict[str, Any]:
    style = parse_style(element.attrib.get("style"))
    state = dict(inherited)

    stroke = property_value(element, style, "stroke")
    if stroke is not None:
        state["stroke"] = stroke.strip()

    stroke_width = numeric_property(element, style, diagnostics, "stroke-width", "strokeWidth")
    if stroke_width is not None:
        state["stroke_width"] = max(0.0, stroke_width)
        state["stroke_width_explicit"] = True

    stroke_opacity = opacity_property(element, style, diagnostics, "stroke-opacity", "strokeOpacity")
    if stroke_opacity is not None:
        state["stroke_opacity"] = stroke_opacity
        state["stroke_opacity_explicit"] = True

    opacity = opacity_property(element, style, diagnostics, "opacity")
    if opacity is not None:
        state["opacity_multiplier"] *= opacity

    display = property_value(element, style, "display")
    visibility = property_value(element, style, "visibility")
    if display and display.strip().lower() == "none":
        state["hidden"] = True
    if visibility and visibility.strip().lower() == "hidden":
        state["hidden"] = True
    return state


def initial_svg_state() -> Dict[str, Any]:
    return {
        "stroke": None,
        "stroke_width": 1.0,
        "stroke_opacity": 1.0,
        "opacity_multiplier": 1.0,
        "stroke_width_explicit": False,
        "stroke_opacity_explicit": False,
        "hidden": False,
    }


def property_value(element: ET.Element, style: Dict[str, str], *names: str) -> Optional[str]:
    for name in names:
        if name in element.attrib:
            return str(element.attrib[name])
    for name in names:
        style_value = style.get(name.lower())
        if style_value is not None:
            return style_value
    return None


def numeric_property(
    element: ET.Element,
    style: Dict[str, str],
    diagnostics: Dict[str, Any],
    *names: str,
) -> Optional[float]:
    raw = property_value(element, style, *names)
    if raw is None:
        return None
    value = parse_number(raw)
    if value is None:
        add_warning(diagnostics, f"invalid_numeric_svg_property:{names[0]}={raw}")
    return value


def opacity_property(
    element: ET.Element,
    style: Dict[str, str],
    diagnostics: Dict[str, Any],
    *names: str,
) -> Optional[float]:
    raw = property_value(element, style, *names)
    if raw is None:
        return None
    value = parse_number(raw)
    if value is None:
        add_warning(diagnostics, f"invalid_opacity_svg_property:{names[0]}={raw}")
        return None
    if str(raw).strip().endswith("%"):
        value = value / 100.0
    return clamp01(value)


def parse_style(raw_style: Optional[str]) -> Dict[str, str]:
    if not raw_style:
        return {}
    output: Dict[str, str] = {}
    for chunk in str(raw_style).split(";"):
        if ":" not in chunk:
            continue
        key, value = chunk.split(":", 1)
        output[key.strip().lower()] = value.strip()
    return output


def parse_number(raw: Any) -> Optional[float]:
    if raw is None:
        return None
    match = NUMBER_RE.search(str(raw).strip())
    if not match:
        return None
    try:
        return float(match.group(0))
    except ValueError:
        return None


def draws_stroke(stroke: Optional[str]) -> bool:
    if stroke is None:
        return False
    normalized = stroke.strip().lower()
    return normalized not in {"", "none"}


def is_transparent_stroke(stroke: Optional[str]) -> bool:
    if stroke is None:
        return False
    normalized = stroke.strip().lower().replace(" ", "")
    return normalized == "transparent" or normalized.endswith(",0)") or normalized.endswith(",0.0)")


def local_name(tag: str) -> str:
    if "}" in tag:
        return tag.rsplit("}", 1)[1]
    return tag


def numeric_summary(prefix: str, values: List[float]) -> Dict[str, float]:
    return {
        f"{prefix}_min": min(values),
        f"{prefix}_mean": sum(values) / len(values),
        f"{prefix}_max": max(values),
    }


def floor_risk(value: Optional[float], floor: float) -> float:
    if value is None:
        return 0.0
    if floor <= 0:
        return 0.0
    return clamp01((floor - value) / floor)


def clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def add_warning(diagnostics: Dict[str, Any], message: str) -> None:
    diagnostics.setdefault("warnings", []).append(message)
    diagnostics["warning_count"] = len(diagnostics["warnings"])
