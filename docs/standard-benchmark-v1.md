# Standard benchmark v1

The controlled benchmark exercises the adaptive content-intelligence protocol across nine public
sources:

- three interviews or talks;
- three film or drama sources;
- three education or knowledge sources.

Each item has one AUTO task and two materially different DIRECTED tasks. The benchmark validates
content profiles, resolution traces, all 14 dimension policies, hard include/exclude behavior,
soft versus strong track diversity, selection, and portable CutPlans.

## Boundaries

- It is a protocol and maintainer-review benchmark, not final weight calibration.
- It performs no publishing and no account access.
- It uses no cookies, private accounts, or paid media.
- The run uses curated `host_ai_file` inputs and makes no external model API calls.
- Film and education evaluation windows never exceed 30 minutes.
- Feature films are never downloaded in full.
- Result transcript fields are curator paraphrases, not verbatim transcript redistribution.
- Media rendering is not part of Gate G.

## Run locally

```bash
PYTHONPATH=src uv run python scripts/run_standard_benchmark.py \
  benchmarks/standard-v1/manifest.json \
  benchmarks/standard-v1/curated-inputs.json \
  /absolute/new/output-directory
```

The output directory must not already exist. Each task produces a non-technical `00-result.md`,
protocol JSON documents, metrics, failure records, and a human evaluation form.

## Source records

- `benchmarks/standard-v1/manifest.json` is the versioned machine-readable manifest.
- `benchmarks/standard-v1/candidate-pool.md` records selected and rejected candidates.
- `benchmarks/standard-v1/curated-inputs.json` records provisional content profiles, candidates,
  paraphrased evidence and assessment profiles.

Source and rights notes describe evidence and test boundaries only. They are not legal conclusions.
