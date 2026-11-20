import os

from server.worker.providers.base import ProviderError, ShotRequest, ShotResult


class GeminiVideoProvider:
    name: str = "gemini-omni-1.2-flash"

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")

    def generate(self, request: ShotRequest) -> ShotResult:
        if not self.api_key:
            raise ProviderError("Gemini API key not configured", transient=False)

        # Rule 7: Duration cannot exceed 15 seconds
        if request.duration_seconds > 15.0 or request.duration_seconds < 5.0:
            raise ProviderError(
                "Duration exceeds Gemini Omni maximum clip length (5-15s)", transient=False
            )

        if request.source_image_path is not None and not request.source_image_path.exists():
            raise ProviderError(
                f"Source image not found: {request.source_image_path}", transient=False
            )

        # Provider would call google-genai client
        # In mock or when testing without real quota:
        raise ProviderError(
            "Live Gemini Omni cloud engine requires manual execution gate.", transient=True
        )
