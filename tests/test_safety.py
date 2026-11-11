import asyncio

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

import command_center as app_module
from command_center import SafeResolver
from command_center import TestConfig as RunConfig


def test_loopback_target_is_allowed():
    assert app_module.validate_target("http://127.0.0.1:8000/health") == "http://127.0.0.1:8000/health"


def test_unlisted_host_is_rejected(monkeypatch):
    monkeypatch.setattr(app_module, "ALLOWED_HOSTS", {"localhost", "127.0.0.1", "::1"})
    with pytest.raises(HTTPException) as error:
        app_module.validate_target("https://not-allowlisted.example/health")
    assert error.value.status_code == 403


def test_allowlisted_public_host_uses_standard_port(monkeypatch):
    monkeypatch.setattr(app_module, "ALLOWED_HOSTS", {"localhost", "127.0.0.1", "::1", "status.example"})
    assert app_module.validate_target("https://status.example/health")


def test_public_nonstandard_port_is_rejected(monkeypatch):
    monkeypatch.setattr(app_module, "ALLOWED_HOSTS", {"localhost", "127.0.0.1", "::1", "status.example"})
    with pytest.raises(HTTPException) as error:
        app_module.validate_target("https://status.example:8443/health")
    assert error.value.status_code == 400


@pytest.mark.parametrize("url", [
    "ftp://127.0.0.1/file",
    "http://user:pass@127.0.0.1:8000/",
    "not-a-url",
])
def test_invalid_url_forms_are_rejected(url):
    with pytest.raises(HTTPException):
        app_module.validate_target(url)


@pytest.mark.parametrize("config", [
    {"target": "http://127.0.0.1:8000/", "rate": 0},
    {"target": "http://127.0.0.1:8000/", "rate": 11},
    {"target": "http://127.0.0.1:8000/", "workers": 6},
    {"target": "http://127.0.0.1:8000/", "duration": 61},
    {"target": "http://127.0.0.1:8000/", "method": "POST"},
])
def test_run_limits_are_enforced(config):
    with pytest.raises(ValidationError):
        RunConfig(**config)


def test_resolver_accepts_loopback_only_for_local_target():
    result = asyncio.run(SafeResolver().resolve("127.0.0.1", 8000))
    assert result[0]["host"] == "127.0.0.1"


def test_resolver_rejects_private_ip_literal():
    with pytest.raises(OSError):
        asyncio.run(SafeResolver().resolve("10.0.0.8", 80))
