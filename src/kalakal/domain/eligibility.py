"""Shared pure §5.6 candidate-eligibility derivation.

One evaluator serves both the decision-record validator (which re-derives
and enforces every persisted eligibility result) and the slice 6
orchestrator (which computes the result the first time), so eligibility
logic is never duplicated and a record can never carry a forged result.

The function is pure: it reads only the candidate evidence it is given —
never the clock, scenario oracle fields (``expected_outcome_class``,
``expected_reason_code``), files, or network. Staleness is deliberately not
an eligibility signal (§5.6, §7.7): stale evidence stays eligible so the
policy engine can reject it with ``POLICY_STALE_DATA``. Non-estimator gaps
or conflicts — including everything declared on the market snapshot — leave
a candidate eligible; only the ``MATCH_ESTIMATOR_FIELDS`` evidence gates
selection.
"""

from __future__ import annotations

from kalakal.domain.market import CandidateMarket
from kalakal.domain.match import MATCH_ESTIMATOR_FIELDS, MatchContext
from kalakal.domain.primitives import EligibilityReason


def derive_ineligibility_reasons(
    market: CandidateMarket, match_context: MatchContext
) -> tuple[EligibilityReason, ...]:
    """Return the exact §5.6 ineligibility reasons, in stable order.

    Stable order: ``NOT_OPEN``, ``ESTIMATOR_INPUT_MISSING``,
    ``ESTIMATOR_INPUT_CONFLICTED``. An empty tuple means the candidate is
    eligible.
    """
    reasons: list[EligibilityReason] = []
    if market.status != "open":
        reasons.append("NOT_OPEN")
    quality = match_context.data_quality
    if any(path in MATCH_ESTIMATOR_FIELDS for path in quality.missing_fields):
        reasons.append("ESTIMATOR_INPUT_MISSING")
    if any(
        conflict.field_path in MATCH_ESTIMATOR_FIELDS for conflict in quality.conflicts
    ):
        reasons.append("ESTIMATOR_INPUT_CONFLICTED")
    return tuple(reasons)
