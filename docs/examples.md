# Examples

These are intentionally small.
They exist to show how the framework should feel in practice.

## Example 1 — App lane

### Prompt
> Build me a lightweight hiring workspace for startup founders to review applicants, track interview stages, and leave team notes. It should feel closer to Linear and Notion than a generic AI dashboard. Constraints: web, polished but not overbuilt, mobile decent, auth required.

### Likely flow
- lane: App
- repo-first search for strong full-stack app / SaaS bases
- choose the best auth/data/dashboard base
- maintainability gate on routes, data access, naming, and state seams
- polish dashboard hierarchy and candidate flow UI
- verify core flow: sign in -> create role -> review candidate -> update stage

### Receipt shape
- chosen base: ...
- why: ...
- changed files: ...
- commands run: ...
- proof: ...

---

## Example 2 — Dashboard / internal tool lane

### Prompt
> Build me an internal support dashboard for managers to see ticket backlog, blocked items, agent load, and SLA risk. It should feel clean and operational, not flashy. Constraints: desktop-first web app, mock data first, room for Zendesk later.

### Likely flow
- lane: Dashboard / internal tool
- repo-first search for strong dashboard/admin bases
- pick clarity and maintainability over bells and whistles
- enforce readable data components and obvious state handling
- finish with strong table/filter/status patterns
- verify key flow: open dashboard -> filter backlog -> inspect blocked queue

---

## Example 3 — Landing page lane

### Prompt
> Build me a launch page for an AI inbox copilot for founders. It should feel premium, fast, and direct — closer to Stripe or Arc than a typical glossy AI site. Constraints: one main CTA, mobile strong, restrained animation.

### Likely flow
- lane: Landing page
- repo-first search for strong landing page / marketing bases
- keep codebase smaller and avoid over-abstracting sections
- focus Tier 3 on hierarchy, spacing, CTA emphasis, and purposeful motion
- verify mobile rendering, CTA visibility, and page performance sanity

## What these examples are proving

The toolkit is not trying to replace product thinking.
It is giving a repeatable build discipline that improves:
- base selection
- maintainability
- finish quality
- verification

---

## Example 4 — Report / Document lane

### Prompt
> Create an executive QA report for a founder deciding whether a new AI-built landing page is ready to share. Use the local test logs, screenshots, browser QA output, and known compromises. Tone: direct, decision-ready, non-technical. Format: Markdown with a source appendix.

### Likely flow
- lane: Report / Document
- source-first intake: collect logs, screenshots, commands, and open issues
- choose report skeleton before prose
- separate facts, assumptions, and recommendations
- format for skimming: summary, findings table, risks, next actions
- verify links/files and render Markdown tables cleanly

### Receipt shape
- report audience: founder
- decision supported: ready to share / hold / fix first
- sources used: logs, screenshots, QA output
- checks run: Markdown/table/link review
- known gaps: unverifiable claims or missing sources

---

## Example 5 — Free source collection inside Report / Document

This is not a fifth lane. It is a source-acquisition step inside the Report / Document lane.

### Prompt

> Compare the public documentation for two open-source extraction tools. Use only their public project pages, no paid APIs, no login, and no anti-bot bypass. Return a short recommendation with source hashes and known evidence gaps.

### Likely flow

- lane: Report / Document
- repo-first shortlist based on live maintenance, license, fit, and dependency weight
- run `brief2ship scrape` on each allowed public project page
- stop and record any robots, JavaScript, content-type, size, or network-policy failure
- compare only claims present in the saved source artifacts
- produce a decision-ready report plus per-source JSON/Markdown receipts

### Commands

```bash
brief2ship scrape https://example.com/project-a --format markdown --output sources/project-a.md
brief2ship scrape https://example.org/project-b --format markdown --output sources/project-b.md
```

### Receipt shape

- requested and final URLs
- robots.txt URL and allowed decision
- UTC fetch time
- raw-response SHA-256
- extraction adapter and warnings
- source artifact paths
- recommendation evidence and gaps

---

## Example 6 — Find reusable code before building

### Prompt

> Find the best maintained implementation for a local robots-aware web scraper. Search my scoped workspace plus public repositories and package registries, inspect the top three real candidates, score the evidence, and recommend library, fork, selective reuse, rejection, or clean build. Do not execute candidate code.

### Command

```bash
brief2ship discover "local robots-aware web scraper" \
  --local /path/to/scoped/workspace \
  --sources local,github,pypi,npm,crates,huggingface \
  --per-source 10 --limit 10 --inspect-top 3 \
  --output discovery/
```

### Receipt shape

- provider endpoints, status, returned count, warnings, and rate-limit evidence
- canonical repository/package identity and duplicate aliases
- feature, maintenance, dependency, security, tests, portability, reuse, and adoption scores
- exact license, version, activity date, dependency count, OSV finding IDs, and unknown evidence
- shallow-clone commit and inspected manifests/tests/CI/docs/examples
- recommendation: `fork`, `use-as-library`, `selective-reuse`, `reject`, or `build-clean`
- limitations and source failures

## What these examples prove

Brief2Ship does not replace product or research judgment. It gives repeatable discipline for base selection, maintainability, finish quality, source provenance, and verification.
