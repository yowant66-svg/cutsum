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

On 2026-08-03, preliminary exact-name checks found no PyPI project at `cutsum` and no exact GitHub
repository-name search result. These checks are time-bound engineering observations, not trademark
clearance or a guarantee that the names remain available.

## Must resolve before public release

1. Complete a human or legal name/trademark review for `CutSum` where appropriate.
2. Review every record in `provenance/ledger.yaml`, especially the private predecessor references,
   and approve its public wording.
3. Confirm benchmark URL, metadata, paraphrase, and timestamp use; remove any item that lacks an
   acceptable public-test basis. Do not publish downloaded media or transcripts by default.
4. Run the configured CI on an actual remote Linux/macOS/Windows matrix and preserve results.
5. Configure DCO enforcement and private vulnerability reporting on the future GitHub repository.
6. Complete maintainer viewing of real output packs before making editorial-quality claims.

REUSE success, dependency audit success, and this inventory are necessary engineering evidence;
none establishes judicial originality, non-infringement, or final permission to publish.
