import json
import re
from dataclasses import dataclass

from server.app.config import settings


@dataclass
class SplitScene:
    position: int
    description: str
    duration_seconds: float
    split_method: str


def split_by_paragraphs(text: str, default_duration: float = 5.0) -> list[SplitScene]:
    """Split scenario text into scenes by double newlines."""
    if not text:
        return []

    # Split on two or more newlines
    raw_paragraphs = re.split(r"\n\s*\n", text.strip())
    scenes: list[SplitScene] = []

    for p in raw_paragraphs:
        cleaned = p.strip()
        if cleaned:
            scenes.append(
                SplitScene(
                    position=len(scenes),
                    description=cleaned,
                    duration_seconds=default_duration,
                    split_method="paragraph",
                )
            )
    return scenes


def split_with_llm(text: str, default_duration: float = 5.0, client=None) -> list[SplitScene]:
    """Split scenario text into scenes using Claude Haiku, falling back to paragraph splitting."""
    if not text or not text.strip():
        return []

    fallback = split_by_paragraphs(text, default_duration=default_duration)

    if client is None:
        if not settings.ANTHROPIC_API_KEY:
            return fallback
        try:
            import anthropic

            client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        except Exception:
            return fallback

    prompt = (
        "You are a cinematic director. Split the following scenario into visual scenes for video generation. "
        "Each scene must have a visual prompt description and a duration between 5.0 and 10.0 seconds. "
        "Return ONLY a JSON array of objects with keys 'prompt' (string) and 'duration' (float). "
        "No narration or audio fields. Do not omit any part of the story.\n\n"
        f"Scenario:\n{text}"
    )

    try:
        response = client.messages.create(
            model="claude-haiku-5-5",
            max_tokens=2048,
            messages=[{"role": "user", "content": prompt}],
        )
        content_text = ""
        for block in response.content:
            if hasattr(block, "text"):
                content_text += block.text
            elif isinstance(block, dict) and "text" in block:
                content_text += block["text"]

        # Parse JSON
        parsed = json.loads(content_text.strip())
        if not isinstance(parsed, list) or not parsed:
            return fallback

        llm_scenes: list[SplitScene] = []
        for i, item in enumerate(parsed):
            p_desc = item.get("prompt")
            dur = float(item.get("duration", default_duration))
            if not p_desc or dur < 5.0 or dur > 10.0:
                # Any validation failure falls back
                return fallback
            llm_scenes.append(
                SplitScene(
                    position=i,
                    description=str(p_desc).strip(),
                    duration_seconds=dur,
                    split_method="llm",
                )
            )
        return llm_scenes
    except Exception:
        return fallback
