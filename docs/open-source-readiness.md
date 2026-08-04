# Open-source readiness

更新时间：2026-08-03

This is an engineering and license-risk record, not a legal opinion or final clearance.

## Distribution inventory

| Item | Current boundary | Status |
|---|---|---|
| Project Python and Swift source | Apache-2.0 via root LICENSE and REUSE annotations | Engineering checks pass |
| Python runtime dependencies | Pydantic, PyYAML, Typer; resolved by the installer, not vendored | `pip-audit` has no known vulnerability in the locked environment |
| FFmpeg and ffprobe | External system programs; not bundled | Operator installs and follows upstream licenses |
| Swift/AppKit fallback | Uses installed macOS runtime only | No Apple binary redistributed |
| Fonts | Uses system fonts | No font file redistributed |
| Model weights and cloud SDKs | None bundled | Provider integration remains replaceable |
| Tests and synthetic fixtures | Maintainer-authored; manifest records SPDX, provenance, generator, and hash | REUSE checks pass |
| Standard benchmark records | URLs, metadata, timestamps, curator summaries/paraphrases; no media or full transcript files | Rights notes remain engineering records |
| Local evidence videos | Stored outside the repository and wheel | Must not be committed or published by default |

The locked runtime tree observed locally contains Pydantic/pydantic-core (MIT), PyYAML (MIT), Typer
(MIT), Click (BSD-3-Clause), Rich/markdown-it-py/mdurl (MIT), Pygments (BSD-2-Clause), Shellingham
(ISC), annotated-types/annotated-doc/typing-inspection (MIT), and typing-extensions (PSF-2.0).
These classifications come from installed distribution metadata and included license files; a
release review must regenerate the inventory from the final lock rather than copying this snapshot.

The wheel contains package source plus LICENSE and NOTICE. It does not contain benchmark media,
fonts, credentials, cookies, local evidence, the repository-local Skill, or evaluation reports.

## Engineering provenance conclusion

The current evidence supports a predominantly new typed implementation under this repository,
with earlier private `youtube-cutup-pipeline` symbols recorded as reference rewrites in
`provenance/ledger.yaml`. The ledger states that blocks were not copied and records target files,
hashes, review dates, and AI assistance.

No obvious external copied-code evidence was found in the current audit. This is an engineering
provenance conclusion only. The early private reference repository, its authorship, and the legal
effect of any reference use still need human or legal confirmation.

## Public identity and governance decisions

- Public project and Python distribution name: `CutSum` / `cutsum`.
- Copyright holder: `DXBATM`.
- Maintainer, security, and conduct contact: `yowant66@gmail.com`.
- Contribution attestation: Developer Certificate of Origin 1.1 with commit sign-off.
- Community conduct: Contributor Covenant 2.1.
- Compatibility boundary: the public CLI is `cutsum`; `cutup` remains an alias and the Python
  import namespace remains `universal_cutup`. Existing protocol and evidence identifiers are not
  silently renamed.

The maintainer approved use of `CutSum` / `cutsum` for this Alpha under the engineering boundary in
`docs/maintainer-release-approval.md`. This is not trademark clearance or a legal opinion.

## Public Alpha controls

1. The maintainer approved the name, provenance wording, and benchmark-use boundary for this Alpha.
2. Downloaded media and complete third-party transcripts remain excluded from the repository and
   release assets.
3. GitHub-hosted Linux, macOS, and Windows CI, DCO enforcement, protected `main`, secret scanning,
   dependency alerts, and private vulnerability reporting are enabled.
4. Public examples use generated media and synthetic transcripts only.
5. The release continues to prohibit editorial-quality claims because personal viewing was not
   separately attested.
6. Future real-media benchmarks require their own rights record and human review before any
   precision, recall, or quality statement.

REUSE success, dependency audit success, and this inventory are necessary engineering evidence;
none establishes judicial originality, non-infringement, or final permission to publish.
