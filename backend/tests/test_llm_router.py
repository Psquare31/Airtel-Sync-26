from types import SimpleNamespace

import pytest

from app.services.llm import LLMUnavailable, ModelRouter, _parse_reset, redact


class RateLimited(Exception):
    status_code = 429

    def __init__(self, retry_after="7"):
        super().__init__("rate_limit_exceeded")
        self.response = SimpleNamespace(headers={"retry-after": retry_after})


class FakeClient:
    def __init__(self, behaviour):
        self.behaviour = behaviour
        self.calls = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

    def create(self, model, **kw):
        self.calls.append(model)
        b = self.behaviour[model]
        if isinstance(b, Exception):
            raise b
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=b))],
                               usage=SimpleNamespace(total_tokens=10))


def test_rotates_on_429_and_cools_down():
    client = FakeClient({"a": RateLimited(), "b": '{"ok": 1}'})
    r = ModelRouter(client=client)
    data, info = r.chat_json([{"role": "user", "content": "hi"}], models=["a", "b"])
    assert data == {"ok": 1} and info.model == "b"
    assert r.cooling("a")
    client.calls.clear()
    r.chat_json([{"role": "user", "content": "hi"}], models=["a", "b"])
    assert client.calls == ["b"]  # 'a' is skipped while cooling


def test_cooldown_expires(monkeypatch):
    import app.services.llm as mod

    t = [1000.0]
    monkeypatch.setattr(mod.time, "monotonic", lambda: t[0])
    r = ModelRouter(client=FakeClient({"a": '{"x": 1}'}))
    r.cool_down("a", 5)
    assert r.cooling("a")
    t[0] += 6
    assert not r.cooling("a")


def test_malformed_json_moves_to_next_model():
    r = ModelRouter(client=FakeClient({"a": "not json at all", "b": '```json\n{"y": 2}\n```'}))
    data, info = r.chat_json([{"role": "user", "content": "x"}], models=["a", "b"])
    assert data == {"y": 2} and info.model == "b"


def test_all_exhausted_raises():
    r = ModelRouter(client=FakeClient({"a": RateLimited(), "b": RateLimited()}))
    with pytest.raises(LLMUnavailable):
        r.chat([{"role": "user", "content": "x"}], models=["a", "b"])


def test_parse_reset_formats():
    assert _parse_reset("2.5s") == 2.5
    assert _parse_reset("1m3s") == 63
    assert _parse_reset("450ms") == pytest.approx(0.45)
    assert _parse_reset("12") == 12


def test_redact():
    out = redact("my gst is 37IHKXV5167L1ZS call 9876543210 or a@b.com")
    assert "37IHK" not in out and "9876543210" not in out and "a@b.com" not in out


class NotFound(Exception):
    status_code = 404


def test_missing_model_is_parked_for_an_hour():
    r = ModelRouter(client=FakeClient({"gone": NotFound("model_not_found"), "b": '{"ok": 1}'}))
    _, info = r.chat_json([{"role": "user", "content": "x"}], models=["gone", "b"])
    assert info.model == "b" and r.status(["gone"])[0]["cooldown_s"] > 3000


def test_catalog_filters_unavailable_models():
    client = FakeClient({"a": '{"ok": 1}'})
    client.models = SimpleNamespace(list=lambda: SimpleNamespace(data=[SimpleNamespace(id="a")]))
    r = ModelRouter(client=client)
    _, info = r.chat_json([{"role": "user", "content": "x"}], models=["retired", "a"])
    assert info.model == "a" and client.calls == ["a"]
