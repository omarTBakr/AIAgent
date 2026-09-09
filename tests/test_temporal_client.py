import asyncio

import pytest

import utils.temporal_client
from exceptions.workflow import TemporalConnectionError
from utils.temporal_client import CONNECT_TIMEOUT_SECONDS, get_temporal_client


@pytest.fixture(autouse=True)
def reset_client(monkeypatch):
    monkeypatch.setattr(utils.temporal_client, "_client", None)


async def test_a_hanging_connect_raises_rather_than_blocking(monkeypatch):
    """Client.connect retries forever when nothing is listening."""

    async def never_returns(*args, **kwargs):
        await asyncio.sleep(3600)

    monkeypatch.setattr(utils.temporal_client.Client, "connect", never_returns)
    monkeypatch.setattr(utils.temporal_client, "CONNECT_TIMEOUT_SECONDS", 0.05)

    with pytest.raises(TemporalConnectionError, match="timed out"):
        await get_temporal_client()


async def test_a_refused_connection_becomes_a_connection_error(monkeypatch):
    async def refused(*args, **kwargs):
        raise OSError("connection refused")

    monkeypatch.setattr(utils.temporal_client.Client, "connect", refused)

    with pytest.raises(TemporalConnectionError, match="could not reach Temporal"):
        await get_temporal_client()


async def test_the_client_is_cached(monkeypatch):
    calls = []

    async def connect(*args, **kwargs):
        calls.append(1)
        return object()

    monkeypatch.setattr(utils.temporal_client.Client, "connect", connect)

    first = await get_temporal_client()
    second = await get_temporal_client()

    assert first is second
    assert len(calls) == 1


async def test_it_connects_to_the_configured_host_and_namespace(monkeypatch, settings):
    seen = {}

    async def connect(target, **kwargs):
        seen["target"] = target
        seen["namespace"] = kwargs.get("namespace")
        return object()

    monkeypatch.setattr(utils.temporal_client.Client, "connect", connect)

    await get_temporal_client()

    assert seen["target"] == settings.temporal_host
    assert seen["namespace"] == settings.temporal_namespace


def test_the_timeout_is_a_sane_default():
    assert 0 < CONNECT_TIMEOUT_SECONDS <= 30
