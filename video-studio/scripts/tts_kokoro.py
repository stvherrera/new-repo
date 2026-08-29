from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import soundfile as sf
from kokoro import KPipeline

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "project.json"
BUILD = ROOT / "build"
AUDIO_DIR = BUILD / "audio"
SAMPLE_RATE = 24000


def silence(seconds: float) -> np.ndarray:
    return np.zeros(int(SAMPLE_RATE * seconds), dtype=np.float32)


def main() -> None:
    cfg = json.loads(PROJECT.read_text(encoding="utf-8"))
    BUILD.mkdir(exist_ok=True)
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)

    tts = cfg.get("tts", {})
    lang_code = tts.get("lang_code", "a")
    voice = tts.get("voice", "am_michael")
    speed = float(tts.get("speed", 0.98))
    tail_silence = float(tts.get("tail_silence_seconds", 0.45))

    pipeline = KPipeline(lang_code=lang_code)

    master_parts: list[np.ndarray] = []
    timing = []
    cursor = 0.0

    for scene in cfg["scenes"]:
        scene_id = str(scene["id"]).zfill(2)
        text = scene["narration"].strip()
        chunks: list[np.ndarray] = []

        generator = pipeline(text, voice=voice, speed=speed)
        for _graphemes, _phonemes, audio in generator:
            arr = np.asarray(audio, dtype=np.float32).reshape(-1)
            if arr.size:
                chunks.append(arr)
                chunks.append(silence(0.10))

        if not chunks:
            raise RuntimeError(f"Kokoro returned no audio for scene {scene_id}")

        scene_audio = np.concatenate(chunks + [silence(tail_silence)])
        scene_path = AUDIO_DIR / f"scene_{scene_id}.wav"
        sf.write(scene_path, scene_audio, SAMPLE_RATE)

        duration = len(scene_audio) / SAMPLE_RATE
        timing.append({
            "id": scene_id,
            "title": scene["title"],
            "start": round(cursor, 3),
            "duration": round(duration, 3),
            "audio": str(scene_path.relative_to(ROOT)),
        })
        master_parts.append(scene_audio)
        cursor += duration

    master = np.concatenate(master_parts)
    sf.write(BUILD / "narration_master.wav", master, SAMPLE_RATE)
    (BUILD / "timings.json").write_text(json.dumps(timing, indent=2), encoding="utf-8")
    print(f"Generated {len(timing)} scenes, total {cursor:.1f}s, voice={voice}")


if __name__ == "__main__":
    main()
