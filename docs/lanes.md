# Default Lanes

This toolkit intentionally ships with only **four** default lanes.

That is enough to reduce ambiguity without turning the system into a bloated category tree. The fourth lane covers report/document work, because many AI-assisted outputs are not apps but decision artifacts that still need structure, evidence, formatting, and proof.

## 1. App

Use for:
- customer-facing product apps
- SaaS products
- authenticated workflows
- feature-rich multi-screen builds

### Bias
- stronger repo-first search
- architecture and maintainability matter heavily
- design should feel product-grade, not template-grade

### Common bases
- product/app starters
- SaaS boilerplates
- proven auth/data/dashboard stacks

## 2. Dashboard / Internal tool

Use for:
- ops panels
- support tooling
- admin consoles
- internal reporting UIs

### Bias
- clarity over visual theatrics
- speed and maintainability over brand spectacle
- real table/filter/state handling matters more than marketing polish

### Common bases
- admin templates
- data-heavy dashboards
- internal CRUD foundations

## 3. Landing page

Use for:
- launches
- waitlists
- marketing pages
- single-goal conversion surfaces

### Bias
- stronger design finish expectations
- tighter motion discipline
- fewer abstractions, smaller codebase
- clarity of hierarchy and CTA matters most

### Common bases
- landing page starters
- lightweight marketing templates
- component-driven sections

## 4. Report / Document

Use for:
- executive summaries
- audit reports
- QA reports
- project handoff reports
- market/research reports
- formatted Markdown/PDF/client docs
- internal decision briefs

### Bias
- reader outcome over writer cleverness
- evidence separated from opinion
- assumptions, gaps, risks, and recommendations are explicit
- formatting is part of the deliverable, not an afterthought
- render/check the final file when producing Markdown, HTML, PDF, DOCX, or slides

### Common bases
- existing report templates
- prior client/report examples
- source docs, transcripts, logs, spreadsheets, screenshots, and research notes
- Markdown/HTML/PDF generation pipelines when layout matters

See [report-document-lane.md](report-document-lane.md).

## Lane rule

Pick the nearest lane at the start.

If a project overlaps multiple lanes, choose the one that best matches the **primary user outcome**.
Do not try to merge all lanes into a mega-template.
