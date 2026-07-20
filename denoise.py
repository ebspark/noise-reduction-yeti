#!/usr/bin/env python3
"""Remove the constant hiss from Blue Yeti X recordings (USB-hub noise).

Works on video files (MP4/MOV — video stream is copied untouched, only the
audio is cleaned) and on plain audio files (m4a, wav, mp3, flac, ...).

The repo bundles noise_profile.flac, a recording of the bare hiss from the
Yeti X + powered USB hub + Pixel setup. Every input is denoised against that
profile by default, so you don't need to re-record the hiss each time. If the
noise ever changes (different hub, cable, gain), record ~10 s of silence on
the new setup and pass it with --noise.

Usage:
    python3 denoise.py recording.mp4                 # -> recording_clean.mp4
    python3 denoise.py voice.m4a -o clean.m4a
    python3 denoise.py video.mp4 --strength 0.9      # gentler, keeps some room tone
    python3 denoise.py video.mp4 --noise new_hiss.m4a
    python3 denoise.py video.mp4 --noise auto        # learn the hiss from the
                                                     # recording's own quiet pauses

Requires: ffmpeg on PATH, and `pip install -r requirements.txt`.
"""

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
import soundfile as sf
import noisereduce as nr

REPO_DIR = Path(__file__).resolve().parent
DEFAULT_NOISE = REPO_DIR / "noise_profile.flac"

# Extensions we hand back as AAC-in-MP4-container audio; everything else
# that's audio-only comes back as the same extension via ffmpeg.
VIDEO_AUDIO_CODEC = ["-c:a", "aac", "-b:a", "192k"]


def run(cmd: list[str]) -> None:
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        sys.exit(f"command failed: {' '.join(cmd)}\n{proc.stderr.strip()}")


def probe(path: Path) -> dict:
    proc = subprocess.run(
        ["ffprobe", "-v", "error", "-print_format", "json",
         "-show_streams", str(path)],
        capture_output=True, text=True)
    if proc.returncode != 0:
        sys.exit(f"ffprobe failed on {path}:\n{proc.stderr.strip()}")
    return json.loads(proc.stdout)


def has_video(path: Path) -> bool:
    return any(
        s.get("codec_type") == "video" and s.get("disposition", {}).get("attached_pic", 0) == 0
        for s in probe(path)["streams"])


def decode_to_wav(src: Path, dst: Path, sample_rate: int | None = None) -> None:
    cmd = ["ffmpeg", "-v", "error", "-y", "-i", str(src), "-vn"]
    if sample_rate:
        cmd += ["-ar", str(sample_rate)]
    cmd += ["-c:a", "pcm_f32le", str(dst)]
    run(cmd)


def auto_noise_profile(speech: np.ndarray, sr: int) -> np.ndarray:
    """Build a noise profile from the quietest 20% of 100 ms windows.

    Works because the hiss is constant, so the pauses between words contain
    pure noise. Robust to gain-knob changes, unlike a pre-recorded profile.
    """
    mono = speech.mean(axis=1)
    w = sr // 10
    n = len(mono) // w
    if n < 10:
        sys.exit("--noise auto needs at least ~1s of audio")
    rms = np.array([np.sqrt(np.mean(mono[i * w:(i + 1) * w] ** 2)) for i in range(n)])
    thresh = np.percentile(rms, 20)
    quiet = [i for i in range(n) if rms[i] <= thresh]
    return np.concatenate([speech[i * w:(i + 1) * w] for i in quiet])


def reduce(speech: np.ndarray, noise: np.ndarray, sr: int, strength: float) -> np.ndarray:
    if speech.ndim == 1:
        speech = speech[:, None]
    if noise.ndim == 1:
        noise = noise[:, None]
    out = np.zeros_like(speech)
    for ch in range(speech.shape[1]):
        noise_ch = noise[:, min(ch, noise.shape[1] - 1)]
        out[:, ch] = nr.reduce_noise(
            y=speech[:, ch], y_noise=noise_ch, sr=sr,
            stationary=True, prop_decrease=strength,
            n_fft=2048, freq_mask_smooth_hz=500, time_mask_smooth_ms=64)
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("input", type=Path, help="video or audio file to clean")
    ap.add_argument("-o", "--output", type=Path,
                    help="output path (default: <input>_clean.<ext>)")
    ap.add_argument("-n", "--noise", default=str(DEFAULT_NOISE),
                    help="recording of just the noise, or 'auto' to learn the hiss "
                         "from the input's own quiet pauses — use auto whenever the "
                         "gain knob has moved (default: bundled hiss profile)")
    ap.add_argument("-s", "--strength", type=float, default=1.0,
                    help="how much of the noise to remove, 0-1 (default 1.0; "
                         "try 0.9 if full strength sounds too processed)")
    args = ap.parse_args()

    auto = args.noise == "auto"
    noise_path = None if auto else Path(args.noise)
    if not args.input.exists():
        sys.exit(f"input not found: {args.input}")
    if noise_path and not noise_path.exists():
        sys.exit(f"noise profile not found: {noise_path}")
    if not 0.0 < args.strength <= 1.0:
        sys.exit("--strength must be in (0, 1]")

    out_path = args.output or args.input.with_stem(args.input.stem + "_clean")
    video = has_video(args.input)

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        speech_wav, noise_wav, clean_wav = tmp / "in.wav", tmp / "noise.wav", tmp / "clean.wav"

        decode_to_wav(args.input, speech_wav)
        speech, sr = sf.read(speech_wav, always_2d=True)
        if auto:
            noise = auto_noise_profile(speech, sr)
        else:
            decode_to_wav(noise_path, noise_wav, sample_rate=sr)
            noise, _ = sf.read(noise_wav, always_2d=True)

        print(f"denoising {args.input.name}: {speech.shape[0]/sr:.1f}s, "
              f"{sr} Hz, {speech.shape[1]} ch, strength {args.strength}, "
              f"profile {'auto' if auto else noise_path.name}")
        sf.write(clean_wav, reduce(speech, noise, sr, args.strength), sr)

        if video:
            run(["ffmpeg", "-v", "error", "-y",
                 "-i", str(args.input), "-i", str(clean_wav),
                 "-map", "0:v", "-map", "1:a", "-c:v", "copy",
                 *VIDEO_AUDIO_CODEC, str(out_path)])
        elif out_path.suffix.lower() in {".wav", ".flac"}:
            run(["ffmpeg", "-v", "error", "-y", "-i", str(clean_wav), str(out_path)])
        else:
            run(["ffmpeg", "-v", "error", "-y", "-i", str(clean_wav),
                 *VIDEO_AUDIO_CODEC, str(out_path)])

    print(f"wrote {out_path}")


if __name__ == "__main__":
    main()
