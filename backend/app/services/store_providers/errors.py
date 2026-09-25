"""Exceptions raised by the store provider service.

These signal *programming* or *infrastructure* faults. A store simply not
supporting a feature is not an exception — it is a declared capability and a
per-item status (see ``models.py``). The orchestrator therefore catches
``ProviderUnavailableError`` and degrades; it never catches
``CapabilityNotSupportedError``, because reaching that means the caller skipped
the ``supports()`` check and that is a bug worth surfacing.
"""

from __future__ import annotations


class ProviderError(Exception):
    """Base class for store provider failures."""


class ProviderNotFoundError(ProviderError):
    """No provider is registered under that slug."""


class CapabilityNotSupportedError(ProviderError):
    """A capability was invoked on a provider that never declared it."""


class ProviderUnavailableError(ProviderError):
    """The store could not be reached, or answered in a shape we cannot read.

    Always transient from the caller's point of view: the orchestrator turns
    this into a degraded result rather than an error response.
    """


class ProviderConfigurationError(ProviderError):
    """A provider is registered inconsistently (declared capability with no
    implementation, duplicate slug, ...). Raised at import time, on purpose."""
