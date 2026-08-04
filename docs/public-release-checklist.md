# CutSum public Alpha release checklist

更新时间：2026-08-03

This checklist separates local engineering readiness from actions that create public state. A checked
local item does not imply legal clearance, public adoption, or Codex for Open Source eligibility.

## Decided and implemented locally

- [x] Project and distribution name: `CutSum` / `cutsum`.
- [x] Copyright holder: `DXBATM`.
- [x] Maintainer, security, and conduct contact: `yowant66@gmail.com`.
- [x] Apache-2.0 project license with REUSE annotations.
- [x] DCO 1.1 contribution sign-off policy.
- [x] Contributor Covenant 2.1.
- [x] Public `cutsum` CLI with compatible `cutup` alias and `universal_cutup` import namespace.
- [x] Sports Alpha frozen as transcript-only heuristic functionality.
- [x] Clean public Git history starts on `main` with one DCO-signed root commit.
- [x] CI includes a dedicated branch-coverage job with an explicit 85% failure threshold.
- [x] Maintainer release approval is recorded in `docs/maintainer-release-approval.md`.
- [x] Three public examples use generated media and maintainer-authored synthetic transcripts.

## Required before public release

- [x] Maintainer accepted the documented CutSum name/trademark engineering boundary for this Alpha.
- [x] Maintainer approved the public provenance-ledger wording as engineering evidence.
- [x] Maintainer approved the benchmark metadata, URL, paraphrase, and rights-note boundary.
- [x] Editorial-quality claims remain prohibited because personal viewing was not separately attested.
- [x] Create the GitHub repository under the maintainer-controlled account from the clean public
  repository only; never push the private complete-history bundle or old branches.
- [x] Configure branch protection, required CI checks, DCO enforcement, and private vulnerability
  reporting on GitHub.
- [x] Run the checked-in Linux, macOS, and Windows CI remotely and preserve the successful evidence.
- [x] Review the final wheel, sdist, SBOM, release manifest, checksums, and annotated tag before upload.

The annotated tag is not a cryptographic Git signature. Release authenticity is bounded by the
protected `main` branch, required GitHub checks, the GitHub Release record, and published SHA-256
checksums.

## Required before a Codex for Open Source application

- [ ] Public repository and public releases exist.
- [ ] Real external users, issues, pull requests, or integrations provide observable adoption and
  maintenance evidence.
- [ ] The maintainer can truthfully document ongoing issue triage, review, release, and Codex usage.
- [ ] Re-check the current OpenAI program form and terms at application time.
