# Research: Jupiter Prediction Markets (API and Automation Policy)

Phase 1 evidence capture for Kalakal Agent. Access date for all evidence: 2026-08-05.
Status labels: `Verified` / `Inference` / `Unverified` / `Conflicting`. Evidence comes
from live web fetches of official Jupiter documentation, plus direct read-only calls to
Jupiter's official Trading MCP connector (labeled "MCP observation"). No orders were
placed, no transactions built or signed, and no undocumented endpoints were probed.

## 1. Product identity

- Developer product: **Jupiter Prediction Market API** (exact OpenAPI title), a binary
  prediction market on Solana covering Sports, Crypto, Politics, E-sports, Culture,
  Economics, Tech; "agnostic of the underlying data provider."
  [Jupiter Developers: Prediction](https://developers.jup.ag/docs/prediction) —
  accessed 2026-08-05. **Status: Verified** (independently re-fetched by a second
  session on the same date; content matched).
- User-facing product: **Jupiter Predict**, with markets from "external prediction
  market providers" — a **Polymarket integration** is explicitly named for Browse
  markets. [Prediction Markets - Jupiter Documentation](https://docs.jup.ag/user-docs/trade/predict)
  — accessed 2026-08-05. **Status: Verified**
- "Jupiter Forecast" is a separate native 15-minute BTC up/down product (provider
  `bisonfi`, Chainlink-settled).
  [Forecast docs](https://developers.jup.ag/docs/prediction/forecast.md) — accessed
  2026-08-05. **Status: Verified**

## 2. Documented API capabilities

Base URL `https://api.jup.ag/prediction/v1`; auth via `x-api-key`; prices/amounts in
native units (1,000,000 = $1.00 for JupUSD/USDC). All items below **Status: Verified**
against the cited page, accessed 2026-08-05.

- **Discovery** — `GET /events`, `/events/search`, `/events/{eventId}`,
  `/events/suggested/{pubkey}`, `/markets/{marketId}`, `/orderbook/{marketId}`,
  `/events/scores`, `/trading-status`. Market status: open/closed/cancelled; result:
  null/yes/no. [Events and markets](https://developers.jup.ag/docs/prediction/events-and-markets.md)
- **Order construction** — `POST /orders` (ownerPubkey, marketId, isYes, isBuy,
  depositAmount, depositMint JupUSD/USDC; $5 minimum) returns a "Base64-encoded Solana
  transaction to sign and submit" — client-side signing; a keeper network matches, and
  the opening tx "does not guarantee that the order will be filled."
  [Open positions](https://developers.jup.ag/docs/prediction/open-positions.md)
- **Submission** — `POST /execute` ("Submit a signed order transaction for execution")
  in the OpenAPI spec; docs also show direct `sendRawTransaction`. Which path is
  canonical is not stated.
  [OpenAPI spec](https://developers.jup.ag/docs/openapi-spec/prediction/prediction.yaml)
- **Order lifecycle** — `GET /orders/status/{orderPubkey}`; statuses
  `created`/`partiallyfilled`/`filled`/`failed`; immediate polling may return `pending`
  or "no order history found." Stale-quote guidance: re-fetch the market immediately
  before ordering; gate on `GET /trading-status` → `trading_active: true`.
  [Trading lifecycle](https://developers.jup.ag/docs/prediction/trading-lifecycle.md)
- **Close/sell** — `DELETE /positions/{positionPubkey}` and `DELETE /positions`
  (close-all, `minSellPriceSlippageBps` required). Partial closes are not documented.
  [Manage positions](https://developers.jup.ag/docs/prediction/manage-positions.md)
- **Claims** — `POST /positions/{positionPubkey}/claim`; some markets settle
  automatically; no claim fees.
- **Position/PnL data** — `GET /positions`, `/orders`, `/history` (7 audit event
  types), plus profiles, pnl-history, trades, leaderboards, vault-info.
  [Position data](https://developers.jup.ag/docs/prediction/position-data.md)

## 3. Official agent-facing interfaces

- **Trading MCP** at `https://mcp.jup.ag` — "75 tools across 11 domains" including a
  Prediction domain; "Trading prompts that move funds return an unsigned transaction.
  Your client signs it with your wallet and submits it." API key optional.
  [Trading MCP docs](https://developers.jup.ag/docs/ai/trading-mcp.md) — accessed
  2026-08-05. **Status: Verified**
- **Docs MCP** (read-only documentation server) at `https://developers.jup.ag/docs/mcp`.
  [MCP docs page](https://developers.jup.ag/docs/ai/mcp) — accessed 2026-08-05.
  **Status: Verified**

## 4. Live read-only MCP observations (2026-08-05)

Direct calls through the official Jupiter MCP connector, with no side effects. The
observations below summarize those responses; the raw connector responses were not
retained as repository artifacts. **Status: Verified (direct observation)** unless
noted.

- `prediction_get_trading_status` → `{"trading_active": true}`.
- `prediction_search_events("Dota 2")` → **8 active Dota 2 events** (pagination total
  8), category `esports`, subcategory `dota2` — e.g., "Dota 2: 1win vs BetBoom Team
  (BO3) - 1win Essence Playoffs." Event IDs are `POLY-`-prefixed with
  `"series": "polymarket"` and Polymarket-hosted images — consistent with the
  documented Polymarket integration. **Status: Inference** (provider identity) on top
  of verified raw data.
- `prediction_list_markets(POLY-788904)` → two complementary team moneyline markets
  (`provider: "polymarket"`, `sportsMarketType: "moneyline"`, Polymarket
  `clobTokenIds`), pricing in documented native units (e.g., `buyYesPriceUsd: 240000`
  = $0.24), plus full written resolution rules. Notable resolution details: source is
  "official information from https://www.dotabuff.com" with a credible-reporting
  fallback after 2 hours; cancellations/ties/certain forfeit cases resolve **50-50**;
  match delayed beyond 7 days resolves 50-50.
- `prediction_get_orderbook(POLY-3298166-0)` → yes/no depth ladders returned both in
  integer cents and dollar-string form; the response does not label bid/ask semantics.
  Liquidity on this mid-tier match was thin (top-of-book sizes in the tens to low
  thousands of dollars across the ladder).
- Reported event `volumeUsd` values are consistent with the documented 1e6-per-dollar
  scaling (≈ $1.08M on the largest listed Dota 2 event) but units for volume fields are
  not explicitly documented. **Status: Inference**

## 5. Automation and license policy — conflicting evidence

Jupiter's own documents point in different directions on agent trading. The conflict
is recorded here and preserved, not resolved. **Status: Conflicting.**

- **Product documentation supports agent trading.** The official Trading MCP docs
  state the MCP "lets AI agents trade and run DeFi operations on Jupiter," and its
  Prediction domain tools "Browse prediction market events, place and close bets,
  claim payouts, and read scores and forecasts." Fund-moving prompts "return an
  unsigned transaction. Your client signs it with your wallet and submits it, so you
  stay in control of every transaction." This is strong evidence for an
  **agent-prepared, human-controlled transaction flow** — but nothing in it clearly
  authorizes unattended signing and execution.
  [Trading MCP docs](https://developers.jup.ag/docs/ai/trading-mcp) — accessed
  2026-08-05. **Status: Verified**
- **The legal documents cut the other way, or don't clearly apply.**
  [API & SDK License Agreement](https://developers.jup.ag/docs/legal/sdk-api-license-agreement)
  — accessed 2026-08-05:
  - §3.2(h) prohibits transmitting through a licensee product content that "promotes
    illegal or harmful activity, or gambling or adult content." A prediction-betting
    application plausibly falls inside this restriction. **Status: Verified (clause
    text); applicability to this project: Conflicting**
  - §2.4 directs uses "not prescribed by this Agreement" to seek written consent
    (info@jup.ag). **Status: Verified**
  - §§7.3–7.5 impose potentially significant licensee obligations: compliance with
    KYC/AML due-diligence laws, "transaction screening and monitoring of all digital
    wallets," and blocking specific wallets on Jupiter's written request.
    **Status: Verified**
  - The agreement's operative language is written around the swap products ("Jupiter
    Ultra Swap API," "Metis Swap API") and never mentions the Prediction API or AI
    agents, while the newer Prediction API and Trading MCP explicitly advertise
    prediction betting by agents. Whether the license governs those products unchanged
    is unclear. **Status: Conflicting (scope)**
- [Terms of Use](https://developers.jup.ag/docs/legal/terms-of-use.md) — accessed
  2026-08-05 — no explicit statement on bots/automated trading; prohibits
  spoofing/wash trading, system interference, and VPN circumvention. The license
  agreement separately prohibits usage that "exceeds reasonable request volume."
  **Status: Verified (absence)**

Net reading: technical support for agent-prepared unsigned proposals is verified;
unattended autonomous signing/execution is nowhere approved; and the gambling-content
clause sits in unresolved tension with the Prediction product's own agent-facing
marketing.

## 6. Auth, rate limits, fees, wallet, geography

- **Auth/portal:** keys from https://developers.jup.ag/portal, shown once, sent as
  `x-api-key`, permission-scopable per API including Prediction.
  [API keys](https://developers.jup.ag/docs/portal/api-keys.md) — accessed 2026-08-05.
  **Status: Verified**
- **Rate limits:** per organization — Keyless 0.5 RPS/30 RPM; Free 1/60; Developer
  10/600; Launch 50/3,000; Pro 150/9,000; sliding window, no post-429 lockout. No
  prediction-specific bucket documented.
  [Rate limits](https://developers.jup.ag/docs/portal/rate-limits.md) — accessed
  2026-08-05. **Status: Verified**
- **Fees:** only on executed trades, never claims; scale with contract price, size,
  and outcome uncertainty (docs example: 100 contracts @ $0.25 → $1.32 fee; user docs:
  Browse/Polymarket markets charge "twice the Polymarket fee," rounded up to the cent).
  Exact formula not published. **Status: Verified** (qualitative), **Unverified**
  (formula).
- **Wallet:** any standard Solana wallet; API returns unsigned base64 transactions;
  deposits in JupUSD or USDC (Forecast: USDC only). **Status: Verified**
- **Order size:** Forecast docs state 5–250 USDC per order; whether the 250 cap applies
  to all prediction markets is **Unverified**.
- **Geography — layered and preserved as found:**
  1. Prediction API docs: "We have restricted United States and South Korea IPs from
     accessing the Prediction Market API." **Status: Verified** (independently
     re-fetched same date).
  2. User docs: trading unavailable "in some regions, including the United States and
     South Korea"; the mobile app restricts more (parts of the EU).
     **Status: Verified**
  3. General Terms of Use: Jupiter "does not interact with digital wallets located in,
     established in, or a resident of the United States, the Republic of China,
     Singapore, Myanmar…" plus a sanctions list; VPN circumvention prohibited.
     **Status: Verified**
  The prediction-specific list (US+KR) is narrower than the general wallet exclusion
  list; the documents do not reconcile this. **Status: Conflicting (preserved)** —
  operator jurisdiction/IP compliance must be confirmed before any live mode.

## 7. Failure behavior and beta status

- Documented failure surface: order statuses incl. `failed`; early-poll `pending` /
  "no order history found"; sub-$5 orders → HTTP 400; completed orders → 400 on the
  standard endpoint (use the status endpoint). Keeper/matching internals and a full
  error-code catalog are **not documented**. **Status: Verified (including gaps)**
- Beta: "The Prediction Market API is currently in beta and subject to breaking
  changes" — repeated across the prediction doc pages. Breaking-change risk is high;
  contract tests and defensive parsing are required. **Status: Verified**

## Failed / unusable fetches

- `https://support.jup.ag/hc/en-us/articles/23089115602716-Prediction-Markets` —
  rendered without prediction content (nav only).
- `https://prediction-market-api.jup.ag/docs` — JS-rendered SPA; no readable content.
  Not cited for content.

## Conclusion

The full programmatic loop Kalakal needs is officially documented: discovery, orderbook,
fresh pricing, trading-status gate, unsigned-tx order building with client-side
signing, submission, status polling, closes, claims, and position/PnL history — plus an
official Trading MCP, and live-verified Dota 2 esports events (Polymarket-sourced).
**Technical support for agent-prepared, human-signed transaction proposals is
verified** (§3, §5). This supports Backtest, Paper, and Shadow modes (CLAUDE.md §6,
Modes 1–3) today, and the mechanics — though not yet the live exercise — of Mode 4.

**Gates before any live mode:**

1. **Automation/license conflict (Conflicting, §5)** — unattended autonomous
   signing/execution remains unapproved anywhere in Jupiter's documents, and use of
   the Prediction API in a public gambling-oriented product or demo requires written
   clarification from Jupiter, because of the §3.2(h) gambling-content restriction,
   the §§7.3–7.5 compliance obligations, and the license's swap-specific scope.
2. **Geographic eligibility (conditional gate, §6)** — US/South Korea IP blocks on the
   Prediction API and a broader ToS wallet-exclusion list (Conflicting, preserved);
   any live use is conditional on a runtime jurisdiction/IP eligibility check, and VPN
   workarounds are expressly prohibited.
3. **Beta API** — explicit breaking-change warning; no changelog/deprecation policy
   found.

**Remaining uncertainty:** exact fee formula; whether the 250-USDC cap is
Forecast-only; orderbook bid/ask semantics and volume-field units; `POST /execute` vs.
direct RPC submission; depth/liquidity of Dota 2 markets beyond the one thin book
sampled.
