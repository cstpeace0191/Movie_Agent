from dataclasses import dataclass

DEFAULT_MOTION_PROMPT = "Slow cinematic motion, ambient atmosphere."


@dataclass
class MappedScene:
    position: int
    description: str
    duration_seconds: float
    source_image_id: str | None
    split_method: str


def map_photo_only(image_ids: list[str], duration_seconds: float = 5.0) -> list[MappedScene]:
    """Map a sequence of uploaded images to scenes with default motion prompts."""
    scenes: list[MappedScene] = []
    for i, img_id in enumerate(image_ids):
        scenes.append(
            MappedScene(
                position=i,
                description=DEFAULT_MOTION_PROMPT,
                duration_seconds=duration_seconds,
                source_image_id=img_id,
                split_method="photo_only",
            )
        )
    return scenes


def map_combined_scenes(
    descriptions: list[str],
    photo_ids: list[str],
    duration_seconds: float = 5.0,
) -> tuple[list[MappedScene], int]:
    """Map scenario descriptions and photos to scenes, returning (scenes, unused_count)."""
    scenes: list[MappedScene] = []
    num_photos = len(photo_ids)
    num_scenes = len(descriptions)
    unused_count = max(0, num_photos - num_scenes)

    for i, desc in enumerate(descriptions):
        assigned_photo = photo_ids[i] if i < num_photos else None
        scenes.append(
            MappedScene(
                position=i,
                description=desc,
                duration_seconds=duration_seconds,
                source_image_id=assigned_photo,
                split_method="paragraph",
            )
        )
    return scenes, unused_count
