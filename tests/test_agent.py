"""Desktop agent, with a fake server and a fake engine (no browser, no network)."""

from pathlib import Path

import pytest
import requests

from agent import config
from agent.client import ApiClient, ApiError, NetworkError
from agent.supervisor import STOP_GRACE_SECONDS, AgentStopped, Outbox, Supervisor


# ----------------------------------------------------------------------------- config
@pytest.mark.parametrize("url, ok", [
    ("https://app.applyxai.com/", True),
    ("http://127.0.0.1:8000", True),
    ("http://localhost:8000", True),
    ("http://192.168.1.20:8000", False),          # a device token must not cross the network in clear
    ("ftp://example.com", False),
    ("app.applyxai.com", False),
])
def test_server_urls(url, ok):
    if ok:
        assert not config.check_server_url(url).endswith("/")
    else:
        with pytest.raises(ValueError):
            config.check_server_url(url)
    assert config.check_server_url("http://192.168.1.20:8000", allow_insecure=True)


def test_config_round_trip_keeps_the_token_out_of_repr(tmp_path):
    cfg = config.AgentConfig(server="https://x.test", token="axd_secret", device_id="d1", user_id="u1", name="PC")
    config.save(tmp_path, cfg)
    assert config.load(tmp_path) == cfg
    assert "axd_secret" not in repr(cfg)
    config.forget(tmp_path)
    assert config.load(tmp_path) is None


# ----------------------------------------------------------------------------- client
class FakeResponse:
    def __init__(self, status, body=None, content=b""):
        self.status_code, self._body, self.content = status, body, content

    def json(self):
        if self._body is None:
            raise ValueError("not json")
        return self._body


class FakeSession:
    def __init__(self, *responses):
        self.responses, self.calls = list(responses), []

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def test_client_unwraps_envelopes_and_sends_the_device_token():
    session = FakeSession(FakeResponse(200, {"success": True, "data": {"run": None}}),
                          FakeResponse(409, {"success": False, "error": {"code": "SEQUENCE_GAP", "message": "x",
                                                                          "details": {"next_seq": 4}}}),
                          FakeResponse(502, None),
                          requests.ConnectionError("refused"),
                          FakeResponse(200, None, content=b"%PDF-"))
    client = ApiClient("https://x.test/", "axd_tok", session=session)
    assert client.poll() == {"run": None}
    method, url, kwargs = session.calls[0]
    assert (method, url) == ("POST", "https://x.test/api/agent/poll")
    assert kwargs["headers"]["Authorization"] == "Bearer axd_tok"
    with pytest.raises(ApiError) as err:
        client.post_events("r1", 9, [])
    assert err.value.code == "SEQUENCE_GAP" and err.value.details == {"next_seq": 4}
    with pytest.raises(NetworkError):
        client.poll()
    with pytest.raises(NetworkError) as net:
        client.poll()
    assert "axd_tok" not in str(net.value)
    assert client.download_resume("r1") == b"%PDF-"


# ----------------------------------------------------------------------------- outbox
def test_outbox_numbers_events_and_drops_only_what_the_server_confirmed():
    box = Outbox(next_seq=5)
    for n in range(3):
        box.add({"event": "applied", "n": n})
    assert box.batch() == (5, [{"event": "applied", "n": 0}, {"event": "applied", "n": 1}, {"event": "applied", "n": 2}])
    box.ack(7)
    assert box.batch() == (7, [{"event": "applied", "n": 2}])
    box.renumber_from(3)
    assert box.batch()[0] == 3 and box.next_seq == 4
    box.ack(4)
    assert box.batch() == (4, []) and box.count("applied") == 0


# ----------------------------------------------------------------------------- supervisor
class FakeEngine:
    """Plays a script: one list of events per tick. Exits after the script unless told to stop sooner."""

    def __init__(self, workspace, run_id, script, exit_on_stop=True, finish=True):
        self.dir = workspace.run_dir(run_id)
        self.log_path = self.dir / "engine.log"
        self.script = list(script)
        self.exit_on_stop, self.finish = exit_on_stop, finish
        self.config = None
        self.max_applied = None
        self.calls = []
        self.alive = False
        self.killed = False

    def start(self, cfg, max_applied=None):
        self.config, self.max_applied, self.alive = cfg, max_applied, True

    def pause(self):
        self.calls.append("pause")

    def resume(self):
        self.calls.append("resume")

    def request_stop(self):
        self.calls.append("stop")

    def stop(self, timeout=60):
        self.calls.append("stop")
        self.alive = False

    def kill(self):
        self.killed, self.alive = True, False

    @property
    def running(self):
        return self.alive

    @property
    def returncode(self):
        return None if self.alive else (-9 if self.killed else 0)

    def new_events(self):
        if not self.alive:
            return []
        if "stop" in self.calls and self.exit_on_stop:
            self.alive = False
            return [{"event": "run_finished", "stopped": True}] if self.finish else []
        if self.script:
            return self.script.pop(0)
        self.alive = False
        return [{"event": "run_finished", "stopped": False}] if self.finish else []


class FakeServer:
    """Stands in for ApiClient: records batches, answers with scripted controls."""

    def __init__(self, controls=(), remaining=10, failures=()):
        self.batches, self.controls, self.failures = [], list(controls), list(failures)
        self.remaining = remaining
        self.next_seq = 1

    def download_resume(self, run_id):
        return b"%PDF-1.4 resume"

    def post_events(self, run_id, first_seq, events):
        if self.failures:
            raise self.failures.pop(0)
        self.batches.append((first_seq, list(events)))
        fresh = events[self.next_seq - first_seq:]
        self.next_seq += len(fresh)
        self.remaining -= sum(1 for ev in fresh if ev.get("event") == "applied")
        control = self.controls.pop(0) if self.controls else "run"
        return {"next_seq": self.next_seq, "control": control, "remaining_applications": self.remaining}

    def events(self):
        seen = {}
        for first, events in self.batches:
            for i, ev in enumerate(events):
                seen.setdefault(first + i, ev)
        return [seen[k] for k in sorted(seen)]


PAYLOAD = {
    "id": "run-1", "dry_run": False, "control": "run", "next_seq": 1, "remaining_applications": 10,
    "values": {"first_name": "A", "last_name": "B", "phone_number": "9876543210", "search_terms": ["Dev"]},
    "resume": {"id": "r", "filename": "My CV (final).pdf", "file_type": "pdf", "file_size": 10},
}


class Clock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t

    def sleep(self, seconds):
        self.t += seconds


def supervise(tmp_path, server, script, payload=None, engines=None, **engine_kwargs):
    engines = [] if engines is None else engines

    def factory(workspace, run_id):
        engines.append(FakeEngine(workspace, run_id, script, **engine_kwargs))
        return engines[-1]

    clock = Clock()
    sup = Supervisor(server, tmp_path, "user-1", engine_factory=factory, sleep=clock.sleep, clock=clock)
    sup.execute(dict(PAYLOAD, **(payload or {})))
    return engines[0] if engines else None


def kinds(server):
    return [e["event"] for e in server.events()]


def test_a_run_reports_every_event_once_and_hands_the_engine_its_resume(tmp_path):
    server = FakeServer()
    engine = supervise(tmp_path, server, [[{"event": "run_started"}], [{"event": "applied", "job_id": "1"}], []])
    assert kinds(server) == ["run_started", "applied", "run_finished"]
    resume = Path(engine.config["questions"]["default_resume_path"])
    assert resume.name == "My CV final.pdf" and resume.read_bytes() == b"%PDF-1.4 resume"
    assert engine.config["secrets"]["username"] == "username@example.com"         # never real credentials
    assert Path(engine.config["settings"]["file_name"]).parent == tmp_path / "workspace" / "user-1" / "history"


def test_server_controls_reach_the_engine(tmp_path):
    server = FakeServer(controls=["pause", "pause", "run", "stop"])
    script = [[{"event": "run_started"}], [{"event": "paused"}], [{"event": "job_started", "job_id": "1"}],
              [{"event": "resumed"}], [{"event": "skipped", "job_id": "1"}], [], []]
    engine = supervise(tmp_path, server, script)
    assert engine.calls == ["pause", "resume", "stop"]
    assert server.events()[-1] == {"event": "run_finished", "stopped": True}


def test_the_agent_stops_the_engine_itself_when_the_plan_limit_is_reached(tmp_path):
    server = FakeServer(remaining=1)
    script = [[{"event": "applied", "job_id": "1"}, {"event": "applied", "job_id": "2"}], [{"event": "job_started", "job_id": "3"}]]
    engine = supervise(tmp_path, server, script, payload={"remaining_applications": 1})
    assert engine.max_applied == 1
    assert engine.calls == ["stop"]
    assert kinds(server)[-1] == "run_finished"


def test_a_practice_run_has_no_application_cap(tmp_path):
    engine = supervise(tmp_path, FakeServer(), [[]], payload={"dry_run": True, "remaining_applications": 3})
    assert engine.max_applied is None


def test_events_survive_a_dropped_connection(tmp_path):
    server = FakeServer(failures=[NetworkError("offline"), NetworkError("offline")])
    supervise(tmp_path, server, [[{"event": "run_started"}], [{"event": "applied", "job_id": "1"}], []])
    assert kinds(server) == ["run_started", "applied", "run_finished"]
    assert [first for first, _ in server.batches] == sorted(first for first, _ in server.batches)


def test_an_engine_crash_is_reported_with_the_counts_so_far(tmp_path):
    server = FakeServer()
    supervise(tmp_path, server, [[{"event": "applied", "job_id": "1"}], [{"event": "failed", "job_id": "2"}]],
              finish=False)
    final = server.events()[-1]
    assert final["event"] == "run_finished" and final["stopped"] is False
    assert "closed unexpectedly" in final["error"] and (final["applied"], final["failed"]) == (1, 1)


def test_an_engine_that_ignores_stop_is_closed_after_the_grace_period(tmp_path):
    server = FakeServer(controls=["stop"])
    script = [[{"event": "login_required"}]] + [[] for _ in range(int(STOP_GRACE_SECONDS) + 30)]
    engine = supervise(tmp_path, server, script, exit_on_stop=False, finish=False)
    assert engine.killed
    final = server.events()[-1]
    assert final["event"] == "run_finished" and final["stopped"] is True and final["error"] == ""


def test_a_run_without_a_resume_fails_without_starting_the_engine(tmp_path):
    server = FakeServer()
    engine = supervise(tmp_path, server, [], payload={"resume": None})
    assert engine.config is None
    (final,) = server.events()
    assert final["event"] == "run_finished" and "resume" in final["error"]


def test_a_disconnected_computer_stops_its_engine(tmp_path):
    server = FakeServer(failures=[ApiError(401, "DEVICE_UNAUTHORIZED", "This computer isn't connected.")])
    engines = []
    with pytest.raises(AgentStopped):
        supervise(tmp_path, server, [[{"event": "run_started"}]] * 5, engines=engines)
    assert engines[0].killed and "stop" in engines[0].calls


def test_a_sequence_gap_renumbers_and_resends(tmp_path):
    server = FakeServer(failures=[ApiError(409, "SEQUENCE_GAP", "Expected 1", {"next_seq": 1})])
    supervise(tmp_path, server, [[{"event": "run_started"}], []], payload={"next_seq": 7})
    assert server.batches[0][0] == 1 and kinds(server) == ["run_started", "run_finished"]


def test_poll_without_a_run_does_nothing_and_a_revoked_device_stops_the_agent(tmp_path):
    class Poller:
        def __init__(self, answer):
            self.answer = answer

        def poll(self):
            if isinstance(self.answer, Exception):
                raise self.answer
            return self.answer

    assert Supervisor(Poller({"run": None}), tmp_path, "u").run_once() is False
    with pytest.raises(AgentStopped):
        Supervisor(Poller(ApiError(401, "DEVICE_UNAUTHORIZED", "gone")), tmp_path, "u").run_once()
    with pytest.raises(NetworkError):
        Supervisor(Poller(ApiError(429, "RATE_LIMITED", "slow down")), tmp_path, "u").run_once()
