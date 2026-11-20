from typing import cast

from server.worker.providers.base import ProviderError, VideoProvider
from server.worker.providers.gemini import GeminiVideoProvider
from server.worker.providers.ltx import LtxVideoProvider
from server.worker.providers.mock import MockVideoProvider

# Central provider registry (FR-016: no engine name outside worker/providers)
_PROVIDERS: dict[str, type[VideoProvider]] = {
    "ltx-2.3": LtxVideoProvider,
    "mock": MockVideoProvider,
    "gemini-omni-1.2-flash": GeminiVideoProvider,
}


def register_provider(name: str, provider_cls: type[VideoProvider]) -> None:
    """Register a VideoProvider class under a given engine name."""
    _PROVIDERS[name] = provider_cls


def is_registered(name: str) -> bool:
    """Check whether a video provider name is registered."""
    return name in _PROVIDERS


def get_provider(name: str) -> VideoProvider:
    """Instantiate and return the registered VideoProvider for the given engine name."""
    cls = _PROVIDERS.get(name)
    if not cls:
        raise ProviderError(f"Unknown or unsupported video provider '{name}'", transient=False)
    return cast(VideoProvider, cls())
