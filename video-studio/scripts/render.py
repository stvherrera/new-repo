from __future__ import annotations

import json
import math
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "build"
ASSETS = ROOT / "assets"
PROJECT = ROOT / "project.json"


def run(cmd: list[str]) -> None:
    print("+", " ".join(cmd))
    subprocess.run(cmd, check=True)


def font(size: int, mono: bool = False):
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf" if mono else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationMono-Regular.ttf" if mono else "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    ]
    for path in candidates:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def fit_cover(img: Image.Image, w: int, h: int) -> Image.Image:
    ratio = max(w / img.width, h / img.height)
    nw, nh = math.ceil(img.width * ratio), math.ceil(img.height * ratio)
    img = img.resize((nw, nh), Image.Resampling.LANCZOS)
    left = (nw - w) // 2
    top = (nh - h) // 2
    return img.crop((left, top, left + w, top + h))


def make_scene_frame(scene: dict, cfg: dict, output: Path) -> None:
    w = cfg["output"]["width"]
    h = cfg["output"]["height"]
    style = cfg["style"]
    scene_id = str(scene["id"]).zfill(2)

    base = None
    for ext in ("jpg", "jpeg", "png", "webp"):
        candidate = ASSETS / f"scene_{scene_id}.{ext}"
        if candidate.exists():
            base = fit_cover(Image.open(candidate).convert("RGB"), w, h)
            break

    if base is None:
        base = Image.new("RGB", (w, h), style.get("background", "#081019"))

    # Documentary treatment: blur very slightly, darken, then add a left-to-right vignette.
    if base:
        base = base.filter(ImageFilter.GaussianBlur(radius=0.25))
    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    for x in range(w):
        alpha = int(175 - 95 * (x / w))
        od.line((x, 0, x, h), fill=(2, 8, 14, max(45, alpha)))
    base = Image.alpha_composite(base.convert("RGBA"), overlay)

    draw = ImageDraw.Draw(base)
    accent = style.get("accent", "#55d6be")
    text = style.get("text", "#f2f6f8")

    draw.rounded_rectangle((90, 82, 215, 128), radius=12, fill=accent)
    draw.text((112, 91), scene_id, font=font(24, mono=True), fill="#071019")

    title_font = font(64)
    title = scene["title"]
    # Simple wrapping tuned for 1080p.
    words = title.split()
    lines, current = [], ""
    for word in words:
        test = (current + " " + word).strip()
        if draw.textlength(test, font=title_font) > 960 and current:
            lines.append(current)
            current = word
        else:
            current = test
    if current:
        lines.append(current)

    y = 170
    for line in lines[:3]:
        draw.text((90, y), line, font=title_font, fill=text)
        y += 78

    diagram = scene.get("diagram", [])
    card_y = max(470, y + 45)
    x = 90
    card_font = font(28, mono=True)
    for item in diagram[:8]:
        tw = int(draw.textlength(item, font=card_font)) + 60
        if x + tw > w - 90:
            x = 90
            card_y += 82
        draw.rounded_rectangle((x, card_y, x + tw, card_y + 58), radius=14,
                               fill=(11, 25, 36, 225), outline=accent, width=2)
        draw.text((x + 30, card_y + 13), item, font=card_font, fill=text)
        x += tw + 20

    draw.text((90, h - 100), "WEB ARCHITECTURE STUDY GUIDE", font=font(24), fill=(205, 220, 226, 210))
    base.convert("RGB").save(output, quality=94)


def main() -> None:
    cfg = json.loads(PROJECT.read_text(encoding="utf-8"))
    timings = json.loads((BUILD / "timings.json").read_text(encoding="utf-8"))
    timing_by_id = {t["id"]: t for t in timings}

    frames = BUILD / "frames"
    clips = BUILD / "clips"
    frames.mkdir(parents=True, exist_ok=True)
    clips.mkdir(parents=True, exist_ok=True)

    w = int(cfg["output"]["width"])
    h = int(cfg["output"]["height"])
    fps = int(cfg["output"]["fps"])

    concat_lines = []
    for scene in cfg["scenes"]:
        sid = str(scene["id"]).zfill(2)
        duration = float(timing_by_id[sid]["duration"])
        image_path = frames / f"scene_{sid}.jpg"
        clip_path = clips / f"scene_{sid}.mp4"
        video_asset = None
        for ext in ("mp4", "mov", "webm"):
            c = ASSETS / f"scene_{sid}.{ext}"
            if c.exists():
                video_asset = c
                break

        if video_asset:
            # Loop real footage as needed; keep it muted. A slow crop/scale normalizes mixed sources.
            run([
                "ffmpeg", "-y", "-stream_loop", "-1", "-i", str(video_asset),
                "-t", f"{duration:.3f}", "-an",
                "-vf", f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},fps={fps}",
                "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-pix_fmt", "yuv420p",
                str(clip_path)
            ])
        else:
            make_scene_frame(scene, cfg, image_path)
            frames_count = max(2, int(duration * fps))
            # Ken Burns-style motion on stills for a documentary feel.
            vf = (
                f"scale=2048:-2,zoompan=z='min(zoom+0.00020,1.07)':"
                f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
                f"d={frames_count}:s={w}x{h}:fps={fps},format=yuv420p"
            )
            run([
                "ffmpeg", "-y", "-loop", "1", "-i", str(image_path),
                "-t", f"{duration:.3f}", "-vf", vf,
                "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-pix_fmt", "yuv420p",
                str(clip_path)
            ])
        concat_lines.append(f"file '{clip_path.resolve()}'")

    concat_file = BUILD / "concat.txt"
    concat_file.write_text("\n".join(concat_lines) + "\n", encoding="utf-8")
    silent_video = BUILD / "video_silent.mp4"
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_file), "-c", "copy", str(silent_video)])

    narration = BUILD / "narration_master.wav"
    music = ASSETS / "music.mp3"
    final_path = BUILD / cfg["output"]["filename"]

    if music.exists():
        run([
            "ffmpeg", "-y", "-i", str(silent_video), "-i", str(narration),
            "-stream_loop", "-1", "-i", str(music),
            "-filter_complex",
            "[1:a]loudnorm=I=-16:TP=-1.5:LRA=8[voice];[2:a]volume=0.10[music];[voice][music]amix=inputs=2:duration=first:dropout_transition=2[a]",
            "-map", "0:v:0", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
            "-shortest", str(final_path)
        ])
    else:
        run([
            "ffmpeg", "-y", "-i", str(silent_video), "-i", str(narration),
            "-filter_complex", "[1:a]loudnorm=I=-16:TP=-1.5:LRA=8[a]",
            "-map", "0:v:0", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
            "-shortest", str(final_path)
        ])

    print(f"FINAL={final_path}")


if __name__ == "__main__":
    main()
