import os

import pytest

from server.worker.providers.base import ShotRequest
from server.worker.providers.ltx import LtxVideoProvider


@pytest.mark.skipif(
    not os.getenv("LTX_COMFYUI_URL") or os.getenv("LTX_COMFYUI_URL") == "http://127.0.0.1:8188",
    reason="Requires active GPU with running ComfyUI service",
)
def test_ltx_gpu_workflow(tmp_path):
    provider = LtxVideoProvider()
    out = tmp_path / "ltx_shot.mp4"
    req = ShotRequest(
        prompt="A car driving down an empty highway at dusk",
        duration_seconds=5.0,
        width=832,
        height=480,
        fps=16,
        source_image_path=None,
        output_path=out,
    )
    res = provider.generate(req)
    assert res.clip_path.exists()
