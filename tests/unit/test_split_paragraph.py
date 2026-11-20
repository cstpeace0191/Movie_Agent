from server.worker.pipeline.split import split_by_paragraphs


def test_split_by_paragraphs_basic():
    text = "Paragraph 1: Alice enters the dark forest.\n\nParagraph 2: She discovers a glowing lantern.\n\nParagraph 3: The lantern leads to a castle."
    scenes = split_by_paragraphs(text)
    assert len(scenes) == 3
    assert scenes[0].position == 0
    assert scenes[0].description == "Paragraph 1: Alice enters the dark forest."
    assert scenes[1].position == 1
    assert scenes[1].description == "Paragraph 2: She discovers a glowing lantern."
    assert scenes[2].position == 2
    assert scenes[2].description == "Paragraph 3: The lantern leads to a castle."


def test_split_by_paragraphs_ignores_blank_lines():
    text = "\n\n   \nScene 1.\n\n\n\nScene 2.\n   \n"
    scenes = split_by_paragraphs(text)
    assert len(scenes) == 2
    assert scenes[0].description == "Scene 1."
    assert scenes[1].description == "Scene 2."


def test_split_by_paragraphs_empty_text():
    assert split_by_paragraphs("") == []
    assert split_by_paragraphs("   \n\n  ") == []
