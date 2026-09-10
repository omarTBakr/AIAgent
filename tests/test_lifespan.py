"""The API can host the worker in-process. These tests drive the lifespan via
TestClient's context manager, which is what actually runs startup/shutdown."""

import pytest
from fastapi.testclient import TestClient

import main
from exceptions.workflow import TemporalConnectionError


class FakeWorker:
    def __init__(self, task_queue="process_pdf_queue"):
        self.task_queue = task_queue
        self.entered = False
        self.exited = False

    async def __aenter__(self):
        self.entered = True
        return self

    async def __aexit__(self, *args):
        self.exited = True


@pytest.fixture
def worker(monkeypatch):
    """Captures the worker the lifespan builds, if it builds one at all."""
    built = []

    async def fake_create():
        instance = FakeWorker()
        built.append(instance)
        return instance

    monkeypatch.setattr(main, "create_process_pdf_worker", fake_create)
    return built


def test_no_worker_when_the_setting_is_off(worker, monkeypatch):
    monkeypatch.setenv("RUN_WORKER_IN_API", "false")
    monkeypatch.setattr("utils.config._settings_instance", None)

    with TestClient(main.app) as client:
        assert client.get("/health").status_code == 200

    assert worker == []


def test_the_worker_runs_when_the_setting_is_on(worker, monkeypatch):
    monkeypatch.setenv("RUN_WORKER_IN_API", "true")
    monkeypatch.setattr("utils.config._settings_instance", None)

    with TestClient(main.app) as client:
        assert client.get("/health").status_code == 200
        assert len(worker) == 1
        assert worker[0].entered is True

    assert worker[0].exited is True


def test_the_worker_is_stopped_on_shutdown(worker, monkeypatch):
    monkeypatch.setenv("RUN_WORKER_IN_API", "true")
    monkeypatch.setattr("utils.config._settings_instance", None)

    with TestClient(main.app):
        pass

    assert worker[0].exited is True


def test_startup_fails_loudly_when_temporal_is_down(monkeypatch):
    """An API asked to host the worker but running without one is a trap:
    uploads would be accepted that nothing ever picks up."""
    monkeypatch.setenv("RUN_WORKER_IN_API", "true")
    monkeypatch.setattr("utils.config._settings_instance", None)

    async def explode():
        raise TemporalConnectionError("could not reach Temporal at localhost:7233")

    monkeypatch.setattr(main, "create_process_pdf_worker", explode)

    with pytest.raises(TemporalConnectionError), TestClient(main.app):
        pass


def test_the_setting_defaults_to_off(monkeypatch):
    """A fresh deployment must not silently host a worker."""
    from utils.config import Settings

    monkeypatch.delenv("RUN_WORKER_IN_API", raising=False)
    fields = Settings.model_fields

    assert fields["run_worker_in_api"].default is False


def test_the_setting_parses_truthy_strings(monkeypatch):
    import utils.config

    monkeypatch.setenv("RUN_WORKER_IN_API", "true")
    monkeypatch.setattr(utils.config, "_settings_instance", None)

    assert utils.config.get_setting().run_worker_in_api is True
