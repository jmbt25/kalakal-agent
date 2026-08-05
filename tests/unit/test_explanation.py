"""Unit tests for DecisionExplanation (§6.2.8): both source directions."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from kalakal.domain import DecisionExplanation
from tests.unit import factories as f


class TestAgentSource:
    def test_valid(self) -> None:
        explanation = f.make_explanation("agent")
        assert explanation.prompt_version == "prompt-1"
        assert explanation.model_metadata_ref == "invocation-1"
        assert explanation.explanation_template_version is None

    def test_missing_prompt_version_rejected(self) -> None:
        with pytest.raises(ValidationError, match="requires prompt_version"):
            f.make_explanation("agent", prompt_version=None)

    def test_missing_model_metadata_ref_rejected(self) -> None:
        with pytest.raises(ValidationError, match="requires model_metadata_ref"):
            f.make_explanation("agent", model_metadata_ref=None)

    def test_template_version_present_rejected(self) -> None:
        with pytest.raises(
            ValidationError, match="must not carry\\s+explanation_template_version"
        ):
            f.make_explanation("agent", explanation_template_version="template-1")


class TestOrchestratorSource:
    def test_valid(self) -> None:
        explanation = f.make_explanation("orchestrator")
        assert explanation.explanation_template_version == "template-1"
        assert explanation.prompt_version is None
        assert explanation.model_metadata_ref is None

    def test_missing_template_version_rejected(self) -> None:
        with pytest.raises(ValidationError, match="requires"):
            f.make_explanation("orchestrator", explanation_template_version=None)

    def test_prompt_version_present_rejected(self) -> None:
        with pytest.raises(ValidationError, match="must not carry prompt_version"):
            f.make_explanation("orchestrator", prompt_version="prompt-1")

    def test_model_metadata_ref_present_rejected(self) -> None:
        with pytest.raises(ValidationError, match="must not carry"):
            f.make_explanation("orchestrator", model_metadata_ref="invocation-1")


class TestExplanationStructure:
    @pytest.mark.parametrize("source", ["model", "AGENT", ""])
    def test_unknown_source_rejected(self, source: str) -> None:
        kwargs = f.explanation_kwargs("agent")
        kwargs["source"] = source
        with pytest.raises(ValidationError):
            DecisionExplanation(**kwargs)

    def test_overlong_summary_rejected(self) -> None:
        with pytest.raises(ValidationError):
            f.make_explanation("agent", summary="x" * 2001)

    def test_empty_summary_rejected(self) -> None:
        with pytest.raises(ValidationError):
            f.make_explanation("agent", summary="")

    def test_too_many_key_factors_rejected(self) -> None:
        factors = tuple(f.make_explanation("agent").key_factors[0] for _ in range(17))
        with pytest.raises(ValidationError):
            f.make_explanation("agent", key_factors=factors)

    @pytest.mark.parametrize("qualifier", ["certain", "HIGH", ""])
    def test_unknown_confidence_qualifier_rejected(self, qualifier: str) -> None:
        with pytest.raises(ValidationError):
            f.make_explanation("agent", confidence_qualifier=qualifier)

    def test_unknown_field_rejected(self) -> None:
        with pytest.raises(ValidationError):
            f.make_explanation("agent", numeric_edge_ppm=44_000)

    @pytest.mark.parametrize(
        "field",
        [
            "schema_version",
            "run_id",
            "source",
            "summary",
            "key_factors",
            "conflicts",
            "data_gaps",
            "confidence_qualifier",
            "evidence_refs",
        ],
    )
    def test_required_fields(self, field: str) -> None:
        kwargs = f.explanation_kwargs("agent")
        del kwargs[field]
        with pytest.raises(ValidationError):
            DecisionExplanation(**kwargs)
