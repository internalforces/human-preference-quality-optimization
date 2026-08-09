#!/usr/bin/env python3
"""Build deterministic large comparison, fixed-zoom, and pixel-diff panels."""

from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFont, ImageStat


ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "portfolio" / "assets"
PAIRS = ("pair-1", "pair-2", "pair-3", "pair-7")


def main():
    for pair_id in PAIRS:
        before = thread_panel(Image.open(ASSETS / f"{pair_id}-before.png"))
        after = thread_panel(Image.open(ASSETS / f"{pair_id}-after.png"))
        output = ASSETS / f"{pair_id}-detail-diff.png"
        build_panel(pair_id, before, after).save(output)
        print(output)


def thread_panel(image):
    image = image.convert("RGB")
    panel_width = image.width // 3
    return image.crop((panel_width, 0, panel_width * 2, image.height))


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

    full_size = (600, 600)
    before_large = before.resize(full_size, Image.Resampling.LANCZOS)
    after_large = after.resize(full_size, Image.Resampling.LANCZOS)
    canvas.paste(before_large, (80, 125))
    canvas.paste(after_large, (760, 125))

    zoom_box = (32, 32, 96, 96)
    for x in (80, 760):
        draw.rectangle((x + 150, 275, x + 450, 575), outline=accent, width=5)

    zoom_size = (280, 280)
    before_zoom = before.crop(zoom_box).resize(zoom_size, Image.Resampling.NEAREST)
    after_zoom = after.crop(zoom_box).resize(zoom_size, Image.Resampling.NEAREST)
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
    for index, note in enumerate(notes):
        draw.text((1040, 855 + index * 38), note, fill=muted, font=body_font)
    return canvas


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
