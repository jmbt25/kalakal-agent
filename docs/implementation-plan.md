# Kalakal Agent — Implementation Plan (Phase 3)

Companion to [architecture.md](architecture.md); governed by
[CLAUDE.md](../CLAUDE.md). Written 2026-08-05. This plan divides the work into small
vertical slices. Slices 1–11 build and demonstrate the fixture-only MVP. Slices
12–19 are post-MVP and gated; slice 16 requires the Mode 4 development-entry
criteria and slice 19 verifies the live-activation criteria, both defined in
[architecture.md §12](architecture.md#12-mode-4-entry-criteria).
**Mode 5 unattended execution is not a slice and must never be added as one.**

## Global conventions

- **CI policy.** Normal CI uses deterministic offline tests only: fake model
  clients, a fake in-memory Firestore repository, and mocked external services.
  Firestore-emulator tests are a separate, marked suite (local + optional CI job).
  No CI job may require wallet keys, real credentials beyond Google-managed CI
  identity, or perform live financial actions. No CI job ever calls Jupiter.
- **Suggested layout** (expected, refined during slice 1):
  `src/kalakal/{domain,fixtures,estimator,edge,policy,agent,explain,draft,persistence,web,observability,config}`,
  `tests/{unit,contract,integration}`, `fixtures/` (versioned synthetic scenario
  data), `pyproject.toml`.
- **Quality tooling.** `ruff` (lint + format), `mypy` (strict on `src/`), `pytest`.
  A single local check command (e.g., `make check` or a small script) runs
  lint + types + tests; CI runs the same command.
- **Definition of done per slice.** Acceptance criteria met, tests and checks green,
  no excluded item present, docs touched only where the slice says so. Completion
  claims follow CLAUDE.md §1 (required checks must pass first).
- **Commits.** One commit per slice at the suggested boundary (small slices may
  merge into one commit only if both are complete); never rewrite history.
- **Money/probability conventions** are fixed by
  [architecture.md §6.1](architecture.md#61-cross-cutting-invariants): integer
  micro-units and ppm, UTC RFC 3339 `Z` timestamps, versioned everything.

## Delivery priority and cut line

The submission deadline is 2026-08-31 17:00 PT
([research/hackathon.md](research/hackathon.md) §3). Priorities:

- **Must-have foundation — slices 1–11.** Fixture MVP, cloud deployment, audit
  record, unedited demo rehearsal, submission artifacts. This must be
  submission-ready before post-MVP work is allowed to threaten stability.
- **Competitive target — slices 12–15.** Validated transparent baseline, permitted
  live-data adapters, paper trading, live shadow mode. If every applicable gate
  passes (licensing, region, adapter contracts, model validation), the preferred
  final hackathon demo is live shadow mode — the full pipeline with no transaction
  preparation and no financial side effects. The fixture demo remains the
  guaranteed fallback.
- **Stretch target — slices 16–19.** Human-signed Mode 4. This work starts only
  after the repository already has a stable, submission-ready demo. Cut Mode 4
  first if schedule, security, data, or deployment work slips.

Target schedule — planning guidance only, never permission to skip tests or
safety gates:

| Date (2026) | Target |
|---|---|
| Aug 15 | Fixture MVP deployed (slices 1–10) |
| Aug 22 | Prediction, live-data, and shadow target (slices 12–15) |
| Aug 27 | Feature freeze |
| Aug 28–29 | Record and validate the final demo |
| Aug 30 | Complete the Devpost submission |
| Aug 31 | Contingency only |

Standing rules:

- A polished shadow-mode demo is more valuable than incomplete Mode 4
  functionality.
- Transaction and signer work is never rushed for the deadline.
- The final demo falls back to synthetic fixtures if live-data, licensing, model,
  region, or availability gates are not ready.

## Slice 1 — Python project scaffold and local quality tooling

- **Goal:** an installable, checkable, empty-but-runnable Python project skeleton.
- **Expected files:** `pyproject.toml`, `src/kalakal/__init__.py`, package
  subpackage stubs, `tests/unit/test_smoke.py`, `.gitignore`, `.env.example`
  (placeholders only), quality-check script/config (`ruff`, `mypy`, `pytest`
  configuration), README setup section update.
- **Acceptance criteria:** fresh clone → create venv → install → `ruff`, `mypy`,
  `pytest` all pass; a trivial smoke test runs; no application logic yet.
- **Tests and checks:** the smoke test; lint/type/test commands documented and
  green.
- **Explicit exclusions:** no dependencies beyond tooling + `pydantic`; no ADK, no
  Google Cloud libraries yet; no Dockerfile; no CI config unless trivial.
- **Dependencies:** none.
- **Suggested commit boundary:** one commit: "scaffold Python project and quality
  tooling".
- **Rollback:** delete the scaffold; nothing depends on it.

## Slice 2 — Domain schemas and deterministic calculations

- **Goal:** the fixture-MVP contracts of
  [architecture.md §6.2](architecture.md#62-fixture-mvp-contracts) as typed
  Pydantic schemas, plus the pure calculators: micro-unit/ppm arithmetic helpers,
  edge and fee calculator, and the demo estimator behind the estimator interface.
- **Expected files:** `src/kalakal/domain/*.py` (one module per contract group),
  `src/kalakal/estimator/{interface,demo}.py`, `src/kalakal/edge/calculator.py`,
  `tests/unit/` for each.
- **Acceptance criteria** (amended 2026-08-06 by the pre-Slice-5 alignment
  pass, which added the truthful `deterministic_stub` source variants and the
  record-layer `selection_source` attribution, and by the candidate-evidence
  audit correction, which extended `candidates_considered` to complete
  evidence bundles with derived, non-forgeable eligibility results and
  record-wide evidence-reference pools per
  [architecture.md §6.2.10](architecture.md#6210-decisionrecord)): every
  §6.2 contract exists
  with its invariants enforced
  by validators (e.g., `is_synthetic` must be true, `is_predictive` false, label
  literal, micro/ppm ranges, UTC-only timestamps); `DecisionRecord` is conditional
  by outcome path — exactly the three terminal shapes of
  [architecture.md §6.2.10](architecture.md#6210-decisionrecord) validate
  (pre-selection abstention with its three source variants, policy no-bet after
  selection and completed proceed each with their agent and
  deterministic-stub selection-source variants), model-level validators reject
  every
  inconsistent conditional-field combination, and model-invocation metadata is
  truthful — `invocation_status: "not_invoked"` records carry no model ID,
  prompt version, responses, tokens, or model tool calls (absent, never
  dummy-valued), and `deterministic_stub`-sourced records require the
  `DeterministicSelectorMetadata` block of
  [architecture.md §6.2.13](architecture.md#6213-deterministicselectormetadata)
  while every other source forbids it; `DecisionExplanation` enforces its
  source-conditional fields
  (agent: `prompt_version` + model metadata ref, no template version;
  orchestrator: `explanation_template_version`, no prompt version or model
  metadata ref); the shared `DataQuality` block of
  [architecture.md §6.2.12](architecture.md#6212-dataquality) distinguishes
  structural invalidity (the `FIXTURE_INVALID` path) from explicitly incomplete
  or conflicting evidence, with per-contract allowlists of conditionally
  optional evidence fields, exact correspondence between absent/null allowlisted
  fields and `missing_fields`, and typed, bounded conflicts; edge and fee
  calculation reproduces the documented
  [architecture.md §6.2.6](architecture.md#626-edgeassessment) worked example
  exactly in integer arithmetic (conservative ceiling division for the synthetic
  fee; out-of-range financial inputs rejected, never clamped); the demo estimator
  enforces its field-specific input boundary (typed rejection when an
  estimator-consumed field is missing or conflicted; acceptance when
  `is_complete: false` stems only from non-estimator evidence; no substituted
  defaults or invented values) and is bit-for-bit reproducible from recorded
  inputs.
- **Tests and checks:** unit tests per contract (valid, invalid, boundary),
  written as parametrized pytest cases — no new dependency (e.g., Hypothesis) is
  needed or added. Required coverage:
  - all three valid source variants of the pre-selection abstention shape
    (agent
    variant with `invocation_status: "invoked"` and full model metadata;
    orchestrator variant with reason `NO_VALID_CANDIDATES`,
    `invocation_status: "not_invoked"`, and no model metadata;
    deterministic-stub variant with at least one eligible candidate, a
    non-orchestrator reason code, `invocation_status: "not_invoked"`,
    deterministic-selector metadata, and an orchestrator-sourced
    explanation), plus the valid
    policy no-bet and completed-proceed shapes in both their agent and
    deterministic-stub selection-source variants;
  - rejection of every source/model-metadata mismatch: orchestrator source with
    a model ID, prompt version, responses, tokens, or model tool calls; agent
    source with `invocation_status: "not_invoked"`; agent source without the
    required model metadata; orchestrator source with a reason code other than
    `NO_VALID_CANDIDATES`; any variant containing a selected market or any
    post-selection artifact on shape A; every deterministic-stub shape
    structurally rejecting model IDs, prompts, responses, tokens, fallback
    data, and model tool calls; a `deterministic_stub` source without
    selector metadata; selector metadata paired with any non-stub source; a
    stub abstention with reason `NO_VALID_CANDIDATES` or zero eligible
    candidates; a stub selection or abstention with an agent-sourced
    explanation;
  - rejection of the remaining inconsistent conditional fields (e.g., a draft
    with `no_bet` or `abstained`, `completed` without a draft, shape B or C
    with `selection_source: "agent"` and `invocation_status: "not_invoked"`);
  - `DecisionExplanation` conditional-field validation in both directions for
    both sources;
  - structural invalidity vs. explicitly incomplete data: malformed types,
    invalid ranges, unknown fields, invalid timestamps, and broken provenance
    rejected outright (never representable as incompleteness), while
    structurally valid entities with declared `missing_fields`/`conflicts`
    validate; `is_complete` consistency enforced in both directions;
  - exact correspondence between absent/null allowlisted fields and
    `missing_fields`: absent-but-undeclared and declared-but-present both
    rejected; attempts to mark structural fields missing rejected; unknown and
    duplicate field paths rejected;
  - conflict typing: entries without a `field_path`, with an over-length
    `description`, or with empty or unresolvable `evidence_refs` rejected;
  - complete records with every conditionally optional estimator input present
    (`is_complete: true`); incomplete records with genuinely absent declared
    fields; conflicts-only incomplete records (all fields present, at least one
    typed conflict, `is_complete: false`);
  - demo estimator field-specific boundary: a missing estimator-consumed field
    → typed rejection; a conflict on an estimator-consumed field → typed
    rejection; only a non-estimator field missing → estimation succeeds using
    the complete estimator inputs; only a non-estimator field conflicted →
    estimation succeeds; neither rejection path substitutes defaults or invents
    replacement values;
  - fee ceiling-division behavior, including zero and boundary fee rates (`0`
    and `1_000_000` ppm accepted; out-of-range rates rejected, not clamped);
  - positive, zero, and negative gross and net edges as valid values;
  - the exact §6.2.6 example: probability `650_000` ppm, ask `600_000`
    micro-USD, fee rate `10_000` ppm → fee `6_000` micro-USD (ceiling division),
    gross edge `50_000` ppm, net edge `44_000` ppm;
  - integer-only inputs on all value paths, with float inputs rejected;
  - estimator determinism (same input → same output and same `inputs_digest`).
- **Explicit exclusions:** no post-MVP contracts (§6.3 stays documentation-only);
  no I/O, no Firestore, no model calls.
- **Dependencies:** slice 1.
- **Suggested commit boundary:** one commit: "domain contracts and deterministic
  calculators".
- **Rollback:** revert the commit; pure code with no external surface.

## Slice 3 — Synthetic fixtures and fixture repository

- **Goal:** versioned synthetic scenario data and the read-only repository that
  loads and validates it.
- **Expected files:** `fixtures/<fixture_set_version>/*.json` (or `.yaml`) for the
  scenarios recommended in [architecture.md §8.1](architecture.md#81-interface):
  clear-edge, thin-edge, conflicting-evidence, stale-data, outside-entry-band,
  no-valid-candidates;
  `src/kalakal/fixtures/repository.py`; `tests/unit/test_fixtures.py`.
- **Acceptance criteria:** all shipped fixtures pass schema validation; every
  fixture entity is clearly synthetic (invented names, synthetic link domain,
  `is_synthetic: true`, provenance + digests); each scenario deterministically
  produces its intended downstream outcome class; unknown scenario IDs produce the
  typed permanent failure.
- **Tests and checks:** a test that validates every shipped fixture file (schema +
  invariants + digest integrity); repository behavior tests (load, list, unknown
  ID).
- **Explicit exclusions:** no copied Jupiter responses, real order books,
  third-party images, real market text, or data with uncertain redistribution
  rights; no network access of any kind.
- **Dependencies:** slice 2.
- **Suggested commit boundary:** one commit: "synthetic scenario fixtures and
  repository".
- **Rollback:** revert; fixtures are data-only.

## Slice 4 — Policy and abstention engine

- **Goal:** the deterministic policy engine with final authority.
- **Expected files:** `src/kalakal/policy/{engine,config}.py`, versioned policy
  configuration (entry band, minimum net edge, freshness rules, completeness
  rules, configured Jup Callers parameters with provenance),
  `tests/unit/test_policy.py`.
- **Acceptance criteria:** engine is a pure function producing `PolicyDecision`
  with per-check results and reason codes; entry band and thresholds are versioned
  config, not constants; stale or incomplete inputs yield `no_bet` with the correct
  codes; `no_bet` is a normal result, not an exception.
- **Tests and checks:** unit tests per rule (pass, fail, boundary values in
  micro/ppm); a table-driven test covering each scenario fixture's expected policy
  outcome; config-provenance assertion (policy_version + rule source recorded).
- **Explicit exclusions:** no exposure/daily-limit rules yet (meaningless without
  positions — added with paper trading); no LLM involvement anywhere.
- **Dependencies:** slices 2–3.
- **Suggested commit boundary:** one commit: "deterministic policy and abstention
  engine".
- **Rollback:** revert; consumers arrive in slices 5–6.

## Slice 5 — Explanation and simulated-draft generation

- **Goal:** the explanation generator producing the source-aware
  `DecisionExplanation` and the deterministic `SIMULATION — DO NOT POST`
  draft template, built before the pipeline so slice 6 can assemble complete,
  valid terminal records: versioned deterministic orchestrator explanations
  (covering the eligibility-filter `NO_VALID_CANDIDATES` abstention and the
  deterministic-stub selection/abstention paths of
  [architecture.md §5.10](architecture.md#510-test-only-deterministic-selector-composition)),
  plus the agent-sourced explanation assembly contracts that slice 7 feeds
  with real validated model output later.
- **Expected files:** `src/kalakal/explain/generator.py`,
  `src/kalakal/draft/simulated.py`, `tests/unit/` for both.
- **Acceptance criteria:** `DecisionExplanation` assembled and validated for both
  sources — `source: "orchestrator"` with its deterministic
  `explanation_template_version` (and no prompt version or model metadata ref)
  for every no-model path: the pre-selection `NO_VALID_CANDIDATES` abstention
  and the deterministic-stub selection and abstention variants of
  [architecture.md §6.2.10](architecture.md#6210-decisionrecord);
  `source: "agent"` assembly with `prompt_version` and model metadata ref,
  implemented against the validated structured-output contract of
  architecture §5.2 and exercised with synthetic validated agent output in
  unit tests (no ADK, no model call — slice 7 supplies real output later) —
  with evidence refs
  resolving, length caps enforced, and numbers only from deterministic
  contracts; `SimulatedDiscordDraft` contains every mandatory element of
  [architecture.md §6.2.9](architecture.md#629-simulateddiscorddraft) in one
  message, records the producing `renderer_version` (as does the typed
  stale-refusal result), uses the synthetic link domain, and is produced iff
  the policy decision
  is `proceed`; abstention and no-bet runs produce a documented
  `DecisionExplanation` instead; every post-selection consumer (the
  post-selection explanation generator and the draft generator) verifies the
  supplied `PolicyDecision` by exact recomputation through the shared pure
  policy verifier (`verify_policy_decision`,
  [architecture.md §6.2.7](architecture.md#627-policydecision)) with explicit
  policy-configuration and duplicate-run inputs — never by digest trust or
  spot-checked observations; draft generation additionally binds the complete
  estimator basis to the considered match context and enforces truthful
  stage-time ordering (`estimate.computed_at <= edge.computed_at <=
  evaluated_at <= generated_at`, equality allowed).
- **Tests and checks:** template tests asserting each mandatory element's presence
  (label, event + side, synthetic link, ask price, confidence with non-predictive
  label, edge, `#nfa`, timestamp, expiry warning, renderer version);
  deterministic-repeatability and stable-identity-key tests — deterministic
  repeatability is not operational idempotency, and the operational
  one-draft-per-(run, market, side) enforcement is slice 6's
  ([architecture.md §6.2.9](architecture.md#629-simulateddiscorddraft));
  adversarial exact-policy-verification tests (forged digests, foreign
  configurations, foreign evidence with matching observations, mismatched
  duplicate-run status), foreign-estimator-basis rejection tests, and
  stage-time-inversion tests; explanation-validation rejection tests, including
  source-conditional field mismatches for both `DecisionExplanation` sources;
  orchestrator-template tests covering all three no-model paths
  (`NO_VALID_CANDIDATES`, stub selection, stub abstention).
- **Explicit exclusions:** no Discord API, no real `jup.ag` links, no LLM-composed
  draft text; no orchestrator or state machine (slice 6); no ADK (slice 7).
- **Dependencies:** slices 2–4.
- **Suggested commit boundary:** one commit: "explanation assembly and simulated
  draft generation".
- **Rollback:** revert; nothing depends on it until slice 6.

## Slice 6 — Deterministic pipeline without an LLM

- **Goal:** the run orchestrator and state machine executing end-to-end with
  the test-only deterministic stub selector of
  [architecture.md §5.10](architecture.md#510-test-only-deterministic-selector-composition)
  (no model calls): fixtures → validation → deterministic selection →
  estimate → edge → policy → explanation/draft (slice 5 generators) → record
  assembly, producing fully valid `DecisionRecord`s in the
  `deterministic_stub` source variants of
  [architecture.md §6.2.10](architecture.md#6210-decisionrecord).
- **Expected files:** `src/kalakal/orchestrator/{runner,states}.py`, the stub
  selector module, in-memory run
  store, `tests/unit/test_orchestrator.py`,
  `tests/integration/test_pipeline_no_llm.py`.
- **Acceptance criteria:** all states and transitions of
  [architecture.md §7](architecture.md#7-run-state-machine) implemented, strictly
  forward, terminals correct; every scenario runs to its expected terminal
  (`completed`/`abstained`/`failed`) with a truthful `DecisionRecord` or
  `RunFailure`: `completed_proceed` scenarios produce shape C and
  `policy_no_bet` scenarios shape B, both with
  `selection_source: "deterministic_stub"`, `invocation_status:
  "not_invoked"`, an orchestrator-sourced explanation, and
  `DeterministicSelectorMetadata`
  ([architecture.md §6.2.13](architecture.md#6213-deterministicselectormetadata));
  `agent_abstention`-class scenarios produce shape A with
  `abstention_source: "deterministic_stub"` and the scenario's expected
  reason code; `orchestrator_abstention` scenarios keep the unchanged
  orchestrator variant (`NO_VALID_CANDIDATES`,
  `invocation_status: "not_invoked"`, no selector metadata — decided before
  selector execution); no record on any path carries model metadata; the
  candidate-eligibility filter of
  [architecture.md §5.6](architecture.md#56-incomplete-conflicting-or-stale-input--abstention)
  implemented — only candidates with complete, non-conflicting
  estimator-consumed evidence reach the selector (staleness is never an
  eligibility reason, so the shipped `stale-data` scenario reaches
  `policy_checking` and terminates `POLICY_STALE_DATA`), and an
  all-ineligible
  candidate set terminates before any selector invocation with the
  orchestrator-variant pre-selection abstention; eligibility is computed by
  the shared pure evaluator (`derive_ineligibility_reasons`,
  [architecture.md §5.6](architecture.md#56-incomplete-conflicting-or-stale-input--abstention)) —
  never a second implementation — and every record persists exactly the
  considered-candidate evidence bundles supplied to the selector (candidate
  market, match context, market snapshot, evaluation side, derived
  eligibility result), which the record validator re-derives and enforces;
  the stub selector behaves
  exactly per architecture §5.10 — it never reads
  `expected_outcome_class` or `expected_reason_code`, never branches on
  scenario ID, operates only on the eligible candidate data it is given,
  examines candidates in documented ascending-lexicographic `market_id`
  order, abstains `CONFLICTING_EVIDENCE` on declared non-estimator
  conflicts and `INSUFFICIENT_EVIDENCE` on declared non-estimator gaps
  insufficient for selection, otherwise selects deterministically and uses
  that candidate's explicit evaluation side, and never invents
  probabilities (the demo estimator remains the only probability source);
  the evaluation clock implemented per
  [architecture.md §7.7](architecture.md#77-the-evaluation-clock-and-input-becoming-stale-during-execution) —
  effective evaluation time = the immutable `evaluation_time` origin +
  monotonic elapsed since run start, no wall-clock lookup after run start,
  the hard 60 s deadline on monotonic elapsed, policy checking receiving
  the effective time at its start with `PolicyDecision.evaluated_at`
  recording exactly that value; the
  stale-during-execution path (§7.7) reachable in a test; the orchestrator
  owns the §6.2.9 one-draft invariant — draft generation is memoized by the
  stable identity `(run_id, market_id, side)`, at most one draft is emitted
  and persisted per identity, and a later attempt with changed inputs for an
  existing identity returns the original result or fails with a typed
  conflict, never a replacement draft; before explanation assembly, draft
  assembly, and terminal-record construction the orchestrator invokes the
  shared exact policy verifier (`verify_policy_decision`,
  [architecture.md §6.2.7](architecture.md#627-policydecision)) with the
  recorded evidence, edge, policy configuration, and duplicate-run status —
  a mismatch fails the run safely as a safety-classified
  `POLICY_INVARIANT_BREACH` `RunFailure`, never a no-bet and never a
  narrated valid outcome.
- **Tests and checks:** state-machine transition tests (allowed + rejected
  transitions); per-scenario end-to-end tests asserting the truthful
  stub-source records above; eligibility-filter tests (mixed
  eligible/ineligible candidate sets expose only eligible candidates to the
  selector; an all-ineligible set produces the orchestrator-variant abstention
  with truthful `not_invoked` metadata); fake-clock tests — injected fake
  clock making elapsed time deterministic, a short-lived synthetic input
  becoming stale before `policy_checking` while inside the 60 s deadline,
  and a zero-advance run evaluating every step at exactly the supplied
  `evaluation_time` (shipped fixture outcomes reproducible); timeout test
  with a fake clock;
  idempotent memoization test (one recorded computation per market);
  one-draft idempotency tests — a repeated call for the same
  `(run_id, market_id, side)` identity returns the memoized first draft, and
  a call with changed inputs for an existing identity returns the original
  result or fails with a typed conflict, never a second draft; an
  exact-policy-verification test — a tampered or foreign `PolicyDecision`
  fails the run as a safety-classified `POLICY_INVARIANT_BREACH`, never a
  no-bet; an
  oracle-independence test proving the stub's input surface excludes the
  scenario oracle fields.
- **Explicit exclusions:** no ADK, no Vertex, no Firestore, no HTTP; the
  stub selector is test-only and structurally marked by its §6.2.13
  metadata; it is never a hidden production flag or a fallback pretending to
  be the model — slice 7 adds the agent as a separate, explicit composition
  root while this pipeline remains the clearly labeled emergency-demo
  composition (§5.10, §8.3).
- **Dependencies:** slices 2–5.
- **Suggested commit boundary:** one commit: "deterministic run pipeline and state
  machine".
- **Rollback:** revert; slice 7 composes the agent alongside this pipeline
  rather than extending the stub.

## Slice 7 — ADK/Vertex adapter with fake-model tests

- **Goal:** the bounded `LlmAgent` of
  [architecture.md §5](architecture.md#5-agent-boundaries): five read-only tools,
  structured output schema, bounds/timeouts/retries, fallback model, output
  validation and rejection, prompt templates under version control.
- **Expected files:** `src/kalakal/agent/{agent,tools,schemas,prompts/,model_client}.py`,
  fake model client for tests, `tests/unit/test_agent_validation.py`,
  `tests/integration/test_agent_fake_model.py`.
- **Acceptance criteria:** the agent becomes the primary selector composition
  through its own explicit composition root, while the slice 6 deterministic
  pipeline remains available as a separately and explicitly labeled
  emergency-demo composition (§5.10, §8.3) — separate composition roots or
  constructors, never a hidden production flag and never a fallback
  pretending to be the model, with every record truthful about which path
  ran (agent-sourced records carry `invocation_status: "invoked"` with full
  model metadata; stub-sourced records carry the §6.2.13 selector metadata
  and no model metadata); agent runs feed validated structured output into
  the slice 5 agent-sourced explanation assembly; tool surface
  is exactly the five tools (asserted by a test); the architecture §5.3 bounds
  enforced (8 tool calls, 4 turns, 15 s per model call, 45 s agent/model budget, at
  most one repair or retry, budget-guarded fallback); malformed output triggers one
  repair attempt then safety-classed rejection (`MODEL_OUTPUT_REJECTED`); selection
  outside the candidate set rejected; the §5.7 defense-in-depth cross-check
  rejects, with `MODEL_OUTPUT_REJECTED`, a selection of a candidate whose
  estimator-consumed input is missing or affected by a typed conflict —
  exercised through a deliberate contract/tool mismatch seam, since normal §5.6
  orchestration filters both candidate kinds before agent invocation;
  fallback-model use recorded per §5.9; prompt
  templates carry `prompt_version`; a test measures and reports end-to-end
  fake-model pipeline latency, which must sit far inside the 45 s/60 s budgets.
- **Tests and checks:** fake-model tests for: happy selection, abstention, invalid
  JSON then repaired, invalid twice → failed run, out-of-set selection (kept as
  its own case), selection of a candidate with a missing estimator-consumed
  input → `MODEL_OUTPUT_REJECTED`, selection of a candidate with a typed
  conflict on an estimator-consumed input → `MODEL_OUTPUT_REJECTED` (both
  injected past the §5.6 eligibility filter through a deliberate contract/tool
  mismatch seam), tool-limit
  breach, primary-model failure → fallback recorded, fallback failure →
  `MODEL_UNAVAILABLE`. Normal CI runs entirely on the fake client. One optional,
  manually triggered smoke test against real Vertex AI via ADC (not in normal CI)
  verifies structured output + tools on `gemini-3.6-flash`.
- **Explicit exclusions:** no side-effecting tools; no Firestore writes from any
  tool handler; no API keys (ADC only); no autonomous anything.
- **Dependencies:** slice 6.
- **Suggested commit boundary:** one commit: "bounded ADK agent with fake-model
  test suite".
- **Rollback:** revert to the slice-6 deterministic pipeline (still fully
  functional for the emergency demo path).

## Slice 8 — Firestore audit persistence and emulator tests

- **Goal:** the Firestore repository of
  [architecture.md §9](architecture.md#9-firestore-and-observability):
  idempotent creation, progress markers, atomic terminal write with precondition,
  read paths; plus the in-memory fake used by normal CI.
- **Expected files:** `src/kalakal/persistence/{firestore_repo,fake_repo}.py`,
  `tests/unit/test_fake_repo.py`, `tests/integration/test_firestore_emulator.py`
  (marked suite), decision-record validator wiring.
- **Acceptance criteria:** duplicate `idempotency_key` → same run returned, no
  second execution; terminal write is one transaction with a non-terminal
  precondition (double-finalize impossible); persistence failure path degrades per
  §7.6 (bounded retries, then `PERSISTENCE_ERROR` + full record in structured
  logs); fake and emulator repositories pass the same behavioral test suite.
- **Tests and checks:** shared repository contract tests run against both fake and
  emulator; race test for duplicate finalization (emulator); reconciliation-path
  test (write fails → record present in captured logs).
- **Explicit exclusions:** no composite indexes, no TTL policy, no security-rule
  deployment, no cloud resources created; emulator only.
- **Dependencies:** slice 6 (record assembly); slots in behind the orchestrator.
- **Suggested commit boundary:** one commit: "Firestore audit repository with fake
  and emulator test suites".
- **Rollback:** switch orchestrator wiring back to the in-memory store (a code
  change, not a flag).

## Slice 9 — Minimal HTTP/demo interface

- **Goal:** the four routes of
  [architecture.md §8.1](architecture.md#81-interface) and the server-rendered
  demo page with all required display elements and fixture/paper labels.
- **Expected files:** `src/kalakal/web/{app,views,templates/}.py`,
  `tests/integration/test_http.py`.
- **Acceptance criteria:** `GET /healthz` cheap and dependency-free;
  `POST /api/runs` executes synchronously within the hard 60 s deadline (target
  30 s or less for a normal fixture run) and returns the terminal result; `GET /api/runs/{run_id}` returns the persisted view; `/` lists
  scenarios, triggers runs, and displays every element required by §8.1 including
  the run/audit ID and the `SIMULATION — DO NOT POST` draft when applicable;
  structured logs carry run correlation IDs.
- **Tests and checks:** route tests with fake model + fake repository; a rendered-
  page test asserting the mandatory labels are present; error paths (unknown
  scenario, duplicate key) return correct statuses.
- **Explicit exclusions:** no public exposure decisions here (deployment is slice
  10); no JavaScript framework — server-rendered minimalism; no multi-user
  anything.
- **Dependencies:** slices 7–8.
- **Suggested commit boundary:** one commit: "minimal HTTP and demo interface".
- **Rollback:** revert; the pipeline remains usable via tests/CLI entrypoint.

## Slice 10 — Cloud Run fixture-only deployment and smoke test

- **Goal:** the owner-authenticated Cloud Run deployment of the fixture MVP with
  Vertex AI via service identity, and a documented smoke test.
- **Expected files:** deployment documentation (README "deploy" section or
  `docs/deploy.md`), optional `Procfile`/service config for buildpacks; no wallet
  or secret material anywhere.
- **Acceptance criteria:** service deployed from source to the fixture-demo region
  with a dedicated least-privilege service account (`datastore` + `aiplatform`
  roles), IAM-authenticated, `max-instances` capped, scale-to-zero, and the Cloud
  Run request timeout set just above the 60 s run deadline; **no Gemini API key
  exists in the deployment** (asserted by reviewing service env); `/healthz` and
  one full fixture run succeed against the deployed service; the smoke test
  manually measures and records that run's end-to-end latency against the 30 s
  target and 60 s deadline; the Firestore document and Cloud Logging entries are
  visible for that run.
- **Tests and checks:** documented smoke-test procedure (health check + one run +
  console verification); confirm Secret Manager is not enabled/used; confirm
  billing budget + spend-cap backstops per research §4.4 are in place (console
  step, documented).
- **Explicit exclusions:** no live-data adapters, no scheduler, no custom domain,
  no min-instances kept warm outside the recording window, no unauthenticated
  access (except, if rehearsal demands, the documented time-boxed alternative in
  architecture §8.1). This slice requires explicit user authorization before any
  paid cloud resource is created (CLAUDE.md §5).
- **Dependencies:** slice 9.
- **Suggested commit boundary:** one commit: "Cloud Run deployment configuration
  and smoke-test docs".
- **Rollback/disablement:** delete the Cloud Run service (or route traffic to the
  previous revision); Firestore data retained per the retention policy; nothing
  else exists to tear down.

## Slice 11 — Demo rehearsal and submission evidence

- **Goal:** the unedited ≤4-minute demo executed per
  [architecture.md §8.3](architecture.md#83-unedited-four-minute-demo-sequence),
  plus the submission artifacts.
- **Expected files:** README spin-up instructions finalized; architecture diagram
  export/reference for the submission; demo script/checklist in `docs/`; recorded
  video (external to the repo).
- **Acceptance criteria:** one full rehearsal passes all seven demo steps; warm-up
  and restore-scale-to-zero steps verified; measured run latency fits the
  four-minute take (target 30 s or less, with any failure surfacing safely inside
  the 60 s deadline rather than stalling the recording); fallback ladder rehearsed
  (fallback
  model + previously persisted run + deterministic-core emergency path);
  submission checklist items from
  [research/hackathon.md](research/hackathon.md) §4 all addressed.
- **Tests and checks:** rehearsal checklist executed end-to-end; link/lint check
  over the submitted docs.
- **Explicit exclusions:** no live-data claims, no predictive-performance claims,
  no profit language anywhere in the demo or description.
- **Dependencies:** slice 10.
- **Suggested commit boundary:** one commit: "demo script and submission
  materials".
- **Rollback:** n/a (documentation and rehearsal).

---

## Post-MVP slices (gated)

Slices 12–15 require the fixture MVP (slices 1–11) accepted, plus the per-slice
gates below. Slice 16 additionally requires **all** Mode 4 development-entry
criteria ([architecture.md §12.1](architecture.md#121-development-entry-criteria));
slice 17 depends on slice 16, and slice 18 on slice 17; slice 19 verifies the
live-activation criteria
([architecture.md §12.2](architecture.md#122-live-activation-criteria)) before any
limited-funds validation. The development-entry criteria permit offline
implementation and testing only — no signing, submission, or real-money activity
before §12.2 holds.

## Slice 12 — Prediction-model research and baseline validation

- **Goal:** complete the mandatory prediction-model gate of
  [architecture.md §10.2](architecture.md#102-mandatory-later-research-and-validation-gate).
- **Expected files:** `docs/research/prediction-model.md` (research report per
  CLAUDE.md §3), offline evaluation code under `src/kalakal/estimator/` +
  `tests/`, versioned datasets/snapshots outside Git if large.
- **Acceptance criteria:** a transparent baseline (Elo/TrueSkill or equivalent)
  evaluated with temporal splits, leakage prevention demonstrated, calibration +
  Brier + log loss reported against the market-implied baseline, fees/slippage/
  sample size/drawdown/abstention analyzed, roster/tier/patch effects addressed,
  fully reproducible; a written go/no-go conclusion.
- **Tests and checks:** deterministic evaluation pipeline tests; leakage tests
  (train/test boundary assertions); reproducibility run (same inputs → same
  metrics).
- **Explicit exclusions:** no live wiring of the model into the agent pipeline in
  this slice; the demo estimator remains bound until the gate's conclusion says
  otherwise.
- **Dependencies:** slices 1–11; requires licensed historical data (§13.6 gates).
- **Suggested commit boundary:** research report and evaluation code as separate
  commits.
- **Rollback/disablement:** the demo estimator remains the bound implementation;
  swapping estimators is an explicit code change behind the estimator interface.

## Slice 13 — Permitted live-data adapters

- **Goal:** typed, contract-tested adapters for the permitted Dota data sources
  (per [research/dota2-data-sources.md](research/dota2-data-sources.md):
  Liquipedia APIs for schedules/rosters; a results source whose license has been
  cleared) and, separately gated, the documented Jupiter read-only data interfaces.
- **Expected files:** `src/kalakal/adapters/<source>/…`, contract tests with
  recorded documented shapes, rate-limit/caching layer, Secret Manager wiring for
  real API credentials (first legitimate use), attribution handling.
- **Acceptance criteria:** each adapter validates payloads into the §6 schemas at
  the boundary; rate limits and caching respect the source's published rules;
  license/terms verification recorded per source before first use
  ([architecture.md §13.7](architecture.md#137-conditions-before-introducing-live-data-adapters));
  Jupiter data access additionally requires the eligible-region and runtime
  jurisdiction/IP eligibility gates.
- **Tests and checks:** contract tests (recorded fixtures of documented shapes —
  normal CI stays offline); schema-rejection tests for malformed payloads;
  rate-limiter unit tests.
- **Explicit exclusions:** no scraping; no undocumented endpoints; no order
  construction; no wallet anything; CI never calls live services.
- **Dependencies:** slices 1–11; §13.7 conditions per source.
- **Suggested commit boundary:** one commit per source adapter.
- **Rollback/disablement:** adapters are separate modules behind interfaces; the
  fixture repository remains a first-class data source for all tests and demos;
  removing an adapter is deleting its module and wiring.

## Slice 14 — Paper trading with live data (Mode 2)

- **Goal:** simulated positions and balances over live data with no real
  transactions.
- **Expected files:** `src/kalakal/paper/{ledger,runner}.py`, position/exposure
  schemas, extended policy rules (exposure and daily limits now meaningful),
  `tests/` including an end-to-end paper-trading test.
- **Acceptance criteria:** paper ledger is integer-micro accurate, idempotent, and
  auditable; exposure/daily-limit policy rules active and tested; decision records
  extended with simulated position outcomes; abstention rate and outcome metrics
  reported with fees and slippage assumptions labeled.
- **Tests and checks:** ledger unit tests; end-to-end paper run on recorded live
  shapes (offline in CI); calibration/metric reporting tests.
- **Explicit exclusions:** no transaction construction, no signing, no submission,
  no Discord posting; drafts remain simulation-labeled until slice 12's gate and
  CLAUDE.md §8 conditions are met.
- **Dependencies:** slices 12–13.
- **Suggested commit boundary:** one commit: "paper-trading ledger and runner".
- **Rollback/disablement:** paper mode is an explicit runner entrypoint; stop
  invoking it. Ledger data remains for audit.

## Slice 15 — Shadow production (Mode 3)

- **Goal:** the full pipeline against live markets where decisions are recorded but
  no transactions are prepared or sent.
- **Expected files:** `src/kalakal/shadow/runner.py`, scheduling documentation
  (optional single Cloud Scheduler cron — a paid-resource decision requiring
  explicit authorization), monitoring dashboards/queries documentation.
- **Acceptance criteria:** shadow runs produce complete decision records with live
  snapshots and freshness data; stale-data and thin-liquidity behavior observed and
  handled (depth-aware edge inputs); shadow metrics (abstention rate, would-have
  outcomes) reported honestly with sample size.
- **Tests and checks:** shadow runner tests on recorded shapes; idempotency under
  repeated scheduling; kill-switch precursor: a documented stop mechanism for the
  scheduler.
- **Explicit exclusions:** still no transaction preparation of any kind.
- **Dependencies:** slice 14.
- **Suggested commit boundary:** one commit: "shadow-mode runner".
- **Rollback/disablement:** disable/delete the scheduler job; the runner is
  otherwise manual.

## Slice 16 — Mode 4 transaction-intent and unsigned-proposal construction

**Gate: every development-entry criterion in
[architecture.md §12.1](architecture.md#121-development-entry-criteria) must hold
before this slice starts. Slices 16–18 are offline implementation and testing
only — no signing, submission, or real-money activity.**

- **Goal:** `TransactionIntent` production from `proceed` decisions and retrieval
  of unsigned proposals from the documented Jupiter order-construction interface.
- **Expected files:** `src/kalakal/mode4/{intent,proposal}.py`, transaction-policy
  layer extensions (market/program allowlists, amount/exposure/freshness/duplicate
  limits), `tests/`.
- **Acceptance criteria:** intents are deterministic, bounded by policy config,
  idempotency-keyed, and immutable once approved; unsigned proposals carry the
  transaction digest and expiry; the policy layer rejects out-of-allowlist or
  over-limit intents; nothing in this slice can sign or submit.
- **Tests and checks:** policy-rejection matrix tests; intent immutability tests;
  contract tests for the order endpoint (recorded shapes; CI offline).
- **Explicit exclusions:** no decoding/simulation yet (next slice blocks
  approval); no signer, no submission, no human-review UI.
- **Dependencies:** slices 13–15 + the §12.1 development-entry criteria.
- **Suggested commit boundary:** one commit: "transaction intent and unsigned
  proposal construction".
- **Rollback/disablement:** the Mode 4 pipeline is inert without slices 17–18 and
  cannot reach signing or submission before §12.2 holds; reverting this slice
  removes intent production entirely.

## Slice 17 — Instruction decoding and transaction simulation

- **Goal:** decode every instruction of every proposal, compare against the
  approved intent, and mandatorily simulate the exact transaction.
- **Expected files:** `src/kalakal/mode4/{decoder,simulator}.py`, known-transaction
  fixtures, `tests/`.
- **Acceptance criteria:** every instruction decoded and compared (programs,
  accounts, amounts, mints, destinations, data); any unexpected or undecodable
  element rejects the proposal; simulation of the exact bytes is mandatory and its
  absence/failure blocks review; decoder verified against known fixtures.
- **Tests and checks:** decoder tests against known-good and adversarial fixtures
  (extra instruction, changed destination, changed amount, unknown program);
  simulation-required tests; digest-binding tests.
- **Explicit exclusions:** still no signing or submission; no human approval yet.
- **Dependencies:** slice 16.
- **Suggested commit boundary:** one commit: "instruction decoder and mandatory
  simulation".
- **Rollback/disablement:** without this slice passing, slice 16's proposals can
  never reach review; reverting it re-blocks the pipeline safely.

## Slice 18 — Human-review and external-wallet signing flow

- **Goal:** the human-readable review, digest-bound single-use expiring approval,
  the kill switch, hand-off to the external wallet/isolated signer, submission,
  and full recording
  ([architecture.md §11.3–§11.6](architecture.md#113-mode-4-flow-human-reviewed-human-signed)).
- **Expected files:** `src/kalakal/mode4/{review,approval,submission,kill_switch}.py`,
  review presentation (CLI or minimal page), `tests/`.
- **Acceptance criteria:** review shows every §11.3-step-10 element; approval binds
  to the exact transaction digest, is single-use, and expires; **any** change
  invalidates the approval and forces a new review; the application hands off the
  verified unsigned transaction and receives back only signatures/results; no key
  material appears in code, records, logs, telemetry, or memory interfaces the
  application controls; the kill switch immediately halts intent production,
  review, and hand-off, and is covered by tests; submission and confirmation
  states recorded.
- **Tests and checks:** approval-invalidation tests (mutate any byte → invalid);
  expiry tests; end-to-end dry-run against a local validator/test environment with
  a throwaway test key held only by the external signer process; log/record scans
  asserting no key-material patterns.
- **Explicit exclusions:** no autonomous approval; no retry-into-signing; no use of
  the user's primary wallet; no mainnet activity in tests.
- **Dependencies:** slice 17; the §12.1-identified signer candidate — its
  compatibility is proven in this slice without key exposure
  ([architecture.md §11.6](architecture.md#116-key-isolation-non-negotiable)).
- **Suggested commit boundary:** one commit: "human review, approval, and external
  signing hand-off".
- **Rollback/disablement:** kill switch halts the pipeline; removing signer
  configuration disables hand-off entirely; approvals expire on their own.

## Slice 19 — Mode 4 live-activation verification and limited-funds validation

- **Goal:** verify every live-activation criterion of
  [architecture.md §12.2](architecture.md#122-live-activation-criteria), complete
  the holistic security review, and — only with separate explicit user
  authorization — perform a bounded validation exercise on a dedicated
  limited-funds wallet.
- **Expected files:** `docs/security-review.md` (findings, mitigations, sign-off),
  runbook updates (kill switch, incident response, reconciliation), a §12.2
  verification checklist with evidence links.
- **Acceptance criteria:** every §12.2 criterion verified with evidence; security
  review covers key isolation, policy bypass resistance, prompt-injection surface,
  approval binding, audit completeness, and failure recovery, with no unresolved
  critical or high-severity findings (lower-severity findings resolved or
  explicitly accepted); the separately authorized small-value validation on the
  dedicated limited-funds wallet executes the entire §11.3 flow with explicit
  per-proposal human approval and produces a complete audit trail; kill switch
  exercised during the validation.
- **Tests and checks:** failure-recovery and audit tests passing (§12.2 item 10);
  the validation exercise's checklist; post-validation review of every record
  and log for key material and PII (must find none).
- **Explicit exclusions:** no expansion of limits, no session-style approvals
  beyond CLAUDE.md §6's bounded-session definition, and **no work toward Mode 5 —
  which is not a future slice**.
- **Dependencies:** slice 18; every §12.2 criterion is verified in this slice.
- **Suggested commit boundary:** one commit: "Mode 4 live-activation verification
  and validation evidence".
- **Rollback/disablement:** kill switch; revoke signer configuration; Mode 4
  remains proposal-only (its default) whenever any gate condition regresses.
