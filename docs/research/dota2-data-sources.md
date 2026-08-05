# Research: Dota 2 Esports Data Sources

Phase 1 evidence capture for Kalakal Agent. Access date for all evidence: 2026-08-05.
Status labels: `Verified` / `Inference` / `Unverified` / `Conflicting`. Evidence from
live web fetches and one direct live API call (labeled). Sources whose terms prohibit
scraping are not proposed for scraping.

## 1. OpenDota API

- **Data:** pro matches (`/proMatches`), pro players, teams, leagues, live games, full
  replay-parsed match details. The live OpenAPI spec (v31.1.0) contains **no endpoint
  for upcoming/scheduled matches** — schedules are not covered.
  [OpenDota OpenAPI spec](https://api.opendota.com/api) — accessed 2026-08-05.
  **Status: Verified** (endpoint list); schedule absence: **Inference** from the
  verified endpoint list.
- **Freshness:** a direct call to `/proMatches` on 2026-08-05 returned same-day
  finished pro matches (e.g., Team Falcons vs Team Liquid, "1win Essence II") with
  scores and `radiant_win` — pro results land within hours or less.
  **Status: Verified (direct observation)**
- **Auth/limits/cost:** key optional; spec states a key "remove[s] monthly call
  limits" (**Verified**). Commonly cited figures — 50,000 free calls/month, 60
  req/min, premium $0.0001/call — come from secondary snippets because the primary
  pricing/blog pages were bot-blocked (403). **Status: Unverified (consistent
  secondary)**
- **Licensing:** platform code is MIT (github.com/odota); no data license or
  commercial-use statement located on a fetchable primary page. **Status: Unverified**
  — check in a browser before commercial reliance.

## 2. Valve Steam Web API (Dota 2)

- **Terms:** limit of "one hundred thousand (100,000) calls to the Steam Web API per
  day"; key must stay confidential; Valve may suspend or terminate "at any time for
  any reason, without notice." No explicit blanket commercial ban found in the ToU.
  [Steam Web API Terms of Use](https://steamcommunity.com/dev/apiterms) — accessed
  2026-08-05. **Status: Verified (quotes)**; commercial permissibility: **Inference —
  permitted but revocable at will**.
- **Key issuance:** all use requires a key and ToU agreement.
  [Steam Web API Documentation](https://steamcommunity.com/dev) — accessed 2026-08-05.
  **Status: Verified**
- **Endpoints:** `IDOTA2Match_570` (GetMatchHistory, GetMatchDetails,
  GetLiveLeagueGames, GetScheduledLeagueGames, GetTeamInfoByTeamID, …),
  `IDOTA2MatchStats_570/GetRealtimeStats`, `IEconDOTA2_570/GetTournamentPrizePool`.
  [WebAPI — Official TF2 Wiki](https://wiki.teamfortress.com/wiki/WebAPI) (Valve
  community-maintained) — accessed 2026-08-05. **Status: Verified (semi-official)**
- **Reliability caveats:** GetScheduledLeagueGames returns essentially nothing
  (tournaments don't use Valve's scheduling UI); GetLiveLeagueGames has reported
  latency and missing `server_steam_id` links needed for GetRealtimeStats — from
  dev.dota2.com threads and Dota2-Gameplay GitHub issues located via search, not
  individually fetched. **Status: Unverified (longstanding community consensus)**

## 3. STRATZ API

- GraphQL at `api.stratz.com`; GraphiQL IDE confirmed live (fetched 2026-08-05).
  Token auth. **Status: Verified (endpoint exists)**
- Tiers per the official (but dated) announcement: free with STRATZ login; Default
  2,000 calls/hour; Individual 4,000/hour & 20,000/day; higher tiers gated on referral
  traffic. [STRATZ API — Major Update](https://stratz.medium.com/stratz-api-major-update-5557335dbdfd)
  — accessed 2026-08-05. **Status: Verified (official, dated)** — current numbers
  **Unverified** (stratz.com pages 403 to automated fetches).
- Licensing/commercial/attribution terms: not retrievable. **Status: Unverified —
  must be checked manually before reliance.**

## 4. Liquipedia

- **Terms:** free public MediaWiki API (max 1 request per 2 seconds; parse actions 1
  per 30 seconds); LiquipediaDB (LPDB) API requires application/approval, max 60
  requests/hour. Content **CC-BY-SA 3.0 with required attribution**. "Automated access
  to non-API endpoints (ie, generated HTML pages) is not permitted" — HTML scraping is
  prohibited and will not be used. Custom User-Agent with contact info, gzip, and
  caching required; violations trigger automated IP bans.
  [Liquipedia API Terms of Use](https://liquipedia.net/api-terms-of-use) — accessed
  2026-08-05. **Status: Verified**
- **Coverage:** the pro-scene reference for upcoming schedules, rosters, transfers,
  and brackets — the schedule/roster data OpenDota and Valve lack.
  **Status: Inference** (well-established; not verified via fetch this session).

## 5. Commercial esports APIs

- **PandaScore:** free plan covers "Schedules, Results & Context Data" at 1,000
  req/hour, no credit card; paid stats from €400/mo; live from €1,000/mo. Key clause:
  "Stats plans are only available to customers with non betting-related usage."
  [PandaScore Pricing](https://www.pandascore.co/pricing) — accessed 2026-08-05.
  **Status: Verified.** A prediction-market trading agent is plausibly
  "betting-related," likely disqualifying use — legal-risk flag. **Status: Inference**
- **GRID Open Access:** free official Dota 2 + CS2 telemetry for pre-revenue startups,
  academics, indie devs, and fans; application + review; governed by an Open Access
  ToS PDF (not fetched). [GRID Open Access](https://grid.gg/open-access/) — accessed
  2026-08-05. **Status: Verified (page); ToS specifics Unverified**
- **Abios (Kambi):** B2B contact-sales model; no public pricing or free tier; not
  realistic for a hackathon. Fetched 2026-08-05 (via curl; WebFetch 403).
  **Status: Verified (page content)**

## 6. datdota

- All fetches failed (403 Cloudflare challenge); no terms page or sanctioned API
  confirmed. **Status: Unverified — treat as not sanctioned; excluded.**

## 7. Cross-reference: market resolution source

Jupiter's Polymarket-provided Dota 2 market rules name **dotabuff.com** as the
resolution source (with a credible-reporting fallback) — see the live market-rules
evidence in [jupiter-prediction-markets.md](jupiter-prediction-markets.md) §4. Any
result-confirmation pipeline should be aware the market resolves off Dotabuff, not off
whichever source Kalakal uses for modeling. **Status: Verified (direct observation)**

## Failed fetches (not cited for content)

docs.opendota.com, www.opendota.com/api-keys, blog.opendota.com pricing post,
stratz.com/api and knowledge-base pages, www.datdota.com, abiosgaming.com via WebFetch
(succeeded via curl), web.archive.org (blocked by tooling). All 2026-08-05.

## Conclusion and recommendation

- **(a) Schedules / rosters / tournament context — primary: Liquipedia** (MediaWiki
  API now; apply for LPDB) — free, sanctioned, CC-BY-SA with mandatory attribution and
  strict limits (cache aggressively). **Fallback: PandaScore free tier**, but only
  after clarifying its non-betting clause against this use case.
- **(b) Results / history — candidate primary: OpenDota** — technically strong
  (same-day pro results verified live), but its data-license status is unresolved; do
  not adopt it as a production dependency until that licensing question is settled.
  **Fallbacks: STRATZ GraphQL; Valve GetMatchDetails/GetMatchHistory** as the official
  first-party match-data source (100k calls/day). None of these sources is the
  market-resolution ground truth — Jupiter's cited market rules resolve off Dotabuff
  (§7) — so result confirmation must account for what Dotabuff shows, not only what
  the modeling source reports.
- **(c) Live state — primary: Valve GetLiveLeagueGames + GetRealtimeStats** (official,
  free, latency caveats — design staleness checks around it). **Fallbacks: STRATZ live
  queries; GRID Open Access** if application timing allows.

**Remaining uncertainty:** OpenDota current limits/pricing and data license; STRATZ
current limits and terms; PandaScore's "betting-related" interpretation; GRID ToS and
approval turnaround; Valve's revoke-at-will ToU (no SLA — every pipeline needs a second
source); datdota excluded.
