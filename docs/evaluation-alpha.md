# Synthetic evaluation Alpha

The Gate F evaluation harness measures protocol behavior, not real content
quality or model accuracy.

It reports:

- host hard-constraint adherence;
- expected content-label recall;
- dimension applicability consistency;
- constraint satisfaction;
- duplicate and overlap counts;
- ranking stability;
- reproducible hashes;
- the preserved failure taxonomy.

The 12 scenarios in `tests/fixtures/gate_f/scenarios.json` are short,
maintainer-directed synthetic text licensed under Apache-2.0. They contain no
third-party course, film, podcast, article, or subtitle material.

Human annotation templates live in `evaluation/`. Scores use the 0–4 draft
scale and retain reviewer notes. Failed cases must remain in the evaluation
record.
