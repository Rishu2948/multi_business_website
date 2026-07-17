"""
Feature Registry for Prime-gatable features.

All premium features that can be gated behind Prime membership
must be registered here with their metadata.
"""

from dataclasses import dataclass
from typing import Dict, Optional


@dataclass(frozen=True)
class PrimeFeature:
    key: str
    label: str
    description: str
    default_enabled: bool = False


FEATURE_REGISTRY: Dict[str, PrimeFeature] = {
    "ai_chatbot": PrimeFeature(
        key="ai_chatbot",
        label="AI Catalog Assistant",
        description="Conversational product discovery via the AI chatbot",
        default_enabled=True,
    ),
    "priority_support": PrimeFeature(
        key="priority_support",
        label="Priority Customer Support",
        description="Faster response times for support tickets",
        default_enabled=False,
    ),
    "free_delivery": PrimeFeature(
        key="free_delivery",
        label="Free Delivery",
        description="Waive delivery charges on all orders",
        default_enabled=False,
    ),
    "early_access": PrimeFeature(
        key="early_access",
        label="Early Access",
        description="Preview and purchase new products before general release",
        default_enabled=False,
    ),
}


def get_feature(key: str) -> Optional[PrimeFeature]:
    """Get a feature by key, or None if not registered."""
    return FEATURE_REGISTRY.get(key)


def list_features() -> Dict[str, PrimeFeature]:
    """Get all registered features."""
    return FEATURE_REGISTRY.copy()
