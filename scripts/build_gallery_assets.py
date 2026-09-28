#!/usr/bin/env python3
"""Build deterministic large comparison, fixed-zoom, and pixel-diff panels."""

from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFont, ImageStat


ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "portfolio" / "assets"
PAIRS = ("pair-1", "pair-2", "pair-3", "pair-7")
DISPLAY_INK_SCALE = {"pair-2": 4}


def main():
    for pair_id in PAIRS:
        before_asset = Image.open(ASSETS / f"{pair_id}-before.png")
        after_asset = Image.open(ASSETS / f"{pair_id}-after.png")
        before = thread_panel(before_asset)
        after = thread_panel(after_asset)
        output = ASSETS / f"{pair_id}-detail-diff.png"
        build_panel(pair_id, before, after).save(output)
        print(output)
        comparison_output = ASSETS / f"{pair_id}-source-render-comparison.png"
        source = source_panel(before_asset)
        build_source_render_panel(pair_id, source, before, after).save(
            comparison_output,
            optimize=True,
        )
        print(comparison_output)


def thread_panel(image):
    image = image.convert("RGB")
    panel_width = image.width // 3
    return image.crop((panel_width, 0, panel_width * 2, image.height))


def source_panel(image):
    image = image.convert("RGB")
    panel_width = image.width // 3
    return image.crop((0, 0, panel_width, image.height))


def build_source_render_panel(pair_id, source, before, after):
    """Build a compact, high-contrast comparison with source context."""
    canvas = Image.new("RGB", (1400, 820), (247, 248, 251))
    draw = ImageDraw.Draw(canvas)
    title_color = (17, 24, 39)
    muted = (91, 100, 115)
    accent = (239, 68, 68)
    card = (255, 255, 255)

    draw.text(
        (70, 48),
        "Human preference reveals what metrics miss",
        fill=title_color,
        font=font(42, bold=True),
    )
    draw.text(
        (70, 108),
        f"{pair_id} · Source context and high-visibility thread renders",
        fill=muted,
        font=font(23),
    )

    cards = (
        (60, 280, "SOURCE", source, 1),
        (390, 430, "BASELINE", before, 5),
        (860, 430, "TRACK B", after, 5),
    )
    for x, width, label, image, ink_scale in cards:
        draw.rounded_rectangle((x, 170, x + width, 670), radius=26, fill=card)
        draw.text((x + 40, 205), label, fill=accent, font=font(20, bold=True))
        size = 220 if label == "SOURCE" else 320
        image_x = x + (width - size) // 2
        image_y = 275 if label == "SOURCE" else 265
        displayed = image if label == "SOURCE" else darken_ink(image, ink_scale)
        paste_circle(canvas, displayed, (image_x, image_y), size)
        if label == "SOURCE":
            draw.text(
                (x + 38, 535),
                "Open-license source",
                fill=title_color,
                font=font(22, bold=True),
            )
            draw.text((x + 38, 575), "same source · blind review", fill=muted, font=font(18))
        else:
            draw.text(
                (x + 72, 610),
                f"128×128 render · contrast ×{ink_scale}",
                fill=muted,
                font=font(18),
            )

    draw.text(
        (70, 742),
        "Actual StringArtio renders · display-only contrast · no generative enhancement",
        fill=muted,
        font=font(19),
    )
    return canvas


def paste_circle(canvas, image, position, size):
    resized = image.resize((size, size), Image.Resampling.LANCZOS)
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, size - 1, size - 1), fill=255)
    canvas.paste(resized, position, mask)


def build_panel(pair_id, before, after):
    canvas = Image.new("RGB", (1440, 1080), "white")
    draw = ImageDraw.Draw(canvas)
    title_font = font(42, bold=True)
    heading_font = font(28, bold=True)
    body_font = font(22)
    muted = (75, 85, 99)
    accent = (220, 38, 38)

    draw.text((70, 24), f"{pair_id}: rendered thread comparison", fill=(17, 24, 39), font=title_font)
    draw.text((80, 82), "Baseline", fill=(17, 24, 39), font=heading_font)
    draw.text((760, 82), "Track B candidate", fill=(17, 24, 39), font=heading_font)

    ink_scale = DISPLAY_INK_SCALE.get(pair_id, 1)
    before_display = darken_ink(before, ink_scale)
    after_display = darken_ink(after, ink_scale)

    full_size = (600, 600)
    before_large = before_display.resize(full_size, Image.Resampling.LANCZOS)
    after_large = after_display.resize(full_size, Image.Resampling.LANCZOS)
    canvas.paste(before_large, (80, 125))
    canvas.paste(after_large, (760, 125))

    zoom_box = (32, 32, 96, 96)
    for x in (80, 760):
        draw.rectangle((x + 150, 275, x + 450, 575), outline=accent, width=5)

    zoom_size = (280, 280)
    before_zoom = before_display.crop(zoom_box).resize(zoom_size, Image.Resampling.NEAREST)
    after_zoom = after_display.crop(zoom_box).resize(zoom_size, Image.Resampling.NEAREST)
    raw_diff = ImageChops.difference(after, before)
    amplified_diff = raw_diff.point(lambda value: min(255, value * 12))
    diff_large = amplified_diff.resize(zoom_size, Image.Resampling.NEAREST)

    labels = (
        (80, "Baseline — fixed center zoom", before_zoom),
        (400, "After — fixed center zoom", after_zoom),
        (720, "Absolute pixel difference ×12", diff_large),
    )
    for x, label, image in labels:
        draw.text((x, 755), label, fill=(17, 24, 39), font=body_font)
        canvas.paste(image, (x, 795))

    mean_difference = sum(ImageStat.Stat(raw_diff).mean) / 3.0
    draw.text((1040, 805), "Comparison notes", fill=(17, 24, 39), font=heading_font)
    notes = [
        "• same 128×128 render panel",
        "• same fixed center crop",
        "• no generative enhancement",
        "• diff brightness multiplied by 12",
        f"• raw mean abs. pixel diff: {mean_difference:.3f}/255",
    ]
    if ink_scale != 1:
        notes.insert(3, f"• display ink contrast multiplied by {ink_scale}")
    note_y = 850 if ink_scale != 1 else 855
    note_step = 34 if ink_scale != 1 else 38
    for index, note in enumerate(notes):
        draw.text((1040, note_y + index * note_step), note, fill=muted, font=body_font)
    return canvas


def darken_ink(image, scale):
    """Increase display contrast while preserving white and the original geometry."""
    if scale == 1:
        return image
    return image.point(lambda value: max(0, 255 - (255 - value) * scale))


def font(size, bold=False):
    candidates = [
        Path("/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Arial.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return ImageFont.truetype(str(candidate), size)
    return ImageFont.load_default()


if __name__ == "__main__":
    main()
