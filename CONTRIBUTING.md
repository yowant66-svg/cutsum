# Contributing

Contributions to CutSum are welcome through issues and pull requests once the public repository is
available. Before contributing, read the Code of Conduct, security policy, source-material rights
boundary, and Developer Certificate of Origin (DCO) 1.1.

1. Inspect the relevant protocol, tests, provenance, and runtime path before editing.
2. Keep changes narrow and preserve the `domain → application/strategies → media/providers →
   SDK/CLI/Skill` dependency direction.
3. Add or update tests for behavior changes. Do not replace real regression evidence with mocks when
   FFmpeg or a deterministic local path is the behavior under review.
4. Do not add media, transcripts copied from third parties, fonts, credentials, generated output,
   model weights, or third-party code without an explicit source and license record.
5. Use the public `universal_cutup.sdk` surface for integrations. Internal modules may change.
6. Run the complete gates documented in README before requesting review.
7. Describe what was verified and what remains unverified. Automated benchmark success is not a
   content-quality claim.

## Developer Certificate of Origin

Every commit must include a `Signed-off-by` line certifying the repository's `DCO` file. Sign a
commit with:

```bash
git commit -s -m "type: concise description"
```

The sign-off name and email become part of the permanent public Git history. Use an identity you
are authorized to publish. Contributions intentionally submitted for inclusion remain governed by
Apache-2.0 section 5; the DCO records the contributor's certification and is not a separate CLA.

For contribution-process questions, contact `yowant66@gmail.com`. Report security vulnerabilities
through `SECURITY.md`, not a public issue.
