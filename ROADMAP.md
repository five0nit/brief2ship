# Brief2Ship roadmap

Brief2Ship stays deliberately lean. Roadmap items must improve repo-first decisions, portable installation, evidence quality, or verified delivery without turning the project into a general-purpose agent framework.

## Now — v0.6.x distribution and adoption

- publish signed, tagged Python distributions to PyPI through GitHub Trusted Publishing;
- validate and publish `skills/brief2ship` through GitHub's Agent Skills workflow;
- test documented installation on GitHub Copilot, Claude Code, Codex, Cursor, Gemini CLI, and Hermes before claiming compatibility;
- improve first-run examples, error messages, and receipt readability;
- publish small, reproducible decision cases rather than unsupported savings claims.

## In the working tree — v0.7 evidence quality: reliable reuse decisions (unreleased)

- explicit inconclusive decisions for incomplete collection or insufficient evidence;
- display-only limits, complete evaluated/inspection receipts and selected identities;
- bounded core/constraint query planning and relevance/confidence-aware ranking;
- unknown dependency evidence, package/repository scoping and strict full-text MIT normalization;
- concise JSON summary alongside full v2 receipts;
- synthetic task-quality regressions plus automated lint/type/wheel/sdist gates.

The public v0.6.2 tag does not contain this work. Publication remains a separate approval.

## Next evidence-quality work

- human-reviewed real-world briefs and provider recall benchmarks, beyond synthetic regression fixtures;
- package-subtree identification for monorepos before claiming package-specific test readiness;
- additional canonical license formats with conservative, fixture-backed normalization;
- better source-budget fairness and explainable query recall without mandatory model calls.

## Later — only with demonstrated demand

- optional CI check for repository-owned Brief2Ship policy;
- portable adapters where an agent host cannot consume the open Agent Skills format directly;
- signed provenance for published release artifacts;
- additional registries only when a maintained public API and bounded threat model exist.

## Non-goals

- becoming a full coding agent or project-management platform;
- executing candidate repositories during ordinary discovery;
- paid-service requirements in the core flow;
- unbounded crawling, authenticated scraping, CAPTCHA bypass, or stealth automation;
- ranking by stars alone;
- adding integrations before their install and verification paths are tested.

## Contributing to the roadmap

Use [GitHub Discussions](https://github.com/five0nit/brief2ship/discussions) for problem statements and adoption stories. Open an issue only when the desired outcome and acceptance checks are bounded enough to implement.
