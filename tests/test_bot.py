from pathlib import Path

import httpx
import pytest

from app import llm as llm_mod
from app.bot import HANDOFF_REPLY, SupportBot
from app.config import Settings
from app.knowledge import KnowledgeBase, split_document, stem

DOCS = Path(__file__).resolve().parent.parent / "data" / "sample_docs"


@pytest.fixture
def settings(tmp_path):
    return Settings(docs_dir=DOCS, data_dir=tmp_path, llm_provider="offline")


# ---- knowledge base ------------------------------------------------------------
def test_stemmer():
    assert stem("delivery") == stem("delivered") == "deliver"
    assert stem("shipping") == "ship"
    assert stem("batteries") == "battery"


def test_split_keeps_headings():
    ps = split_document("faq.md", "# Returns\nYou can return it.\n\n# Hours\nOpen 9-5.")
    assert [p.heading for p in ps] == ["Returns", "Hours"]
    assert ps[0].source == "faq.md › Returns"


@pytest.mark.parametrize(
    "question, expected_heading",
    [
        ("How long does delivery take to Melbourne?", "Delivery times"),
        ("Can I return a bike I've ridden?", "30-day returns"),
        ("how much is the e-bike?", "Harbour E1 (e-bike)"),
        ("where is my order", "Tracking your order"),
        ("what are your opening hours", "Showroom address and opening hours"),
        ("which size for 172cm", "Which size do I need?"),
    ],
)
def test_search_finds_the_right_passage(question, expected_heading):
    kb = KnowledgeBase.from_dir(DOCS)
    assert kb.search(question, 1)[0][0].heading == expected_heading


# ---- bot behaviour ---------------------------------------------------------------
def test_answers_with_sources(settings):
    bot = SupportBot(settings)
    r = bot.answer("How long does delivery take to Melbourne?", session="t1")
    assert "5-8 business days" in r.answer
    assert r.sources[0] == "shipping.md › Delivery times"
    assert not r.handoff


def test_hands_off_when_unsure(settings):
    bot = SupportBot(settings)
    r = bot.answer("Can I pay with bitcoin?", session="t2")
    assert r.handoff and r.answer == HANDOFF_REPLY


def test_follow_up_uses_previous_question(settings):
    bot = SupportBot(settings)
    bot.answer("What are your opening hours on Saturday?", session="t3")
    r = bot.answer("and on Sunday?", session="t3")
    assert "Sunday" in r.answer


def test_leads_and_messages_are_stored(settings):
    import sqlite3

    bot = SupportBot(settings)
    bot.answer("Do you sell scooters?", session="t4")
    bot.save_lead("web", "t4", "Sam", "sam@example.com", "question")
    with sqlite3.connect(bot.db_path) as db:
        assert db.execute("SELECT COUNT(*) FROM messages").fetchone()[0] == 2
        assert db.execute("SELECT email FROM leads").fetchone()[0] == "sam@example.com"


# ---- real providers (HTTP mocked) -------------------------------------------------
class _Resp:
    def __init__(self, status, payload):
        self.status_code, self._payload, self.text = status, payload, str(payload)

    def json(self):
        return self._payload


def test_anthropic_provider(monkeypatch, tmp_path):
    seen = {}

    def fake_post(url, headers, json, timeout):
        seen.update(url=url, headers=headers, body=json)
        return _Resp(200, {"content": [{"type": "text", "text": "Interstate delivery takes 5-8 business days."}]})

    monkeypatch.setattr(llm_mod.httpx, "post", fake_post)
    s = Settings(docs_dir=DOCS, data_dir=tmp_path, llm_provider="anthropic", anthropic_api_key="test-key")
    r = SupportBot(s).answer("How long to Melbourne?", session="t5")
    assert r.answer == "Interstate delivery takes 5-8 business days." and r.provider == "anthropic"
    assert seen["url"].endswith("/v1/messages") and seen["headers"]["x-api-key"] == "test-key"
    assert "<context>" in seen["body"]["system"]


def test_model_can_trigger_handoff(monkeypatch, tmp_path):
    monkeypatch.setattr(
        llm_mod.httpx, "post", lambda *a, **k: _Resp(200, {"choices": [{"message": {"content": "[HANDOFF]"}}]})
    )
    s = Settings(docs_dir=DOCS, data_dir=tmp_path, llm_provider="openai", openai_api_key="k")
    r = SupportBot(s).answer("Do you price-match other stores?", session="t6")
    assert r.handoff and r.provider == "openai"  # the model, not the rules, decided


def test_falls_back_to_offline_when_the_api_fails(monkeypatch, tmp_path):
    def boom(*a, **k):
        raise httpx.ConnectError("network down")

    monkeypatch.setattr(llm_mod.httpx, "post", boom)
    s = Settings(docs_dir=DOCS, data_dir=tmp_path, llm_provider="openai", openai_api_key="k")
    r = SupportBot(s).answer("How long does delivery take to Melbourne?", session="t7")
    assert r.provider == "offline-fallback" and "5-8" in r.answer
