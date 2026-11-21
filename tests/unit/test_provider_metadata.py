from dataclasses import fields

from server.worker.celery_app import celery_app
from server.worker.providers.base import ShotRequest
from server.worker.providers.registry import get_provider_class, registered_names


def test_every_provider_declares_capabilities():
    for name in registered_names():
        cls = get_provider_class(name)
        assert isinstance(cls.requires_photos, bool), name
        assert isinstance(cls.sends_data_externally, bool), name


def test_only_cloud_provider_sends_data_externally():
    assert get_provider_class("gemini-omni-1.2-flash").sends_data_externally is True
    assert get_provider_class("ltx-2.3").sends_data_externally is False
    assert get_provider_class("mock").sends_data_externally is False


def test_unknown_provider_class_is_none():
    assert get_provider_class("nope") is None


def test_shot_request_has_optional_motion_last():
    names = [f.name for f in fields(ShotRequest)]
    assert names[-1] == "motion"
    assert ShotRequest.__dataclass_fields__["motion"].default is None


def test_task_routes_split_planning_from_generation():
    routes = celery_app.conf.task_routes
    assert routes["run_job"]["queue"] == "generation"
    for name in ("draft_captions_task", "expire_old_jobs_task", "send_verification_email_task"):
        assert routes[name]["queue"] == "planning"
    assert celery_app.conf.task_default_queue == "generation"
