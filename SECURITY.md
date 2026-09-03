# Security Policy

## Supported versions

Security fixes are applied to the latest tagged release.

| Version | Supported |
|---|---|
| 0.6.x | Yes |
| Earlier versions | No |

## Reporting a vulnerability

Do not open a public issue containing credentials, exploit details, private URLs,
or personal data.

Report sensitive vulnerabilities through this repository's GitHub Security
Advisories page. Include:

- affected version or commit;
- minimal reproduction steps;
- expected and observed behavior;
- security impact;
- whether the issue affects discovery, repository inspection, sandboxing,
  URL validation, redirects, robots handling, or receipt redaction.

For a non-sensitive security hardening suggestion, open a normal GitHub issue.
Never include real tokens, cookies, private keys, or private repository URLs in a
report or test fixture.

## Security boundaries

Brief2Ship is designed to:

- reject private, loopback, link-local, reserved, and multicast network targets
  unless explicit owner-authorized local testing enables `--allow-private`;
- revalidate redirects and DNS answers;
- ignore environment HTTP(S) proxies in the default transport;
- respect robots.txt and fail closed when it cannot be checked safely;
- keep discovered repository code non-executable by default;
- run explicitly authorized candidate tests only inside the documented
  no-network, read-only Bubblewrap sandbox;
- keep credentials out of receipts, logs, and canonical repository URLs.

`--allow-private` relaxes only the destination-address restriction. It does not
disable robots rules, redirect validation, timeouts, response-size limits, crawl
bounds, or receipt generation.
