# Brief2Ship roadmap

Brief2Ship stays deliberately lean. Roadmap items must improve repo-first decisions, portable installation, evidence quality, or verified delivery without turning the project into a general-purpose agent framework.

## Now — v0.6.x distribution and adoption

- publish signed, tagged Python distributions to PyPI through GitHub Trusted Publishing;
- validate and publish `skills/brief2ship` through GitHub's Agent Skills workflow;
- test documented installation on GitHub Copilot, Claude Code, Codex, Cursor, Gemini CLI, and Hermes before claiming compatibility;
- improve first-run examples, error messages, and receipt readability;
- publish small, reproducible decision cases rather than unsupported savings claims.

## Next — v0.7 evidence quality

- normalize common package-license metadata without weakening hard blockers;
- improve multi-query recall while keeping provider limits deterministic;
- make inspection-budget allocation easier to explain from receipts;
- add fixture-backed examples for local/public deduplication and partial provider failure;
- expose concise summary output without removing the full Markdown/JSON receipt.

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
