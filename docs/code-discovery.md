# Code discovery and v2 migration

Brief2Ship searches a **bounded, selected source scope**. It does not prove that
no reusable software exists. Normal discovery reads metadata and source; it
never installs candidate dependencies or executes candidate code.

## Run

```bash
brief2ship discover "local robots-aware web scraper" \
  --local /path/to/scoped/workspace \
  --sources local,github,pypi,npm,crates,huggingface \
  --per-source 5 --limit 5 --inspect-top 2 --total-timeout 180 \
  --summary --output discovery/
```

The output directory must be new or empty. Omit `--summary` to preserve the
existing stdout form: one Markdown receipt path. `--summary` emits a JSON object,
not a replacement for the full receipts. Both forms use identical exit semantics.

## Decision contract

The v2 receipt separates:

- `discovery_status`: source collection health (`complete`, `partial`, `failed`).
  Complete means requested providers returned successfully, **not exhaustive recall**.
- `decision_status`: `complete`, `provisional`, or `inconclusive`.
- `overall_recommendation`: the supported reuse disposition, `build-clean`, or
  `inconclusive` when the run cannot support an actionable disposition.
- `selected_candidate_id`: stable identity of the selected, statically inspected
  candidate, or null. A top-ranked lead is not necessarily selected.
- `incomplete_reasons`: why a supported decision could not be made.

`inconclusive` is an evidence state, not a sixth reuse strategy. Failed or partial
provider collection, an empty result set, failed inspection or an uninspected
lead cannot silently become `build-clean`. Increase a bounded inspection budget,
repair a failed provider, narrow the scope explicitly or refine the brief;
do not automatically authorize greenfield work on exit 5.

An inspected reusable candidate may be selected **provisionally**. Required
checks, unknown constraint matches and test/OSV gaps remain in its evidence.
Provisional selection is a lead for further validation, not proof of production
readiness. A supported clean-build conclusion applies only to the evaluated set
and recorded policy, never the entire ecosystem.

Exit codes for `discover`:

| Code | Meaning |
|---:|---|
| 0 | Supported complete or provisional decision; inspect `decision_status` and required checks |
| 2 | Invalid command-line arguments |
| 3 | Safety policy blocked the operation |
| 4 | Operational/input/output failure |
| 5 | Receipts written, but evidence is insufficient for a decision |

This changes v1, which returned success whenever candidates existed and could
turn source outages or display truncation into `build-clean`.

## Queries and evidence

`query_plan` preserves the original brief, extracted core query, explicit
constraints and up to three deterministic variants. The parser removes only
recognized instruction/constraint patterns; it is not an LLM or a semantic
requirements solver. `web scraper` survives the brief
`local robots-aware web scraper`; `local` and `robots-aware` remain unverified
checks rather than disappearing or being claimed as satisfied.

GitHub searches at most three variants and uses reciprocal-rank fusion
(`1 / (60 + source rank)`), deduplicating before the per-source candidate cap.
Other registries search the core query under their existing bounded provider
contracts. Each source receipt records attempted queries, endpoints, status,
errors and warnings. Source ranks are tie-breakers, never raw cross-registry
relevance comparisons. Later providers still share the total wall-clock budget;
source failures and truncation must remain visible.

Missing dependency metadata stays unknown. PyPI absent/null/malformed declarations
are not an observed empty list. For npm, an absent `dependencies` field in an
actually retrieved version document is contract-confirmed zero; a missing version
document, failed hydration or malformed dependency field is unknown. Scores do
not credit an unknown count as verified dependency-free.

Package identity remains separate from repository evidence. `repository_evidence`
records repository-level metadata merged into package leads. Repository-wide
license, descriptions, dates and dependencies do not overwrite unknown or
package-specific observations. `inspection` covers the whole repository, not a
proven package subtree; package-level readiness retains an explicit scope check.

Raw `license` evidence remains unchanged. `normalized_license` accepts supported
metadata identifiers. `license_kind=file` requires a complete canonical grant;
a title-only file is not treated as a metadata license identifier. Inspection
retains the raw file and records a superseded repository metadata license in
`repository_evidence.prior_metadata_license` when the observations differ.
The normalizer accepts supported identifiers and exact canonical MIT grant text
with whitespace and exact title variations. **Free-form copyright notices are
recognized, not automatically approved**: `license_body_match=MIT` records a
complete body, but `normalized_license=null` and `license_review_required=true`
prevent reuse authorization. Arbitrary holder names and hidden conditions cannot
be distinguished reliably by a regex; there is no holder allowlist or vocabulary
denylist. This deliberately requires review for ordinary copyright-bearing MIT
files too. Modified/truncated grants and unknown identifiers remain blocked from
automatic reuse. This is a conservative reuse filter, not legal
advice or a complete SPDX expression parser.

## Scoring contract and ordering

The existing raw `/100` component sum remains available as `score.total`:

| Component | Maximum |
|---|---:|
| Core feature match / relevance | 25 |
| Maintenance/activity | 15 |
| Dependency weight | 10 |
| Security/license/OSV posture | 15 |
| Test quality and CI | 10 |
| Portability | 10 |
| Reuse readiness/adaptation | 10 |
| Adoption/issue health | 5 |

`score.decision_score = max(0, total - unknown_cost)` discounts missing evidence.
Ranking first gates on feature relevance (at least 8/25), then usable evidence,
ready/provisional status and decision score. Within-source rank is a stable,
bounded tie-breaker. A popular unrelated project cannot beat a relevant reuse
lead merely by accumulating maintenance and adoption points.

Candidate disposition thresholds retain the raw component contract. Run-level
selection additionally requires static inspection and successful source
collection. `recommendation_status`, `required_checks`, `hard_blockers`, coverage
and per-component evidence must be read alongside the score.

## Repository inspection and complete receipts

```text
discovery/
├── discovery.md       # bounded table plus complete candidate/inspection evidence
├── discovery.json     # full reconstruction of the bounded evaluation
├── candidates/        # one JSON file per evaluated candidate, not only display rows
└── worktrees/         # bounded inspection clones when needed
```

- `candidates` remains the display shortlist, bounded by `--limit`.
- `evaluated_candidates` contains every deduplicated, scored candidate.
- `inspection_decisions` records allocation reasons and results for attempted
  inspections. An inspected candidate falling outside the table does not vanish.
- The supported selected candidate is pinned into the display shortlist.
- Changing `--limit` cannot change the build/reuse decision.
- Markdown escapes untrusted candidate text and terminal/bidirectional controls;
  JSON preserves raw evidence using JSON encoding.

The version markers change from `brief2ship-discovery-v1` and `brief2ship-score-v1`
to `brief2ship-discovery-v2` and `brief2ship-score-v2`.
The sandbox policy remains `brief2ship-bwrap-v2`. Consumers should reject unknown
schemas rather than inferring success from a nonempty `candidates` array.

## Regression benchmark and release gates

```bash
python scripts/benchmark-discovery.py --output quality-report.json
python scripts/validate-release.py
```

The benchmark uses committed **fictional, agent-authored synthetic fixtures**:
short and constraint-rich briefs, non-obvious names, popular unrelated projects,
blocked lexical matches, uninspected leads and failed providers. It measures
top-one/top-three relevance, false clean-build outcomes, blocked winners and
ranking latency. It performs no network requests or candidate execution.
It is a regression gate, **not measured real-world recall or a human-reviewed
accuracy benchmark**. Provider-query behavior and evidence failures have separate
fixture-backed unit and integration tests.

CI additionally runs pinned Ruff/Pyright checks, benchmark validation, installed
wheel round-trip smoke and full release validation from the extracted sdist.
The Linux/Windows Python matrix remains 3.11, 3.12 and 3.13. A local pass does not
claim GitHub Actions passed before this branch is pushed.

## Sandboxed tests

Tests remain opt-in using **both** `--test-top N` and `--allow-untrusted-tests`.
They require the supported Linux Bubblewrap sandbox, no network, cleared
environment, read-only candidate/work/temp/home filesystems and bounded
CPU/process/memory/output/wall time. Missing controls block execution; there is
no unsafe fallback. Static inspection and passing metadata gates never imply
candidate tests ran. Native Windows onboarding does not claim Bubblewrap support.

## Sources and candidate dispositions

- **Local workspaces:** repeatable `--local PATH` roots, bounded read-only breadth-first traversal,
  no symlinked Git metadata, and in-place static inspection.
- **GitHub:** public repositories with license/activity, stars, forks, watchers,
  contributor and issue evidence where available. **Private results are filtered**
  even when an optional `GH_TOKEN` or `GITHUB_TOKEN` is present.
- **PyPI:** bounded name-index discovery and project JSON, not full-text semantic package search.
- **npm:** package search and version-specific detail hydration.
- **crates.io:** relevant Rust crate metadata and dependency evidence.
- **Hugging Face:** model, dataset and Space metadata; gated/disabled artifacts remain blocked.

Candidate dispositions remain `use-as-library`, `fork`, `selective-reuse`, `reject`
and `build-clean`. A candidate-level recommendation is not itself a run-level
decision. Read `recommendation_status`, evidence coverage and required checks;
the overall run can remain inconclusive even with a nonempty shortlist.
