# Brief2Ship decision cases

These cases show the decision Brief2Ship is designed to improve. They are not performance benchmarks, invented savings claims, or guarantees that the highest-scoring candidate should always be reused.

## 1. Dogfooding found the canonical local project

**Need:** verify that local-workspace discovery could find and inspect Brief2Ship inside a larger workspace.

**Search:** `brief2ship repository search` with the local source enabled.

**Observed result:**

```text
candidate: local/brief2ship
score: 70.50/100
feature match: 11.00/25
inspection: inspected
disposition: selective-reuse
status: provisional
overall: selective-reuse
```

**Decision:** `selective-reuse` the existing canonical repository rather than create another implementation.

**What the receipt exposed:** an earlier depth-first scanner could let a broad directory starve sibling projects under the traversal cap. A deterministic regression reproduced the problem, traversal changed to breadth-first, and the successful dogfood run was repeated.

**Proof:** source-checkout receipt `docs/releases/v0.6.0-single-search-skill-receipt.md`, section “Dogfood proof.” Release receipts stay outside built packages to avoid self-referential artifact hashes.

## 2. A specialist avatar base beat a custom first attempt

**Need:** build a 3D rigged talking avatar with morph targets and visemes.

**Initial failure:** implementation began with a custom mouth-overlay/2D cutout before repository comparison.

**Candidate review:**

| Score | Candidate | Evidence-backed fit |
|---:|---|---|
| 88 | [`met4citizen/TalkingHead`](https://github.com/met4citizen/TalkingHead) | MIT; direct 3D talking-avatar and lip-sync fit |
| 75 | `lexziconAI/TalkingHead` | Related fork/copy with lower confidence |

**Decision:** use the specialist 3D base for a deterministic bundled-GLB proof before adapting a branded avatar.

**Boundary:** a flat puppet or arbitrary uploaded image is a different problem class. Reusing a high-scoring repository does not remove asset-format constraints.

**Proof:** [`skills/brief2ship/references/talking-avatar-case-study.md`](../skills/brief2ship/references/talking-avatar-case-study.md).

## 3. Search can correctly end in `build-clean`

**Need:** find a Python robots-aware scraper with strict public-target safety.

**Live bounded run:** local workspace, GitHub, PyPI, npm, crates.io, and Hugging Face were queried; 13 provider results were observed and the final shortlist contained four candidates.

| Score | Candidate | Source | Decision |
|---:|---|---|---|
| 62.50 | `ts-web-scraper` | npm | `build-clean` |
| 55.39 | `mcp-scraper` | npm | `build-clean` |
| 54.50 | `@the-convocation/twitter-scraper` | npm | `build-clean` |
| 51.77 | `web-scraper-python-library` | PyPI | `reject` |

**Decision:** `build-clean` because no candidate cleared the reuse gates. The top candidate was recent and light, but the observed evidence did not establish the required Python and network-safety fit.

**Why this matters:** repo-first does not mean “force reuse.” It means search, inspect, make unknowns visible, and justify greenfield work when adaptation would cost more or violate constraints.

**Receipt note:** this run was executed on 2026-09-04 UTC with Brief2Ship v0.6.1. Public metadata can change; the table is an observed decision receipt, not a current endorsement of any package.

## Reproduce the decision shape

```bash
brief2ship discover "TARGET AND CONSTRAINTS" \
  --local /path/to/scoped/workspace \
  --sources local,github,pypi,npm,crates,huggingface \
  --per-source 10 --limit 10 --inspect-top 3 \
  --total-timeout 180 \
  --output discovery/
```

Read `discovery.md` for the human decision and retain `discovery.json` for machine-readable evidence.
