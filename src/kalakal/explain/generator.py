"""Deterministic, source-aware explanation generation (§5.2, §6.2.8, slice 5).

Every generator here is a pure function: no clock, no I/O, no randomness,
no scenario-ID branching, and no oracle input (``expected_outcome_class`` /
``expected_reason_code`` are never accepted). Orchestrator-sourced
narratives are fixed code templates keyed by typed reasons and entity
kinds — no fixture prose, identifiers, or numbers ever enter the narrative
text; citations happen exclusively through typed evidence references.
Numbers of record live only in the deterministic contracts (§6.2.5–§6.2.7),
and :func:`find_numeric_narrative` enforces that rule on every narrative
location, generated and agent-supplied alike.

Agent-sourced assembly (:func:`assemble_agent_explanation`) validates
already-structured qualitative model output; it performs no model call and
never fabricates invocation metadata. Slice 7 feeds it real validated
output later.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Annotated, Final

from pydantic import Field, ValidationError

from kalakal.domain.edge import EdgeAssessment
from kalakal.domain.explanation import DecisionExplanation, KeyFactor
from kalakal.domain.match import MATCH_ESTIMATOR_FIELDS
from kalakal.domain.policy import PolicyDecision
from kalakal.domain.primitives import (
    SCHEMA_VERSION,
    AbstainReasonCode,
    ConfidenceQualifier,
    EligibilityReason,
    EvidenceRef,
    EvidenceRefKind,
    LongText,
    MediumText,
    StrictModel,
)
from kalakal.domain.quality import DataQuality
from kalakal.domain.record import CandidateEligibility
from kalakal.domain.sensitive import find_sensitive_content
from kalakal.policy.config import FIXTURE_POLICY_CONFIG, PolicyConfig
from kalakal.policy.engine import (
    CHECK_CANDIDATE_COMPLETENESS,
    CHECK_CANDIDATE_FRESHNESS,
    CHECK_DUPLICATE_RUN,
    CHECK_ENTRY_PRICE_MAX,
    CHECK_ENTRY_PRICE_MIN,
    CHECK_MATCH_COMPLETENESS,
    CHECK_MATCH_FRESHNESS,
    CHECK_MIN_NET_EDGE,
    CHECK_SNAPSHOT_COMPLETENESS,
    CHECK_SNAPSHOT_FRESHNESS,
    PolicyInputError,
    verify_policy_decision,
)

# The immutable deterministic template version recorded in every
# orchestrator-sourced explanation (§6.1, §6.2.8). Changing any template in
# this module requires a new version string.
EXPLANATION_TEMPLATE_VERSION: Final = "fixture-explanation-1"

# The deterministic no-model paths make no predictive claim, so their
# qualitative confidence is fixed at the lowest enum value.
_ORCHESTRATOR_CONFIDENCE: Final[ConfidenceQualifier] = "low"

_MAX_NARRATIVE_ITEMS: Final = 16

_STUB_ABSTAIN_REASONS: Final = ("CONFLICTING_EVIDENCE", "INSUFFICIENT_EVIDENCE")


class ExplanationGenerationError(ValueError):
    """Bounded typed generation failure.

    Messages name locations, typed reasons, and validated identifiers only —
    never echoed narrative content or arbitrary raw input.
    """


# --- Narrative-only rule (§6.2.8): prose can never carry numeric claims ---

_NUMERIC_NARRATIVE_PATTERNS: Final[tuple[tuple[str, re.Pattern[str]], ...]] = (
    ("ASCII digit", re.compile(r"[0-9]")),
    ("percent sign", re.compile(r"%")),
    ("currency symbol", re.compile(r"[$¢€£¥₿]")),
    (
        "micro/ppm numeric notation",
        re.compile(r"(?i)\b(?:ppm|micro[\s-]?usd)\b|_ppm\b|_micro\b"),
    ),
)


def find_numeric_narrative(text: str) -> str | None:
    """Return the label of the first numeric-prose indicator, else ``None``.

    Conservative and deterministic: ASCII digits, percent signs, the
    project's currency symbols, and explicit micro/ppm notation all reject.
    Typed identifiers (evidence-ref IDs, versions) are exempt because they
    are structured fields, never narrative prose — this validator applies
    only to narrative locations.
    """
    for label, pattern in _NUMERIC_NARRATIVE_PATTERNS:
        if pattern.search(text):
            return label
    return None


def _require_narrative(location: str, text: str) -> None:
    indicator = find_numeric_narrative(text)
    if indicator is not None:
        raise ExplanationGenerationError(
            f"{location} contains numeric or currency-shaped narrative "
            f"content ({indicator})"
        )


# --- Evidence-scope validation (reused by slice 7 agent-output checks) ---


@dataclass(frozen=True)
class EvidenceCatalog:
    """The allowable evidence-reference pools for one run's explanation."""

    market_ids: frozenset[str]
    match_ids: frozenset[str]
    snapshot_market_ids: frozenset[str]
    fixture_source_ids: frozenset[str]


def build_evidence_catalog(
    considered: Iterable[CandidateEligibility], *, fixture_source_id: str
) -> EvidenceCatalog:
    """Build the allowable catalog from the considered evidence bundles."""
    market_ids: set[str] = set()
    match_ids: set[str] = set()
    snapshot_market_ids: set[str] = set()
    for candidate in considered:
        market_ids.add(candidate.market.market_id)
        match_ids.add(candidate.match_context.match_id)
        snapshot_market_ids.add(candidate.market_snapshot.market_id)
    return EvidenceCatalog(
        market_ids=frozenset(market_ids),
        match_ids=frozenset(match_ids),
        snapshot_market_ids=frozenset(snapshot_market_ids),
        fixture_source_ids=frozenset({fixture_source_id}),
    )


def find_unresolved_evidence_refs(
    refs: Iterable[EvidenceRef], catalog: EvidenceCatalog
) -> tuple[EvidenceRef, ...]:
    """Return every reference that does not resolve within the catalog."""
    pools: dict[str, frozenset[str]] = {
        "market": catalog.market_ids,
        "match": catalog.match_ids,
        "snapshot": catalog.snapshot_market_ids,
        "fixture_source": catalog.fixture_source_ids,
    }
    return tuple(ref for ref in refs if ref.ref_id not in pools[ref.kind])


def _require_refs_resolve(
    refs: Iterable[EvidenceRef], catalog: EvidenceCatalog
) -> None:
    unresolved = find_unresolved_evidence_refs(refs, catalog)
    if unresolved:
        first = unresolved[0]
        raise ExplanationGenerationError(
            f"unresolved evidence ref {first.kind}:{first.ref_id}"
        )


# --- Fixed deterministic templates (no digits, no fixture prose) ---

_NO_VALID_CANDIDATES_SUMMARY: Final = (
    "Abstained before selection: no considered candidate market passed the "
    "deterministic eligibility filter, so no selector and no model ran."
)

_STUB_ABSTENTION_SUMMARIES: Final[dict[str, str]] = {
    "CONFLICTING_EVIDENCE": (
        "The deterministic stub selector abstained: declared data conflicts "
        "affect the eligible candidate evidence, so no market was selected."
    ),
    "INSUFFICIENT_EVIDENCE": (
        "The deterministic stub selector abstained: declared evidence gaps "
        "leave the eligible candidates insufficient for selection, so no "
        "market was selected."
    ),
}

_PROCEED_SUMMARY: Final = (
    "A market was selected by the documented deterministic stub procedure "
    "and all binding configured policy checks passed."
)

_NO_BET_SUMMARY: Final = (
    "A market was selected by the documented deterministic stub procedure "
    "and the binding policy engine returned a no-bet decision; the failed "
    "checks are recorded as opposing factors."
)

_STUB_PROCEDURE_FACTOR: Final = (
    "Selection followed the documented deterministic stub procedure: "
    "eligible candidates are examined in ascending market-identifier order "
    "and the first whose declared evidence is fully complete and "
    "conflict-free is selected on its declared evaluation side."
)

_POLICY_PROCEED_FACTOR: Final = (
    "All binding configured policy checks passed for the selected market."
)

_ELIGIBILITY_FACTOR_TEXTS: Final[dict[EligibilityReason, str]] = {
    "NOT_OPEN": "The candidate market is not open for entry.",
    "ESTIMATOR_INPUT_MISSING": (
        "Estimator-consumed match evidence is declared missing for this candidate."
    ),
    "ESTIMATOR_INPUT_CONFLICTED": (
        "Estimator-consumed match evidence carries a declared conflict for "
        "this candidate."
    ),
}

_ELIGIBILITY_FACTOR_KINDS: Final[dict[EligibilityReason, EvidenceRefKind]] = {
    "NOT_OPEN": "market",
    "ESTIMATOR_INPUT_MISSING": "match",
    "ESTIMATOR_INPUT_CONFLICTED": "match",
}

_CONFLICT_TEXTS: Final[dict[EvidenceRefKind, str]] = {
    "market": (
        "A declared data conflict affects the recorded candidate-market evidence."
    ),
    "match": ("A declared data conflict affects the recorded match-context evidence."),
    "snapshot": (
        "A declared data conflict affects the recorded market-snapshot evidence."
    ),
}

_GAP_TEXTS: Final[dict[EvidenceRefKind, str]] = {
    "market": (
        "A declared evidence gap affects the recorded candidate-market evidence."
    ),
    "match": ("A declared evidence gap affects the recorded match-context evidence."),
    "snapshot": (
        "A declared evidence gap affects the recorded market-snapshot evidence."
    ),
}

# Failed policy checks rendered qualitatively (§6.2.7 categories): fixed
# text plus the entity kind whose recorded evidence the check observed.
# Threshold values, prices, probabilities, and edge numbers stay in the
# deterministic contracts and never enter this prose.
_POLICY_CHECK_FACTORS: Final[dict[str, tuple[str, EvidenceRefKind]]] = {
    CHECK_CANDIDATE_COMPLETENESS: (
        "The selected candidate market's declared evidence is incomplete "
        "under the binding policy.",
        "market",
    ),
    CHECK_MATCH_COMPLETENESS: (
        "The selected match context's declared evidence is incomplete under "
        "the binding policy.",
        "match",
    ),
    CHECK_SNAPSHOT_COMPLETENESS: (
        "The selected market snapshot's declared evidence is incomplete "
        "under the binding policy.",
        "snapshot",
    ),
    CHECK_CANDIDATE_FRESHNESS: (
        "The selected candidate market's evidence was stale at policy evaluation time.",
        "market",
    ),
    CHECK_MATCH_FRESHNESS: (
        "The selected match context's evidence was stale at policy evaluation time.",
        "match",
    ),
    CHECK_SNAPSHOT_FRESHNESS: (
        "The selected market snapshot was stale at policy evaluation time.",
        "snapshot",
    ),
    CHECK_ENTRY_PRICE_MIN: (
        "The recorded ask price sits below the configured entry band.",
        "snapshot",
    ),
    CHECK_ENTRY_PRICE_MAX: (
        "The recorded ask price sits above the configured entry band.",
        "snapshot",
    ),
    CHECK_MIN_NET_EDGE: (
        "The calculated net edge falls below the configured minimum.",
        "snapshot",
    ),
    CHECK_DUPLICATE_RUN: (
        "The run duplicates a previously decided run for this market.",
        "market",
    ),
}


# --- Shared assembly helpers ---


def _entity_ref(candidate: CandidateEligibility, kind: EvidenceRefKind) -> EvidenceRef:
    if kind == "market":
        return EvidenceRef(kind="market", ref_id=candidate.market.market_id)
    if kind == "match":
        return EvidenceRef(kind="match", ref_id=candidate.match_context.match_id)
    if kind == "snapshot":
        return EvidenceRef(kind="snapshot", ref_id=candidate.market_snapshot.market_id)
    raise ExplanationGenerationError(
        "evidence factors may cite market, match, or snapshot entities only"
    )


def _entity_qualities(
    candidate: CandidateEligibility,
) -> tuple[tuple[EvidenceRefKind, DataQuality], ...]:
    return (
        ("market", candidate.market.data_quality),
        ("match", candidate.match_context.data_quality),
        ("snapshot", candidate.market_snapshot.data_quality),
    )


def _sorted_candidates(
    considered: tuple[CandidateEligibility, ...],
) -> tuple[CandidateEligibility, ...]:
    return tuple(sorted(considered, key=lambda c: c.market.market_id))


def _dedup_factors(factors: Iterable[KeyFactor]) -> tuple[KeyFactor, ...]:
    deduped: list[KeyFactor] = []
    for factor in factors:
        if factor not in deduped:
            deduped.append(factor)
    return tuple(deduped)


def _dedup_texts(texts: Iterable[str]) -> tuple[str, ...]:
    deduped: list[str] = []
    for text in texts:
        if text not in deduped:
            deduped.append(text)
    return tuple(deduped)


def _dedup_sorted_refs(refs: Iterable[EvidenceRef]) -> tuple[EvidenceRef, ...]:
    unique = {(ref.kind, ref.ref_id): ref for ref in refs}
    return tuple(unique[key] for key in sorted(unique))


def _build_orchestrator_explanation(
    *,
    run_id: str,
    summary: str,
    factors: Iterable[KeyFactor],
    conflicts: Iterable[str],
    data_gaps: Iterable[str],
    extra_refs: Iterable[EvidenceRef],
    catalog: EvidenceCatalog,
) -> DecisionExplanation:
    """Deduplicate, order, validate, and assemble one orchestrator
    explanation carrying the deterministic template version."""
    key_factors = _dedup_factors(factors)
    conflict_texts = _dedup_texts(conflicts)
    gap_texts = _dedup_texts(data_gaps)
    evidence_refs = _dedup_sorted_refs(
        [factor.evidence_ref for factor in key_factors] + list(extra_refs)
    )
    for name, items in (
        ("key_factors", key_factors),
        ("conflicts", conflict_texts),
        ("data_gaps", gap_texts),
        ("evidence_refs", evidence_refs),
    ):
        if len(items) > _MAX_NARRATIVE_ITEMS:
            raise ExplanationGenerationError(
                f"{name} exceeds the bounded explanation capacity"
            )
    _require_narrative("summary", summary)
    for factor in key_factors:
        _require_narrative("key_factors", factor.factor)
    for text in conflict_texts:
        _require_narrative("conflicts", text)
    for text in gap_texts:
        _require_narrative("data_gaps", text)
    _require_refs_resolve(list(evidence_refs), catalog)
    try:
        return DecisionExplanation(
            schema_version=SCHEMA_VERSION,
            run_id=run_id,
            source="orchestrator",
            summary=summary,
            key_factors=key_factors,
            conflicts=conflict_texts,
            data_gaps=gap_texts,
            confidence_qualifier=_ORCHESTRATOR_CONFIDENCE,
            evidence_refs=evidence_refs,
            explanation_template_version=EXPLANATION_TEMPLATE_VERSION,
        )
    except ValidationError:
        raise ExplanationGenerationError(
            "generated explanation failed contract validation"
        ) from None


def _declared_evidence(
    candidates: Iterable[CandidateEligibility],
) -> tuple[list[KeyFactor], list[str], list[str], list[EvidenceRef]]:
    """Collect factors, conflict texts, gap texts, and recorded conflict
    references from the declared data quality of the given candidates."""
    factors: list[KeyFactor] = []
    conflict_texts: list[str] = []
    gap_texts: list[str] = []
    extra_refs: list[EvidenceRef] = []
    for candidate in candidates:
        for kind, quality in _entity_qualities(candidate):
            for conflict in quality.conflicts:
                conflict_texts.append(_CONFLICT_TEXTS[kind])
                factors.append(
                    KeyFactor(
                        factor=_CONFLICT_TEXTS[kind],
                        direction="opposes",
                        evidence_ref=_entity_ref(candidate, kind),
                    )
                )
                extra_refs.extend(conflict.evidence_refs)
            if quality.missing_fields:
                gap_texts.append(_GAP_TEXTS[kind])
                factors.append(
                    KeyFactor(
                        factor=_GAP_TEXTS[kind],
                        direction="opposes",
                        evidence_ref=_entity_ref(candidate, kind),
                    )
                )
    return factors, conflict_texts, gap_texts, extra_refs


# --- Orchestrator path 1: eligibility-filter abstention (§5.6) ---


def generate_no_valid_candidates_explanation(
    *,
    run_id: str,
    considered: tuple[CandidateEligibility, ...],
    fixture_source_id: str,
) -> DecisionExplanation:
    """Explain the pre-selection ``NO_VALID_CANDIDATES`` abstention.

    Requires zero eligible considerations. Each derived eligibility reason
    becomes a fixed qualitative factor: ``NOT_OPEN`` cites the candidate
    market; missing or conflicted estimator evidence cites the relevant
    match context. Staleness is never an eligibility reason (§5.6) and is
    never claimed here.
    """
    if not considered:
        raise ExplanationGenerationError(
            "the no-valid-candidates path requires at least one considered candidate"
        )
    if any(candidate.eligible for candidate in considered):
        raise ExplanationGenerationError(
            "the no-valid-candidates path requires zero eligible candidates"
        )
    factors: list[KeyFactor] = []
    conflict_texts: list[str] = []
    gap_texts: list[str] = []
    extra_refs: list[EvidenceRef] = []
    for candidate in _sorted_candidates(considered):
        for reason in candidate.ineligibility_reasons:
            factors.append(
                KeyFactor(
                    factor=_ELIGIBILITY_FACTOR_TEXTS[reason],
                    direction="opposes",
                    evidence_ref=_entity_ref(
                        candidate, _ELIGIBILITY_FACTOR_KINDS[reason]
                    ),
                )
            )
        quality = candidate.match_context.data_quality
        if any(path in MATCH_ESTIMATOR_FIELDS for path in quality.missing_fields):
            gap_texts.append(_GAP_TEXTS["match"])
        for conflict in quality.conflicts:
            if conflict.field_path in MATCH_ESTIMATOR_FIELDS:
                conflict_texts.append(_CONFLICT_TEXTS["match"])
                extra_refs.extend(conflict.evidence_refs)
    return _build_orchestrator_explanation(
        run_id=run_id,
        summary=_NO_VALID_CANDIDATES_SUMMARY,
        factors=factors,
        conflicts=conflict_texts,
        data_gaps=gap_texts,
        extra_refs=extra_refs,
        catalog=build_evidence_catalog(considered, fixture_source_id=fixture_source_id),
    )


# --- Orchestrator path 2: deterministic-stub abstention (§5.10) ---


def generate_stub_abstention_explanation(
    *,
    run_id: str,
    considered: tuple[CandidateEligibility, ...],
    abstain_reason_code: AbstainReasonCode,
    fixture_source_id: str,
) -> DecisionExplanation:
    """Explain a deterministic-stub abstention over eligible candidates.

    The reason must be ``CONFLICTING_EVIDENCE`` or ``INSUFFICIENT_EVIDENCE``
    and must be supported by the actual recorded evidence: the eligible
    considerations' declared conflicts or gaps are cited entity by entity
    (market, match context, or snapshot), and each recorded conflict's own
    evidence references are propagated. A reason without matching recorded
    evidence is rejected, never narrated.
    """
    if abstain_reason_code not in _STUB_ABSTAIN_REASONS:
        raise ExplanationGenerationError(
            "a deterministic-stub abstention requires reason "
            "CONFLICTING_EVIDENCE or INSUFFICIENT_EVIDENCE"
        )
    eligible = tuple(
        candidate for candidate in _sorted_candidates(considered) if candidate.eligible
    )
    if not eligible:
        raise ExplanationGenerationError(
            "a deterministic-stub abstention requires at least one eligible candidate"
        )
    factors, conflict_texts, gap_texts, extra_refs = _declared_evidence(eligible)
    if abstain_reason_code == "CONFLICTING_EVIDENCE" and not conflict_texts:
        raise ExplanationGenerationError(
            "CONFLICTING_EVIDENCE requires at least one declared conflict on "
            "eligible-candidate evidence"
        )
    if abstain_reason_code == "INSUFFICIENT_EVIDENCE" and not gap_texts:
        raise ExplanationGenerationError(
            "INSUFFICIENT_EVIDENCE requires at least one declared evidence "
            "gap on eligible-candidate evidence"
        )
    return _build_orchestrator_explanation(
        run_id=run_id,
        summary=_STUB_ABSTENTION_SUMMARIES[abstain_reason_code],
        factors=factors,
        conflicts=conflict_texts,
        data_gaps=gap_texts,
        extra_refs=extra_refs,
        catalog=build_evidence_catalog(considered, fixture_source_id=fixture_source_id),
    )


# --- Orchestrator path 3: deterministic-stub post-selection (§5.10) ---


def generate_stub_post_selection_explanation(
    *,
    run_id: str,
    considered: tuple[CandidateEligibility, ...],
    selected: CandidateEligibility,
    edge: EdgeAssessment,
    policy_decision: PolicyDecision,
    fixture_source_id: str,
    policy_config: PolicyConfig = FIXTURE_POLICY_CONFIG,
    is_duplicate_run: bool = False,
) -> DecisionExplanation:
    """Explain a deterministic-stub selection and its binding policy result.

    The supplied policy decision is never narrated on trust: it must equal,
    exactly, the policy result recomputed from the selected consideration's
    evidence and the supplied ``edge`` with the supplied ``policy_config``
    and ``is_duplicate_run`` (the fixture defaults are conveniences; slice 6
    passes both deliberately). Only then does the explanation state that
    binding checks passed (``proceed``) or render each failed check as a
    fixed qualitative opposing factor citing the entity the check observed
    (``no_bet``). No threshold values, prices, probabilities, or edge
    numbers enter the prose.
    """
    if selected not in considered:
        raise ExplanationGenerationError(
            "the selected consideration must be among the considered candidates"
        )
    if not selected.eligible:
        raise ExplanationGenerationError(
            "the selected consideration must be an eligible candidate"
        )
    try:
        verify_policy_decision(
            decision=policy_decision,
            candidate=selected.market,
            match_context=selected.match_context,
            snapshot=selected.market_snapshot,
            edge=edge,
            config=policy_config,
            is_duplicate_run=is_duplicate_run,
        )
    except PolicyInputError:
        raise ExplanationGenerationError(
            "supplied policy decision does not equal the exact recomputed "
            "policy result for the selected evidence"
        ) from None
    factors: list[KeyFactor] = [
        KeyFactor(
            factor=_STUB_PROCEDURE_FACTOR,
            direction="neutral",
            evidence_ref=_entity_ref(selected, "market"),
        )
    ]
    declared_factors, conflict_texts, gap_texts, extra_refs = _declared_evidence(
        (selected,)
    )
    factors.extend(declared_factors)
    if policy_decision.decision == "proceed":
        summary = _PROCEED_SUMMARY
        factors.append(
            KeyFactor(
                factor=_POLICY_PROCEED_FACTOR,
                direction="supports",
                evidence_ref=_entity_ref(selected, "market"),
            )
        )
    else:
        summary = _NO_BET_SUMMARY
        for check in policy_decision.checks:
            if check.passed:
                continue
            # Defense in depth: after exact recomputation the check series
            # can only contain engine-produced check IDs, so this branch is
            # reachable only through an engine/template drift bug.
            entry = _POLICY_CHECK_FACTORS.get(check.check_id)
            if entry is None:
                raise ExplanationGenerationError(
                    "the policy decision contains an unrecognized failed check"
                )
            text, kind = entry
            factors.append(
                KeyFactor(
                    factor=text,
                    direction="opposes",
                    evidence_ref=_entity_ref(selected, kind),
                )
            )
    return _build_orchestrator_explanation(
        run_id=run_id,
        summary=summary,
        factors=factors,
        conflicts=conflict_texts,
        data_gaps=gap_texts,
        extra_refs=extra_refs,
        catalog=build_evidence_catalog(considered, fixture_source_id=fixture_source_id),
    )


# --- Agent-sourced assembly (§5.2; fed with real model output in slice 7) ---


class AgentQualitativeContent(StrictModel):
    """The validated qualitative structured-output fields of §5.2.

    Strict and frozen: unknown fields are rejected, and no numeric monetary
    or probability field is representable — numbers live only in the
    deterministic contracts. Selection/abstention fields, prices, token
    usage, source attribution, prompt versions, and model metadata do not
    exist on this contract.
    """

    summary: LongText
    key_factors: Annotated[tuple[KeyFactor, ...], Field(max_length=16)]
    conflicts: Annotated[tuple[MediumText, ...], Field(max_length=16)]
    data_gaps: Annotated[tuple[MediumText, ...], Field(max_length=16)]
    confidence_qualifier: ConfidenceQualifier
    evidence_refs: Annotated[tuple[EvidenceRef, ...], Field(max_length=16)]


def assemble_agent_explanation(
    *,
    run_id: str,
    content: AgentQualitativeContent,
    prompt_version: str,
    model_metadata_ref: str,
    catalog: EvidenceCatalog,
) -> DecisionExplanation:
    """Assemble an agent-sourced explanation from validated content.

    Performs no model call and fabricates no invocation metadata: the
    supplied ``prompt_version`` and ``model_metadata_ref`` are recorded
    exactly. Sensitive-shaped content is rejected early (without echoing
    it), every narrative location must be numeric-free, and every evidence
    reference — top-level and per key factor — must resolve within the
    supplied catalog. The content is preserved exactly, never rewritten.
    """
    if not isinstance(content, AgentQualitativeContent):
        raise ExplanationGenerationError(
            "content must be a validated AgentQualitativeContent instance"
        )
    sensitive = find_sensitive_content(content)
    if sensitive is not None:
        raise ExplanationGenerationError(
            f"agent qualitative content rejected by sensitive-content scan: {sensitive}"
        )
    _require_narrative("summary", content.summary)
    for factor in content.key_factors:
        _require_narrative("key_factors", factor.factor)
    for text in content.conflicts:
        _require_narrative("conflicts", text)
    for text in content.data_gaps:
        _require_narrative("data_gaps", text)
    _require_refs_resolve(
        list(content.evidence_refs)
        + [factor.evidence_ref for factor in content.key_factors],
        catalog,
    )
    try:
        return DecisionExplanation(
            schema_version=SCHEMA_VERSION,
            run_id=run_id,
            source="agent",
            summary=content.summary,
            key_factors=content.key_factors,
            conflicts=content.conflicts,
            data_gaps=content.data_gaps,
            confidence_qualifier=content.confidence_qualifier,
            evidence_refs=content.evidence_refs,
            prompt_version=prompt_version,
            model_metadata_ref=model_metadata_ref,
        )
    except ValidationError:
        raise ExplanationGenerationError(
            "assembled agent explanation failed contract validation"
        ) from None
