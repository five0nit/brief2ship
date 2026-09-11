# 0.8.0 update and migration guide

Status: unpublished source update based on v0.7.0 commit
`2119cd8de44104641c13aa39c80580dc0293c5a4`. The source version is 0.8.0;
this does not imply a GitHub tag, hosted CI result or PyPI release exists.

## Run the updated CLI

From the extracted source directory:

```text
uv tool install .
brief2ship doctor
brief2ship discover "Python retry library with exponential backoff" --sources github,pypi --text
```

The discovery command works in PowerShell and POSIX shells. Without `--output`,
it creates a fresh system temporary directory, performs up to two static
inspections and prints a readable decision. Normal discovery does not execute
candidate code or install candidate dependencies. Provisional and inconclusive
results are evidence states, not a test failure.

Use `--summary` for JSON, `--progress` for stderr progress, and `--inspect-top 0`
for an intentional search-only run. Progress is automatic on an interactive
stderr. Existing `--output DIR` calls still print one receipt path unless
`--summary` or `--text` is requested. The Python API retains its explicit
`DiscoveryConfig.inspect_top` default of zero for compatibility.

## Retry an incomplete search

Each completed provider writes `checkpoint.json` before vulnerability checks
and repository inspection. Retry with the same query, sources, local roots and
per-source limit:

```text
brief2ship discover "Python retry library with exponential backoff" --sources github,pypi --summary --output first-run
brief2ship discover "Python retry library with exponential backoff" --sources github,pypi --summary --resume first-run --output retry-run
```

Successful public-source observations up to 24 hours old may be reused. Failed,
partial, expired and local sources are fetched again. Vulnerability checks,
ranking, requirements and inspections run again. Display, inspection and timeout
budgets may change on retry. Use a fresh output directory; inspection clones
are not reused. An interruption during the first provider can still leave no
completed checkpoint. Later failures retain completed provider observations.

Checkpoints are bounded to 10 MB when read, typed and checked against the exact
source scope. They are unsigned local evidence; resume only checkpoints you
trust. Individual source observation times remain visible and do not become
newer on reuse. A retry can inspect a newer upstream commit than the cached
metadata; review the new pinned identity and outstanding checks.

## Requirements and decisions

Candidates add structured `requirement_checks` with pass/fail/unknown status
and evidence. Existing string checks remain. Domain phrases retain meaningful
terms; supported explicit contradictions prevent selection. Unsupported
constraints remain unknown. Declaration-based matches are not runtime
verification: language metadata does not prove bindings, offline behavior or
compatibility with a target device.

The planner does not implement a Boolean requirement grammar. Compound `or`
and `and/or` requirements, detected negation and optional/preferred targets remain
unknown for manual review rather than becoming mandatory constraints. This is a
conservative heuristic, not a complete natural-language grammar. `parser for Java`
retains Java as domain intent; explicit
implementation cues such as `written in Java` can establish a runtime requirement.

A low keyword score alone no longer authorizes `build-clean`. It can leave a
candidate and the run `inconclusive`. Review explicit negative evidence before
concluding none of the evaluated candidates can be reused. This is a bounded
comparison, not proof about every package or repository.

The full receipt schema remains `brief2ship-discovery-v2`; new fields are
additive. The summary now includes selected identity/version/commit,
requirement evidence, source observation times and a `next_action`. Human text
uses that same summary contract. Consumers must handle candidate-level
`inconclusive` and retain provisional checks even when the process exits zero.
Exit codes retain their v0.7 meanings: 0 supported/provisional, 5 inconclusive,
and 2/3/4 input/policy/operational errors.

## Retrieval and inspection

PyPI retrieval supplements name matching with a small transparent concept-to-name
hint list confirmed against the observed Simple index. It hydrates a bounded
pool, ranks observed name/summary/keyword/description evidence, and records
retrieval provenance. This is not an ecosystem-wide semantic index. A cold
Simple-index fetch can still be slow; no paid search service or model call is
introduced. The retrieved set is not exhaustive.

Exact package identity receives priority before the hydration budget is applied.
When meaningful topic terms exist, generic artifact words such as `library` and
`package` do not crowd them out; ignored terms remain visible in the receipt.
Hint-only candidates require matching observed metadata even when result slots
are empty. These guards do not establish broad search recall or accuracy.

Manifest parsing distinguishes invalid declarations from verified zero
dependencies. Candidate metadata/I/O failures produce inspection evidence
instead of losing the whole result. README terms retain bounded source order
instead of alphabetically discarding terms after the first 200. Limits and
partial evidence remain explicit. Known blocked candidates no longer consume
inspection slots ahead of otherwise eligible candidates just through keyword fit.

Incomplete traversal and unreadable or unsupported recognized manifests leave
the aggregate dependency count unknown, not a verified subtotal. A cap limited
to README feature evidence does not invalidate otherwise complete dependency
inspection. Hydrated metadata is type-checked before candidate fields are changed.
Requirements-file includes/options/markers and unsupported Go module declarations
remain unknown; only the supported static declaration subset is counted. No
included files or package-manager commands are executed to resolve uncertainty.

## Agent instructions and delivery

The skill focuses on choosing reusable implementations. Existing canonical
work, supplied-source reports and direct page extraction can use reduced or
conditional workflows. Detailed design/report/scraping guidance is loaded
only when relevant. Portable examples use automatic output directories.
The build receipt retains status, checks, identities, provenance and next actions.

## Verification and remaining work

Run `python scripts/validate-release.py` for documentation, unit/integration
tests and synthetic decision regressions. Save benchmark detail with
`python scripts/benchmark-discovery.py --output quality-report.json`.
The delivered ZIP includes exact local test/build logs and a validation report.
Local Windows results do not establish Linux sandbox behavior.

New mismatch, synonym and abstention cases are agent-authored synthetic
regressions. They do not establish human-reviewed real-world recall or accuracy.
A reviewed corpus of 30–50 real briefs and recorded provider responses remains
follow-up work. The hint list does not replace that evaluation.

Release publishing, PyPI trusted-publisher setup, hosted CI, real agent-host
installation trials and a new rendered demo require their own final verification.
Candidate-test runner improvements and writable Linux sandbox build/temp areas
were deferred pending Linux evidence. No production publication or account
configuration is part of this source package.
