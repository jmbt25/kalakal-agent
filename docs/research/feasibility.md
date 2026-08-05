# Feasibility Report — Kalakal Agent (Phase 1)

Synthesis of the Phase 1 research documents, plus a Phase 2 addendum (§9). Access
date for all evidence: 2026-08-05. Full citations live in the per-topic documents;
this file cites only pivotal sources.
Status labels: `Verified` / `Inference` / `Unverified` / `Conflicting`.

## 1. Verified capabilities

- **The hackathon is real and the window is open.** All Things Agentic Hackathon
  (Google/Devpost), submission period Aug 3–31, 2026; mandatory Gemini 3.5+, one
  Google agent framework, one Google Cloud service; ≤4-minute unedited live demo with
  visible Google Cloud deployment.
  ([rules](https://allthingsagentichackathon.devpost.com/rules), 2026-08-05;
  [hackathon.md](hackathon.md).) **Verified**
- **Jupiter publishes a real Prediction Market API (beta)** at
  `api.jup.ag/prediction/v1` covering the full loop: discovery, orderbook, fresh
  pricing, trading-status gate, unsigned-transaction order building (client-side
  signing), submission, status polling, closes, claims, positions/PnL/history — plus
  an official Trading MCP at `mcp.jup.ag`.
  ([developers.jup.ag/docs/prediction](https://developers.jup.ag/docs/prediction),
  2026-08-05; [jupiter-prediction-markets.md](jupiter-prediction-markets.md).)
  **Verified**
- **Dota 2 markets exist on Jupiter right now.** Live read-only MCP calls on
  2026-08-05 returned `trading_active: true` and 8 active Dota 2 events
  (Polymarket-provided moneyline team markets with written resolution rules; one
  sampled orderbook was thin). **Verified (direct observation)**
- **A promising signing-layer candidate exists.** MoonPay PayBox: MPC/TEE keys that
  never reach the agent, scoped revocable grants (chains/contracts/spend limits),
  operation-bound single-use passkey approvals, append-only audit, per-client + global
  kill switch, official MCP server — all **Verified** as general capabilities. Jupiter
  prediction-program compatibility, Solana program allowlisting, transaction-format
  support, and exact grant semantics remain **Unverified**; PayBox cannot be selected
  as the production signer until a later isolated compatibility proof succeeds.
  ([docs.paybox.sh](https://docs.paybox.sh/concepts/model), 2026-08-05;
  [paybox-security.md](paybox-security.md).)
- **Jup Callers rules are published and compatible with CLAUDE.md §8, with
  intentionally stricter project rules.** Band, weekly cap, qualification, event-only,
  cutoff, channel, ask-at-timestamp, and duplicate rules are **Verified**; Kalakal is
  deliberately stricter in always requiring the jup.ag market link (tracker:
  recommended, not required) and requiring `#nfa` in the same message (tracker allows
  an adjacent message within 5 minutes). The tracker appears community-run, not
  official. ([jupcallers.fun/methodology](https://jupcallers.fun/methodology) and
  [/season](https://jupcallers.fun/season), 2026-08-05; [jupcallers.md](jupcallers.md).)
- **Workable Dota 2 data paths exist, with uneven legal clarity.** Liquipedia's APIs
  are verified and sanctioned for schedules/rosters (CC-BY-SA, attribution, strict
  rate limits; HTML scraping prohibited — and avoided). Valve's official Steam Web API
  is available (100k calls/day, revocable at will). OpenDota is a technically useful
  candidate (same-day pro results verified live) whose data-license status is
  unresolved — not a production dependency until that is settled.
  ([dota2-data-sources.md](dota2-data-sources.md).)

## 2. Unverified assumptions

- Exact Jupiter trading-fee formula; whether the 5–250 USDC order-size band applies
  beyond Forecast; orderbook bid/ask semantics; volume-field units.
- OpenDota current pricing/limits and data license; STRATZ current limits and terms
  (primary pages bot-blocked).
- PayBox World prediction-market plugin (undocumented publicly); whether Jupiter's
  prediction program can be allowlisted/signed through PayBox in practice.
- jupcallers.fun operator identity and official status; season-week timezone.
- Whether hackathon judges accept a real-money prediction-market agent as submission
  subject matter (no prohibition found; no allowance either).

## 3. Blockers and gates

1. **Jupiter agent-trading evidence is genuinely conflicting (Conflicting).** The
   official Trading MCP documentation says the MCP "lets AI agents trade," describes
   Prediction tools that browse markets, place and close bets, claim payouts, and read
   data, and specifies that fund-moving prompts return unsigned transactions the
   client signs and submits — verified support for an **agent-prepared,
   human-controlled** flow, but nothing that clearly authorizes unattended signing and
   execution. Against that, the API & SDK License Agreement §3.2(h) restricts
   transmitting through a licensee product content that promotes gambling, §2.4
   directs uses not prescribed by the agreement to seek written consent, and §§7.3–7.5
   impose potentially significant compliance, transaction-screening, KYC/AML, and
   wallet-blocking obligations — and the license is written around the swap APIs,
   never mentioning the Prediction API or agents, so its applicability is unclear.
   (Full evidence: [jupiter-prediction-markets.md](jupiter-prediction-markets.md) §5.)
   Consequences: **Mode 5 (unattended execution) stays blocked**; **Mode 4 is
   technically supported but not cleared for live exercise** until Jupiter confirms
   the license and automation interpretation; and the §3.2(h) gambling-content
   restriction plus the §§7.3–7.5 obligations are a **potentially project-wide
   platform blocker** — they could reach any public, gambling-oriented product or demo
   built on the Prediction API, not only autonomous trading.
2. **Geographic eligibility — a conditional runtime gate, not an unconditional
   blocker.** US and South Korea IPs are blocked from the Prediction API; the general
   ToS excludes wallets from a broader country list (**Conflicting — preserved**, see
   [jupiter-prediction-markets.md](jupiter-prediction-markets.md) §6); VPN
   circumvention is expressly prohibited. The application must check jurisdiction/IP
   eligibility at runtime before any live market interaction, and must not store
   personal location data in the public repository. This report deliberately records
   no conclusion about the developer's location.

Backtest, Paper, and Shadow modes involve no live transactions and are unaffected by
the execution gates — but a *public* demo built on live Prediction API data is touched
by the §3.2(h) question above, hence the fixtures recommendation in §8.

## 4. Security risks

- **No pre-signing simulation documented in PayBox** — Kalakal must run its own
  transaction simulation and decoded-instruction verification in front of any signer
  (CLAUDE.md §4 already mandates this).
- **PayBox returns stored secrets raw to granted agents** (only cards/wallets are
  tokenized) — never store wallet key material as a PayBox "secret"; scope grants
  minimally.
- **Prompt injection via untrusted data**: market titles/rules, Dota data, and Discord
  content are attacker-controllable text and must be schema-validated before reaching
  decision or policy components.
- **Beta API drift**: Jupiter explicitly warns of breaking changes — defensive
  parsing, contract tests, and version pinning required.

## 5. Compliance / platform risks

- Jupiter ToS: wash-trading/spoofing prohibitions, "reasonable request volume" clause,
  Panama governing law, OFAC representations.
- Jupiter API & SDK License: §3.2(h) gambling-content restriction and §§7.3–7.5
  KYC/AML, transaction-screening, and wallet-blocking obligations, of unclear
  applicability to the Prediction API (see §3.1) — potentially project-wide.
- Valve ToU: revocable "at any time for any reason" — no SLA; requires a second source
  for every pipeline.
- Liquipedia: strict rate limits, mandatory attribution (CC-BY-SA), automated HTML
  access prohibited.
- PandaScore: stats plans restricted to "non betting-related usage" — likely
  disqualifying for this project without written clarification.
- Hackathon: work must be "newly created during the Submission Period" with disclosure
  of pre-existing code — the clean-room policy (CLAUDE.md §2) satisfies this.

## 6. Data-quality risks

- **No sanctioned schedule feed from the match-data APIs**: OpenDota has no upcoming-
  match endpoint; Valve's GetScheduledLeagueGames is effectively empty (community
  consensus, **Unverified**). Schedules must come from Liquipedia (rate-limited) —
  latency and coverage risk for fast-moving tier-2 events.
- **Thin orderbooks** on mid-tier Dota 2 markets (observed): slippage and stale-price
  risk; edge calculations must use depth, not just top-of-book.
- **Resolution mismatch risk**: markets resolve off dotabuff.com per Polymarket rules,
  with 50-50 outcomes on cancellations/ties/certain forfeits and fuzzy team-name
  matching — model and policy layers must handle these outcomes explicitly.
- **Live-state latency** in Valve live endpoints (reported) — staleness checks
  required before any decision uses live data.

## 7. Questions requiring organizer or platform confirmation

1. Jupiter (in writing): does §3.2(h)'s gambling-content restriction apply to an
   application using the Prediction API?
2. Jupiter (in writing): does the general API & SDK License govern the Prediction API
   and Trading MCP unchanged, despite its swap-specific language?
3. Jupiter (in writing): is an agent-prepared, human-reviewed, human-signed prediction
   transaction permitted?
4. Jupiter (in writing): is unattended agent signing/execution permitted?
5. Jupiter (in writing): which compliance and wallet-screening obligations (§§7.3–7.5)
   apply to a single-user hackathon project?
6. Jupiter: which geographic rule set governs prediction-market API trading — the
   US+KR IP list or the broader ToS wallet-exclusion list?
7. Hackathon organizers: is a real-money prediction-market agent acceptable subject
   matter, and does Vertex AI alone satisfy the "Google Cloud infrastructure service"
   requirement given the demo must show a backend running on Google Cloud?
8. PayBox/MoonPay: can Jupiter prediction-market transactions be signed under a scoped
   grant (program allowlist), and what are World-plugin geographic restrictions?
9. PandaScore: does a prediction-market agent count as "betting-related usage"?
10. jupcallers.fun: who operates it, and is Discord the authoritative rule source?

## 8. Recommendation (conservative)

**Proceed — continue architecture and implementation in Backtest, Paper-trading, and
Shadow modes (Modes 1–3), plus offline Jup Callers draft generation.** Design Mode 4
(agent-prepared, human-reviewed, human-signed transaction proposals) — its mechanics
are technically supported and verified — but do not exercise it against live markets
until Jupiter confirms the license and automation interpretation (§3.1) and the
runtime geographic eligibility gate (§3.2) passes. Mode 5 (unattended execution)
remains disabled; its CLAUDE.md §6 preconditions are not close to satisfied.

For any **public demo**, use mocks or recorded fixtures rather than live Prediction
API data until Jupiter clarifies §3.2(h)'s applicability. No transaction construction,
signing, submission, or other real-money behavior should be demonstrated yet.

Rationale: every capability needed for the hackathon demo — data ingestion,
probability estimation, edge comparison, policy checks, draft generation, audit
records — is demonstrable on fixtures or paper/shadow state, and the hackathon judges
"are not required to test the Project" beyond the video and description. The open
questions gate live execution and public use of live API data, not the engineering.

## 9. Phase 2 addendum — Google stack and policy (2026-08-05)

Phase 2 ([google-stack.md](google-stack.md)) researched the Google side (Gemini
models, agent frameworks, Cloud architecture, acceptable-use policy). Net result:
**no new Google-side blocker** — no in-scope Google or Devpost policy prohibits a
prediction-market application per se (no gambling-application ban, no financial-AI
ban, no crypto-trading ban; the only gambling clause anywhere is the Google APIs
ToS restriction on "unlawful online gambling"). Mode 4's human review sits outside
the one automated-decisions restriction in scope by that clause's own wording
("without human supervision"); Mode 5 faces two ambiguous clauses and stays
disabled. This is an evidence-based project reading of the policy texts, not legal
permission or legal advice. The decisive gate remains the §3.1 Jupiter questions
plus external gambling-law legality. (Evidence: google-stack.md §5.
**Verified/Inference** per that document.)

Two rules findings materially sharpen §3 and §7:

- **The hackathon rules bind the submission to third-party terms.** "Third-Party
  Integrations: ... Entrants must be authorized to use these third-party tools and
  information in accordance with any terms and conditions or licensing requirements
  of the tool" — so the unresolved Jupiter license questions (§3.1) are now also a
  **submission-validity risk**, not only a platform risk. The rules additionally
  require that no part of the submission is unlawful "in any country, state or
  applicable territory where you created the video and in the United States" — a
  US-law overlay on the demo regardless of entrant location.
  ([rules](https://allthingsagentichackathon.devpost.com/rules), 2026-08-05.)
  **Verified (clauses); Inference (consequence).** This reinforces and raises the
  stakes of the §8 fixtures-only demo recommendation.
- **Open question 7 is half-mooted.** Whether Vertex AI alone satisfies "Google
  Cloud infrastructure service" no longer matters: the recommended stack uses Cloud
  Run + Firestore, which satisfy the requirement unambiguously
  (google-stack.md §4/§6). The subject-matter-acceptability half of question 7
  remains open. **Inference.**

The §8 recommendation is unchanged: proceed in Modes 1–3 plus offline draft
generation; demo on fixtures/paper data; Mode 4 designed but not exercised; Mode 5
disabled. Recommended Google stack (non-binding, google-stack.md §6): Python +
Google ADK single agent + `gemini-3.6-flash` via Vertex AI with ADC/service
identity (fallback `gemini-3.5-flash`) + Cloud Run + Firestore (+ Secret Manager
once external API credentials exist). The fixtures-only demo may run in
us-central1 (it makes no Jupiter calls); any environment that accesses live
Jupiter data has a **TBD region** until the §3.2 geographic rules are clarified.
Expected cost ≈$0 and under $5/month for the stated demo assumptions — a bounded
estimate, not a worst-case guarantee (google-stack.md §4.7). The Google research
is sufficient to begin fixture-only implementation; model-region availability,
actual quotas, current prices, and the final region remain pre-deployment checks
(google-stack.md §6).
