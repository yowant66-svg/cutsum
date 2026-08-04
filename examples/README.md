# Reproducible local examples

These examples use a generated test pattern, a generated tone, and maintainer-authored synthetic
transcripts. They contain no downloaded media, third-party transcript, model call, credential, or
account access. The visual pattern is intentionally meaningless: these examples verify installation,
planning, provenance, subtitles, and media execution rather than editorial quality.

From the repository root, generate one 60-second source file:

```bash
python examples/generate_demo_media.py examples/demo-source.mp4
```

To run and verify all three workflows with one command instead, use:

```bash
python examples/run_quickstart.py cutsum-demo
```

This creates playable outputs plus `cutsum-demo/quickstart-report.json`, whose artifact paths are
relative and whose media entries include SHA-256, codec, dimensions, and duration. See the
[complete quickstart](../docs/quickstart.md) for installation and troubleshooting.

## Interview-style deterministic cut

```bash
cutsum full \
  examples/demo-source.mp4 \
  examples/transcripts/interview.srt \
  examples/output-interview \
  --rights owned \
  --subtitle-mode source_sidecar
```

## Education distillation

```bash
cutsum education-plan \
  examples/demo-source.mp4 \
  examples/transcripts/education.srt \
  --mode auto \
  --rights owned \
  --quality-preset preview \
  --resolution-mode 360p \
  --output examples/education-plan.json

cutsum cut \
  examples/education-plan.json \
  examples/demo-source.mp4 \
  examples/output-education
```

## Sports transcript Alpha

```bash
cutsum sports-transcript-plan \
  examples/demo-source.mp4 \
  examples/transcripts/sports.srt \
  basketball \
  --mode directed \
  --instruction "只要一个绝杀" \
  --rights owned \
  --quality-preset preview \
  --resolution-mode 360p \
  --output examples/sports-plan.json

cutsum cut \
  examples/sports-plan.json \
  examples/demo-source.mp4 \
  examples/output-sports
```

CutSum refuses to overwrite existing outputs. Remove or choose new output paths before rerunning an
example. The sports example proves only deterministic transcript behavior; it does not perform
visual, audio, OCR, scoreboard, or MatchState confirmation.
