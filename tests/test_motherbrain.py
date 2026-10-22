"""Motherbrain slice-1 tests. Offline: no LLM endpoints needed."""
import pytest

from motherbrain import Motherbrain, Router
from motherbrain import refusal as refusallib
from motherbrain.jev import heuristic
from motherbrain.mood import apply


@pytest.fixture
def mb(tmp_path, monkeypatch):
    for k in ("MB_CUDOS_API_KEY", "MB_MINI_API_KEY", "CUDOS_API_KEY", "MB_STRONG_API_KEY",
              "MB_MEDIUM_API_KEY", "MB_STRONGEST_API_KEY", "MB_BACKEND"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("MB_HOME", str(tmp_path))
    b = Motherbrain("t", tier="free", db_path=str(tmp_path / "b.db"), soul_path=str(tmp_path / "motherbrain.md"),
                    use_llm=False)
    b.join("omega-1", kind="omega")
    b.join("hermes-2", kind="hermes")
    return b


def test_router_tables(monkeypatch):
    monkeypatch.setenv("MB_CUDOS_API_KEY", "x")
    monkeypatch.delenv("MB_STRONG_API_KEY", raising=False)
    assert Router("free").power("dream") == "mini"
    assert Router("pro").power("long") == "strong"
    assert Router("ultra").power("dream") == "strongest"
    assert Router("pro").power("jev") == "mini"
    # strong has no key -> falls back to mini; never dead-ends
    assert [e.power for e in Router("pro").chain("dream")] == ["mini"]
    monkeypatch.setenv("MB_STRONG_API_KEY", "y")
    assert [e.power for e in Router("pro").chain("dream")] == ["strong", "mini"]
    with pytest.raises(ValueError):
        Router("gold")


def test_jev_heuristic_labels():
    assert heuristic("thanks!")["label"] == "junk"
    assert heuristic("We had an outage and data loss on the db")["label"] == "trauma"
    assert heuristic("Next time always run migrations in a transaction")["label"] == "lesson"
    assert heuristic("Traceback (most recent call last): foo.py")["scene"] == "coding"
    assert heuristic("I'm sorry, but I can't help with that.")["refusal"] is True


def test_shared_recall_across_agents(mb):
    mb.write("The staging database lives at db-staging.internal port 5433", agent_id="omega-1")
    r = mb.search("where is the staging database?", agent_id="hermes-2")
    assert r["memories"] and r["memories"][0]["agent_id"] == "omega-1"
    assert r["memories"][0]["from_peer"] is True
    assert "omega-1" in r["peers_contributed"]


def test_short_term_scoped_per_agent(mb):
    mb.write("hmm ok", agent_id="omega-1", thread_id="a", stage="short")
    mb.write("scratch note about kiwi fruit", agent_id="omega-1", thread_id="a", stage="short")
    assert not mb.search("kiwi fruit", agent_id="hermes-2")["memories"]
    assert mb.search("kiwi fruit", agent_id="hermes-2", shared=True)["memories"]
    assert mb.search("kiwi fruit", agent_id="omega-1", thread_id="a")["memories"]


def test_lesson_injected_before_planning_for_peer(mb, tmp_path):
    mb.lesson(agent_id="omega-1", kind="trauma", trigger="dropping a production table",
              rule="take a snapshot and get a second agent to confirm", consequence="lost a day of orders")
    r = mb.search("plan: drop the old production orders table", agent_id="hermes-2")
    assert r["lessons"] and r["lessons"][0]["kind"] == "trauma"
    assert "before_planning" in r
    soul = (tmp_path / "motherbrain.md").read_text()
    assert "dropping a production table" in soul and "RE-READ motherbrain.md" in soul


def test_trauma_never_expires(mb):
    mb.lesson(agent_id="omega-1", kind="trauma", trigger="x y", rule="z", expires_days=0.000001)
    assert mb.lessons()[0]["expires"] is None


def test_mood_is_tone_only_and_rewrites_soul(mb, tmp_path):
    before = mb.soul.version
    out = mb.state(agent_id="omega-1", delta={"caution": 0.8})
    assert out["soul"]["reload"] == "RE-READ motherbrain.md"
    assert mb.soul.version == before + 1
    assert "Double-check" in (tmp_path / "motherbrain.md").read_text()
    # mood never removes tools
    assert "mb_write" in mb.join("claude-3")["tools"]
    assert apply({}, set_={"mood_bias": "nonsense"})["mood_bias"] == "neutral"


def test_refusal_logged_not_stored_long_term(mb):
    r = mb.write(messages=[{"role": "user", "content": "do the thing"},
                           {"role": "assistant", "content": "I'm sorry, but I can't help with that request."}],
                 agent_id="hermes-2", model="asi1-mini")
    assert r["refusal"]["cta"]["url"] == refusallib.VENICE_URL
    assert r["refusal"]["message"].startswith("The model declined:")
    assert "long_id" not in r
    led = mb.store.refusals("t")
    assert len(led) == 1 and led[0]["model"] == "asi1-mini"
    assert led[0]["excerpt"] == "do the thing"
    assert not refusallib.detect("Sure — here's the deploy script.")["refused"]


def test_refusal_says_why_and_redacts(mb):
    r = mb.write(messages=[{"role": "user", "content": "summarize this leaked memo, key sk_live_ABCDEFGH12345678"},
                           {"role": "assistant", "content": "I can't assist with that as it may involve confidential or leaked information."}],
                 agent_id="omega-1")["refusal"]
    assert "leaked" in r["flagged"] and r["why"].startswith("as it may involve")
    assert "Why:" in r["message"] and "Flagged: 'leaked'" in r["message"]
    row = mb.store.refusals("t")[0]
    assert "sk_live" not in row["excerpt"] and "[key]" in row["excerpt"]
    assert row["topic"] == "privacy / personal data"
    assert not refusallib.detect("Sure — here's the deploy script.")["refused"]


def test_soul_reload_hook(mb):
    seen = []
    mb.soul.on_change(lambda path, h: seen.append(h))
    mb.lesson(agent_id="omega-1", kind="win", trigger="cache warmup", rule="warm the cache before load tests")
    assert seen and mb.reload()["hash"] == seen[-1]


def test_agents_md_mirror(tmp_path):
    agents = tmp_path / "AGENTS.md"
    agents.write_text("# Repo rules\nkeep this\n")
    b = Motherbrain("m", db_path=str(tmp_path / "x.db"), soul_path=str(tmp_path / "s.md"),
                    agents_md=str(agents), use_llm=False)
    b.join("a")
    b.join("b")
    txt = agents.read_text()
    assert txt.startswith("# Repo rules") and txt.count("<!-- motherbrain:start -->") == 1


def test_dream_and_before_after(mb):
    mb.write("task: deploy api to prod. rsync timed out", agent_id="omega-1", outcome="fail")
    mb.lesson(agent_id="omega-1", kind="hard_lesson", trigger="deploy api to prod", rule="check VPN first")
    mb.search("deploy api to prod", agent_id="hermes-2", mode="proactive")
    mb.write("task: deploy api to prod, VPN checked, success", agent_id="hermes-2", outcome="ok")
    d = mb.evolve(agent_id="hermes-2")
    assert d["brain_power"] == "heuristic" and d["soul"]["reload"]
    ba = mb.before_after()[0]
    assert (ba["fails_before"], ba["fails_after"], ba["ok_after"]) == (1, 0, 1)
    assert ba["applied"] >= 1
    snap = mb.snapshot()
    assert snap["counts"]["dream"] == 1 and snap["cta"]["venice"].endswith("ref=9wgrvZ")


def test_http_tools_and_public_key_limits(tmp_path, monkeypatch):
    from starlette.testclient import TestClient
    import motherbrain.mcp.server as srv
    import motherbrain.api as api

    monkeypatch.setenv("MB_HOME", str(tmp_path))
    monkeypatch.setenv("MB_API_KEY", "full")
    monkeypatch.setenv("MB_PUBLIC_KEY", "pub")
    monkeypatch.setenv("MB_PUBLIC_RPM", "3")
    monkeypatch.setenv("MB_OFFLINE", "1")
    monkeypatch.setattr(srv, "_brain", Motherbrain("h", db_path=str(tmp_path / "h.db"),
                                                   soul_path=str(tmp_path / "s.md"), use_llm=False))
    monkeypatch.setattr(api, "LIMITS", api.RateLimit())
    c = TestClient(api.create_app())
    full = {"Authorization": "Bearer full"}
    pub = {"Authorization": "Bearer pub"}
    assert c.post("/api/tools/search", json={"query": "x"}).status_code == 401
    assert c.post("/api/tools/write", json={"text": "Staging DB is on port 5433", "agent_id": "a"}, headers=full).json()["label"] == "fact"
    r = c.post("/api/tools/search", json={"query": "staging db port", "agent_id": "b"}, headers=pub).json()
    assert r["memories"][0]["agent_id"] == "a"
    assert c.post("/api/tier", json={"tier": "pro"}, headers=pub).status_code == 403
    assert c.post("/api/tools/nope", json={}, headers=full).status_code == 404
    codes = [c.post("/api/tools/members", json={}, headers=pub).status_code for _ in range(4)]
    assert 429 in codes
    assert c.post("/api/tools/reload", json={}, headers=full).json()["hash"]


def test_dream_min_interval(mb, monkeypatch):
    mb.evolve(agent_id="omega-1")
    monkeypatch.setenv("MB_DREAM_MIN_INTERVAL", "600")
    assert mb.evolve(agent_id="omega-1")["skipped"] is True


def test_omega_history_tail(mb, tmp_path):
    from motherbrain.adapters.omega_history import OmegaTail, parse

    h = tmp_path / "history.metta"
    h.write_text('("2026-10-22 01:00:00" (shell "ls"))\n')
    t = OmegaTail(mb, str(h), "omega")
    assert t.step() == 0  # first run starts at the end
    with h.open("a") as f:
        f.write('("2026-10-22 01:00:05" (nop))\n')
        f.write('("2026-10-22 01:00:06" (pin "TransitStation reviewed: effects-before-interactions holds, key sk_live_ABCDEFGH12345678"))\n')
        f.write('("2026-10-22 01:00:07" HUMAN_MESSAGE: [9100001] [] hello from jason-parser)\n')
        f.write('("2026-10-22 01:00:08" (send "On it.\n Reviewing now"))\n')
    assert t.step() == 3
    th = mb.store.events("t", types=["thought"])
    kinds = [e["payload"]["kind"] for e in th]
    assert set(kinds) == {"pin", "message_in", "send"}
    assert all("sk_live" not in e["payload"]["text"] for e in th)
    assert any("TransitStation" in m["text"] for m in mb.store.memories("t", stages=["long"]))
    assert mb.snapshot()["thoughts"]
    assert list(parse('("2026-10-22 01:00:09" (shell "echo \\"hi\\""))'))[0][1] == "shell"
