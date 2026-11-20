from server.worker.pipeline.mapping import DEFAULT_MOTION_PROMPT, map_photo_only


def test_map_photo_only_three_images():
    image_ids = ["img-1", "img-2", "img-3"]
    scenes = map_photo_only(image_ids, duration_seconds=5.0)
    assert len(scenes) == 3
    for i, s in enumerate(scenes):
        assert s.position == i
        assert s.source_image_id == image_ids[i]
        assert s.description == DEFAULT_MOTION_PROMPT
        assert s.duration_seconds == 5.0
        assert s.split_method == "photo_only"
