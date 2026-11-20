from server.worker.pipeline.mapping import map_combined_scenes


def test_map_combined_fewer_photos_than_scenes():
    scene_descriptions = ["Scene 0", "Scene 1", "Scene 2", "Scene 3"]
    photo_ids = ["img-0", "img-1"]

    # 4 scenes, 2 photos
    # Scene 0 -> img-0, Scene 1 -> img-1, Scene 2 & 3 -> None (to be chained)
    mapped, unused = map_combined_scenes(scene_descriptions, photo_ids, duration_seconds=5.0)
    assert len(mapped) == 4
    assert unused == 0
    assert mapped[0].source_image_id == "img-0"
    assert mapped[1].source_image_id == "img-1"
    assert mapped[2].source_image_id is None
    assert mapped[3].source_image_id is None


def test_map_combined_more_photos_than_scenes():
    scene_descriptions = ["Scene 0", "Scene 1"]
    photo_ids = ["img-0", "img-1", "img-2"]

    # 2 scenes, 3 photos -> unused count is 1
    mapped, unused = map_combined_scenes(scene_descriptions, photo_ids, duration_seconds=5.0)
    assert len(mapped) == 2
    assert unused == 1
    assert mapped[0].source_image_id == "img-0"
    assert mapped[1].source_image_id == "img-1"
