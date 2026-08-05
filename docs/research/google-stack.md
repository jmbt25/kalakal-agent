# Research: Google Stack — Gemini, Agent Framework, Cloud, Policy

Phase 2 evidence capture for Kalakal Agent. Access date for all evidence: 2026-08-05.
Status labels: `Verified` (source fetched, states this), `Inference` (reasoned from
verified facts), `Unverified` (not confirmed), `Conflicting` (sources disagree,
preserved). Evidence was gathered via live web fetches of official Google, Devpost,
and framework documentation on the access date. Research only: no Google Cloud
project, resource, service account, secret, API key, billing account, or deployment
was created, and no application code was written.

Naming note (affects several citations): `cloud.google.com/...` documentation URLs
now 301-redirect to `docs.cloud.google.com/...`, and the Vertex AI product surface is
being rebranded — one direct fetch showed the product page header "Gemini Enterprise
Agent Platform (formerly Vertex AI)" (page body truncated), and current doc titles use
the new name. Old `vertex-ai` URLs still resolve. The hackathon rules say "Vertex AI";
this document uses "Vertex AI (Agent Platform)" for that path. **Status: Verified
(redirects, doc titles); product-page wording: Verified via one fetch, second fetch
truncated.**

## 1. Hackathon requirement mapping

Source unless noted: [Official Rules](https://allthingsagentichackathon.devpost.com/rules)
— "All Things Agentic Hackathon: Rules" — accessed 2026-08-05 (re-fetched this phase;
matches [hackathon.md](hackathon.md)). **Status: Verified.**

Mandatory technology clause, quoted:

> "Mandatory for all categories: 1) Gemini 3.5 or newer accessed through Gemini API
> or Vertex AI, 2) AND at least one Google Agent Framework: Google ADK, GenAI SDK,
> Antigravity SDK or GenKit 3) AND at least one Google Cloud infrastructure service
> (such as Cloud Run, Cloud SQL, Firestore, GKE, Pub/Sub)."

Mapping of each requirement:

| Requirement | Mandatory? | Primary documentation | Notes |
|---|---|---|---|
| Gemini 3.5 or newer via Gemini API or Vertex AI | Mandatory | [Gemini API models](https://ai.google.dev/gemini-api/docs/models) | Qualifying model set in §2. **Verified** |
| One Google Agent Framework (ADK, GenAI SDK, Antigravity SDK, GenKit) | Mandatory (any one) | See §3 per framework | "GenAI SDK" is explicitly enumerated as qualifying even though Google describes it as a client SDK, not an agent framework — **Verified (clause) / Inference (optics risk)** |
| One Google Cloud infrastructure service | Mandatory (any one; list is examples, "such as") | [Cloud Run](https://cloud.google.com/run), [Firestore](https://cloud.google.com/firestore) | Whether Vertex AI alone counts as "infrastructure" is unresolved — **Unverified**; mooted by using Cloud Run + Firestore (§4). **Inference** |
| ≤4-minute demo video: "an unedited, live execution of the agent performing its task" and "demonstrate the backend is running on Google Cloud (ie: Google Cloud Console, Cloud Run dashboard, Vertex AI logs, URL of .run, etc)"; public on YouTube/Vimeo; English or subtitled | Mandatory | Official Rules §"Submission Requirements" | **Verified** |
| Published content, #AllThingsAgenticHackathon social post, Gemma/Veo/Lyria integration | Optional bonus only | Official Rules | **Verified** |

The [resources page](https://allthingsagentichackathon.devpost.com/resources)
("All Things Agentic Hackathon: Resources", accessed 2026-08-05, **Verified**) links:
Gemini API / AI Studio (https://ai.google.dev), ADK
(https://google.github.io/adk-docs — observed 301 → https://adk.dev/), Antigravity
SDK (https://antigravity.google/docs/sdk — returned HTTP 404 to our fetcher;
https://antigravity.google/docs/sdk/overview serves full docs — **Conflicting** only
as to the exact link), Genkit (https://firebase.google.com/docs/genkit; current home
is https://genkit.dev/), Cloud Run, Firestore, and Gemini Enterprise Agent Platform
docs. It adds no extra requirements. **Status: Verified.**

Two rules findings new in this phase (both quoted from the Official Rules, accessed
2026-08-05, **Verified**), with consequences recorded in
[feasibility.md](feasibility.md) §9:

- **Third-party terms are binding on the submission**: "Third-Party Integrations: If
  a Project integrates any third-party SDK, APIs, data and/or any information
  belonging to a third party, Entrants must be authorized to use these third-party
  tools and information in accordance with any terms and conditions or licensing
  requirements of the tool." This couples the unresolved Jupiter license questions
  ([jupiter-prediction-markets.md](jupiter-prediction-markets.md) §5) to submission
  validity, not just platform risk. **Inference (consequence).**
- **US-law overlay on the demo**: no part of the submission may contain anything
  "unlawful, or otherwise in violation of or contrary to all applicable federal,
  state, or local laws and regulations in any country, state or applicable territory
  where you created the video and in the United States" — US law applies to the
  submission content regardless of entrant location. **Verified (clause).**

## 2. Gemini model selection

Primary sources, all accessed 2026-08-05: [Models](https://ai.google.dev/gemini-api/docs/models)
("Models | Gemini API"), per-model pages, [Pricing](https://ai.google.dev/gemini-api/docs/pricing),
[Rate limits](https://ai.google.dev/gemini-api/docs/rate-limits),
[Structured output](https://ai.google.dev/gemini-api/docs/structured-output),
[Function calling](https://ai.google.dev/gemini-api/docs/function-calling),
[Thinking](https://ai.google.dev/gemini-api/docs/thinking),
[Changelog](https://ai.google.dev/gemini-api/docs/changelog),
[Deprecations](https://ai.google.dev/gemini-api/docs/deprecations),
[Gemini API Additional Terms](https://ai.google.dev/gemini-api/terms).

### 2.1 What "Gemini 3.5 or newer" comprises today

- The family was launched as "Gemini 3.5: frontier intelligence with action"
  (blog.google, May 19, 2026); Gemini 3.6 Flash, 3.5 Flash-Lite, and 3.5 Flash Cyber
  followed on July 21, 2026
  ([launch post](https://blog.google/innovation-and-ai/models-and-research/gemini-models/gemini-3-5/),
  [July post](https://blog.google/innovation-and-ai/models-and-research/gemini-models/gemini-3-6-flash-3-5-flash-lite-3-5-flash-cyber/),
  accessed 2026-08-05). **Status: Verified**
- Exactly **three GA text/reasoning models satisfy the mandate** on the Gemini API
  model list: `gemini-3.5-flash`, `gemini-3.5-flash-lite`, `gemini-3.6-flash` (model
  IDs verbatim from the models page). **Status: Verified**
- **No Gemini 3.5 or 3.6 Pro exists.** The May launch post said 3.5 Pro would roll
  out "next month"; on 2026-08-05 no official model list contains it. The only
  Pro-tier reasoning model is `gemini-3.1-pro-preview` — below 3.5 and Preview, so it
  fails the mandate. **Status: Verified (absence on official lists); Conflicting
  (Google's May promise vs. current absence — preserved).**
- Excluded 3.5-era entries: `gemini-3.5-live-translate-preview` (speech-to-speech
  translation only, Preview) and "Gemini 3.5 Flash Cyber" ("exclusively available to
  governments and trusted partners"). **Status: Verified**

### 2.2 Candidate records

All three candidates share: input limit 1,048,576 tokens; output limit 65,536 tokens;
structured output and function calling both marked Supported on the model page
capability tables; thinking control via `thinking_level`
(minimal/low/medium/high); free tier on the Gemini Developer API; "No shutdown date
announced" on the deprecations page. **Status: Verified** (per-model pages, thinking
page, pricing page, deprecations page, accessed 2026-08-05).

| Field | `gemini-3.6-flash` | `gemini-3.5-flash` | `gemini-3.5-flash-lite` |
|---|---|---|---|
| Status | GA 2026-07-21; models page: "Our latest model" | GA 2026-05-19 | GA 2026-07-21 |
| Price / 1M tokens (standard) | $1.50 in / $7.50 out | $1.50 in / $9.00 out | $0.30 in / $2.50 out |
| Batch/Flex | $0.75 / $3.75 | $0.75 / $4.50 | $0.15 / $1.25 |
| Default `thinking_level` | medium | medium | minimal |
| Knowledge cutoff | Not stated (**Unverified**) | January 2025 (**Verified**) | Not stated (**Unverified**) |

Additional per-model evidence, accessed 2026-08-05:

- `gemini-3.6-flash` — changelog: "improved token efficiency and code/agentic
  planning capabilities at a lower price point than 3.5 Flash"; the July launch post
  claims ~17% fewer output tokens than 3.5 Flash (marketing claim, not independently
  benchmarked); it is the model used in the current structured-output and
  function-calling doc examples; the
  [latest-model page](https://ai.google.dev/gemini-api/docs/latest-model) designates
  `gemini-3.6-flash` and `gemini-3.5-flash-lite` "generally available (GA) and ready
  for production use". **Status: Verified**
- Vertex AI (Agent Platform) path: all three are listed on the Cloud side, at the
  same standard prices, with cached-input pricing ($0.15/M for the Flash models,
  $0.03/M for Flash-Lite) and Priority tier at 1.8x
  ([Vertex generative-AI pricing](https://cloud.google.com/vertex-ai/generative-ai/pricing),
  accessed 2026-08-05). **Status: Verified**
- Regional availability: a **global endpoint** exists on the Cloud path ("directs
  traffic to a global entry point that dynamically routes your request to a region
  with available capacity"; no data-residency support), plus regional endpoints. The
  per-model region matrix could not be read (docs pages returned navigation only).
  **Status: Verified (global endpoint); Unverified (region matrix).**

### 2.3 Quotas, data use, determinism

- **Rate limits are no longer published per model** for interactive use: "Rate limits
  depend on a variety of factors (such as your usage tier) and can be viewed in
  Google AI Studio." Usage tiers: Free; Tier 1 (billing linked); Tier 2 ($100 spent +
  3 days); Tier 3 ($1,000 spent + 30 days), with per-tier spend caps described on the
  page. Only Batch enqueued-token quotas are published per model. Actual limits must
  be read from the AI Studio dashboard after choosing a tier.
  ([Rate limits](https://ai.google.dev/gemini-api/docs/rate-limits), 2026-08-05.)
  **Status: Verified (structure); Unverified by design (numbers).**
- **Data use** ([Gemini API terms](https://ai.google.dev/gemini-api/terms), effective
  2026-03-23, accessed 2026-08-05, **Verified**): Unpaid Services — "Google uses the
  content you submit to the Services and any generated responses to provide, improve,
  and develop Google products and services", with human review possible; "Do not
  submit sensitive, confidential, or personal information to the Unpaid Services."
  Paid Services — Google "doesn't use your prompts ... or responses to improve our
  products"; ~30-day abuse-monitoring retention. Vertex path: "Google will not use
  Customer Data to train or fine-tune any AI/ML models without Customer's prior
  permission or instruction"
  ([Service Specific Terms](https://cloud.google.com/terms/service-terms) §18,
  accessed 2026-08-05, **Verified**). Consequence: the primary deployed path is
  Vertex AI (§4.3); the Developer API free tier is acceptable only for local,
  fixture-only development, and anything non-public or sensitive requires paid
  service status on whichever path is used. **Inference.**
- **Structured output**: the current API shape configures a `response_format` object
  carrying `mime_type: application/json` with the schema in a `schema` field
  (superseding older `responseSchema` usage); a subset of JSON Schema is supported;
  "Very large or deeply nested schemas may be rejected"; docs instruct apps to
  "always validate values in your application". Combining structured output with
  tools/function calling on Gemini 3-series models is flagged as a preview feature.
  ([Structured output](https://ai.google.dev/gemini-api/docs/structured-output),
  2026-08-05.) **Status: Verified**
- **Function calling**: modes `auto`/`any`/`none`/`validated`; parallel and
  compositional calling. ([Function calling](https://ai.google.dev/gemini-api/docs/function-calling),
  2026-08-05.) **Status: Verified**
- **Determinism**: the changelog (2026-07-21 entry) deprecates `temperature`,
  `top_p`, and `top_k` for the latest Gemini models; `thinking_level` replaces
  `thinking_budget`; no seed or reproducibility guarantee is documented.
  Reproducibility for CLAUDE.md §7 therefore cannot come from sampler settings — it
  must come from the pipeline: pinned model ID, versioned prompts, recorded inputs
  and timestamps, schema validation, and app-side range checks. **Status: Verified
  (deprecation, thinking_level); Unverified/absent (seed); Inference (consequence).**
- `gemini-3.5-flash`'s stated January 2025 knowledge cutoff predates current Dota 2
  rosters and tournaments by ~18 months — model memory must never be a data source;
  all match/market facts must arrive via the data pipeline (already mandated by
  CLAUDE.md §7). **Status: Verified (cutoff); Inference (consequence).**
- Lifecycle risk: all three are GA with no shutdown date, but churn is fast (3.6
  Flash shipped 9 weeks after 3.5 Flash and immediately became the docs' default;
  `gemini-3.1-flash-lite` already lists an earliest-possible shutdown of 2027-05-07).
  Pin exact IDs; record model version per decision. **Status: Verified (dates);
  Inference (risk).**

### 2.4 Model recommendation

- **Primary: `gemini-3.6-flash`** — GA, Google's own "latest ... ready for
  production" designation, full structured-output + function-calling + thinking
  support, cheapest Flash-tier output ($7.50/M), used throughout current doc
  examples. **Inference from verified facts.**
- **Fallback: `gemini-3.5-flash`** — same capability surface and limits; drop-in
  swap; slightly higher output price. **Inference.**
- Optional cost floor for mechanical extraction/parsing steps:
  `gemini-3.5-flash-lite` ($0.30/$2.50), still mandate-compliant. **Inference.**
- Do not plan around `gemini-3.1-pro-preview` (fails the mandate) or an unreleased
  3.5 Pro (no committed date). **Inference from verified facts.**

## 3. Agent-framework comparison

Only the four hackathon-permitted options are compared. All evidence accessed
2026-08-05.

### 3.1 Google ADK (Agent Development Kit)

Docs: https://adk.dev/ (301 target of the resources page's
https://google.github.io/adk-docs). **Verified** unless noted.

- **Languages/maturity**: Python, TypeScript, Go, Java, Kotlin; ADK 2.0 GA;
  self-described "open-source agent development framework". Python package
  `google-adk` 2.6.2 (released 2026-08-04, Python 3.10–3.14, ~bi-weekly releases)
  ([PyPI](https://pypi.org/project/google-adk/)).
- **Tools/schemas**: tools are plain Python functions passed to `Agent(tools=[...])`;
  `LlmAgent` supports Pydantic `output_schema`/`input_schema`; `output_key` persists
  the final response into session state
  ([LLM agents](https://adk.dev/agents/llm-agents/)). Caveat: combining
  `output_schema` with tools in one request is "only supported by specific models,
  including [Gemini 3.0]" — mitigated here since the mandate requires Gemini 3.5+.
  **Verified (caveat); Inference (mitigation).**
- **Workflows**: `SequentialAgent`, `LoopAgent`, `ParallelAgent`; ADK 2.0 adds
  graph-based and dynamic workflows ([Workflow agents](https://adk.dev/agents/workflow-agents/)).
- **State/sessions**: `SessionService` (in-memory for dev; database/cloud options for
  persistence) plus `MemoryService` ([Sessions](https://adk.dev/sessions/)).
- **Eval/tracing**: `adk eval`, evalsets, pytest integration (Python only);
  OpenTelemetry tracing ([Evaluate](https://adk.dev/evaluate/),
  [Observability](https://adk.dev/observability/)).
- **Human approval**: built-in Tool Confirmation — `FunctionTool(...,
  require_confirmation=True)` or `tool_context.request_confirmation(hint=...,
  payload=...)`; supports dynamic thresholds. **Marked Experimental**, with "known
  limitations regarding `DatabaseSessionService` and `VertexAiSessionService`
  compatibility" ([Tool confirmation](https://adk.dev/tools-custom/confirmation/)).
- **Deployment**: first-class `adk deploy cloud_run`, or plain `gcloud run deploy`
  with `get_fast_api_app()`; "does not require Vertex AI Agent Engine — Cloud Run
  functions standalone". Agent Engine has been renamed/superseded by the optional,
  paid Agent Runtime ([Deploy](https://adk.dev/deploy/),
  [Cloud Run](https://adk.dev/deploy/cloud-run/)).
- **Local dev**: `adk create` / `adk run` / `adk web` dev UI
  ([Python quickstart](https://adk.dev/get-started/python/)).
- **Single-agent viability**: the quickstart's complete app is one `Agent` with
  function tools in one `agent.py`; multi-agent constructs are optional. **Verified.**
- **Lock-in**: moderate — Agent/Runner/SessionService abstractions and project
  layout; the model layer is `google.genai` underneath; deployment is a plain
  container. **Inference.**
- **Qualifies as agent framework**: yes — first-listed in the rules; Google's own
  wording calls it one. **Verified.**

### 3.2 Google Gen AI SDK

Docs: https://ai.google.dev/gemini-api/docs/libraries,
https://googleapis.github.io/python-genai/. **Verified** unless noted.

- **Languages/maturity**: official libraries for Python (`google-genai` 2.16.0,
  released 2026-07-30), JS/TS, Go, Java, C#; GA since May 2025; legacy SDKs
  deprecated 2025-11-30.
- **Tools/schemas**: Pydantic or raw JSON Schema for structured output; function
  calling with a developer-run tool loop ("The model doesn't execute the function
  itself").
- **Workflows/state/eval/HITL/deployment**: none as framework features — it is a
  model client library; orchestration, persistence, evaluation, approval gates, and
  deployment are all hand-built application code. **Verified (docs describe an SDK);
  Inference (absence claims).**
- **Qualifies**: by the rules' explicit enumeration, yes; by Google's own wording it
  is an SDK, not an agent framework — the weakest judging position under
  "Architectural Discipline & Tech Stack". **Verified (wording) / Inference (optics).**

### 3.3 Genkit

Docs: https://genkit.dev/ (resources page links the Firebase docs URL). **Verified**
unless noted.

- **Languages/maturity**: TypeScript GA, Go GA, **Python Preview** — the Python
  get-started warns it is early ("production use is not yet recommended"); labels
  across Google surfaces disagree (Alpha/Beta/Preview). **Verified (not GA);
  Conflicting (exact label).**
- **Tools/schemas**: `ai.defineTool()` with Zod schemas (TS); typed flows;
  Genkit runs the tool loop (`maxTurns`).
- **Workflows**: flows are typed, streamable, auto-traced functions; control flow is
  ordinary code.
- **Eval/tracing**: strong — built-in evaluators, `eval:flow`, Dev UI with trace
  visualization ([Evaluation](https://genkit.dev/docs/evaluation/)).
- **Human approval**: **Interrupts** ("pause the LLM generation-and-tool-calling loop
  to return control back to you"), Beta, **documented for TypeScript only**
  ([Interrupts](https://genkit.dev/docs/interrupts/)).
- **Deployment**: Cloud Run documented first-class; Firebase not required
  ([Cloud Run](https://genkit.dev/docs/cloud-run/)).
- **Fit constraint**: first-class Genkit means TypeScript; the natural data/modeling
  stack for this project is Python. **Inference.**

### 3.4 Antigravity SDK

Docs: https://antigravity.google/docs/sdk/overview (the resources page's exact
/docs/sdk URL returned 404 to our fetcher). **Verified** unless noted.

- **Exists officially**: announced 2026-05-19 as a **Research Preview** — "a Python
  library that gives you programmatic access to Google's premier Antigravity coding
  agent" ([blog](https://antigravity.google/blog/introducing-google-antigravity-sdk)).
- **Maturity**: Python only; PyPI `google-antigravity` 0.1.9 (2026-07-29), classifier
  "3 - Alpha"; ships compiled runtime binaries; Apache-2.0
  ([PyPI](https://pypi.org/project/google-antigravity/)).
- **Features**: coding-agent harness (file I/O, code editing, shell execution),
  custom tools, MCP, Pydantic structured output, human-in-the-loop pauses,
  session persistence, "deny by default" safety policies.
- **Gaps**: no documented cloud deployment path; no eval harness found.
  **Verified (absence on overview); Unverified (whole docs tree).**
- **Fit**: a real, enumerated framework, but alpha, coding-harness-oriented (shell
  execution is the opposite of what a finance-adjacent policy-gated agent wants), and
  without a deployment story — a risky base. **Inference.**

### 3.5 Framework recommendation

**Recommended: Google ADK, Python (`google-adk` 2.x), single-agent design, deployed
to Cloud Run.** It is the smallest option that satisfies every project need (typed
Pydantic schemas, function tools, workflow constructs if needed, sessions, eval,
OpenTelemetry tracing, `adk web` local dev, documented standalone Cloud Run deploy)
while unambiguously counting as a "Google Agent Framework". **Inference from
verified facts.**

- **Multi-agent design is not necessary.** Nothing in the rules or ADK requires it; a
  single `LlmAgent` inside a deterministic pipeline matches CLAUDE.md §7's
  separation of prediction, comparison, policy, and explanation better than agent
  proliferation. **Inference.**
- ADK's Tool Confirmation is Experimental — treat it as UI convenience only. The
  binding human-approval gate stays in Kalakal's own policy layer outside the LLM
  loop, as CLAUDE.md §4/§6 already require. **Verified (experimental status);
  Inference (design consequence).**
- The Gen AI SDK (`google-genai`) is present underneath ADK regardless and can be
  cited truthfully in the submission; relying on it alone as the "framework" is the
  weakest judging position. Genkit is the runner-up only if the project switched to
  TypeScript; Antigravity SDK is not recommended. **Inference.**

## 4. Google Cloud architecture

All evidence accessed 2026-08-05; `cloud.google.com/...docs` URLs redirect to
`docs.cloud.google.com`.

### 4.1 Selected minimal architecture

Cloud Run (one service or job) + Firestore (audit/state) + Secret Manager
(conditional — for external API credentials once those integrations exist; Vertex AI
itself uses service identity, not a stored key) + built-in Cloud Logging/Monitoring +
optionally one Cloud Scheduler cron. Everything else is excluded (§4.7).

- **Cloud Run**: services (HTTPS endpoint on a unique `*.run.app` subdomain,
  scale-to-zero) vs jobs (run-to-completion, console Execute button, schedulable)
  ([What is Cloud Run](https://docs.cloud.google.com/run/docs/overview/what-is-cloud-run),
  [Create jobs](https://docs.cloud.google.com/run/docs/create-jobs)). **Verified**
- **Deploy from source**: `gcloud run deploy --source .` builds via buildpacks +
  Cloud Build "without having to install Docker on your machine" — the
  lowest-friction path from a Windows 11 dev machine
  ([Deploying from source](https://docs.cloud.google.com/run/docs/deploying-source-code)).
  **Verified (mechanism); Inference (Windows-friction judgment).**
- **Container state is not durable**: the writable filesystem "is an in-memory file
  system" and "Data written to the file system doesn't persist when the instance
  stops" — SQLite-in-container is ruled out for the audit log; Firestore is on the
  documented durable-storage shortlist
  ([Container contract](https://docs.cloud.google.com/run/docs/container-contract),
  [Storage options](https://docs.cloud.google.com/run/docs/storage-options)).
  **Verified; Inference (consequence).**
- **Firestore (Native, Standard edition)** free quota: 1 GiB storage, 50,000
  reads/day, 20,000 writes/day, 20,000 deletes/day, 10 GiB/month egress, first
  database in the project only
  ([Quotas](https://docs.cloud.google.com/firestore/quotas)). An append-style
  decision/audit log for a single-user agent (tens of decisions/day) sits orders of
  magnitude below this. CLAUDE.md requires an auditable record of every decision, so
  persistent state is genuinely required — Firestore is the smallest durable option
  with a local emulator. **Verified (quotas); Inference (fit).**
- **Secret Manager**: free tier "6 active secret versions per month" + 10,000 access
  operations; Cloud Run integration as env vars (version-pinned) or mounted volumes;
  runtime SA needs `roles/secretmanager.secretAccessor`
  ([Free tier](https://docs.cloud.google.com/free/docs/free-cloud-features),
  [Secrets on Cloud Run](https://docs.cloud.google.com/run/docs/configuring/services/secrets)).
  Secret Manager is conditional: Vertex AI model access authenticates via service
  identity/ADC (§4.3), so no model-access key exists to store; adopt Secret Manager
  when external API credentials (Dota data sources, a Jupiter API key) are actually
  introduced — a handful of credentials sits within the free tier.
  **Verified (mechanics); Inference (fit).** Constraint from CLAUDE.md §4: Secret Manager may
  hold ordinary API credentials only — never wallet key material, which must never
  reach Google Cloud at all. **Inference (application of project rule).**
- **Logging/Monitoring**: automatic for Cloud Run — request logs and stdout/stderr
  "no setup or configuration required"; structured JSON on stdout becomes
  `jsonPayload`; Metrics tab auto-populated; first 50 GiB/month of logs free
  ([Logging](https://docs.cloud.google.com/run/docs/logging),
  [Monitoring](https://docs.cloud.google.com/run/docs/monitoring),
  [Free tier](https://docs.cloud.google.com/free/docs/free-cloud-features)).
  **Verified**
- **Cloud Scheduler**: 3 free jobs per billing account, $0.10/job/month after;
  Scheduler can invoke a Cloud Run job/service directly via OAuth with a
  `roles/run.invoker` service account — **no Pub/Sub needed**
  ([Scheduler pricing](https://cloud.google.com/scheduler/pricing),
  [Jobs on a schedule](https://docs.cloud.google.com/run/docs/execute/jobs-on-schedule)).
  For the demo, manual triggering suffices; one cron is optional. **Verified;
  Inference (demo choice).**

### 4.2 Local-to-cloud flow (described only; nothing was executed or created)

1. Local-first development on Windows 11: single small HTTP service (or CLI
   entrypoint for a job) run against the Firestore emulator
   (`gcloud emulators firestore start`, `FIRESTORE_EMULATOR_HOST=127.0.0.1:8080`,
   in-memory only) with Gemini via ADC user credentials against Vertex AI (or a
   Developer API key as a fixtures-only local fallback)
   ([Emulator](https://docs.cloud.google.com/firestore/docs/emulator),
   [Local testing](https://docs.cloud.google.com/run/docs/testing/local)). **Verified**
2. One-time cloud setup: project → billing (free trial if eligible) → enable Cloud
   Run/Cloud Build/Firestore/Vertex AI APIs → Firestore database (demo region,
   §4.5) → dedicated least-privilege service account → budgets + spend caps
   (+ Secret Manager only once external API credentials exist).
3. Deploy: `gcloud run deploy kalakal-agent --source . --region <region>
   --service-account <sa>` (region: us-central1 is technically workable for the
   fixtures-only demo; any live-Jupiter environment's region is TBD — §4.5), with
   `--set-secrets` version-pinned once secrets exist; min-instances=0,
   request-based billing, max-instances 1–2 as a cost-safety baseline; require
   authentication on the endpoint to prevent drive-by request costs
   ([Cost optimization](https://docs.cloud.google.com/run/docs/tips/services-cost-optimization)).
   **Verified (mechanisms).**
4. Prove it (see §4.6).

### 4.3 Authentication

- Application Default Credentials: env var → `gcloud auth application-default login`
  user credentials → attached service account via metadata server; "your code can run
  in either a development or production environment without changing how your
  application authenticates"
  ([How ADC works](https://docs.cloud.google.com/docs/authentication/application-default-credentials)).
  **Verified**
- On Cloud Run, attach a dedicated least-privilege user-managed service account
  (default compute SA may carry Editor); "Never set `GOOGLE_APPLICATION_CREDENTIALS`
  as an environment variable on Cloud Run resources"; no service-account key files
  anywhere ([Service identity](https://docs.cloud.google.com/run/docs/securing/service-identity)).
  Likely roles: `roles/datastore.user` and `roles/aiplatform.user` (Vertex AI model
  calls), plus `roles/secretmanager.secretAccessor` once external API credentials
  exist — exact role IDs to be confirmed at implementation.
  **Verified (guidance); Inference (role list).**
- Gemini access paths: **the primary deployed path is Vertex AI (Agent Platform)**,
  called through the same `google-genai` SDK and authenticated with ADC/service
  identity — no model API key exists anywhere in the deployment. Prefer a verified
  eligible regional endpoint; use the global endpoint only after documenting its
  tradeoff (capacity-routed, higher availability, no data-residency support — §2.2).
  Local development uses ADC user credentials against Vertex AI. The Gemini
  Developer API (API-key auth) remains a fixtures-only local fallback; "Supported
  regions may differ" between the paths
  ([Migrate to Cloud](https://ai.google.dev/gemini-api/docs/migrate-to-cloud)).
  Express mode exists (API key, no billing info, free up to 90 days) as a
  low-friction on-ramp — quota specifics unverified
  ([Express mode overview](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/start/express-mode/overview)).
  **Verified (mechanics); Inference (path choice); Unverified (express quotas).**

### 4.4 Spending limits, quotas, billing alerts

- Alert-only budgets do **not** cap spending: "Setting an alerts-only budget doesn't
  automatically cap Google Cloud or Google Maps Platform usage or spending"
  ([Budgets](https://docs.cloud.google.com/billing/docs/how-to/budgets)). **Verified**
- **Spend cap budgets (Preview)** now exist and do hard-pause usage at 100% of
  budget until manually lifted; eligible services explicitly include the Gemini API,
  Gemini Enterprise Agent Platform (formerly Vertex AI), and Cloud Run; single
  project + single service per cap; monthly period; resources are paused, not
  deleted ([Spend caps](https://docs.cloud.google.com/billing/docs/how-to/budgets-spend-caps)).
  Directly usable as a **secondary guardrail**: one cap on Cloud Run, one on the
  Gemini service. **Verified; Inference (application).** Caveats: Preview status =
  Pre-GA terms, and enforcement cannot be assumed instantaneous — billing usage
  reporting is delayed (budget notifications alone "may take several hours",
  [Notifications](https://docs.cloud.google.com/billing/docs/how-to/notify)), so
  in-flight requests and enforcement/reporting latency can produce billable overage
  before a pause takes effect. Primary cost controls remain low quotas,
  `max-instances`, an authenticated endpoint, short request timeouts, bounded model
  calls, and monitoring; spend caps are the backstop, not the sole control.
  **Verified (notification latency); Inference (overage mechanism, control
  hierarchy).**
- Free trial: "$300 Welcome credit to spend over 90 days", no auto-charge, projects
  stopped at trial end without upgrade
  ([Free features](https://docs.cloud.google.com/free/docs/free-cloud-features)).
  **Verified**
- Cloud Run free tier (request-based billing), quoted from the Free Program page:
  "2 million requests per month. 360,000 GB-seconds of memory, 180,000 vCPU-seconds
  of compute time. 1 GB of outbound data transfer from North America per month."
  A search summary showed different figures (240k vCPU-s / 450k GiB-s) that could not
  be traced to page text — **Conflicting (preserved); prefer the verified row; check
  the pricing page in a browser before quoting numbers in the submission.** The
  egress allowance is stated for North America; if a non-US region is later selected
  for live-data environments (§4.5), re-check which free-tier rows apply.
  **Inference.**
- Per-unit paid prices for Cloud Run/Firestore/Logging were **not directly
  verifiable** (pricing pages truncated/JS-rendered on every fetch) — the ≈$0
  estimate below does not depend on them because usage sits far below verified free
  allowances. **Unverified (per-unit prices); Verified (free allowances).**

### 4.5 Cold starts, regions, demo reliability

- Cold starts: default min-instances=0 (scale to zero); kept-warm instances bill
  ([Min instances](https://docs.cloud.google.com/run/docs/configuring/min-instances)).
  **Verified.** A cold start is a demo-reliability risk, not a benefit. For the
  recorded take: deploy ahead of time and run a health check; warm the service
  shortly before recording (one real request), or temporarily set
  `--min-instances 1` for the recording window if the small cost is acceptable —
  the recorded agent execution remains live and unedited even when the backend is
  already warm. Restore scale-to-zero afterwards, and keep a fixtures-based fallback
  run available in case an external model or service is temporarily unavailable.
  **Inference (demo practice, on verified mechanics).**
- Region — split by mode:
  - **Fixtures-only demo** (no Jupiter calls anywhere in the pipeline): us-central1
    is technically workable — Cloud Run Tier 1 pricing, colocating Cloud Run +
    Firestore + a regional model endpoint
    ([Locations](https://docs.cloud.google.com/run/docs/locations)). **Verified
    (tiering); Inference (choice).**
  - **Any environment that accesses live Jupiter Prediction data: region TBD.**
    Jupiter's Prediction docs block US and South Korea IPs, and the broader Jupiter
    Terms of Use exclude additional localities — the preserved conflict in
    [jupiter-prediction-markets.md](jupiter-prediction-markets.md) §6, whose general
    list names, among others, the United States, the Republic of China, Singapore,
    and Myanmar. A region must therefore not be picked for geographic proximity
    (Singapore, for example, appears on the broader exclusion list); the final
    region must be checked against every applicable Jupiter restriction once
    Jupiter clarifies which rule set governs, and against the chosen Gemini model's
    verified regional availability (§2.2). VPN/proxy/routing workarounds are
    expressly prohibited by Jupiter and are not an option. This document records no
    assumption or inference about the developer's location.
    **Verified (Jupiter clauses, Phase 1); Inference (TBD posture).**

### 4.6 Demo proof of Google Cloud backend

All zero-setup console surfaces (**Verified** via the logging/monitoring docs above;
sequence is **Inference**). Deploy, health-check, and warm the service before the
take (§4.5) — the on-camera execution below is still live and unedited:

1. Cloud Run service details page: `*.run.app` URL, region, revision, Metrics/Logs
   tabs.
2. Trigger one pipeline run on camera (open the run.app URL, or click Execute on the
   Cloud Run job).
3. Logs tab: the request log and structured audit lines appear within seconds;
   optionally `gcloud beta run services logs tail` in a terminal alongside.
4. Firestore console data viewer: the new audit document appears.
5. The rules' own proof list names "Cloud Run dashboard" and "URL of .run" — this
   sequence hits both, unedited, inside 4 minutes.

### 4.7 Estimated cost and exclusions

Estimated demo-period cost: **expected ≈$0 and under $5/month for the stated
assumptions below — a bounded estimate for this workload, not a worst-case
guarantee.** Assumptions: ~50 pipeline runs/day at ~30 s on 1 vCPU/512 MiB
request-based ≈ 45k vCPU-s vs 180k free; ~200 Firestore writes/day vs 20k free; 0–4
secret versions vs 6 free; <1 GiB logs vs 50 GiB; ~100 build-minutes vs 2,500 free;
Gemini via Vertex AI at listed per-token rates ≈ $1–3 for a few million tokens (the
Developer API free tier is available for fixture-only local development). The $300
trial credit covers the expected total. Overage above the estimate is possible:
per-unit paid prices are Unverified (§4.4) and must be browser-checked before any
cost claim is published in the submission; spend-cap enforcement is not
instantaneous (§4.4); and a non-US live-data region may change which free-tier rows
apply (§4.4–4.5). Cost is bounded primarily by the §4.4 controls, not by this
estimate. **Inference from verified free-tier rows; per-unit prices Unverified.**

Explicitly excluded services: GKE (one container, no orchestration), Compute Engine
(always-on cost), Cloud SQL/AlloyDB (no free tier for this shape; Firestore
suffices), Memorystore (no cache need), Pub/Sub (Scheduler calls Cloud Run directly),
BigQuery (tiny document-shaped audit log), Load Balancer/CDN/custom domains (run.app
URL is free and is itself the proof), VPC/serverless connectors (public APIs only),
App Engine/Firebase Hosting (no separate frontend), Cloud Run functions (subsumed by
the one service), Workflows/Composer (single linear pipeline), Agent Runtime/Agent
Engine (optional, paid; Cloud Run is documented standalone). **Inference from
verified facts.**

## 5. Safety and acceptable-use policy (critical gate)

All documents captured in full via live fetch on 2026-08-05 (WebFetch plus raw-HTML
retrieval where WebFetch truncated). "Verified absence" below means the full captured
text was searched and the clause does not exist.

### 5.1 Which policies govern which path

- [Generative AI Prohibited Use Policy](https://policies.google.com/terms/generative-ai/use-policy)
  ("Generative AI Prohibited Use Policy", last modified 2024-12-17): applies to
  "the Google products and services that refer to this policy" — incorporated by
  BOTH the Gemini API Additional Terms and Google Cloud's Service Specific Terms
  §20(c), so it governs both access paths. **Verified**
- Gemini API path additionally: [Gemini API Additional Terms](https://ai.google.dev/gemini-api/terms)
  (effective 2026-03-23) sitting on the
  [Google APIs Terms of Service](https://developers.google.com/terms)
  (last modified 2021-11-09). **Verified**
- Vertex AI (Agent Platform) path additionally:
  [Google Cloud Platform ToS](https://cloud.google.com/terms) (2026-06-01),
  [AUP](https://cloud.google.com/terms/aup) (2026-06-23),
  [Service Specific Terms](https://cloud.google.com/terms/service-terms)
  (2026-07-29, §§17–20). **Verified**
- Submission overlay: [Official Rules](https://allthingsagentichackathon.devpost.com/rules)
  + [Devpost ToS](https://info.devpost.com/terms) (2025-12-05) +
  [Devpost Community Guidelines](https://info.devpost.com/legal/community-guidelines).
  **Verified**

### 5.2 The clauses that matter (quoted)

- **The only gambling clause in the entire in-scope corpus** — Google APIs ToS §4(a)
  (Gemini API path only): you may not "Promote or facilitate **unlawful** online
  gambling". The operative word is "unlawful": there is no per-se ban on
  gambling-related applications. Whether Jupiter prediction-market betting is
  "unlawful online gambling" in the relevant jurisdictions is an external legal
  question these documents cannot answer. **Verified (clause); Unverified (the
  legality fact).**
- **Automated decisions** — Prohibited Use Policy: content that "Makes automated
  decisions that have a material detrimental impact on individual rights **without
  human supervision** in high-risk domains -- for example, in employment, healthcare,
  **finance**, legal, housing, insurance, or social welfare." Human supervision is
  written into the clause itself; a human-supervised decision falls outside its
  literal text. "Individual rights" and whether wagering one's own funds impacts them
  are undefined — preserved as ambiguity. **Verified (clause); Inference (Mode 4
  mapping); Unverified (Mode 5 ambiguity).**
- **Deception cluster** — PUP: fraud/scam/impersonation clauses and "Facilitating
  misleading claims of expertise or capability in sensitive areas -- for example in
  ... finance ... **in order to deceive**" — all intent-qualified; honest, disclaimed
  probability estimates without profit guarantees do not match the text (and
  CLAUDE.md §4 already bans profit claims). **Verified (clauses); Inference
  (application).**
- **Agentic services** — Gemini API Additional Terms: "you are solely responsible for
  the actions and tasks performed by the service ... You will not automatically
  bypass any requests for human confirmation." Scope (service-generated vs
  application-level confirmations) is undefined; an autonomous mode that suppresses
  confirmations sits uncomfortably close to this sentence. **Verified (clause);
  Unverified (scope).**
- **Financial advice** — appears only as a *disclaimer*, not a use restriction:
  "Don't rely on the Services for medical, mental health, legal, financial, or other
  professional advice." No in-scope document restricts financial applications or
  personalized financial recommendations as such. **Verified (text + absence).**
- **Google Cloud**: the AUP contains **no** gambling, betting, financial-services,
  or crypto clause (verified absence); the GCP ToS restricts "cryptocurrency
  **mining** without Google's prior written approval" (§3.3(d)(iv)) — mining only —
  and defines "High Risk Activities" around physical safety (nuclear, air traffic,
  life support, weaponry), not finance. SST §20 adds: PUP incorporation (c),
  no under-18-directed services (d), healthcare restrictions (e), and a disclaimer
  that generative AI services are "not designed for or intended to meet Customer's
  regulatory, legal, or other obligations" (b). SST §18: no training on Customer
  Data without permission. **Verified**
- **Age**: Gemini API terms — 18+ developer, and no API Clients "directed towards or
  ... likely to be accessed by individuals under the age of 18"; SST §20(d) similar
  on the Cloud path. Kalakal itself is a single-user developer tool (the human posts
  Discord drafts manually), but public distribution of output into a Discord server
  whose audience includes minors is an unaddressed edge — preserved. Devpost's
  community "includes minors (13 years of age and older)". **Verified (clauses);
  Unverified (edge).**
- **Hackathon/Devpost**: rules require submission content lawful "where you created
  the video and in the United States" and third-party tools used "in accordance with
  any terms and conditions"; neither the rules nor Devpost's ToS/guidelines mention
  gambling, betting, cryptocurrency, or financial services (verified absence — the
  Phase 1 open question "is this subject matter acceptable?" remains a judgment call
  for organizers, not a written prohibition). **Verified**
- No in-scope document references any separate Google real-money-gambling policy
  (Play/Ads gambling policies are out of scope and not incorporated). **Verified
  (absence).**

### 5.3 Path comparison (Gemini API vs Vertex AI)

| Issue | Gemini API (ai.google.dev) | Vertex AI / Agent Platform (Cloud) |
|---|---|---|
| Gambling clause | "unlawful online gambling" (APIs ToS §4(a)) | None — generic illegality only |
| Prohibited Use Policy | Incorporated | Incorporated (SST §20(c)) |
| Agentic human-confirmation sentence | Present | Absent |
| Data training | Unpaid tier trains on inputs; paid tier does not | No training without permission (SST §18) |
| Age restriction | 18+ dev; no under-18-directed API Clients | No under-18-directed services (SST §20(d)) |

The Vertex path carries one fewer gambling-adjacent clause and stronger default data
governance, but path selection is not a compliance mechanism: the decisive legality
question is identical on both paths, neither path makes an unlawful activity
permissible, and choosing Vertex AI as the deployed path (§4.3) is an
authentication/data-governance decision — not a way around the Google APIs ToS
clause. Applicable law and every governing policy must be followed on either path.
**Verified (differences); Inference (assessment).**

### 5.4 Per-activity determinations

"Permitted\*" = no in-scope clause prohibits it; these policies restrict, they never
affirmatively permit. Determinations are strictly textual.

| Activity | Determination | Driving evidence |
|---|---|---|
| Historical backtesting | Permitted\* | Verified absence of any applicable restriction; no transaction, no promotion |
| Paper trading (simulated, live data) | Permitted\* | Same — simulation is reached by no clause |
| Shadow-mode analysis | Permitted\* | Same |
| Educational probability estimates with disclaimers | Permitted\* (conduct conditions) | Deception clauses are all "in order to deceive"-qualified; requires honest presentation, no profit claims (already CLAUDE.md §4) |
| Offline Discord draft generation (human posts) | **Unverified (conditional)** | A publicly posted betting call promotes the underlying betting; APIs ToS §4(a) is violated iff that betting is "unlawful" — external legality unresolved; minor-audience edge preserved |
| Human-reviewed transaction proposals (Mode 4) | **Unverified (conditional)** | Clean under every AI-specific clause (human supervision is inside the PUP clause's own wording; confirmation is the design, not bypassed); contingent solely on external gambling-law legality |
| Autonomous real-money execution (Mode 5) | **Unverified / Conflicting** | Loses the "human supervision" language; "individual rights" impact undefined; agentic no-bypass clause scope undefined; plus the same legality question. Documents neither clearly permit nor clearly prohibit |

**Bottom line of the gate:** no in-scope Google or Devpost document prohibits this
project per se — there is no gambling-application ban, no financial-AI ban, no
crypto-trading ban anywhere in the captured corpus. Every restriction that could
bite is legality-conditional ("unlawful online gambling"; "illegal activity";
"unlawful ... in the United States"). The single load-bearing unknown is the
lawfulness of Jupiter prediction-market betting in the developer's jurisdiction and,
for the submission, under US law — a question that belongs to the Jupiter research
gate ([feasibility.md](feasibility.md) §3/§7) and, if pursued to live mode, to actual
legal advice; it is not answerable from Google's documents. Mode 4's human review is
textually meaningful; Mode 5's disabled status is the posture the documents support.
These determinations are an evidence-based project reading of the quoted policy
texts — not legal permission, and not legal advice.
**Verified (per above); Inference (synthesis).**

## Failed and partial fetches (2026-08-05, not cited for content)

- cloud.google.com/run/pricing, /secret-manager/pricing, /firestore/pricing,
  /pubsub/pricing, /products/observability/pricing — truncated/JS-rendered on every
  attempt; free-tier figures were taken from the Free Program page instead; paid
  per-unit prices remain Unverified.
- docs.cloud.google.com model/region pages (Gemini Enterprise Agent Platform model
  cards, locations tables, release notes, data-governance page) — returned
  navigation scaffolding only; region matrix and Vertex-side model-card bodies
  Unverified.
- https://antigravity.google/docs/sdk — HTTP 404 (resources-page link);
  /docs/sdk/overview works.
- https://cloud.google.com/terms/aup and /terms/service-terms — WebFetch truncated;
  recovered in full via raw-HTML retrieval (cited above as Verified).
- Interactive per-model rate-limit numbers — not published; AI Studio dashboard only.
- Knowledge cutoffs for `gemini-3.6-flash` and `gemini-3.5-flash-lite` — not stated
  on fetched pages.

## 6. Proposed minimal stack (non-binding recommendation)

| Decision | Recommendation | Basis |
|---|---|---|
| Runtime language | **Python** (3.10+; ADK supports up to 3.14) | Mature ADK path; Genkit's HITL is TS-only and its Python is preview; data/modeling ecosystem. **Inference** |
| Gemini model | **`gemini-3.6-flash`** primary; **`gemini-3.5-flash`** fallback; `gemini-3.5-flash-lite` optional for cheap mechanical steps | §2.4 |
| Agent framework | **Google ADK** (`google-adk` 2.x), single agent; `google-genai` underneath | §3.5 |
| Model access path | **Primary deployed path: Vertex AI (Agent Platform)** via the `google-genai` SDK with ADC/service identity (no model API key); prefer a verified eligible regional endpoint, using the global endpoint only with its routing/no-data-residency tradeoff documented (§2.2); local dev uses ADC against Vertex AI; the Gemini Developer API remains a fixtures-only local fallback, with paid service status for anything non-public or sensitive; path choice is an auth/data-governance decision — every governing policy and applicable law applies on both paths (§5.3) | §2.3, §4.3, §5.3. **Inference** |
| Cloud services | **Cloud Run** (fixtures-only demo may use us-central1; **any live-Jupiter environment's region is TBD** pending Jupiter's geographic clarification — §4.5; scale-to-zero, request-based, max-instances capped, authenticated endpoint) + **Firestore** (audit/state) + **Secret Manager** (conditional — only once external API credentials exist; never wallet material) + built-in **Cloud Logging/Monitoring**; optional single Cloud Scheduler cron | §4.1, §4.5 |
| State/audit | Append-style decision documents in Firestore Standard free tier; every decision records sources, timestamps, model ID, prompt version (CLAUDE.md §7) | §4.1 |
| Local development | Windows 11 + gcloud CLI; ADC user credentials against Vertex AI (no key files); Firestore emulator; `gcloud run deploy --source` (no local Docker) | §4.2–4.3 |
| Demo deployment | One Cloud Run service/job; deploy + health-check + warm before the take (§4.5); unedited sequence: console dashboard → live trigger → Logs tab → Firestore document → run.app URL; fixtures-based fallback run on standby; **fixtures/paper data only** per [feasibility.md](feasibility.md) §8 | §4.5–4.6 |
| Estimated cost | Expected ≈$0 and under $5/month for the stated demo assumptions — a bounded estimate, **not a worst-case guarantee**; primary controls are low quotas, max-instances, authentication, short timeouts, bounded model calls, and monitoring; the $300 trial and Preview spend caps (enforcement not instantaneous) are secondary guardrails; unit prices unverified pending a browser check | §4.4, §4.7 |
| Excluded | GKE, Compute Engine, Cloud SQL/AlloyDB, Memorystore, Pub/Sub, BigQuery, ALB/custom domains, VPC connectors, App Engine, Workflows/Composer, Agent Runtime/Agent Engine, Antigravity SDK, Genkit | §3.4–3.5, §4.7 |

**Remaining blockers before implementation of the corresponding parts:**

1. **Jupiter license/legality questions remain the decisive gate** — unchanged from
   [feasibility.md](feasibility.md) §3.1, and now also submission-binding via the
   hackathon third-party-terms clause and US-law overlay (§1). Live modes and any
   public demo on live Prediction API data stay gated; demo on fixtures/paper.
2. **Legality of prediction-market betting** in the developer's jurisdiction and
   under US law — the single load-bearing unknown of the Google policy gate (§5.4);
   not answerable from Google documents.
3. **Verify actual quotas and current prices on the chosen path** — Cloud quotas
   for Vertex AI (the AI Studio dashboard covers only the Developer API fallback),
   and browser-check the truncated pricing pages before publishing any cost claim
   in the submission (§2.3, §4.4).
4. **Final cloud region and model availability are open** — the live-data Cloud Run
   region is TBD until Jupiter clarifies its governing geographic rules (§4.5), and
   the regional model availability matrix is unverified — confirm the chosen model
   is servable from the selected eligible region (global endpoint only with its
   tradeoff documented) before deployment (§2.2, §4.5).
5. **ADK Tool Confirmation is Experimental** — the binding human-approval gate must
   live in Kalakal's own policy layer, not in the framework primitive (§3.5).
6. **Free-tier data use** — do not send sensitive strategy/market data through the
   unpaid Gemini tier (§2.3).
7. **Mode 5 stays disabled** — Google-side clauses are ambiguous at best for
   unattended execution, and CLAUDE.md §6 preconditions are far from satisfied
   (§5.4).

Conclusion: the Google side of the project is feasible, inexpensive under the stated
demo assumptions, and — uniquely among the project's platform dependencies —
presents **no identified per-se policy prohibition** (an evidence-based project
assessment of the policy texts, not legal permission or legal advice). The smallest
compliant stack is a single-agent Python ADK app on one Cloud Run service with
Firestore, calling Gemini through Vertex AI under service identity, demoed unedited
on fixtures. This research is **sufficient to begin fixture-only implementation**
(CLAUDE.md §3 item 4); it does not close every check: model availability in the
final region, actual quotas, current prices, and the live-data region itself remain
pre-deployment checks (blockers 3–4), and Jupiter permission, geographic
eligibility, third-party licensing, and external legality remain separate blockers
(blockers 1–2).
