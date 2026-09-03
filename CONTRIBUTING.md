# Contributing

Thanks for contributing.

## Contribution standard

Brief2Ship should stay **lean, practical, safe, and judgment-preserving**.

Before adding anything, ask:

1. Does this improve build or evidence quality?
2. Does this preserve operator judgment and accuracy?
3. Can the behavior be verified with a bounded receipt?
4. Does this avoid unnecessary ceremony or dependencies?
5. For network behavior, does it reduce rather than expand abuse and SSRF risk?

If the answer is not clearly yes, do not add it.

## Good contributions

- clearer worked examples
- better receipt templates
- sharper lane guidance
- stronger maintainability checks
- practical install or usage improvements
- better upstream reference notes
- extraction quality improvements with deterministic fixtures
- stricter robots, redirect, size, timeout, or private-network tests
- deterministic provider fixtures, scoring evidence, deduplication, and inspection safety improvements

## Likely bad contributions

- giant config systems
- bloated scoring frameworks
- extra lanes without a distinct user outcome
- unnecessary automation layers
- fashionable but vague jargon
- rules that make the workflow harder to apply
- CAPTCHA bypass, stealth fingerprints, rotating proxies, session theft, or rate-limit evasion
- scraping features that require paid keys for the core flow
- unbounded/concurrent crawls without a new reviewed threat model
- executing discovered repository code without explicit consent and a no-network resource-limited sandbox
- letting popularity override feature fit, licensing, security, or maintenance evidence

## Development setup

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -v
.venv/bin/python scripts/validate-docs.py
.venv/bin/python scripts/validate-release.py
.venv/bin/python -m build
```

On Windows, replace `.venv/bin/` with `.venv\Scripts\`.

## Pull request checklist

- [ ] keeps the product simple externally
- [ ] does not reduce judgment, accuracy, privacy, or target-site safety
- [ ] keeps examples short and concrete
- [ ] does not force a specific stack unnecessarily
- [ ] adds/updates tests for behavior changes
- [ ] updates docs and receipts when behavior changes
- [ ] performs a clean wheel install and installed-console round trip
- [ ] runs `git diff --check`

Scraping changes must also prove:

- [ ] robots denial causes no page fetch
- [ ] private targets and redirect pivots are blocked by default
- [ ] response and crawl hard caps hold
- [ ] crawl expansion stays same-origin and sequential
- [ ] output retains source provenance and raw-response hashes
- [ ] no credential, cookie, CAPTCHA, fingerprint-evasion, or proxy-rotation path was added

Discovery changes must also prove:

- [ ] every provider has deterministic offline fixtures and partial-failure coverage
- [ ] tokens are optional, domain-scoped, and absent from receipts/logs
- [ ] score components preserve evidence and explicit unknowns
- [ ] repository URL canonicalization cannot clone local, SSH, or file targets
- [ ] clone count, repository size, file traversal, and read sizes remain bounded
- [ ] code execution remains off by default
- [ ] test execution blocks when Bubblewrap/no-network/resource limits are unavailable
- [ ] no candidate dependency installation occurs during sandbox tests

## Style

- use direct language
- prefer short examples over long theory
- avoid fake precision
- do not present suggestions as mandatory unless they truly are
- keep success stdout machine-readable; send failures to stderr
- use typed expected failures instead of raw tracebacks in the CLI

## Attribution

When adding major concepts, document whether they came from:

- original repository work
- user requirements
- upstream inspiration
- contributor refinement

Do not copy upstream implementation without license and provenance review.
