"""On Render the visitor's real address comes from Cloudflare's headers (not the last X-Forwarded-For hop)."""
from app.security import client_ip


def test_render_uses_cloudflare_headers(app):
    app.config["BEHIND_CLOUDFLARE"] = True
    env = {"REMOTE_ADDR": "10.21.157.68"}
    with app.test_request_context("/", environ_base=env, headers={"X-Forwarded-For": "1.2.3.4, 104.22.17.40",
                                                                   "True-Client-IP": "39.40.1.2"}):
        assert client_ip() == "39.40.1.2"
    with app.test_request_context("/", environ_base=env, headers={"CF-Connecting-IP": "2a00:1450::1"}):
        assert client_ip() == "2a00:1450::1"
    with app.test_request_context("/", environ_base=env, headers={"True-Client-IP": "not-an-ip"}):
        assert client_ip() == "10.21.157.68"


def test_elsewhere_the_headers_are_ignored(app):
    app.config["BEHIND_CLOUDFLARE"] = False
    with app.test_request_context("/", environ_base={"REMOTE_ADDR": "203.0.113.9"},
                                  headers={"True-Client-IP": "39.40.1.2"}):
        assert client_ip() == "203.0.113.9"                 # a visitor cannot fake their address


def test_render_is_detected_automatically(monkeypatch):
    import importlib
    from app import config
    monkeypatch.setenv("RENDER", "true")
    monkeypatch.delenv("BEHIND_CLOUDFLARE", raising=False)
    importlib.reload(config)
    try:
        assert config.Config.BEHIND_CLOUDFLARE is True
    finally:
        monkeypatch.delenv("RENDER")
        importlib.reload(config)
