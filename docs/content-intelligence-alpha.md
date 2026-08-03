# Content intelligence Alpha

Gate F separates content judgment from deterministic enforcement.

The host or a provider supplies:

- the original HostIntent;
- a multi-label ContentProfile;
- candidate proposals;
- evidence-backed assessments for all 14 stable dimensions.

The core package supplies:

- strict Schema validation;
- host-first priority and conflict handling;
- per-task applicability and weight normalization;
- authoritative aggregate calculation;
- count, duration, overlap, duplicate, diversity and ordering selection;
- hashes, provider records, strategy records and CutPlan generation.

## Control modes

- AUTO requires a ContentProfile or provider. It never pretends that a fixed
  fallback profile is content understanding.
- GUIDED preserves supplied constraints and fills only missing strategy fields.
- DIRECTED gives explicit host requirements priority over presets and content
  inference. Capability conflicts remain explicit.

## Alpha calibration boundary

The content-label emphasis in `application/resolution.py` is provisional product
plumbing for synthetic protocol evaluation. It is not a frozen final weight,
threshold, Tier, deletion rule, or quality claim. Real-content calibration
requires a separately authorized evaluation with licensed material and
maintainer annotations.

## Offline file workflow

Authoritative schemas are exported in `schemas/`. A host AI or human may write
strict JSON and validate it through the `intelligence-*` CLI commands. Fixture
files must declare `provider_kind=fixture` and cannot claim to be a real model
response.
