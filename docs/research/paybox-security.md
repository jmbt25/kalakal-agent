# Research: PayBox (MoonPay) — Agent Signing and Custody Security

Phase 1 evidence capture for Kalakal Agent. Access date for all evidence: 2026-08-05.
Status labels: `Verified` / `Inference` / `Unverified` / `Conflicting`. Evidence from
live web fetches of official MoonPay/PayBox sources. Patterns only — no proprietary
code was copied, and no PayBox credential or wallet calls were made in this phase.

## 1. Product identification

- **PayBox** is MoonPay's non-custodial credential vault / wallet for AI agents,
  launched July 29, 2026, live at paybox.sh, connecting into Claude and ChatGPT.
  [MoonPay Launches PayBox…](https://www.moonpay.com/newsroom/moonpay-paybox) —
  accessed 2026-08-05. **Status: Verified**
- Self-description: "the first non-custodial wallet your AI apps can operate on your
  behalf," by MoonPay Inc., "from the team behind MoonPay's open-source Open Wallet
  Standard." [PayBox](https://paybox.sh/) — accessed 2026-08-05. **Status: Verified**
- Disambiguation: distinct from **MoonPay Agents / MoonAgents** (Feb 2026, CLI-based
  local-wallet toolkit) and the **Open Wallet Standard** (Mar 2026 open spec) — see §8.
  No unrelated "Paybox" surfaced in the agentic-trading context. **Status: Verified**

## 2. Custody model (agent/key separation)

- Keys are MPC-split across hardware-isolated TEE enclaves; "no party, including
  MoonPay and the AI itself, can unilaterally access the user's funds." (Newsroom post,
  accessed 2026-08-05.) **Status: Verified**
- "The key never leaves the TEE"; agents receive signed transactions, never key
  material; secrets envelope-encrypted with KMS; cards tokenized.
  [PayBox model docs](https://docs.paybox.sh/concepts/model) — accessed 2026-08-05.
  **Status: Verified**
- "Agents receive signatures or transaction hashes — never your private key, seed
  phrase, or MPC share." Users can self-export keys from the dashboard. Caveat: stored
  *secrets* (e.g., API keys) ARE returned raw to granted agents — only cards/wallets
  are tokenized. [PayBox FAQs](https://support.moonpay.com/en/articles/669843-paybox-faqs)
  — accessed 2026-08-05. **Status: Verified**

## 3. Access granting, scoping, policy controls

- Each agent gets an **agent client** (identity + client key). A **grant** defines
  which credentials it may request, allowed operations, and scope limits: spend limits,
  allowed merchants, allowed chains, allowed contracts, plus approval mode. Revoking a
  grant instantly invalidates the client key; agents "cannot act outside the grant."
  [How agent connections work in PayBox](https://support.moonpay.com/en/articles/669841-how-agent-connections-work-in-paybox)
  — accessed 2026-08-05. **Status: Verified**
- Fine-grained semantics (daily vs. per-transaction limits; Solana program-ID-level
  allowlists) are not publicly enumerated. **Status: Unverified**

## 4. Approval flow

- Three per-client modes: **Always Approve**, **Approve Above Limit**, **Autonomous
  Within Policy**. Approvals are operation-bound: "if anything changes — amount,
  merchant, recipient, contract, function, or secret name — the agent must submit a new
  request." (FAQs, accessed 2026-08-05.) **Status: Verified**
- Sensitive operations require a fresh WebAuthn passkey/biometric assertion; approvals
  expire (~10 minutes) and cannot be replayed against altered parameters.
  [Approvals](https://docs.paybox.sh/concepts/approvals) and
  [Requests](https://docs.paybox.sh/concepts/requests) — accessed 2026-08-05.
  **Status: Verified**
- "Every authorization is scoped to a single action and cannot be reused." (Newsroom,
  accessed 2026-08-05.) **Status: Verified**

## 5. Simulation / preview

- Approval screens show "the full context before you decide," and request `success`
  means "confirmed on-chain, never merely broadcast." However, **no documentation was
  found of pre-signing transaction simulation or decoded-instruction verification.**
  **Status: Unverified (absence)** — Kalakal's own policy layer must perform
  simulation and instruction decoding before anything reaches a signer (CLAUDE.md §4).

## 6. Audit / logging

- "Append-only audit log of every request, decision, and credential issued"; FAQs add
  every "request, approval, denial, timeout, and credential issued" is recorded, with
  per-agent-client trails; agents can read their own history via a read-only
  `list_requests`. [PayBox: store credentials once…](https://support.moonpay.com/en/articles/669779-paybox-store-credentials-once-let-ai-agents-pay-securely)
  — accessed 2026-08-05. **Status: Verified**

## 7. Emergency controls, chains, MCP lifecycle

- Instant per-client revocation plus an account-level **kill switch** that
  "immediately revoke[s] access for every agent client at once." (Help center, accessed
  2026-08-05.) **Status: Verified**
- Chains: Solana plus Ethereum, Hyperliquid, Tempo, Base, Robinhood Chain, Arbitrum,
  Polygon; `solana:*` via base58 addresses. (Newsroom + docs, accessed 2026-08-05.)
  **Status: Verified**
- Official MCP server `https://api.paybox.sh/mcp` (OAuth). Tools include
  `list_credentials`, `request_payment`, `request_wallet_sign` (intent-based, including
  Solana messages and transactions; "the private key never leaves MoonX MPC"),
  `request_swap`, `request_secret`, `get_portfolio`, x402 tools, `list_requests`,
  `get_request`. [MCP tools reference](https://docs.paybox.sh/reference/mcp-tools) —
  accessed 2026-08-05. **Status: Verified**
- Request lifecycle: `pending_approval` (passkey) → `pending_signature` (autonomous
  allowed) → `pending_settlement`/`pending_confirmation` → terminal
  `success`/`denied`/`error`; "submit once, then poll" — re-calling a write tool starts
  a new operation. ([Requests docs](https://docs.paybox.sh/concepts/requests), accessed
  2026-08-05.) **Status: Verified**
- Prediction markets: the live PayBox connector exposes `world_*` tools for "World
  prediction markets" (observed in-product, 2026-08-05), but public docs do not
  document them; money plugins "always require user approval, even under autonomous
  grants." **Status: Verified via in-product connector metadata; public documentation
  Unverified.** Support for **Jupiter** prediction markets specifically is not
  documented; in principle a Jupiter unsigned transaction could be signed via generic
  `request_wallet_sign` Solana-transaction intents. **Status: Inference**

## 8. Alternatives (research-gate comparison)

- **MoonPay Agents (MoonAgents)** — Feb 24, 2026: non-custodial layer on the MoonPay
  CLI; wallets generated and stored on the user's own device; ~54 tools/17 skills.
  Local key custody + CLI vs. PayBox's hosted MPC/TEE control plane with passkey
  approvals. [MoonPay Agents newsroom](https://www.moonpay.com/newsroom/moonpay-agents)
  — accessed 2026-08-05. **Status: Verified**
- **Open Wallet Standard (OWS)** — Mar 23, 2026: MIT-licensed standard from MoonPay +
  15+ orgs (PayPal, Solana Foundation, Ethereum Foundation…): local encrypted key
  storage (AES-256-GCM), pre-signing policy engine (spending limits, contract
  allowlists, chain restrictions, time-bound authorizations), keys never exposed to
  agent/LLM context; Solana supported.
  [Open Wallet Standard newsroom](https://www.moonpay.com/newsroom/open-wallet-standard)
  — accessed 2026-08-05. **Status: Verified.** Note: `https://docs.openwallet.sh/`
  returned HTTP 403 on 2026-08-05 — not cited for content.

## Reusable security patterns (concepts, not code)

1. Credential vault as control plane — the agent receives artifacts (signatures,
   tokens), never key material.
2. Per-agent identity with independently revocable, scoped grants.
3. Operation-bound, single-use, time-expiring approvals — any parameter change forces
   re-approval.
4. Tiered approval modes (always / above-limit / autonomous-within-policy) with passkey
   step-up for sensitive operations.
5. Submit-once-then-poll request lifecycle with explicit terminal states; `success`
   means confirmed on-chain.
6. Append-only audit of every request, decision, and credential.
7. Layered kill switch: per-client revoke + global revoke-all.
8. Pre-signing policy engine at the wallet layer (OWS) as the local-custody fallback
   pattern.

## Conclusion

PayBox is a **promising candidate** for the signing/custody layer of a policy-checked,
human-approval trading agent. Its verified general security capabilities align with
CLAUDE.md §4: keys never reach the LLM (MPC + TEE, signature-only outputs), scoped
revocable grants with chain/contract allowlists and spend limits, operation-bound
passkey approvals (default human-in-the-loop maps to Mode 4), append-only audit, and
per-client + global kill switches.

It is **not selectable as the production signer yet.** Jupiter prediction-program
compatibility, Solana program allowlisting, transaction-format support (whether
Jupiter's unsigned base64 transactions can flow through `request_wallet_sign` under a
scoped grant), and exact grant semantics all remain **Unverified**. Selection requires
a later, isolated compatibility proof on a dedicated limited-funds setup — deliberately
not performed in this phase.

**Remaining uncertainty:** no public docs for the World prediction-market plugin or any
Jupiter-program allowlisting; no documented pre-signing simulation or
decoded-instruction verification (Kalakal must keep its own policy/simulation layer in
front of any signer); exact spend-limit semantics; World-market geographic/eligibility
restrictions; OWS docs site unfetchable (403).
