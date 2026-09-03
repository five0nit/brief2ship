# Historical data-source repo-first recon — pump.fun session note

Use this as an example when Mike asks for historical backtests or last-N-day sims.

## Lesson

Do repo-first/data-source discovery before building bespoke collectors. Mike explicitly corrected this as a Brief2Ship miss.

## Source validation pattern

1. Search existing repos/datasets/APIs first:
   - GitHub repo search and web search for domain + `historical`, `dataset`, `trades`, `parquet`, `csv`, `Dune`, `Bitquery`, `API`.
   - Local workspace search for existing collectors/backtests.
2. For each candidate, verify **live access**, not just README claims:
   - API route returns data with current auth/no-auth.
   - Pagination depth covers requested window.
   - Returned schema has features needed for the strategy.
   - Rate/credit limits make the planned export feasible.
3. Only then build custom collectors/backtest plumbing.

## Pump.fun findings from 2026-07 session

- Pump.fun frontend `/coins` was public but shallow: `offset=1000` reached roughly 1.4 hours old; `offset>=2000` returned empty in that session. Treat it as recent/live sampling, not 30-day history.
- Public Solana RPC `getSignaturesForAddress` for the pump.fun program worked but volume was huge: thousands of signatures covered only seconds. Feasible for samples; impractical for full 30-day exhaustive backfills without paid RPC/indexer.
- Dune free tier was usable after generating/copying an API key from the logged-in workspace. Current smoke pattern used `POST https://api.dune.com/api/v1/sql/execute` with header `X-Dune-Api-Key`, then polled `GET /api/v1/execution/{execution_id}/status` and fetched `GET /api/v1/execution/{execution_id}/results`. `SELECT 1 AS ok` completed and returned `ok=1`.
- Use Dune Dataset Search API for table discovery before expensive SQL schema scans: `POST /api/v1/datasets/search` with `query=pump`, `blockchains=[solana]`, `include_schema=true`. This found `pumpdotfun_solana.pump_evt_createevent` and `pumpdotfun_solana.pump_evt_tradeevent`; a broad `information_schema` pump search timed out.
- Dune SQL-visible decoded table columns may have prefixes: call tables expose `call_block_time`, `call_tx_id`; event tables expose `evt_block_time`, `evt_tx_id`. Trust `SELECT * LIMIT 1` over docs/schema snippets before writing large SQL.
- Verified Dune scale for pump.fun 90d was enormous: ~2.56M create events and ~209.8M trade events. Do not raw-dump first. Create compact feature tables and cache locally.
- For 90-day Dune builds, one giant compact query can still hit result-read limits (`402`) even when execution succeeds. Use 12-hour or daily chunks, cache every SQL/result, write a resumable `chunk_state.json`, and append/UPSERT rows into local SQLite by `mint`.
- If Mike asks whether analysis will start after a long data build, do not assume. Chain it explicitly with a background waiter/watch script that waits for all chunks and then runs the signal-analysis script, producing Markdown/JSON reports.
- `PumpArchive/PumpArchive` claimed a free historical pump.fun archive and docs listed `api.pumparchive.com`, but documented routes returned `404` during live verification. Treat as promising but unverified until an endpoint actually returns data.
- `haccer/pumpfun-research` was tooling for wallet-level analysis using Helius-enhanced transaction data, not a standalone no-key historical dataset.

## Preferred backtest data shape

For strategy work, prefer compact point-in-time feature tables over raw full-trade exports:

- launch time, mint, creator
- first 30/60/120s buy/sell counts, unique buyers/sellers, volume, curve progress
- future 5m/15m max return and drawdown
- graduation/migration flags
- no-lookahead timestamp discipline

This keeps Dune/free-tier exports smaller and avoids wasting credits on raw trade dumps before strategy design.
