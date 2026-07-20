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
```

`-s / --strength` controls how much of the hiss is removed. `1.0` removes it
completely; if that ever sounds too processed ("underwater" tails on words),
try `0.9`, which leaves a whisper of room tone and sounds more natural.

## If the noise changes

The bundled profile matches the current hub/cable/gain setup. If you change
any of that and hear a different noise, record ~10 seconds of silence on the
new setup and either pass it with `--noise` or replace `noise_profile.flac`:

```bash
ffmpeg -i new_silence.m4a -c:a flac noise_profile.flac
```
