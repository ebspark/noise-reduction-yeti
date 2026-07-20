# noise-reduction-yeti

Removes the constant hiss from recordings made with a Blue Yeti X plugged
into a Google Pixel 10 Pro through a powered USB hub.

The hiss is *stationary* (same spectrum the whole time), so it can be
removed almost completely with spectral gating: the script learns the hiss's
frequency fingerprint from a noise-only recording, then subtracts exactly
that fingerprint from your real recordings. On the sample recordings this
drops the noise floor from about −57 dB to −88 dB without touching the voice.

A recording of the bare hiss from this exact setup is bundled as
`noise_profile.flac`, so you never need to re-record silence — just run the
script on any file from the same rig.

## Setup (once)

```bash
pip install -r requirements.txt
# ffmpeg must also be installed and on PATH
```

## Usage

```bash
# MP4 video: video stream is copied untouched, only the audio is cleaned
python3 denoise.py recording.mp4            # -> recording_clean.mp4

# plain audio works too (m4a, wav, mp3, flac, ...)
python3 denoise.py voice.m4a

# options
python3 denoise.py recording.mp4 -o out.mp4     # choose output path
python3 denoise.py recording.mp4 -s 0.9         # gentler (default 1.0 = remove all)
python3 denoise.py recording.mp4 -n new_hiss.m4a  # use a fresh noise recording
python3 denoise.py recording.mp4 -n auto        # learn the hiss from the file's
                                                # own quiet pauses
python3 denoise.py recording.mp4 -p             # + polish: EQ, de-esser,
                                                # compression, -16 LUFS loudness
```

`-p / --polish` fixes a flat, "cheap"-sounding voice after denoising: it
downmixes to mono, cuts rumble below 75 Hz and boxiness at 250 Hz, adds
presence at 3.5 kHz and air at 8 kHz, de-esses, evens out levels with 3:1
compression, and normalizes to the −16 LUFS podcast standard.

`-n auto` needs no noise recording at all: it finds the quietest 20% of the
file (the pauses between words) and uses that as the profile. Use it whenever
the gain knob has moved since the bundled profile was recorded — a mismatched
knob position changes the hiss level, and the auto profile tracks it exactly.

`-s / --strength` controls how much of the hiss is removed. `1.0` removes it
completely; if that ever sounds too processed ("underwater" tails on words),
try `0.9`, which leaves a whisper of room tone and sounds more natural.

## Gain knob findings (tested Jul 2026)

Experiments with this rig showed the hiss comes from the USB hub's power,
not the mic's preamp, so the gain knob barely affects it:

- Gain at zero removed ~6 dB of hiss but ~30 dB of voice — recordings made
  that way are unrecoverable (denoising + boosting leaves heavy artifacts).
- The mute button produces pure digital silence, not ambient audio.
- The sweet spot: set gain so your voice peaks around −10 dB. That gives
  ~35 dB of voice-over-hiss separation, and the script then drops the hiss
  below −90 dB with no audible artifacts.

## If the noise changes

The bundled profile matches the current hub/cable/gain setup. If you change
any of that and hear a different noise, record ~10 seconds of silence on the
new setup and either pass it with `--noise` or replace `noise_profile.flac`:

```bash
ffmpeg -i new_silence.m4a -c:a flac noise_profile.flac
```
