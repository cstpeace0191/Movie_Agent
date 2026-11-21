import httpx

from server.app.config import settings
from server.worker.providers.base import ProviderError, ShotRequest, ShotResult


class LtxVideoProvider:
    name: str = "ltx-2.3"
    requires_photos: bool = False
    sends_data_externally: bool = False

    def __init__(self, comfyui_url: str | None = None):
        self.comfyui_url = comfyui_url or settings.LTX_COMFYUI_URL

    def generate(self, request: ShotRequest) -> ShotResult:
        if request.duration_seconds < 5.0 or request.duration_seconds > 10.0:
            raise ProviderError("Duration must be between 5 and 10 seconds", transient=False)

        if request.source_image_path is not None and not request.source_image_path.exists():
            raise ProviderError(
                f"Source image not found: {request.source_image_path}", transient=False
            )

        try:
            # Check connection
            with httpx.Client(timeout=2.0) as client:
                res = client.get(f"{self.comfyui_url}/system_stats")
                if res.status_code != 200:
                    raise ProviderError("ComfyUI server returned non-200 status", transient=True)
        except Exception as e:
            raise ProviderError(
                f"Cannot connect to local ComfyUI at {self.comfyui_url}: {e}", transient=True
            )

        raise ProviderError(
            "LTX-2.3 local generation workflow requires live GPU worker.", transient=True
        )
