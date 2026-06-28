# How It Works

## Principle

**Simple outside, strict inside.**

The user should experience:
1. one-shot prompt
2. up to five follow-up questions if needed
3. execution
4. proof

The operator or agent should enforce the tougher internal standard behind the scenes.

## Step 0 — Intake

Start with a one-shot prompt in this shape:

> Build me a [thing] for [user] that does [main job]. It should feel like [reference/vibe]. Constraints: [stack/budget/deadline/platform].

Only ask follow-up questions if they materially affect the build.

### Max 5 follow-up questions
1. Who is the primary user?
2. What is the main action they must complete?
3. Are we starting from an existing repo or should I repo-search first?
4. What references or products should this feel closer to?
5. What constraints matter most: speed, polish, budget, mobile, auth, integrations, deployment?

## Step 1 — Repo-first selection

Before writing custom code:
- search existing repos/templates/tools
- compare candidates
- choose a base with a reason
- inspect the real repo, not just the README

### Why this matters
Without this step, agents overproduce custom code and underuse good upstream leverage.

### Minimum output
- short list of candidates
- selected base
- why it won
- whether it will be cloned, forked, used as a library, or used as reference only

## Step 2 — Maintainability gate

This step exists to stop the common failure mode where the code technically works but becomes fragile and expensive to touch.

### Inverted anti-patterns
Reject:
- vague names
- hidden truth
- duplicated business logic
- over-abstracted tiny systems
- giant files with unclear seams
- poor errors/logging
- libraries added to avoid writing 20 lines of code

### Pass criteria
- entrypoint is obvious
- file structure is easy to scan
- important logic is traceable
- debugging paths are clear
- future edits do not require rediscovering the whole system

## Step 3 — Design / finish pass

This is not about adding effects everywhere.
It is about removing generic AI-template feel.

### Goals
- intentional layout
- coherent spacing/type hierarchy
- useful motion
- mobile sanity
- real empty/loading/error states

### Default reference stack
- shadcn/ui for editable component foundations
- Headless UI for accessible primitives
- Motion for purposeful animation
- Lenis only when premium scroll feel is justified
- Magic UI only for selective accents

## Step 4 — Ship gate

Do not mark the work complete until the core flow is verified.

### Minimum checks
- build passes
- runtime smoke test passes
- no obvious console/runtime errors
- key user flow works
- responsive/mobile spot check if UI exists
- proof artifact exists

## Step 5 — Receipts

Every delivery should end with evidence.

### Required receipts
- chosen base and why
- what changed
- commands/tests run
- preview/screenshot/proof
- known compromises or deferred work

## Why this stays lean

This toolkit deliberately avoids:
- heavyweight PM layers
- giant decision matrices
- over-parameterized templates
- mandatory orchestration software

The standard should sharpen judgment, not replace it.
