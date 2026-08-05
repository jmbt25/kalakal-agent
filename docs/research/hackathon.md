# Research: All Things Agentic Hackathon

Phase 1 evidence capture for Kalakal Agent. Access date for all evidence: 2026-08-05.
Status labels: `Verified` (source fetched, states this), `Inference` (reasoned from
verified facts), `Unverified` (not confirmed), `Conflicting` (sources disagree,
preserved). Evidence was gathered via live web fetches on the access date.

## 1. Identity and official page

- The hackathon is real: **All Things Agentic Hackathon**, sponsored by Google,
  administered by Devpost, online and public, $180,000 total prizes.
  - [All Things Agentic Hackathon (Devpost overview)](https://allthingsagentichackathon.devpost.com/)
    — accessed 2026-08-05 — names the hackathon, Google as organizer, online format,
    prize pool. **Status: Verified**
  - [Devpost hackathon search API](https://devpost.com/api/hackathons?search=all%20things%20agentic)
    — accessed 2026-08-05 — confirms the listing (title, URL, "Aug 04 - 31, 2026",
    organizer Google). **Status: Verified**
- Guessed URLs `allthingsagentic.devpost.com` and `all-things-agentic.devpost.com`
  returned HTTP 404 on 2026-08-05 — not the event. No separate Google-hosted landing
  page was found; the Devpost page is the primary source. **Status: Verified**

## 2. Eligibility

Source for this section: [Official Rules](https://allthingsagentichackathon.devpost.com/rules)
— accessed 2026-08-05 — **Status: Verified** unless noted.

- Age of majority in entrant's jurisdiction; internet access as of Aug 3, 2026.
- Employees/interns/contractors of Google/Devpost and immediate families ineligible.
- Geographic exclusions (quoted): "Italy, Quebec, Crimea, Cuba, Iran, Syria, North
  Korea, Sudan, Belarus, Russia and any other country designated by the United States
  Treasury's Office of Foreign Assets Control."
- Team size: no stated minimum or maximum — "You may submit your Project as an
  individual, a team, or on behalf of an organization." One member must be the
  designated Representative.

## 3. Schedule

- Submission period: Aug 3, 2026 09:00 PT → Aug 31, 2026 17:00 PT. Judging: Sep 1 →
  Oct 1, 2026. Winners announced on or around Oct 8, 2026.
  ([Official Rules](https://allthingsagentichackathon.devpost.com/rules), accessed
  2026-08-05.) **Status: Verified**
- Devpost's search API lists "Aug 04 - 31, 2026" vs. the rules' Aug 3 PT start —
  probably timezone rendering, but preserved as stated. **Status: Conflicting (trivial)**

## 4. Submission requirements

Source: Official Rules + overview page, accessed 2026-08-05. **Status: Verified.**

- One of three project categories: Taskmaster (workflow automation), Collaborative
  Partner (adaptive guidance), Fortified Enterprise Fleet (scalable multi-agent).
- URL to a hosted project or test build (credentials required if private). However,
  "Judges are not required to test the Project and may choose to judge based solely on
  the text description, images, and video provided."
- Text description covering features, tech stack, data sources, learnings.
- Code repository (private repos must grant access to `testing@devpost.com` and
  `cloudhackathons@google.com`), with "Spin-up Instructions: A step-by-step guide in
  your README.md".
- Architecture diagram.
- Demo video: "not longer than 4 minutes" (only the first 4 minutes may be evaluated);
  must show "an unedited, live execution of the agent performing its task" and
  "demonstrate the backend is running on Google Cloud (ie: Google Cloud Console, Cloud
  Run dashboard, Vertex AI logs, URL of .run, etc)"; publicly visible on YouTube or
  Vimeo; English or English-subtitled.
- Multiple submissions allowed, each "unique and substantially different."
- Optional bonus (not required): published content, #AllThingsAgenticHackathon social
  post, integration of Gemma/Veo/Lyria.

## 5. Judging criteria

Quoted from the Official Rules, accessed 2026-08-05. **Status: Verified.**

- "Innovation & Operational Utility (40%)" — real-world friction removed autonomously.
- "Architectural Discipline & Tech Stack (30%)" — decoupling, state/memory management,
  security, failure handling.
- "Demo & Production Readiness (30%)" — "Live, unedited demo, a clean architecture
  diagram, reproducible setup."

## 6. Required technologies

Quoted from the Official Rules, accessed 2026-08-05. **Status: Verified.**

> "Mandatory for all categories: 1) Gemini 3.5 or newer accessed through Gemini API or
> Vertex AI, 2) AND at least one Google Agent Framework: Google ADK, GenAI SDK,
> Antigravity SDK or GenKit 3) AND at least one Google Cloud infrastructure service
> (such as Cloud Run, Cloud SQL, Firestore, GKE, Pub/Sub)."

All three are conjunctive requirements. The Cloud list is examples, not exhaustive
("such as"). This matches CLAUDE.md §11 verbatim. The
[resources page](https://allthingsagentichackathon.devpost.com/resources) (accessed
2026-08-05, **Verified**) links ADK, Gemini API/AI Studio, and Genkit docs and adds no
extra requirements.

## 7. Prior work and originality

Quoted from the Official Rules, accessed 2026-08-05. **Status: Verified.**

- "Projects must be newly created during the Submission Period." / "The work described
  and submitted must have been built during the Submission Period."
- Standard tools, frameworks, libraries, starter templates, and AI coding assistants
  are allowed, "but must disclose any other pre-existing code or work incorporated."
- Original work solely owned by the entrant; entrants retain ownership but grant Google
  a perpetual, royalty-free, non-exclusive license for evaluation/promotion.
- Implication: the clean-room rebuild with fresh commit history and disclosure of
  incorporated pre-existing code (CLAUDE.md §2) is consistent with — and slightly
  stricter than — the official rules. **Status: Inference**

## 8. Prize tracks

Overview page, accessed 2026-08-05. **Status: Verified.** Grand Prize $50K (+$5K
credits); three track winners $20K each; Startup Excellence $20K; Individual/Hobbyist
$10K ×2; Best Architectural Design $5K ×2; Best Multimodal UX $5K ×2; Honorable
Mentions $2K ×5.

## 9. What must be demonstrable

From §4–5 above: a live, unedited agent execution on video (≤4 min, YouTube/Vimeo);
visible proof the backend runs on Google Cloud; a reproducible-setup repo with README
spin-up instructions; an architecture diagram; the three mandatory Google technologies
in actual use. **Status: Verified** (derived directly from the rules text).

## Conclusion

Verified. The event exists, the window is Aug 3–31, 2026 (we are inside it), and
CLAUDE.md §11's technology mandates and submission checklist match the official rules.
The binding constraints for this project: build during the submission period, disclose
any pre-existing code, and produce a ≤4-minute unedited live demo showing a Google
Cloud deployment.

**Open questions (organizer-only):**

- Whether a real-money prediction-market trading agent is acceptable submission subject
  matter under the rules' legality/content clauses. **Unverified** — no prohibition was
  found, but no explicit allowance either; worth asking before the live-proposal demo.
- Whether "GenAI SDK" means the Google Gen AI SDK specifically, and whether the
  "Antigravity SDK" has a canonical docs page (the resources page does not link one).
- Whether managed APIs alone (e.g., Vertex AI without a deployed service) satisfy
  "Google Cloud infrastructure service," given the video must show a backend running on
  Google Cloud.
- How strictly "newly created during the Submission Period" applies to pre-period
  design/research work (code vs. planning).
