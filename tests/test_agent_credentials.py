"""#21 — device token in OS keyring with JSON fallback."""

from agent import credentials, config


def test_store_load_clear_token(monkeypatch):
    store: dict[str, str] = {}

    class FakeKeyring:
        @staticmethod
        def set_password(service, user, token):
            store[f"{service}:{user}"] = token

        @staticmethod
        def get_password(service, user):
            return store.get(f"{service}:{user}")

        @staticmethod
        def delete_password(service, user):
            store.pop(f"{service}:{user}", None)

    monkeypatch.setitem(__import__("sys").modules, "keyring", FakeKeyring)

    assert credentials.store_token("secret-token") is True
    assert credentials.load_token() == "secret-token"
    credentials.clear_token()
    assert credentials.load_token() is None


def test_store_token_false_when_keyring_unavailable(monkeypatch):
    class Broken:
        @staticmethod
        def set_password(*_a, **_k):
            raise OSError("Credential Manager unavailable")

        @staticmethod
        def get_password(*_a, **_k):
            raise OSError("Credential Manager unavailable")

        @staticmethod
        def delete_password(*_a, **_k):
            raise OSError("Credential Manager unavailable")

    monkeypatch.setitem(__import__("sys").modules, "keyring", Broken)
    assert credentials.store_token("x") is False
    assert credentials.load_token() is None
    credentials.clear_token()


def test_config_prefers_keyring_and_strips_json(tmp_path, monkeypatch):
    store: dict[str, str] = {}
    monkeypatch.setattr(credentials, "store_token", lambda token: store.update(token=token) or True)
    monkeypatch.setattr(credentials, "load_token", lambda: store.get("token"))
    monkeypatch.setattr(credentials, "clear_token", lambda: store.pop("token", None))

    cfg = config.AgentConfig(
        server="https://test.example.com",
        token="keyring-token",
        device_id="device_1",
        user_id="user_1",
        name="PC",
    )
    config.save(tmp_path, cfg)
    on_disk = (tmp_path / "agent.json").read_text(encoding="utf-8")
    assert "keyring-token" not in on_disk
    loaded = config.load(tmp_path)
    assert loaded is not None
    assert loaded.token == "keyring-token"

    config.forget(tmp_path)
    assert config.load(tmp_path) is None


def test_config_falls_back_to_json_when_keyring_fails(tmp_path, monkeypatch):
    monkeypatch.setattr(credentials, "store_token", lambda token: False)
    monkeypatch.setattr(credentials, "load_token", lambda: None)
    monkeypatch.setattr(credentials, "clear_token", lambda: None)

    cfg = config.AgentConfig(
        server="https://test.example.com",
        token="json-token",
        device_id="device_2",
        user_id="user_2",
        name="PC",
    )
    config.save(tmp_path, cfg)
    on_disk = (tmp_path / "agent.json").read_text(encoding="utf-8")
    assert "json-token" in on_disk
    loaded = config.load(tmp_path)
    assert loaded is not None
    assert loaded.token == "json-token"
