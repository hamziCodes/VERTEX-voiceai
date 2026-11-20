"""Compatibility import for the durable webhook target model."""

from post_call.webhook.models import TenantWebhookTarget, WebhookTargetState

__all__ = ["TenantWebhookTarget", "WebhookTargetState"]
