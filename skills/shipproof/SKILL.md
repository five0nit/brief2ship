---
name: shipproof
description: "ShipProof: run AI-assisted builds that ship with proof, not vibes — one-shot prompt, repo-first selection, maintainability gate, anti-slop finish, and receipts."
version: 0.2.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [build-workflow, repo-first, maintainability, ui-polish, anti-slop, execution]
---

# ShipProof

Use ShipProof for new builds, substantial prototypes, internal tools, landing pages, and customer-facing web work. Former internal name: Three-Tier Build Toolkit.

## Core rule

**Simple outside, strict inside.**

User experience:
1. one-shot prompt
2. up to 5 follow-up questions only if needed
3. execute
4. return proof

## Follow-up questions
Ask only if they materially change the build.

1. Who is the primary user?
2. What is the main action they must complete?
3. Are we starting from an existing repo or should I repo-search first?
4. What references or products should this feel closer to?
5. What constraints matter most: speed, polish, budget, mobile, auth, integrations, deployment?

## The 3 lanes
- App
- Dashboard / Internal tool
- Landing page

Pick the nearest lane based on the primary user outcome.

## Internal workflow

### Tier 1 — Repo-first
Search for the best repo, tool, starter, or template before building greenfield.

Default companion: `repo-first-starter`

### Tier 2 — Maintainability gate
Use `unmaintainable-code` in reverse.

Reject vague naming, hidden logic, duplicated business logic, unjustified abstraction, weak observability, dependency bloat, and chat-context-only code.

### Tier 3 — Design / finish pass
Do not ship generic AI-slop UI.

Default references:
- `shadcn-ui/ui`
- `tailwindlabs/headlessui`
- `motiondivision/motion`
- `darkroomengineering/lenis` only when justified
- `magicuidesign/magicui` selectively only

## Ship gate
Do not call the work done until:
- build passes
- runtime smoke test passes
- key user flow works
- obvious console/runtime issues are checked
- proof exists

## Required receipts
Every build ends with:
- chosen base and why
- what changed
- commands/tests run
- preview/screenshot/proof
- known compromises
