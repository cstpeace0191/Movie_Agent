import json
from unittest.mock import MagicMock

from server.worker.pipeline.split import split_with_llm


def test_split_with_llm_success(monkeypatch):
    mock_client = MagicMock()
    # Mock LLM returning valid json
    valid_response = json.dumps(
        [
            {"prompt": "A bustling futuristic city street.", "duration": 6.0},
            {"prompt": "A flying vehicle lands gently on the platform.", "duration": 5.5},
        ]
    )
    mock_message = MagicMock()
    mock_message.content = [MagicMock(text=valid_response)]
    mock_client.messages.create.return_value = mock_message

    text = "Scene one.\n\nScene two."
    scenes = split_with_llm(text, client=mock_client)

    # Assert Haiku model used
    call_args = mock_client.messages.create.call_args[1]
    assert call_args["model"] == "claude-haiku-5-5"
    assert len(scenes) == 2
    assert scenes[0].description == "A bustling futuristic city street."
    assert scenes[0].duration_seconds == 6.0
    assert scenes[0].split_method == "llm"


def test_split_with_llm_fallback_on_invalid_json(monkeypatch):
    mock_client = MagicMock()
    mock_message = MagicMock()
    mock_message.content = [MagicMock(text="Not valid json")]
    mock_client.messages.create.return_value = mock_message

    text = "Paragraph 1.\n\nParagraph 2."
    scenes = split_with_llm(text, client=mock_client)
    assert len(scenes) == 2
    assert scenes[0].description == "Paragraph 1."
    assert scenes[0].split_method == "paragraph"


def test_split_with_llm_fallback_on_invalid_duration(monkeypatch):
    mock_client = MagicMock()
    # Duration outside 5-10
    invalid_response = json.dumps([{"prompt": "A scene.", "duration": 20.0}])
    mock_message = MagicMock()
    mock_message.content = [MagicMock(text=invalid_response)]
    mock_client.messages.create.return_value = mock_message

    text = "Original paragraph."
    scenes = split_with_llm(text, client=mock_client)
    assert len(scenes) == 1
    assert scenes[0].description == "Original paragraph."
    assert scenes[0].split_method == "paragraph"
