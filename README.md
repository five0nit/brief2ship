# Brief2Ship

**Stop AI coding agents from rebuilding what already exists.**

[![CI](https://github.com/five0nit/brief2ship/actions/workflows/ci.yml/badge.svg)](https://github.com/five0nit/brief2ship/actions/workflows/ci.yml)
[![Python 3.11–3.13](https://img.shields.io/badge/python-3.11%E2%80%933.13-3776AB)](https://www.python.org/)
[![Agent Skill](https://img.shields.io/badge/Agent%20Skill-open%20standard-6CFFB3)](https://agentskills.io/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![GitHub stars](https://img.shields.io/github/stars/five0nit/brief2ship?style=social)](https://github.com/five0nit/brief2ship/stargazers)

Brief2Ship is a dependency-free Python CLI and portable Agent Skill for **repo-first discovery**. It searches local code plus GitHub, PyPI, npm, crates.io, and Hugging Face; inspects and scores real candidates; recommends reuse or a clean build; and finishes work with evidence instead of vibes.

![Terminal demo showing Brief2Ship selecting the local repository for reuse after evidence scoring](https://raw.githubusercontent.com/five0nit/brief2ship/v0.6.2/docs/assets/brief2ship-demo.gif)

*Historical v0.6.2 dogfood receipt (not a v0.7.0 result): `local/brief2ship`, 70.50/100, inspected, `selective-reuse`. [Read the source transcript](https://github.com/five0nit/brief2ship/blob/v0.6.2/docs/assets/demo-transcript.txt) or [see more decision cases](https://github.com/five0nit/brief2ship/blob/v0.6.2/docs/case-studies.md).*

## v0.7.0 — reliable reuse decisions

This release adds reliable reuse decisions: explicit `inconclusive` outcomes,
intent-preserving queries, complete evidence receipts, and `--summary` JSON output.
Discovery receipt and scoring contracts are now v2. Read the
[migration and decision guide](docs/code-discovery.md) before updating automation;
exit `5` means insufficient evidence, not permission to build from scratch.
For native Windows setup, see [PowerShell onboarding](docs/windows-powershell.md).

Install **v0.7.0** using the tagged commands below. The demo above is explicitly
pinned to v0.6.2 historical evidence; its result is not a v0.7.0 claim.
PyPI publication remains separate from the GitHub release.

## 30-second quickstart

Run the tagged release without a permanent install:

```bash
uvx --from git+https://github.com/five0nit/brief2ship.git@v0.7.0 \
  brief2ship discover "local robots-aware web scraper" \
  --sources github,pypi,npm,crates,huggingface \
  --limit 5 --inspect-top 2 \
  --output discovery/
```

Add a bounded local workspace to the same comparison:

```bash
uvx --from git+https://github.com/five0nit/brief2ship.git@v0.7.0 \
  brief2ship discover "local robots-aware web scraper" \
  --local /path/to/scoped/workspace \
  --sources local,github,pypi,npm,crates,huggingface \
  --per-source 10 --limit 10 --inspect-top 3 \
  --total-timeout 180 \
  --output discovery/
```

Brief2Ship writes both human-readable and machine-readable receipts:

```text
discovery/
├── discovery.md
├── discovery.json
└── worktrees/       # bounded inspection clones when required
```

Conclusive discovery records one explicit disposition (inconclusive runs record
`inconclusive` when evidence cannot support a decision):

- `use-as-library`
- `fork`
- `selective-reuse`
- `reject`
- `build-clean`

Repository code is **never executed during normal discovery**. Explicit candidate tests require both `--test-top` and `--allow-untrusted-tests`; they run only in the supported Linux Bubblewrap sandbox with **no network** access, a cleared environment, read-only filesystems, and resource limits.

## Why Brief2Ship?

Most coding agents start generating code as soon as they understand the request. Brief2Ship inserts one high-value decision first:

> **Does a suitable implementation, package, template, tool, dataset, or local project already exist?**

| Approach | Primary job | What Brief2Ship adds |
|---|---|---|
| AI coding agent | Generate or modify code | Mandatory pre-build search, evidence scoring, and a reuse decision |
| Spec-driven toolkit | Define what should be built | Selection of the best existing base before implementation |
| GitHub/code search | Return search results | Registry + local search, bounded inspection, deterministic scoring, and hard blockers |
| Starter or boilerplate | Provide one starting point | Comparison against alternatives instead of defaulting to the first template |
| Generic scraper | Fetch pages | Public-target, robots, redirect, DNS, size, and provenance controls |

Brief2Ship is a **workflow standard**, not a giant framework. It preserves operator judgment and makes unknown evidence visible rather than pretending every candidate is safe or suitable.

## What gets scored

Candidates receive deterministic `/100` evidence-backed scores:

| Component | Weight |
|---|---:|
| Feature and constraint match | 25 |
| Maintenance and activity | 15 |
| Dependency weight | 10 |
| Security posture and OSV findings | 15 |
| Test quality and CI | 10 |
| Portability | 10 |
| Reuse readiness and adaptation cost | 10 |
| Adoption, contributors, forks, watchers, and issue health | 5 |

Brief2Ship inspects manifests, dependency declarations, licenses, tests, CI, docs, examples, source footprint, release activity, contributors, watchers, forks, issue health, and homepage evidence. Missing evidence stays `unknown`; popularity never overrides fit, licensing, security, or maintainability.

## Install the CLI

### Versioned GitHub release

```bash
uv tool install git+https://github.com/five0nit/brief2ship.git@v0.7.0
brief2ship doctor
```

### PyPI — pending first trusted publication

The release workflow is ready for keyless PyPI Trusted Publishing. After the maintainer completes PyPI's one-time pending-publisher setup and the tagged workflow is verified, these shorter commands become available:

```bash
uv tool install brief2ship
brief2ship doctor
```

One-off execution:

```bash
uvx brief2ship --version
```

With optional local Trafilatura extraction:

```bash
uv tool install --with 'trafilatura>=2.1,<3' brief2ship
```

### Local development

```bash
git clone https://github.com/five0nit/brief2ship.git
cd brief2ship
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
.venv/bin/brief2ship doctor
```

On Windows PowerShell, use `.venv\Scripts\python.exe` and `.venv\Scripts\brief2ship.exe`.

## Install the Agent Skill

Brief2Ship follows the open [Agent Skills specification](https://agentskills.io/) and can be discovered from its `skills/brief2ship/SKILL.md` directory.

### GitHub CLI

GitHub CLI 2.90 or newer can install the tagged skill for supported agent hosts:

```bash
gh skill install five0nit/brief2ship brief2ship@v0.7.0
```

Example host-specific installation:

```bash
gh skill install five0nit/brief2ship brief2ship@v0.7.0 \
  --agent claude-code --scope user
```

### skills.sh-compatible agents

```bash
npx skills add five0nit/brief2ship --skill brief2ship
```

### Claude Code plugin

The repository also carries a native Claude Code plugin manifest:

```bash
claude plugin marketplace add five0nit/brief2ship
claude plugin install brief2ship@brief2ship
```

### Hermes Agent

Default profile:

```bash
hermes skills install \
  https://raw.githubusercontent.com/five0nit/brief2ship/v0.7.0/skills/brief2ship/SKILL.md \
  --category software-development \
  --yes
```

Named profile:

```bash
hermes profile create qa --no-alias --no-skills
hermes --profile qa skills install \
  https://raw.githubusercontent.com/five0nit/brief2ship/v0.7.0/skills/brief2ship/SKILL.md \
  --category software-development \
  --yes
hermes --profile qa skills list
```

Tagged skill URLs are immutable. Upgrade by installing the next tag explicitly with `--force --yes`.

## One repo-search skill

Brief2Ship keeps repository, package, template, dataset, tool, and local-workspace discovery in one place. Base selection, maintainability checks, implementation gates, and proof receipts do not drift across overlapping skills.

The workflow stays simple outside and strict inside:

1. **Brief** — lock the target, user, inputs, outputs, and constraints.
2. **Search** — inspect local workspaces and relevant public ecosystems.
3. **Score** — compare fit, health, license, security, tests, and reuse cost.
4. **Decide** — record one reuse/build disposition before implementation.
5. **Ship** — verify the artifact and retain proof.

## Internal delivery gates

### Tier 1 — Repo-first

Search before greenfield work. Use the built-in `brief2ship discover` command for local and public candidates.

### Tier 2 — Maintainability

Reject vague naming, hidden logic, duplicated business rules, unjustified abstraction, weak observability, dependency bloat, retry-unsafe operations, test theatre, and code understandable only from chat history.

### Tier 3 — Finish

Do not ship generic AI-slop UI or prose. Preserve hierarchy, evidence, accessibility, legibility, and restrained motion. For deterministic rendered video, motion graphics, animated decks, or document/site-to-video work, [`heygen-com/hyperframes`](https://github.com/heygen-com/hyperframes) is a conditional reference—not a general UI component base.

## The 4 default lanes

1. **App**
2. **Dashboard / Internal tool**
3. **Landing page**
4. **Report / Document**

Free public-web collection is source acquisition inside a lane, especially Report / Document. It is not a fifth lane.

See [docs/lanes.md](docs/lanes.md), [docs/report-document-lane.md](docs/report-document-lane.md), and [docs/examples.md](docs/examples.md).

## Safe public research

Brief2Ship also provides local, zero-paid-API source collection:

```bash
brief2ship scrape https://example.com/article --format markdown --output article.md
brief2ship crawl https://example.com/docs --output research-pack --max-pages 5 --max-depth 1
```

Core rules include:

- robots.txt required and fail-closed when it cannot be checked safely;
- public HTTP/HTTPS targets only by default;
- private, loopback, link-local, reserved, and multicast destinations blocked;
- DNS answers revalidated and pinned immediately before connection;
- environment HTTP(S) proxies ignored by the default transport;
- every redirect revalidated and page redirects restricted to same-origin;
- sequential crawling with hard page, depth, byte, redirect, and wall-clock limits;
- no cookies, login automation, CAPTCHA bypass, fingerprint evasion, proxy rotation, or personal-data harvesting;
- JSON/Markdown receipts with final URL, fetch time, SHA-256, robots decision, extractor, bytes, warnings, and failures.

See [docs/free-scraping.md](docs/free-scraping.md) and [docs/code-discovery.md](docs/code-discovery.md).

## Proof and trust

The v0.7.0 implementation passed local verification:

- 191 tests on Python 3.11, 3.12, and 3.13;
- native Windows validation, with four platform-specific skips;
- 24/24 synthetic decision-regression cases (not real-world accuracy claims);
- Ruff critical selectors and Pyright with 0 errors and 0 warnings;
- clean installed-wheel and extracted-sdist checks;
- independent review and a live five-source discovery probe.

GitHub Actions runs the Linux/Windows matrix and optional Trafilatura adapter on
pull requests and `main`; inspect the CI badge for the current hosted result.
Historical pre-publication evidence is retained at `docs/releases/v0.7.0-local-verification.md`.
Release receipts remain outside built packages so their artifact hashes cannot become self-referential.
Earlier evidence remains at `docs/releases/v0.6.2-discoverability-receipt.md` and
`docs/releases/v0.6.1-single-search-skill-receipt.md`.

## Repository map

- `src/brief2ship/` — dependency-free CLI implementation
- `skills/brief2ship/SKILL.md` — portable repo-first Agent Skill
- `docs/case-studies.md` — real decision examples
- `docs/code-discovery.md` — providers, scoring, inspection, and sandboxing
- `docs/free-scraping.md` — network safety and receipt contract
- `docs/examples.md` — prompts and execution patterns
- `templates/` — kickoff, report, scrape, and build receipt templates
- `tests/` — unit, integration, security, and release-contract tests
- `scripts/verify-release-assets.py` — exact wheel/sdist/checksum gate used before PyPI publication
- `ROADMAP.md` — bounded public roadmap

## Community

Questions and adoption stories belong in [Discussions](https://github.com/five0nit/brief2ship/discussions). Reproducible defects and scoped improvements belong in [Issues](https://github.com/five0nit/brief2ship/issues).

Read [CONTRIBUTING.md](CONTRIBUTING.md), [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md), [SECURITY.md](SECURITY.md), and [ROADMAP.md](ROADMAP.md) before contributing.

If Brief2Ship stops your agent reinventing one dependency, **[star the repository](https://github.com/five0nit/brief2ship)** so another builder can find it.

## License

MIT for Brief2Ship. Upstream projects retain their own licenses.
