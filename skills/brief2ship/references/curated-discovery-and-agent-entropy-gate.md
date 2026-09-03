# Curated discovery + agent-code entropy gate

Session learning: repo-first should not only choose a starting repository; it should also prevent AI agents from damaging a good base with code that increases future reasoning cost.

## Curated discovery sources

Use curated lists as discovery rails, not final truth:

- `https://github.com/sindresorhus/awesome` — broad language/framework/tooling indexes.
- `https://github.com/trimstray/the-book-of-secret-knowledge` — CLI, ops, security, networking, and practical engineering tools.

Rules:

- Treat curated-list hits as high-signal leads, not automatic winners.
- Still inspect upstream repo/source health, license, maintainers, issues, runtime, and seams.
- Avoid letting generic query terms like `cli`, `tool`, `starter`, or `project` dominate curated-list matching; require distinctive topic terms when possible.
- For non-GitHub URLs surfaced from curated lists, inspect the upstream URL first; do not emit `git clone` unless the URL is actually a VCS/source repo.
- Penalize personal `.config`/dotfiles repos for non-dotfiles queries even when GitHub search ranks them highly.

## AI-agent-specific curated lists

Do not add all AI-agent lists globally. Activate them conditionally for queries containing terms such as `agent`, `ai agent`, `llm`, `mcp`, `tool calling`, `autonomous`, `multi-agent`, `subagent`, `claude code`, `codex`, or `browser agent`.

Recommended domain lists:

- `https://github.com/e2b-dev/awesome-ai-agents` — broad autonomous-agent ecosystem.
- `https://github.com/kaushikb11/awesome-llm-agents` — LLM agent frameworks.
- `https://github.com/punkpeye/awesome-mcp-servers` — large MCP server index.
- `https://github.com/modelcontextprotocol/servers` — MCP server reference set.
- `https://github.com/wong2/awesome-mcp-servers` — alternate MCP server index/fallback.
- `https://github.com/hesreallyhim/awesome-claude-code` — Claude Code skills/hooks/commands/orchestrators.
- `https://github.com/VoltAgent/awesome-claude-code-subagents` — Claude Code subagent examples and patterns.

## Agent-code entropy gate

After base selection and implementation, apply a maintainability gate. The prime directive:

> Avoid creating systems that only make sense inside the chat session that produced them. The codebase must explain itself after the agent, prompt, and conversation history are gone.

Reject or revise agent-written changes that introduce:

- hidden sources of truth
- duplicate business logic
- pattern drift
- abstractions without real pressure
- pointless indirection chains
- context bombs / god files / unrelated responsibilities
- clever runtime behavior for ordinary business logic
- silent failure
- undebuggable success paths
- hidden temporal coupling
- non-idempotent operations without guards
- test theatre
- dependency inflation
- configuration masquerading as logic
- premature distribution
- security bolted on after functionality
- orphaned/dead code
- local correctness that breaks global coherence

Acceptance question: would another agent or maintainer understand and safely extend this without the original conversation?

Final rule: every AI-generated change should reduce or preserve system entropy; working code is not enough.
