# Code and Solution Discovery

Brief2Ship v0.6 is the single repo-search contract. It searches scoped local workspaces plus public code/package ecosystems before greenfield implementation, normalizes candidates, checks evidence, optionally inspects a bounded set, reranks, and produces JSON/Markdown receipts.

## Quick start

```bash
brief2ship discover "local web scraper with robots support" \
  --local /path/to/scoped/workspace \
  --sources local,github,pypi,npm,crates,huggingface \
  --per-source 10 \
  --limit 10 \
  --total-timeout 180 \
  --inspect-top 3 \
  --output discovery/
```

The output directory must be new or empty. Results include:

```text
discovery/
├── discovery.json
├── discovery.md
├── candidates/
│   ├── 01-....json
│   └── ...
└── worktrees/       # bounded public clones only; local candidates stay in place
```

## Sources

### Local workspaces

Use repeatable `--local PATH` arguments. Supplying one automatically enables the `local` source; use `--sources local` for a fully offline local-only pass.

Local discovery is read-only and bounded to five roots, 10,000 visited directories, 10,000 entries and 2,000 retained filenames per directory, depth 16, 500 candidate projects, and the shared `--total-timeout`. Roots are traversed round-robin and breadth-first so a broad root or deep subtree cannot starve another root's shallow projects. Hidden/VCS metadata, dependency/vendor trees, build outputs, caches, and symlinked directories are skipped. Project identity comes from real manifests or a Git checkout; README text alone does not turn every nested folder into a project. Credential-bearing remotes are rejected, remote query/fragment data is stripped, and symlinked `.git` metadata is never followed. Files are opened no-follow and read through a bounded descriptor. Receipts retain local paths, so review them before public sharing.

`--inspect-top` statically inspects selected local projects in place. It never executes them unless the separate explicit sandbox-test gate is enabled.

### GitHub

Uses GitHub's REST repository-search API and repository/community-profile metadata. If a long-form target sentence returns zero repositories, Brief2Ship performs one deterministic, receipt-visible fallback using up to three non-generic terms; it never launches an unbounded query fan-out. Authentication is optional:

```bash
export GH_TOKEN=...
brief2ship discover "..." --sources github --output discovery/
```

`GITHUB_TOKEN` is also accepted. Tokens are sent only to `api.github.com`, are never rendered, and only improve rate limits. Discovery API redirects are rejected so bearer headers cannot cross hosts. Private results are filtered even when an authenticated token can see them. Unauthenticated search remains supported but has a low rate limit.

### PyPI

PyPI's HTML search is currently protected by a JavaScript client challenge. Brief2Ship does not bypass it. Instead, it downloads the official `/simple/` package-name index, applies deterministic local package-name token matching, caches names for seven days, then fetches official package JSON for the best matches. Because the Simple index contains names rather than descriptions, PyPI discovery can miss packages whose relevance appears only in metadata text.

The initial Simple index is approximately 42 MB and has a hard 50 MB response cap. Use `--refresh-cache` to replace the cached name list.

### npm

Uses the public npm registry search endpoint and package documents. It records version, repository, license, update date, relevance, declared runtime dependency count, and separate test/development signals.

### crates.io

Uses the public crate search and exact-version dependency endpoints with a descriptive Brief2Ship User-Agent and a one-request-per-second host throttle. It records downloads, activity, license, repository, version, and dependency count.

### Hugging Face

Searches public models, datasets, and Spaces. It records artifact kind, tags, library/pipeline metadata, license, downloads, likes, and last modification time. Hugging Face artifacts without canonical GitHub repositories can be scored but are not cloned by the GitHub inspector.

### OSV

For exact PyPI, npm, and crates.io package versions, Brief2Ship queries the free OSV API. Finding IDs are preserved. A failed or unsupported OSV query remains `unknown`; it is never silently treated as clean.

## Scoring contract

Scores are deterministic for the same evidence and clock:

| Dimension | Maximum | Main evidence |
|---|---:|---|
| Feature match | 25 | query-token coverage in name, description, topics, and inspected manifests |
| Maintenance/activity | 15 | last update/publish age; archived projects score zero |
| Dependency weight | 10 | declared dependency count; lower is easier to audit/reuse |
| Security posture | 15 | OSV result, declared license, security policy, archived state |
| Test quality | 10 | test files, CI, detected test command, sandbox result |
| Portability | 10 | ecosystem/language and explicit cross-platform/restriction signals |
| Reuse readiness | 10 | repository, description, license, docs, examples, manifests, source footprint |
| Adoption/health | 5 | stars/downloads plus forks, real watchers, contributor depth, and true issue-only ratio penalty after inspection |

Unknown data receives an explicit partial-neutral component value, plus separate weighted evidence coverage and unknown-cost fields. It never becomes silent positive evidence. Every component contains a human-readable evidence list in JSON and Markdown. JSON records `brief2ship-discovery-v1`, `brief2ship-score-v1`, the candidate's package version or inspected commit identity, recommendation status, hard blockers, and required checks.

Popularity cannot outweigh a missing license, archived status, failed sandbox test, poor feature match, or OSV evidence. OSV findings are conservatively blocking until severity and remediation are reviewed. Automatic reuse uses a conservative permissive-license allowlist; reciprocal, custom, or ambiguous licenses are blocked pending explicit compatibility review.

## Recommendation contract

Each candidate receives one disposition:

- `use-as-library` — package candidate clears score/feature/security thresholds
- `fork` — GitHub repository has strong direct fit, evidence, and reusable licensing
- `selective-reuse` — licensed candidate has useful modules but needs meaningful adaptation
- `reject` — candidate is blocked by license, archive, OSV, or sandbox-test evidence
- `build-clean` — candidate does not clear the reuse threshold

Each disposition also carries `ready`, `provisional`, `blocked`, or `not-selected` status. The run-level result chooses the highest-ranked candidate that clears reuse gates. If none clears them, it says `build-clean` and records the top score and disposition.

## Repository inspection

`--inspect-top N` is bounded to five candidates. A local candidate is statically inspected in place under the same file/read/size caps. For each public GitHub candidate Brief2Ship:

1. accepts only a canonical public HTTPS GitHub repository URL;
2. fetches current repository, contributor, real-watcher, homepage/demo, true issue-only count, and community-profile security evidence;
3. blocks archived repositories;
4. blocks repositories whose reported size is unknown or above 250,000 KB;
5. shallow-clones one branch with no tags, no submodules, hooks disabled, and a 1 MB blob filter;
6. ignores symlinks and generated/vendor trees;
7. caps static traversal at 20,000 files and individual evidence reads at 2 MB;
8. checks package/build manifests, dependency declarations, license text, test files, CI workflows, docs, examples, languages, source footprint, and commit hash;
9. reruns deterministic scoring with the new evidence.

Inspection does not execute repository code.

## Sandboxed tests

Untrusted code execution is off by default. It needs all of:

```bash
brief2ship discover "..." \
  --inspect-top 3 \
  --test-top 1 \
  --allow-untrusted-tests \
  --output discovery/
```

The current execution sandbox requires Linux, Bubblewrap, `prlimit`, and `timeout`. It:

- disables network access and unshares network, PID, IPC, UTS, cgroup, and user namespaces;
- clears inherited environment variables and secrets;
- does not mount the host home or Windows drives;
- mounts only system runtime directories read-only;
- mounts the disposable candidate copy, empty `/tmp`, and empty `/home` read-only, then remounts the sandbox root read-only;
- caps additional processes, per-process address space (512 MiB), CPU time, per-file output size, and wall time;
- uses offline package-manager settings;
- captures bounded output tails and exit status.

No dependencies are downloaded or installed during a test. The filesystem is intentionally read-only, so tests that require build artifacts, caches, or temporary files fail conservatively. Tests may also fail because a dependency is absent; the receipt distinguishes failure from evidence absence. If the sandbox is unavailable, testing is `blocked`. Brief2Ship never falls back to unsandboxed execution.

## Limits and caveats

- Public APIs can rate-limit, change fields, or temporarily fail. Other sources continue and every failure is recorded. Calls are capped by a 30-second per-request maximum, a 20-result per-source maximum, and one shared `--total-timeout` network budget (180 seconds by default, 600 maximum).
- Local search is bounded and read-only but can expose absolute local paths in its receipt; do not publish those receipts without review.
- GitHub search without a token is limited to its public unauthenticated quota.
- PyPI discovery initially downloads a large official name index because no challenge-free search API exists.
- Dependency counts are declared direct runtime evidence; optional extras and detected development-only dependencies are excluded where provider metadata distinguishes them. Counts are not complete transitive dependency graphs.
- OSV reports known database entries, not proof that a package is vulnerability-free.
- Static test/CI/docs signals do not prove quality; sandbox pass/fail is stronger but still bounded evidence.
- License identifiers and detected license text require human review before commercial reuse.
- Private results are filtered. Deprecated npm packages, yanked crates, gated artifacts, and disabled artifacts remain blocked evidence and cannot receive an automatic reuse recommendation.
- Hugging Face model/dataset quality cannot be inferred from downloads alone.
- This is code-solution triage, not a substitute for final architecture, legal, security, or performance review.

## Free and bounded promise

The core uses Python's standard library and public endpoints. No paid API is required. No browser automation, client-challenge bypass, CAPTCHA solving, proxy rotation, fingerprint evasion, credential harvesting, or authenticated-session scraping is used.
