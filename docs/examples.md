# Examples

These are intentionally small.
They exist to show how the framework should feel in practice.

## Example 1 — App lane

### Prompt
> Build me a lightweight hiring workspace for startup founders to review applicants, track interview stages, and leave team notes. It should feel closer to Linear and Notion than a generic AI dashboard. Constraints: web, polished but not overbuilt, mobile decent, auth required.

### Likely flow
- lane: App
- repo-first search for strong full-stack app / SaaS bases
- choose the best auth/data/dashboard base
- maintainability gate on routes, data access, naming, and state seams
- polish dashboard hierarchy and candidate flow UI
- verify core flow: sign in -> create role -> review candidate -> update stage

### Receipt shape
- chosen base: ...
- why: ...
- changed files: ...
- commands run: ...
- proof: ...

---

## Example 2 — Dashboard / internal tool lane

### Prompt
> Build me an internal support dashboard for managers to see ticket backlog, blocked items, agent load, and SLA risk. It should feel clean and operational, not flashy. Constraints: desktop-first web app, mock data first, room for Zendesk later.

### Likely flow
- lane: Dashboard / internal tool
- repo-first search for strong dashboard/admin bases
- pick clarity and maintainability over bells and whistles
- enforce readable data components and obvious state handling
- finish with strong table/filter/status patterns
- verify key flow: open dashboard -> filter backlog -> inspect blocked queue

---

## Example 3 — Landing page lane

### Prompt
> Build me a launch page for an AI inbox copilot for founders. It should feel premium, fast, and direct — closer to Stripe or Arc than a typical glossy AI site. Constraints: one main CTA, mobile strong, restrained animation.

### Likely flow
- lane: Landing page
- repo-first search for strong landing page / marketing bases
- keep codebase smaller and avoid over-abstracting sections
- focus Tier 3 on hierarchy, spacing, CTA emphasis, and purposeful motion
- verify mobile rendering, CTA visibility, and page performance sanity

## What these examples are proving

The toolkit is not trying to replace product thinking.
It is giving a repeatable build discipline that improves:
- base selection
- maintainability
- finish quality
- verification
