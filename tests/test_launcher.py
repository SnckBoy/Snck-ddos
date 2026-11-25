import pytest

from launcher import server_settings


@pytest.mark.parametrize("host", ["0.0.0.0", "192.0.2.10", "example.com", "::"])
def test_non_loopback_bind_is_rejected(host):
    with pytest.raises(SystemExit, match="non-loopback"):
        server_settings({"SNCK_BIND_HOST": host, "SNCK_PORT": "6666"})


@pytest.mark.parametrize("host", ["127.0.0.1", "::1", "localhost", "LOCALHOST"])
def test_loopback_bind_is_allowed(host):
    assert server_settings({"SNCK_BIND_HOST": host, "SNCK_PORT": "6666"}) == (host.lower(), 6666)


@pytest.mark.parametrize("port", ["0", "65536", "-1", "not-a-number"])
def test_invalid_port_is_rejected(port):
    with pytest.raises(SystemExit):
        server_settings({"SNCK_BIND_HOST": "127.0.0.1", "SNCK_PORT": port})


def test_default_settings_are_loopback_only(monkeypatch):
    monkeypatch.delenv("SNCK_BIND_HOST", raising=False)
    monkeypatch.delenv("SNCK_PORT", raising=False)
    assert server_settings() == ("127.0.0.1", 6666)
