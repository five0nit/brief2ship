# Brief2Ship Architecture and Release Audit — 2026-07-30

**Status:** Current public tree is a release **NO-GO**
**Repository:** `five0nit/brief2ship`
**Audited commit:** `f2f33bf8c5e610417a323b796b728dcff0aabd35`
**Working tree:** Dirty before this audit; committed and pending state were evaluated separately
**Recommended next release:** `v0.3.1 — Install & Trust`

## Verdict

Brief2Ship has a clear, appropriately lean product model: one brief enters; a lane, base-selection decision, quality gates, verification, and receipt come out. The committed repository matches its “workflow standard, not a giant framework” positioning.

The public tree is not ready for an immutable release. Its advertised installer targets one maintainer profile, alias compatibility is claimed but not packaged, the public repository and live installed skill have diverged, tests check phrases rather than cross-file behavior, no CI/tag/release exists, and the strongest local product page contradicts the four-lane public contract.

**Next move:** release the smallest patch that closes first-user trust and adoption blockers. Keep the product model unchanged. Do not add an LLM runner, custom CLI, marketing site, new lane, or package-manager layer.

## Evidence boundary and freshness

### Canonical source state

- local repository: canonical Brief2Ship checkout
- branch at audit start: `main`
- local `HEAD` and fetched `origin/main`: `f2f33bf8c5e610417a323b796b728dcff0aabd35`
- ahead/behind: `0/0`
- committed footprint: `16` files, `3` commits, no tracked test files
- working-tree validation:
  - `python3 scripts/validate-docs.py` — pass
  - `node tests/product-info-regression.cjs` — pass against untracked files
  - HTML parser check — pass
  - `git diff --check` — fail on one extra blank line in pending `skills/brief2ship/SKILL.md`

### Live public metadata — observed 2026-07-30 AEST

- repository: public, MIT, active, default branch `main`
- tags/releases/workflows/issues/PRs: none
- stars/forks/watchers: `0/0/0`
- GitHub traffic window returned `0` views and `1` unique clone
- repository homepage: unset
- public raw skill: HTTP `200`
- public raw product page: HTTP `404`
- GitHub Pages API: `404`; no Pages site configured
- PyPI `brief2ship` JSON endpoint: HTTP `404`; apparent name availability is not a publication decision

The traffic values are current only for GitHub’s returned window. They show no measured public discovery, not product failure or poor conversion; there is no qualified adoption funnel.

## Product computation

```text
one-shot brief
  -> choose primary outcome lane
  -> search/select or justify a base
  -> apply maintainability gate
  -> apply output-specific finish gate
  -> verify the real user flow
  -> emit proof receipt
```

This computation is the product. Documentation, the agent skill, templates, examples, installation, and CI are support surfaces. `v0.3.1` should make those surfaces consistent and trustworthy without changing the computation.

## Current architecture

| Layer | Current files | Responsibility |
|---|---|---|
| Public contract | `README.md`, `docs/how-it-works.md` | Promise and internal workflow |
| Lane policy | `docs/lanes.md`, `docs/report-document-lane.md` | Output-specific rules |
| Agent application | `skills/brief2ship/SKILL.md` | Applies the standard in Hermes/OpenClaw |
| Input/output templates | `templates/*.md` | Captures briefs and receipts |
| Distribution | `scripts/install-skill.sh` | Copies one skill file into a local profile |
| Validation | `scripts/validate-docs.py` | Checks required phrases/files |
| Local proof, untracked | `product-info.*`, `tests/`, `qa/`, `.agents/` | Self-referential product-page dogfood |
| External dogfood | `../brief2ship-test-run/` | Real Vite brief-checker build with receipt and QA |

### Strengths

1. **Clear promise.** `README.md:3-28` explains the user job and simple outside UX directly.
2. **Correct product boundary.** `README.md:121-130` rejects a giant framework, scoring engine, rigid PM layer, and mandatory stack.
3. **Traceable workflow.** `docs/how-it-works.md:30-108` separates repo selection, maintainability, finish, verification, and receipts.
4. **Bounded lane model.** `docs/lanes.md` uses four outcome-based lanes rather than a sprawling taxonomy.
5. **Useful templates.** The committed build/report request and receipt files are small enough to use.
6. **Existing real dogfood.** `../brief2ship-test-run/BRIEF2SHIP_RECEIPT.md` records an original brief, repo-first comparison, built files, real commands, QA results, and known compromise.
7. **Native install seam exists.** `hermes skills inspect <raw-SKILL.md-url>` recognizes the public skill, and Hermes supports URL installation, named profiles, updates, and uninstall. A custom package manager is unnecessary.

## Findings

No security/data-loss P0 was found in committed product code. Release blockers are ranked P1 because they break first-user trust or canonical identity.

### P1 — Public installer targets a maintainer profile

**Evidence**

- `scripts/install-skill.sh:4-10` hard-codes one maintainer-only named profile
- `README.md:149-157` presents that script as the generic install path
- isolated execution succeeds but installs only into that named profile
- the default profile does not list Brief2Ship while the maintainer profile does
- Hermes docs define the normal root as `$HERMES_HOME/skills/` and named profiles under `$HERMES_HOME/profiles/<name>/`

**Impact**

A public user can receive a successful command and still have no skill in the profile they actually use. The Bash-only path also weakens the declared Windows support.

**Decision**

Use Hermes’ native URL installer as the only public installation architecture. Document global/default and named-profile forms. Remove the bespoke installer rather than replacing it with another installer.

### P1 — Canonical skill identity has drifted

**Evidence**

- public/committed skill: `0.3.0`
- working-tree skill: `0.3.0`
- installed maintainer-profile skill: `0.3.1`
- installed package has ten support files absent from the repository package
- all three `SKILL.md` files have different SHA-256 hashes

**Impact**

There is no single reliable answer to “which behavior is Brief2Ship?” Running the old installer can replace only `SKILL.md` while leaving unrelated profile support files in place.

**Decision**

The repository is canonical. Live-profile additions remain private overlays until generalized and deliberately promoted. `v0.3.1` must not ingest the live profile automatically.

### P1 — Compatibility claims exceed packaged behavior

**Evidence**

- `README.md:159` claims backward-compatible skill names `shipproof` and `three-tier-build-toolkit`
- the repository contains one skill package named `brief2ship`
- local workspace symlinks exist, but they are not distributed to public users
- `README.md:92` calls it a Hermes/OpenClaw package, but the only documented installer targets Hermes

**Impact**

A public user cannot load the advertised aliases from the repository package.

**Decision**

Replace the alias claim with a historical-name note. Narrow the packaged-support claim to Hermes until an OpenClaw install path is documented and smoke-tested. Do not package aliases unless a supported mechanism and tests justify them.

### P1 — Report/Document support is weakly discoverable

**Evidence**

- `CHANGELOG.md:3-7` and the skill body define Report / Document as the fourth lane
- `skills/brief2ship/SKILL.md:3` omits reports/documents from the frontmatter description
- `skills/brief2ship/SKILL.md:15` omits reports/documents from the trigger paragraph
- the current validator only requires the phrase somewhere deeper in the skill

**Impact**

Hermes may not select Brief2Ship for report work because the metadata and trigger text under-describe a released capability.

**Decision**

Add report/document work to the public discovery description and trigger. Test it as a cross-file release claim.

### P1 — “Proof included” is not a repository invariant

**Evidence**

- `scripts/validate-docs.py` tests substring presence
- no CI workflow exists
- no version/claim/link/frontmatter/install-path consistency check exists
- no tracked worked example exists
- no tag or GitHub release maps version `0.3.0` to an immutable commit

**Impact**

Broken claims can pass while required phrases remain. The public promise is stronger than the release machinery.

**Decision**

Add one minimal release validator, one GitHub Actions workflow, and one real worked example. Pin the public install URL to an immutable `v0.3.1` tag after approval.

### P1 — Pending report changes weaken the lean contract

**Evidence**

- committed `docs/report-document-lane.md:45` explicitly allows short reports to collapse sections
- pending `docs/examples.md` says to use one exact structure
- pending `templates/report-request-template.md:14-22` duplicates source inputs
- pending template requires a single structure, three-sentence paragraphs, and five-item bullet caps
- pending `skills/brief2ship/SKILL.md` adds another layout receipt field

**Impact**

The changes contain useful hierarchy ideas but turn defaults into mandatory ceremony. This conflicts with `CONTRIBUTING.md:7-15` and the product’s judgment-preserving non-goals.

**Decision**

Do not include these pending changes in `v0.3.1` as-is. Preserve them locally, then separately simplify: one source section, default-not-mandatory structure, explicit permission to collapse sections, and no arbitrary prose-count rules.

### P1 — Local product page contradicts current public claims

**Evidence**

- `product-info.html:141` says “Three default lanes”; public `0.3.0` has four
- `product-info.html:55` labels an anchor jump “Copy the brief shape”; it does not copy
- `product-info.html:184-189` says users can install, but CTAs open GitHub/README rather than an install action
- its receipt says undeployed and no social preview
- public raw page returns `404`
- static regression passes because it does not test these cross-file claims or CTA behavior

**Impact**

Promoting the page now would publish a polished but stale adoption surface.

**Decision**

Defer product-page publication and repository inclusion from `v0.3.1`. Repair claim parity and real CTA behavior in a later scoped release.

### P2 — Public adoption is unmeasured/near-zero

The observed GitHub window has no views and one unique clone, with no stars/forks/watchers. This supports focusing on installability and proof before building more product surface. It does not establish a conversion problem.

### P2 — Version/release state is informal

Versions appear in `SKILL.md` and `CHANGELOG.md`, but no tag/release exists. A patch release needs one canonical version source or a consistency test and a release receipt.

### P2 — Core policy is duplicated without a declared projection rule

User flow, lane names, follow-up questions, ship gates, and receipt rules repeat across README, workflow docs, the runtime skill, and templates. Duplication is currently small, but every policy edit requires coordinated changes and substring needles do not prove semantic parity.

**Decision:** Declare the repository contract canonical and the skill/templates as tested projections. Do not add a large schema in this patch; add semantic checks for version, four lanes, report discoverability, supported names, links, and install claims.

### P2 — License holder is unnamed

`LICENSE:3` says only `Copyright (c) 2026`. Set the intended holder before the release tag so attribution is unambiguous.

## Architecture decision: `v0.3.1 — Install & Trust`

### Goal

A first external user can discover the public repository, install Brief2Ship through Hermes’ supported skill command into the intended profile, load it, inspect one real non-placeholder proof case, run the repository checks, and map all of that behavior to one immutable release.

### Target architecture

```text
README + docs + templates
          |
          v
skills/brief2ship/SKILL.md  <- canonical public skill
          |
          v
Hermes native URL install   <- default or explicit named profile

worked example + receipt ---> release validator ---> GitHub Actions
                                      |
                                      v
                              immutable v0.3.1 tag
```

### In scope

1. Remove `scripts/install-skill.sh`; use Hermes native URL installation.
2. Document install, activation/load, update, uninstall, and named-profile paths.
3. Narrow unverified OpenClaw/alias claims and add Report/Document discovery metadata.
4. Set public version `0.3.1`, license holder, and repository-canonical projection rule.
5. Promote a cleaned, bounded Brief Checker dogfood example from `../brief2ship-test-run/`.
6. Add minimal checks for docs, relative links, frontmatter/version, four-lane/discovery parity, and the example build/static QA.
7. Add one GitHub Actions workflow.
8. Create the first tag/release only after clean-checkout verification, green CI, and explicit approval.

### Explicitly deferred

- current pending report-layout expansion
- current product-info page and GitHub Pages
- custom Brief2Ship CLI or installer
- LLM/provider integration
- scoring/orchestration runtime
- more lanes
- alias packages
- PyPI or skills-registry publication
- profile-local specialist references
- analytics/telemetry

## `v0.3.1` acceptance criteria

### Adoption path

- [ ] README uses `hermes skills install <immutable-url>` as the primary path
- [ ] named-profile command uses `hermes --profile <name> skills install ...`
- [ ] isolated global/default install lands in the expected Hermes home
- [ ] isolated named-profile install lands in the expected profile
- [ ] `hermes skills list` shows `brief2ship` in the selected profile
- [ ] activation/load command is documented and exercised
- [ ] update/check and uninstall commands are documented accurately
- [ ] no public file hard-codes a maintainer-specific profile or absolute maintainer path

### Canonical identity

- [ ] public version is `0.3.1` in all required surfaces
- [ ] repository is explicitly canonical; profile copies are not release inputs
- [ ] unsupported alias compatibility claim is removed
- [ ] OpenClaw is not claimed as a packaged install target unless its path is tested
- [ ] skill frontmatter and trigger text discover Report / Document work
- [ ] platform claims match the native Hermes install path
- [ ] intended copyright holder is named
- [ ] all relative docs links resolve
- [ ] skill frontmatter parses and contains required fields

### Proof and release

- [ ] one tracked worked example contains original brief, repo choice, source, build command, test output, proof image(s), and known compromise
- [ ] example builds from a clean install
- [ ] example static QA passes
- [ ] CI runs the same release gate used locally
- [ ] `git diff --check` passes
- [ ] clean checkout passes every gate without untracked local files
- [ ] tag `v0.3.1` identifies the exact verified commit
- [ ] pinned raw skill URL returns HTTP `200` and Hermes inspection reports `0.3.1`
- [ ] no push/tag/release occurs without explicit approval

## Release order

1. Create a release branch while preserving all pending local files.
2. Exclude/park the over-prescriptive report edits and stale product page from release scope.
3. Replace custom install docs/script with native Hermes commands.
4. Add version/claim/link validation.
5. Promote and clean the Brief Checker worked example.
6. Add CI and run the clean-checkout gate.
7. Write release receipt and review final diff.
8. Ask before push, tag, or GitHub release.

Detailed plan: [`plans/2026-07-30-v0.3.1-install-and-trust.md`](plans/2026-07-30-v0.3.1-install-and-trust.md).
