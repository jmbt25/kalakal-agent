# Research: Jup Callers — Methodology and Season Rules

Phase 1 evidence capture for Kalakal Agent. Access date for all evidence: 2026-08-05.
Status labels: `Verified` / `Inference` / `Unverified` / `Conflicting`. Evidence from
live web fetches. Discord content is not directly fetchable; coverage gaps are noted.

## 1. Where the methodology is published — and its official status

- The methodology lives at **jupcallers.fun**: "verified caller leaderboard" for
  Jupiter `#prediction-alpha` callers; every call carries a receipt (original message,
  market, entry price, resolution evidence). [jupcallers.fun](https://jupcallers.fun/)
  — accessed 2026-08-05. **Status: Verified** (as the site's own claims).
- The site nowhere identifies its operator or claims Jupiter affiliation
  (independently re-confirmed on the methodology page the same date).
  **Status: Verified (absence of claim)**
- Jupiter's official Predict docs contain **no mention** of Jup Callers,
  `#prediction-alpha`, or caller scoring.
  [Prediction Markets - Jupiter Documentation](https://docs.jup.ag/user-docs/trade/predict)
  — accessed 2026-08-05. **Status: Verified (absence)**
- Therefore the most authoritative public source is jupcallers.fun itself, best treated
  as a **community/unofficial tracker** until proven otherwise. **Status: Inference.**
  This matches CLAUDE.md §8's stance that the rules are externally sourced and
  configurable, subject to stop-and-review on conflict.
- Do not conflate with Jupiter's own trading-PnL leaderboard
  (`jup.ag/prediction/leaderboard`, seen in search results only, not fetched).
  **Status: Unverified**

## 2. Permanent methodology (submission format and scoring)

Source: [jupcallers.fun/methodology](https://jupcallers.fun/methodology) — accessed
2026-08-05 (key claims independently re-fetched the same date). **Status: Verified**
unless noted.

- **Channel + tag:** a call is "A message in #prediction-alpha tagged `#nfa` by its
  author." Untagged messages "are never boarded"; the tag is the caller's explicit
  opt-in and may appear within 5 minutes in an adjacent message. Kalakal is stricter
  by design: CLAUDE.md §8 requires `#nfa` in the same message as the call.
- **Side:** "The side must be stated in a recognizable form."
- **Link:** a jup.ag market link pins the exact market; without one the system searches
  for the single active matching market (exactly one candidate must survive or the call
  goes to review). The season page calls the link "recommended but not required."
  Kalakal's always-include-link rule is stricter — a safe project choice, not a program
  requirement.
- **Entry price:** "The entry is the **ask** on the Jupiter order book at the message's
  own timestamp — the price the buy button charges, not the midpoint." Late-captured
  calls fall back to midpoint; calls posted after an outcome was already decided are
  never graded from that outcome.
- **Stated price:** not required; a written price is noted when it diverges but never
  overrides the market.
- **Scoring:** flat 1-unit stake; loss = −1u; win pays implied odds (entry 40¢ →
  +1.5u; 80¢ → +0.25u). Profit ranks the board; Yield is the skill signal. Main-board
  "Ranked" status needs 10 graded calls (distinct from season qualification).
- **Early close:** reply `#close` to the original call; exit at the contract price at
  the close post.
- **Duplicates:** "One call per (message, market, side)."
- **Integrity:** append-only records; review queue for ambiguity; 48-hour dispute
  window.

## 3. Season 1 parameters

Source: [jupcallers.fun/season](https://jupcallers.fun/season) — accessed 2026-08-05.
**Status: Verified** unless noted.

- **Timeline:** launch July 22, 2026 12:00 UTC through September 30, 2026 (UTC); "only
  calls resolved by Sep 30, 23:59 UTC count."
- **Qualification:** at least 15 resolved season calls.
- **Entry band:** counted calls enter between 10¢ and 90¢ (outside the band the call
  simply doesn't count).
- **Weekly cap:** first 30 calls of each season week count; callers know at posting
  time whether a call counts. The timezone defining a "season week" is not stated.
  **Status: Unverified (detail)**
- **Markets:** "Event markets on Jupiter only. Rapid-cycle up/down markets (like
  Bitcoin Up/Down 15m) don't count."
- **Prizes:** pool scales $1,000 → $5,000 (at 100 qualified); paid places 7 → 20;
  Call of the Week and Call of the Season awards exist.

## 4. Permanent vs. season-specific

The site splits capture/pricing/grading/duplicate rules into `/methodology` (no
band/cap/season content) and the band, weekly cap, 15-call minimum, event-only rule,
prizes, and dates into `/season`, which says scoring is "Unchanged from the main
board." Reading: methodology = permanent layer; Season 1 items = parameters.
**Status: Inference** (structural; never stated in so many words).

## 5. Automation

- Neither page states any policy about bots or automation posting Discord calls; the
  only "No bot" line concerns the Call-of-the-Week "Post on X" button. Capture is
  passive ("All #nfa-tagged messages in #prediction-alpha are captured continuously").
  **Status: Verified (absence of an automation policy)**
- Jupiter Discord's own server rules on self-bots/automation were not accessible.
  **Status: Unverified.** Kalakal's design (agent drafts text; human posts manually,
  per CLAUDE.md §8) does not depend on this either way.

## 6. Configured-rule verification map

| Project-configured rule (CLAUDE.md §8) | Verification (2026-08-05) |
|---|---|
| 10¢–90¢ counted entry band | Verified — Season 1 rule |
| First 30 calls per season week | Verified — Season 1 rule (week-boundary timezone unspecified) |
| ≥15 resolved season calls to qualify | Verified — Season 1 rule (main board "Ranked" needs only 10) |
| Event markets only | Verified — Season 1 rule; rapid-cycle up/down excluded |
| Season cutoff 2026-09-30 23:59 UTC | Verified — resolution cutoff for counted calls |
| `#nfa` required | Verified — tracker allows an adjacent message within 5 min; Kalakal requires same-message (stricter) |
| `#prediction-alpha` channel | Verified — permanent methodology |
| Ask-at-posting-timestamp entry price | Verified — permanent methodology (midpoint fallback if captured late) |
| One call per (message, market, side) | Verified — permanent methodology |

## Conclusion

The project's configured Jup Callers rules are **compatible with the published
methodology and Season 1 pages, with intentionally stricter project rules**; no
stop-and-review conflict exists today. Material caveats: (1) jupcallers.fun appears
community-run — no official Jupiter source acknowledges it, so rules must remain
externally sourced, configurable, and re-checked near posting time; (2) two project
rules are deliberately stricter than the tracker's: Kalakal always requires the exact
jup.ag market link (tracker: recommended but not required) and requires `#nfa` in the
same message (tracker: an adjacent message within 5 minutes suffices); (3) no
automation policy is published by the program, and the Kalakal draft-only design
sidesteps the question.

**Remaining uncertainty:** operator identity and official status of jupcallers.fun;
season-week timezone; whether in-Discord announcements supersede the site (Discord not
fetchable); Jupiter Discord rules on automation.
