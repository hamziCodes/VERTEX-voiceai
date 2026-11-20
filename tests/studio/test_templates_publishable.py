"""Stage 3: an agent created from any template can be published as-is."""

from __future__ import annotations

from uuid import uuid4

import pytest

from control_plane.agents.models.agent_config import AgentConfig
from control_plane.agents.templates import list_templates, load_template
from control_plane.agents.validation.validator import AgentConfigValidator
from control_plane.routes.studio import _safe_template_config
from core.providers.spec import DEFAULT_PROVIDER_CATALOG


@pytest.mark.parametrize("template_id", sorted(list_templates()))
def test_template_routes_exist_in_the_provider_catalog(template_id: str) -> None:
    """Regression: templates named 'whisper', which the catalog does not
    have; Studio silently dropped it and the agent could not be published."""
    config = load_template(template_id)
    for groups in config["providers"].values():
        for group in groups:
            for route in group["routes"]:
                assert route["provider_id"] in DEFAULT_PROVIDER_CATALOG.provider_ids


@pytest.mark.parametrize("template_id", sorted(list_templates()))
def test_template_as_served_to_studio_passes_publish_validation(template_id: str) -> None:
    served = _safe_template_config(load_template(template_id))
    config = AgentConfig.model_validate({**served, "tenant_id": uuid4(), "agent_id": uuid4()})
    result = AgentConfigValidator().validate(config)
    assert result.is_valid, [error.message for error in result.errors]
