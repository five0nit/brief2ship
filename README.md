# Brief2Ship

**One brief. Better build. Proof included.**

Brief2Ship is a lean operating standard and local CLI for AI-assisted product work. It searches local workspaces, repositories, packages, tools, templates, and datasets before greenfield work, scores reuse evidence, collects public-web sources, and turns a strong brief into a shipped, verified artifact.

## What it is

Brief2Ship is a **workflow standard**, not a giant framework.

It helps an operator or agent:

1. **Get a strong one-shot prompt**
2. **Choose a base before building greenfield**
3. **Reject brittle unreadable agent code**
4. **Search, inspect, and score existing local and public code**
5. **Collect public evidence with safe free scraping when needed**
6. **Format reports and documents for decision-ready reading**
7. **Turn the work into a verified artifact with receipts**

The public repository is the canonical source. Installed skills and CLI environments are local projections and should be reproducible from a tagged release.

### One repo-search skill

Brief2Ship is the sole skill for repository, package, template, dataset, and local-workspace discovery. Base-selection policy, maintainability/entropy checks, implementation gates, and proof receipts live here rather than in a second overlapping search skill.

## User experience

1. One-shot prompt
2. Up to 5 follow-up questions only when needed
3. Execute
4. Return proof

The user should not have to learn the internals.

## Internal workflow

The operating model stays simple: one strong brief, three internal tiers, and a final proof gate.

### Tier 1 — Repo-first

Search for the best existing repository, starter, tool, or template before building.

Use the built-in `brief2ship discover` command for both local and public candidates.

### Tier 2 — Maintainability gate

Use [`droogans/unmaintainable-code`](https://github.com/droogans/unmaintainable-code) in reverse.

Reject vague naming, hidden logic, duplicated business logic, unjustified abstraction, weak observability, dependency bloat, and chat-context-only code.

### Tier 3 — Design / UI / document finish

Do not ship generic AI-slop UI or prose. Preserve hierarchy, evidence, accessibility, legibility, and restrained motion.

Useful references:

- [`shadcn-ui/ui`](https://github.com/shadcn-ui/ui)
- [`tailwindlabs/headlessui`](https://github.com/tailwindlabs/headlessui)
- [`motiondivision/motion`](https://github.com/motiondivision/motion)
- [`darkroomengineering/lenis`](https://github.com/darkroomengineering/lenis) only when justified
- [`magicuidesign/magicui`](https://github.com/magicuidesign/magicui) selectively

## The 4 default lanes

Brief2Ship ships with four default lanes:

1. **App**
2. **Dashboard / Internal tool**
3. **Landing page**
4. **Report / Document**

Free scraping is a source-acquisition capability inside these lanes, especially Report / Document. It is not a fifth lane.

See [docs/lanes.md](docs/lanes.md), [docs/report-document-lane.md](docs/report-document-lane.md), and [docs/free-scraping.md](docs/free-scraping.md).

## Code and solution discovery

Brief2Ship v0.6 searches scoped local workspaces plus five free public ecosystems before new code is written:

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

Candidates receive deterministic evidence-backed scores for:

- feature match — `/25`
- maintenance/activity — `/15`
- dependency weight — `/10`
- security posture and OSV findings — `/15`
- test quality — `/10`
- portability — `/10`
- reuse readiness/difficulty — `/10`
- adoption/contributor/issue health — `/5`

The result recommends `fork`, `use-as-library`, `selective-reuse`, `reject`, or `build-clean`. Canonical GitHub URLs are deduplicated across registries and matching local clones, and any merged candidate retaining a validated local path is inspected locally regardless of primary package source. A zero-result long-form GitHub query gets one deterministic three-term fallback, recorded in the receipt. `--inspect-top` allocates scarce inspection slots by direct feature fit, statically inspects local projects in place, hydrates public repository metadata including contributors, real watchers, true issue-only counts, and homepage evidence, performs bounded shallow clones when needed, and checks real manifests, dependencies, licenses, tests, CI, documentation, examples, languages, and source footprint before reranking.

Repository code is never executed by default. Explicit tests require `--test-top N --allow-untrusted-tests` and a Linux Bubblewrap sandbox. The sandbox clears the environment, runs with no network access, hides the host home, makes the entire filesystem read-only, and limits additional processes, CPU, per-process memory, output-file size, and wall time. Unsupported systems produce a blocked receipt—never an unsafe fallback.

See [docs/code-discovery.md](docs/code-discovery.md). Current Linux/Windows tests, local artifacts, clean installs, live provider smoke, and bounded real-candidate inspection are recorded in the source-checkout receipt at `docs/releases/v0.6.0-single-search-skill-receipt.md`. Release receipts remain outside built packages so their artifact hashes cannot become self-referential.

## Free scraping

Brief2Ship includes local, zero-paid-API source collection:

```bash
brief2ship scrape https://example.com/article --format markdown --output article.md
brief2ship crawl https://example.com/docs --output research-pack --max-pages 5 --max-depth 1
```

Built-in rules:

- HTTP/HTTPS public pages only
- robots.txt required and fail-closed when unavailable
- private, loopback, link-local, reserved, and multicast targets blocked by default
- each default-transport connection is pinned to DNS answers revalidated immediately before connect
- environment HTTP(S) proxies are ignored so they cannot bypass target validation
- every redirect revalidated
- page redirects restricted to the same origin and rechecked against robots rules
- same-origin sequential crawl only
- default 1-second minimum delay; robots crawl delay wins when larger
- 2 MB/page default response cap
- one total wall-clock timeout across connect, redirects, and body streaming
- 5-page/depth-1 crawl default; hard cap 20 pages/depth 3
- no cookies, login automation, CAPTCHA bypass, fingerprint evasion, or proxy rotation
- JSON/Markdown receipts include final URL, fetch time, SHA-256, extractor, robots status, and warnings
- untrusted page text is control-stripped and fenced as inert code in Markdown receipts

`--allow-private` exists only for explicit local or owner-authorized testing. It does not disable robots, timeouts, response limits, redirect limits, or crawl caps.

The core extractor has no runtime dependency. Optional [Trafilatura](https://github.com/adbar/trafilatura) improves static-page extraction locally; page content is never sent to a model or scraping service.

## Install the CLI

### Using `uv`

From a release tag:

```bash
uv tool install git+https://github.com/five0nit/brief2ship.git@v0.6.0
brief2ship doctor
```

With optional Trafilatura extraction:

```bash
uv tool install --with 'trafilatura>=2.1,<3' git+https://github.com/five0nit/brief2ship.git@v0.6.0
brief2ship doctor
```

### Local development install

```bash
git clone https://github.com/five0nit/brief2ship.git
cd brief2ship
python3 -m venv .venv
.venv/bin/python -m pip install -e .
.venv/bin/brief2ship doctor
.venv/bin/python -m brief2ship --version
```

On Windows PowerShell, use `.venv\Scripts\python.exe` and `.venv\Scripts\brief2ship.exe`.

## Install the Hermes skill

Default profile:

```bash
hermes skills install \
  https://raw.githubusercontent.com/five0nit/brief2ship/v0.6.0/skills/brief2ship/SKILL.md \
  --category software-development \
  --yes
```

Named profile:

```bash
hermes profile create qa --no-alias --no-skills
hermes --profile qa skills install \
  https://raw.githubusercontent.com/five0nit/brief2ship/v0.6.0/skills/brief2ship/SKILL.md \
  --category software-development \
  --yes
hermes --profile qa skills list
```

Load with `/skill brief2ship` in chat or `hermes --skills brief2ship` at startup.

Tagged skill URLs are immutable. To upgrade, install the next tag URL explicitly with `--force --yes`. `hermes skills uninstall brief2ship` removes the selected profile's copy after confirmation.

## Repository contents

- `src/brief2ship/` — zero-dependency local/public discovery, scraping, and crawl CLI
- `skills/brief2ship/SKILL.md` — the sole Hermes repo-search/build-delivery skill
- `skills/brief2ship/references/` — absorbed curated, entropy, canonical-name, avatar, and historical-data guidance
- `docs/how-it-works.md` — workflow breakdown
- `docs/lanes.md` — the 4 default lanes
- `docs/free-scraping.md` — safety, commands, limits, and receipts
- `docs/code-discovery.md` — providers, scoring, inspection, sandboxing, and receipts
- `docs/examples.md` — prompts and execution patterns
- `templates/` — kickoff, report, scrape, and build receipt templates
- `tests/` — unit and local integration tests
- `scripts/validate-release.py` — release contract gate

## Lightweight receipts

Every build should end with:

- chosen base and why
- changed files
- commands/tests run
- verification/proof
- known compromises

Every scrape adds source URL, final URL, timestamp, raw response hash, robots decision, extractor, byte count, and warnings.

Every discovery run adds provider status, rate-limit evidence, normalized candidate identity, component scores, evidence coverage, unknown cost, hard blockers, repository inspection, OSV results, sandbox receipts, recommendation status, and limitations.

Use [templates/build-receipt-template.md](templates/build-receipt-template.md) and [templates/scrape-receipt-template.md](templates/scrape-receipt-template.md).

## Non-goals

Brief2Ship is not:

- a full app framework
- a replacement for product judgment
- a generic enterprise scoring platform
- a mandatory design system
- a rigid project-management workflow
- a browser-fingerprint or anti-bot evasion product
- an authenticated-session scraper
- an unbounded distributed crawler

The goal is better delivery and evidence without harming judgment, accuracy, websites, or users.

## Development

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
python3 scripts/validate-docs.py
python3 scripts/validate-release.py
python3 -m build
```

See [CONTRIBUTING.md](CONTRIBUTING.md).

## Contributors

Initial framework direction and product requirements: **Mike**  
Packaging, workflow codification, and repository implementation: **Hermes Agent**

Future contributions should keep Brief2Ship lean. If a feature makes the workflow harder to apply safely and consistently, it probably does not belong.

## License

MIT for Brief2Ship. Upstream referenced projects retain their own licenses.
