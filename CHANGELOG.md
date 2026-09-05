# Changelog

## 0.7.0 - 2026-09-05

- separate discovery health, decision status, and reuse disposition; provider failures, empty retrieval and missing inspections now yield `inconclusive` with CLI exit 5, never a false clean-build recommendation
- decide against the full evaluated set; make `--limit` presentation-only and preserve every evaluated candidate, inspection allocation and selected identity in v2 receipts
- add deterministic core/constraint query planning, bounded GitHub reciprocal-rank fusion, registry core queries and source ranks without model calls or new runtime dependencies
- gate ranking on relevance, use confidence-adjusted decision scores and prefer ready evidence; retain original constraints as unverified checks
- preserve unknown dependency metadata and package/repository evidence scope instead of silently awarding dependency-free credit
- recognize canonical full-text MIT bodies while preserving raw evidence; free-form copyright notices are review-required rather than granted authority through a regex
- add explicit `--summary` JSON output with decision state, source health, counts, score, blockers and receipt paths
- add a synthetic task-quality regression benchmark, pinned lint/type checks, clean installed-wheel smoke and extracted-sdist validation in CI
- document v2 migration and native PowerShell onboarding; update versioned installation routes to v0.7.0 while keeping historical demo evidence pinned

## 0.6.2 - 2026-09-05

- reposition Brief2Ship around its sharpest searchable job: stop AI coding agents rebuilding what already exists
- move a runnable tagged-release quickstart, real dogfood demo, scored result, comparison table, and proof strip above the detailed workflow documentation
- add a custom 1280×640 social preview, an animated terminal receipt, and three evidence-bounded decision cases
- add GitHub CLI Agent Skills, skills.sh, Claude Code plugin, versioned-tag, and pending trusted PyPI installation routes
- add GitHub Trusted Publishing workflow for PyPI with exact release-tag/version validation and no repository secret requirement
- add Code of Conduct, issue forms, pull-request template, roadmap, contribution links, and Discussions routes
- expand package metadata and release-contract checks for distribution, community, and marketing artifacts

## 0.6.1 - 2026-09-04

- restore HTTPS scraping on Python 3.12 and 3.13 by forwarding the portable `SSLContext` argument without the removed `HTTPSConnection(check_hostname=...)` keyword
- add Python 3.13 to package classifiers and the Linux/Windows CI matrix
- replace the empty-response timeout test's scheduler-sensitive real sleep with a deterministic monotonic-clock regression
- add `heygen-com/hyperframes` as a conditional Tier 3 rendered-motion, animated-deck, and document/site-to-video finish reference

## 0.6.0 - 2026-09-03

- make Brief2Ship the sole repository/package/local-workspace search skill and absorb the former base-selection, curated-discovery, entropy-gate, canonical-name fallback, avatar, and historical-data guidance
- add bounded read-only local workspace discovery through repeatable `--local PATH` and `--sources local`
- traverse local roots breadth-first so deep trees cannot starve sibling projects under scan caps
- reject credential-bearing remotes, strip remote query/fragment data, and never follow symlinked `.git` metadata
- make local scan caps bound directory entries, retained filenames, depth, descriptor reads, wall time, and each root fairly
- preserve local in-place inspection after local/GitHub/package deduplication regardless of the surviving primary source
- replace GitHub's combined issue/PR count with a true issue-only count before applying issue-health penalties
- statically inspect selected local projects in place without cloning or executing them
- hydrate inspected GitHub candidates with contributor count, real watchers, homepage/demo, and issue-health evidence
- extend adoption/health scoring with forks, watchers, contributors, and issue-ratio penalties
- surface local paths and contributor/watcher/issue evidence in discovery receipts

## 0.5.1 - 2026-09-03 (local candidate)

- correct the build backend floor to `setuptools>=77`, which is required by the declared SPDX license metadata
- pin scraping connections to revalidated DNS answers and ignore environment HTTP(S) proxies, closing the documented DNS-rebinding/proxy gap in the default transport
- prioritize direct feature fit when allocating bounded repository-inspection slots and honor `--inspect-top` independently of the final `--limit`
- make PyPI name-search ties deterministic in ascending lexical order
- retry zero-result long-form GitHub searches once with a receipt-visible three-term focus query
- standardize per-candidate and run-level clean-build dispositions on `build-clean`
- make license/security blockers return `reject` even when a candidate's total score is below the clean-build threshold
- make deduplication side-effect free and compare offset timestamps chronologically
- strip ALM/LRM/RLM in addition to embedding/isolate bidi controls from extracted text and human-readable receipts
- enforce fetch/discovery wall-clock deadlines across DNS validation and after blocking reads, including delayed empty responses
- make untrusted-test sandboxes fully read-only (including work, temp, and home), lower per-process memory to 512 MiB, and reduce the process allowance
- add the equivalent `python -m brief2ship` module entrypoint and verify it in release/CI gates
- reconfigure real CLI stdout/stderr to UTF-8 so Unicode receipts do not fail under an inherited ASCII locale
- return exit `4` for partial crawls while still writing the failure-bearing manifest
- make top-level/doctor help describe repo-first discovery as well as scraping
- require declared release receipts in Git checkouts while continuing to omit them from self-hashed source archives

## 0.5.0 - 2026-07-30

- added `brief2ship discover` across GitHub, PyPI, npm, crates.io, and Hugging Face
- added canonical repository deduplication and exact package-version OSV vulnerability checks
- added deterministic `/100` scoring for feature match, activity, dependency weight, security, tests, portability, reuse readiness, and adoption
- added evidence-backed `fork`, `use-as-library`, `selective-reuse`, `reject`, and `build-clean` decisions
- added bounded GitHub hydration, shallow clone, static manifest/license/test/CI/docs inspection, and score reranking
- added explicitly gated Bubblewrap test execution with no network, cleared environment, resource limits, and no unsafe fallback
- added deterministic JSON/Markdown comparison receipts with source failures, rate-limit evidence, assumptions, and limitations
- retained a dependency-free core and zero-paid-API operation; GitHub tokens only raise optional rate limits

## 0.4.0 - 2026-07-30

- added the zero-paid-API `brief2ship scrape` and `brief2ship crawl` CLI
- added public-network, redirect, robots.txt, timeout, size, content-type, same-origin, delay, page, and depth safety gates
- added deterministic JSON/Markdown/text output with fetch timestamps, raw-response SHA-256, extraction adapter, and warning receipts
- added exact robots product-token matching, percent-encoding normalization, total body-stream deadlines, and inert Markdown fencing for untrusted content
- added zero-dependency stdlib extraction plus optional Apache-2.0 Trafilatura extraction
- added package metadata and installed `brief2ship` console entrypoint
- added local integration tests, release-contract validation, and cross-platform CI
- replaced the author-specific skill installer with native Hermes installation documentation
- removed unsupported alias and OpenClaw packaging claims
- clarified repository source-of-truth and named the MIT copyright holder

## 0.3.0 - 2026-06-29

- added Report / Document as a fourth default lane
- added best-practice report flow for reader outcome, source-first intake, evidence gates, formatting QA, recommendations, and report receipts
- added report request and report receipt templates
- added docs validation script for lane/template coverage

## 0.2.0 - 2026-06-29

- created initial public-facing repo structure
- added README and full workflow breakdown
- added three default lanes: app, dashboard/internal tool, landing page
- added examples for each lane
- added skill packaging and install script
- added lightweight kickoff and receipt templates
- kept scope intentionally lean to avoid harming judgment or accuracy
