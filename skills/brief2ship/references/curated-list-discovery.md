# Curated-list discovery notes

Use this reference when repo-first results are too broad, noisy, or miss obvious canonical resources.

## Curated sources added from session learning

- `https://github.com/sindresorhus/awesome`
  - Best for broad ecosystem maps: languages, frameworks, app categories, libraries, tooling collections.
- `https://github.com/trimstray/the-book-of-secret-knowledge`
  - Best for practical CLI, ops, security, networking, shell, Linux, and troubleshooting tools.

## Why this helps

Raw GitHub search can over-rank unrelated repos that happen to contain query terms in a README or generated config. Curated lists tighten discovery by exposing known categories and accepted tools before the agent commits to a base.

## Guardrails

1. Treat list hits as discovery leads, not final choices.
2. Verify the upstream repo/source/release URL; list entries may point to docs, product pages, wikis, or abandoned projects.
3. Do not output `git clone <url>` for non-GitHub/non-VCS URLs. Inspect first and resolve a real source/package path.
4. Keep license and maintenance checks mandatory; curated inclusion does not imply shareability or health.
5. Penalize personal `.config`, `dotfiles`, or generated-config repos unless the task is explicitly about dotfiles/configuration.

## Regression example

For `GNU Bash shell features CLI Tools`, raw GitHub search surfaced a starred `.config` repository above GNU Bash because it matched query text. Curated-list discovery correctly surfaced the official GNU Bash resource, but the result was a docs URL, so the correct next action is inspect/curl/open the URL, not clone it.
