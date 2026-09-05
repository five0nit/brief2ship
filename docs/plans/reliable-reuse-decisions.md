# Reliable reuse decisions implementation plan

## License evidence refinement after adversarial review

Canonical MIT body recognition is separate from reuse authority. Free-form
copyright holder fields can contain arbitrary restrictions; a regex cannot
distinguish those reliably from names. Such text keeps `normalized_license=null`,
records `license_body_match=MIT`, and requires review. Exact identifiers and
complete MIT bodies with only fixed title prefixes remain supported. This
conservative tradeoff also affects ordinary copyright-bearing MIT files.

## Target and constraints

Improve Brief2Ship's existing dependency-free Python CLI for human and agent operators: reliable reuse decisions from bounded local/public discovery, honest unknown evidence, complete inspection receipts, deterministic relevance evaluation, concise output, and verified installation. No new registries, mandatory models, candidate execution, public pushes, tags, or publication.

## Base selection

- Baseline: `a708480fadcdbd832f7ec1428fe6b76378be5654` (`v0.6.2`).
- Branch: `fix/reliable-reuse-decisions`.
- Fresh installed-CLI preflight: `/tmp/brief2ship-preflight-implementation-dl9iyhrt/discovery.json`.
- Choice: canonical `five0nit/brief2ship`; disposition `selective-reuse`.
- Inspected local candidate: MIT, 74.50/100, `selective-reuse`.
- Rejected alternatives: `abs-repository-core` 56.50, `abs-nosql-repository-core` 54.50, `active-protocol-discovery` 54.50: database abstractions/protocol discovery, not a base for this repository-discovery CLI. No dependency addition needed.

## Acceptance contracts

1. Missing/malformed package detail evidence remains unknown; provider-confirmed empty dependency collections alone count as zero. Preserve source warnings. Canonical full MIT license normalization preserves raw observed text and rejects modified/truncated or additional restrictive text.
2. Query planning is deterministic, bounded to at most three variants, retains core task/domain terms, and records removed constraint terms. No unbounded retries, external model, paid service, or candidate execution. Exact names remain searchable.
3. Raw score remains explainable; add confidence-adjusted decision score and relevance eligibility so unrelated healthy projects cannot crowd out relevant leads. Keep blockers enforced. Unknown requested constraints must be visible, not assumed met.
4. Final build/reuse decision must not depend on output `limit`. Failed/incomplete sources or insufficient static inspection produce inconclusive status, not an automatic clean-build instruction. No-candidates remains inconclusive unless an operator separately justifies greenfield work. Statically inspected reusable candidates remain provisional when runtime/OSV checks are outstanding; never label those ready.
5. Full JSON and candidate artifacts retain every evaluated candidate and attempted inspection. Markdown shortlist honors `limit` but retains all candidate evidence. Record selected candidate identity and why each inspection slot was spent.
6. Optional concise summary contains decision/status, selected/top candidate, raw/decision score and coverage, blockers, source health and all receipt paths. Preserve default path-only stdout. Inconclusive/failed discovery returns nonzero while writing receipts.
7. Add deterministic fixture-backed task-quality benchmark and regression tests for domain false positives, long requests, unknown evidence, source outages, no matches, license text, local/public dedup and display-limit invariance. Fixture outcomes are synthetic regression evidence, not human-reviewed adoption/accuracy claims.
8. Automate critical Ruff, Pyright, full source/extracted-sdist tests, wheel install and installed round-trip gates in CI. Verify local clean package install, existing network-safety controls and live discovery without running candidates.
9. Update docs/CHANGELOG and a local verification receipt. Keep PyPI pending until separately authorized authenticated publication; no remote changes. Commit only verified files from this clean branch.

## Ownership

- Provider lane: `discovery_providers.py`, new `discovery_query.py`, provider/query tests. No shared model edits.
- Scoring lane: `discovery_scoring.py`, new `discovery_licenses.py`, scoring/license tests. No shared model edits.
- Parent integrator: models, orchestration, rendering, CLI, integration/CLI tests, benchmark, documentation, CI, package verification and final commit.

## Review and verification

Each implementation lane captures failing regression then passing focused tests. Parent performs spec verification before independent quality review. Final shared-runtime changes invalidate prior gates; rerun full source, benchmark, package and installed CLI checks before commit. Preserve receipts outside build payloads when they contain artifact hashes.
