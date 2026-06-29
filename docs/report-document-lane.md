# Report / Document Lane

The Report / Document lane extends Brief2Ship beyond code and UI builds. Use it when the requested artifact is a decision-ready document: a report, audit, research summary, client handoff, project review, formatted guide, or executive brief.

## Core outcome

A report is not done when text exists. It is done when the intended reader can understand the situation, trust the evidence, and take the next action.

## Best-practice flow

### 0. Define the reader and decision

Before writing, identify:
- **reader:** who will consume this?
- **decision/action:** what should they be able to do after reading?
- **format:** Markdown, HTML, PDF, DOCX, slides, email, or dashboard note
- **depth:** executive summary, operator detail, technical appendix, or client-facing polish
- **source material:** docs, logs, metrics, screenshots, interviews, research, code, tickets, transcripts

Only ask follow-up questions if they materially change the artifact.

### 1. Source-first intake

Gather real inputs before drafting. Do not invent facts, metrics, quotes, screenshots, customer claims, or tool output.

Minimum source pass:
- list the provided/retrieved inputs
- separate facts from assumptions
- note missing evidence
- preserve source links/paths where practical

### 2. Structure before prose

Choose the report skeleton before writing. Default structure:

1. Executive summary
2. Context / brief
3. Key findings
4. Evidence
5. Risks / caveats
6. Recommendations
7. Next actions
8. Appendix / sources

For short reports, collapse sections, but keep the logic: summary → evidence → implications → action.

### 3. Evidence gate

Every material claim should be one of:
- backed by a source
- explicitly labeled as an assumption
- explicitly labeled as analysis/opinion

Avoid unsupported certainty. Prefer direct wording:

- "The logs show..."
- "The screenshot indicates..."
- "Assumption: ..."
- "Risk: ..."
- "Recommended next step: ..."

### 4. Formatting pass

Formatting is part of the ship gate. Make the report skimmable:
- start with a short executive summary
- use headings that answer reader questions
- use tables for comparisons, findings, owners, status, dates, and risks
- use bullets for action lists
- keep paragraphs short
- put long raw evidence in appendices
- include a clear status label: draft, reviewed, final, blocked, or needs source verification

### 5. Recommendation pass

A good report should not stop at "interesting findings." Add clear decisions or actions:
- what to do now
- who owns it
- what proof would show it worked
- what remains uncertain

### 6. Render / QA gate

Before calling it done:
- spell-check or at least scan headings and obvious typos
- verify links/file references resolve where practical
- if Markdown: render or inspect table/list formatting
- if HTML/PDF/slides: open or generate the artifact and inspect layout
- confirm no secrets/private data leaked
- confirm claims are not fabricated

### 7. Report receipt

End with a small receipt:
- report goal and audience
- sources used
- files produced
- checks run
- known gaps or unverifiable claims

## Default follow-up questions

Ask only what materially changes the report:

1. Who is the reader and what decision/action should this support?
2. What source material must be included?
3. Should the tone be executive, technical, client-facing, or internal/operator-grade?
4. What final format is required: Markdown, HTML, PDF, DOCX, slides, or message?
5. Are there claims, numbers, names, screenshots, or private details that must be excluded or verified?

## Ship gate for reports

Do not call a report complete until:
- reader and decision/action are clear
- sources are listed
- evidence, assumptions, and opinions are separated
- recommendations are concrete
- formatting is skimmable
- final artifact renders/opens when applicable
- known gaps are explicit
- receipt exists

## Anti-patterns

Reject:
- walls of text with no decision path
- invented metrics or customer quotes
- hiding assumptions inside confident prose
- generic AI filler such as "streamline" without substance
- recommendations with no owner, next step, or proof
- unrendered PDFs/HTML/slides
- private/source data dumped into a client-facing report

## Good report prompt shape

> Create a [report type] for [reader] to help them decide [decision/action]. Use these sources: [paths/links/data]. Tone: [executive/client/internal/technical]. Format: [Markdown/PDF/HTML/slides]. Include evidence, assumptions, risks, recommendations, next actions, and a receipt.
