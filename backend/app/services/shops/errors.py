"""Exceptions raised by the shop integration service.

These signal *programming* or *infrastructure* faults. A shop simply not
supporting a feature is not an exception — it is a declared capability and a
per-item status (see ``models.py``). The orchestrator therefore catches
``ShopUnavailableError`` and degrades; it never catches
``CapabilityNotSupportedError``, because reaching that means the caller skipped
the ``supports()`` check and that is a bug worth surfacing.
"""

from __future__ import annotations


class ShopError(Exception):
    """Base class for shop integration failures."""


class ShopNotFoundError(ShopError):
    """No provider is registered under that slug."""


class CapabilityNotSupportedError(ShopError):
    """A capability was invoked on a provider that never declared it."""


class ShopUnavailableError(ShopError):
    """The shop could not be reached, or answered in a shape we cannot read.

    Always transient from the caller's point of view: the orchestrator turns
    this into a degraded result rather than an error response.
    """


class ShopConfigurationError(ShopError):
    """A provider is registered inconsistently (declared capability with no
    implementation, duplicate slug, ...). Raised at import time, on purpose."""
