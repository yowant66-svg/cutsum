# Security Policy

CutSum is pre-release Alpha software. Report suspected vulnerabilities privately to
`yowant66@gmail.com`. Do not open a public issue for an undisclosed vulnerability or include
credentials, private media, exploit payloads, or personal data in a report.

Include the affected version, operating system, reproduction steps, impact, and any safe mitigation
you have identified. The maintainer will acknowledge receipt when practical, investigate, and
coordinate disclosure and remediation according to severity and available capacity. No response or
fix timeline is guaranteed for this pre-release project.

## Data and credential boundary

- Never commit or attach secrets, cookies, OAuth material, private media, generated media, fonts,
  absolute home-directory paths, or raw Provider responses containing sensitive data.
- The core offline path needs no API key. A Provider must obtain its own credentials from the host
  environment; credentials must not enter ProviderRecord, CutPlan, ExecutionRecord, or logs.
- Auditable process commands redact common credential flags and replace the local home prefix with
  `<HOME>`. Review files before sharing because arbitrary media metadata or third-party tool stderr
  may still contain sensitive source content.
- A local path binding is runtime-only. Use portable serialization when a plan leaves the machine.

## Untrusted inputs

- Treat transcripts, observation bundles, CutPlans, benchmark files, subtitles, and media as
  untrusted input. Validate protocol files before execution.
- Output paths are no-overwrite and constrained to the selected root. Parent traversal, foreign
  absolute-path syntax, and symlink escape are rejected.
- Editing requires a rights attestation, but the tool does not verify ownership or make a legal
  determination.
- FFmpeg, ffprobe, Swift/AppKit, fonts, and configured Providers are external trust boundaries and
  should be kept patched by the operator.

## Supported versions

The public `0.1.0a4` Alpha receives best-effort security fixes. Alpha security fixes may change
schemas or behavior when preserving the previous behavior would keep a vulnerability. Older
internal RC identifiers are not publicly supported releases.
