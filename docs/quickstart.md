# CutSum 5–10 minute quickstart

This quickstart produces playable clips for three workflows without downloading media, calling a
model, using an API key, or accessing an account. The source video is generated locally with
FFmpeg, and every transcript is maintainer-authored synthetic text.

## 1. Prerequisites

- Python 3.11, 3.12, or 3.13
- Git
- FFmpeg and ffprobe on `PATH`

Confirm FFmpeg before continuing:

```bash
ffmpeg -version
ffprobe -version
```

## 2. Install the reviewed Alpha wheel

macOS or Linux:

```bash
git clone https://github.com/yowant66-svg/cutsum.git
cd cutsum
python3 -m venv .venv
source .venv/bin/activate
python -m pip install https://github.com/yowant66-svg/cutsum/releases/download/v0.1.0a3/cutsum-0.1.0a3-py3-none-any.whl
cutsum --help
```

Windows PowerShell:

```powershell
git clone https://github.com/yowant66-svg/cutsum.git
Set-Location cutsum
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install https://github.com/yowant66-svg/cutsum/releases/download/v0.1.0a3/cutsum-0.1.0a3-py3-none-any.whl
cutsum --help
```

For a security-sensitive installation, download the wheel and `SHA256SUMS.txt` from the
[`v0.1.0a3` Release](https://github.com/yowant66-svg/cutsum/releases/tag/v0.1.0a3) and verify the
checksum before installing.

## 3. Run all three demonstrations

```bash
python examples/run_quickstart.py cutsum-demo
```

The command runs:

1. an interview-style deterministic cut with source-language subtitle sidecars;
2. an educational distillation plan followed by real media execution;
3. a directed basketball transcript example requesting one decisive score.

Successful completion prints `Quickstart passed` and creates:

```text
cutsum-demo/
├── interview/
├── education/
├── sports/
├── education-plan.json
├── sports-plan.json
├── owned-synthetic-source.mp4
└── quickstart-report.json
```

`quickstart-report.json` contains only relative artifact paths, hashes, codec information,
dimensions, durations, package/runtime versions, and the declared evidence boundary. It contains no
credentials or media content and is the preferred attachment for trial feedback.

Run just one workflow by repeating `--track` as needed:

```bash
python examples/run_quickstart.py education-demo --track education
```

CutSum refuses to overwrite an existing output directory. Choose a new directory for each run.

## 4. Inspect the result

Open at least one MP4 from each selected track and check:

- the file plays to completion;
- video and audio are present;
- the selected segment matches the synthetic transcript;
- any subtitle sidecar remains synchronized.

The automated report proves that the files were rendered and decoded; it does not replace human
editorial review.

## Troubleshooting

- `ffmpeg and ffprobe must both be available`: install FFmpeg and open a new terminal.
- `No module named universal_cutup`: activate the same virtual environment used for installation.
- `output directory already exists`: choose a new output name; CutSum is intentionally no-overwrite.
- Subtitle burn-in unavailable: run `cutsum subtitle-capabilities`. The quickstart uses sidecars and
  does not require libass.
- Sports output is transcript-only heuristic Alpha. It does not inspect pixels, audio, OCR,
  scoreboards, or MatchState.

For a structured trial, continue with the [public trial kit](trial-kit/README.md).
