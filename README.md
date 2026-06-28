# Brief2Ship

**One brief. Better build. Proof included.**

Brief2Ship is a lean build standard for AI-assisted product work. It turns a strong one-shot brief into a shipped, verified artifact without making the user babysit a bloated process.

## What it is

Brief2Ship is a **workflow standard**, not a giant framework.

It helps an operator or agent do four things consistently:

1. **Get a strong one-shot prompt**
2. **Choose a base before building greenfield**
3. **Reject brittle unreadable agent code**
4. **Turn the brief into a verified build**

## User experience

The external UX stays simple:

1. One-shot prompt
2. Up to 5 follow-up questions only if needed
3. Execute
4. Return proof

The user should not have to learn the internals.

## Internal workflow

The public name is Brief2Ship. The operating model underneath stays intentionally simple: one strong brief, three internal tiers, and a final proof gate.

### Tier 1 — Repo-first
Search for the best existing repo, starter, tool, or template before building.

Default companion: [`repo-first-starter`](https://github.com/five0nit/repo-first-starter)

### Tier 2 — Maintainability gate
Use [`droogans/unmaintainable-code`](https://github.com/droogans/unmaintainable-code) in reverse.

Reject:
- vague naming
- hidden logic
- duplicated business logic
- unjustified abstraction
- weak observability
- dependency bloat
- chat-context-only code

### Tier 3 — Design / UI / motion finish
Do not ship generic AI-slop UI.

Default references:
- [`shadcn-ui/ui`](https://github.com/shadcn-ui/ui)
- [`tailwindlabs/headlessui`](https://github.com/tailwindlabs/headlessui)
- [`motiondivision/motion`](https://github.com/motiondivision/motion)
- [`darkroomengineering/lenis`](https://github.com/darkroomengineering/lenis) when justified
- [`magicuidesign/magicui`](https://github.com/magicuidesign/magicui) selectively only

## Why this exists

Most starter kits solve only one part of the build problem:
- scaffolding
- design system
- SaaS boilerplate
- component library

Brief2Ship is different.

It is a **build operating standard** for AI-assisted delivery:
- choose better starting points
- preserve judgment and maintainability
- add tasteful finish without adding ceremony


## Why the name

The old names described the internal mechanism or the final proof. **Brief2Ship** sells the full transformation:

- **Brief** — the user gives one clear starting prompt, not a pile of process docs
- **2** — direct path from intent to execution, with at most five targeted follow-ups
- **Ship** — the result is a usable artifact with receipts, not a planning loop
- **Memorable + searchable** — short enough for prompts, docs, repo names, and package names

Use this line when explaining it publicly:

> Brief2Ship is the lightweight operating standard for AI-assisted builds: start from one strong brief, choose the best base, keep the code maintainable, polish the UX, and prove it works.

## What this repo includes

- `skills/brief2ship/SKILL.md` — Hermes/OpenClaw skill package
- `docs/how-it-works.md` — full breakdown of the workflow
- `docs/lanes.md` — the 3 default build lanes
- `docs/examples.md` — example prompts and execution patterns
- `templates/` — kickoff and receipt templates
- `scripts/install-skill.sh` — install the skill into a local Hermes profile

## The 3 default lanes

To avoid ambiguity without overcomplicating the standard, this repo ships with only three default lanes:

1. **App**
2. **Dashboard / Internal tool**
3. **Landing page**

See [docs/lanes.md](docs/lanes.md).

## Lightweight receipts

Every build should end with a small artifact pack:
- chosen base and why
- changed files
- commands/tests run
- verification/proof
- known compromises

Use [templates/build-receipt-template.md](templates/build-receipt-template.md).

## Non-goals

This project intentionally does **not** try to be:
- a full app framework
- a replacement for product judgment
- a giant scoring engine
- a mandatory design system
- a rigid PM workflow

The goal is to improve build quality **without harming judgment or accuracy**.

## Comparison to adjacent products

| Product type | What it does well | What this adds |
|---|---|---|
| Starter kits | Scaffold fast | Forces repo-first choice instead of default greenfield |
| SaaS boilerplates | Ship common product features | Adds maintainability gate + anti-slop finish rules |
| Component libraries | Better UI primitives | Adds upstream selection + delivery discipline |
| Agent skills/runbooks | Internal process | Adds a public-facing packaging layer and examples |

## Quick start

### As documentation
Read:
1. [docs/how-it-works.md](docs/how-it-works.md)
2. [docs/lanes.md](docs/lanes.md)
3. [docs/examples.md](docs/examples.md)

### As a Hermes skill
```bash
bash scripts/install-skill.sh
```

Then load:
```text
brief2ship
```

Backward-compatible skill names during migration: `shipproof`, `three-tier-build-toolkit`.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## Contributors

Initial framework direction and product requirements: **Mike**  
Packaging, workflow codification, and repo drafting: **Hermes Agent (generalist1)**

Future contributors should keep the project lean. If a feature makes the workflow harder to apply consistently, it probably does not belong here.

## License

MIT for the material in this repo. Upstream referenced projects keep their own licenses.
