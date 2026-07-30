"""
Prime subscription and feature access module.

Provides business-scoped Prime memberships with configurable feature access.
"""

from .feature_registry import FEATURE_REGISTRY, get_feature, list_features
from .access import has_prime_feature, get_enabled_features, sync_is_prime_shim

__all__ = [
    "FEATURE_REGISTRY",
    "get_feature",
    "list_features",
    "has_prime_feature",
    "get_enabled_features",
    "sync_is_prime_shim",
]
