from pathlib import Path

from sqlalchemy import create_engine, inspect, text

from server.app.db import ensure_schema_compatibility

# Minimal feature-001 shapes of the tables that feature 002 extends.
OLD_SCHEMA = [
    """CREATE TABLE users (
        id VARCHAR(36) PRIMARY KEY, username VARCHAR(32) NOT NULL,
        username_lower VARCHAR(32) NOT NULL, password_hash VARCHAR(255) NOT NULL,
        created_at DATETIME NOT NULL)""",
    """CREATE TABLE jobs (
        id VARCHAR(36) PRIMARY KEY, owner_id VARCHAR(36) NOT NULL,
        input_mode VARCHAR(32) NOT NULL, scenario TEXT, status VARCHAR(32) NOT NULL,
        progress INTEGER NOT NULL, message VARCHAR(200) NOT NULL,
        failure_reason VARCHAR(500), width INTEGER NOT NULL, height INTEGER NOT NULL,
        seconds_per_shot FLOAT NOT NULL, fps INTEGER NOT NULL, chain_frames BOOLEAN NOT NULL,
        provider VARCHAR(64) NOT NULL, external_consent_at DATETIME,
        planned_seconds FLOAT NOT NULL, unused_image_count INTEGER NOT NULL,
        final_video_path VARCHAR(500), created_at DATETIME NOT NULL,
        updated_at DATETIME NOT NULL, expires_at DATETIME NOT NULL)""",
    """CREATE TABLE source_images (
        id VARCHAR(36) PRIMARY KEY, job_id VARCHAR(36) NOT NULL, position INTEGER NOT NULL,
        media_type VARCHAR(64) NOT NULL, size_bytes INTEGER NOT NULL, alt_text VARCHAR(500),
        storage_path VARCHAR(500) NOT NULL, used BOOLEAN NOT NULL)""",
    """CREATE TABLE scenes (
        id VARCHAR(36) PRIMARY KEY, job_id VARCHAR(36) NOT NULL, position INTEGER NOT NULL,
        description TEXT NOT NULL, duration_seconds FLOAT NOT NULL,
        source_image_id VARCHAR(36), split_method VARCHAR(32) NOT NULL)""",
]

NEW_COLUMNS = {
    "jobs": {
        "render_options",
        "text_assist_consent_at",
        "review_confirmed_at",
        "bgm_path",
        "subtitles_srt_path",
        "subtitles_ass_path",
        "final_duration_seconds",
    },
    "scenes": {
        "kind",
        "caption",
        "caption_source",
        "narration",
        "transition",
        "motion",
        "start_seconds",
        "length_seconds",
    },
    "source_images": {"note"},
}


def _old_db(tmp_path: Path):
    eng = create_engine(f"sqlite:///{tmp_path / 'old.db'}")
    with eng.begin() as conn:
        for ddl in OLD_SCHEMA:
            conn.execute(text(ddl))
        conn.execute(
            text(
                "INSERT INTO scenes (id, job_id, position, description, duration_seconds,"
                " split_method) VALUES ('s1', 'j1', 0, 'A beach', 5.0, 'paragraph')"
            )
        )
    return eng


def test_adds_all_new_columns_without_data_loss(tmp_path: Path):
    eng = _old_db(tmp_path)
    ensure_schema_compatibility(eng)

    insp = inspect(eng)
    for table, cols in NEW_COLUMNS.items():
        existing = {c["name"] for c in insp.get_columns(table)}
        assert cols <= existing, f"{table} missing {cols - existing}"

    with eng.connect() as conn:
        row = conn.execute(text("SELECT description, kind FROM scenes WHERE id='s1'")).one()
    assert row[0] == "A beach"
    assert row[1] == "scene"


def test_running_twice_is_a_no_op(tmp_path: Path):
    eng = _old_db(tmp_path)
    ensure_schema_compatibility(eng)
    before = {t: {c["name"] for c in inspect(eng).get_columns(t)} for t in NEW_COLUMNS}
    ensure_schema_compatibility(eng)
    after = {t: {c["name"] for c in inspect(eng).get_columns(t)} for t in NEW_COLUMNS}
    assert before == after
