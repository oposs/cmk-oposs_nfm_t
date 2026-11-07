"""Tests for the special agent agent_oposs_nfm_t (runs on the Checkmk server).

The agent reads three NFM-T REST endpoints, sorts the alarms onto the nodes
and writes one piggyback block per node. No network is used: DNS and
requests are patched, and the answers below carry the fields the agent reads
from the NFM-T REST API (the repository holds no captured answers).

The last tests feed the agent output through the check plugin, so a format
change on either side shows up here.
"""

import importlib.util
import json
import os
import pathlib
import subprocess
import sys
import types
from importlib.machinery import SourceFileLoader

import pytest
from cmk.agent_based.v2 import Result, State

ROOT = pathlib.Path(__file__).resolve().parent.parent
PLUGIN = ROOT / "local/lib/python3/cmk_addons/plugins/oposs_nfm_t"
AGENT = PLUGIN / "libexec/agent_oposs_nfm_t"
CHECK = PLUGIN / "agent_based/oposs_nfm_t.py"


def _load_agent():
    """Load the agent with the one monolith module it needs stubbed.

    cmk.utils.password_store exists only inside a Checkmk site. The stub is
    put in sys.modules for the import only.
    """
    password_store = types.ModuleType("cmk.utils.password_store")
    password_store.replace_passwords = lambda: None
    stubs = {"cmk.utils.password_store": password_store}
    if "cmk.utils" not in sys.modules:
        utils = types.ModuleType("cmk.utils")
        utils.password_store = password_store
        stubs["cmk.utils"] = utils
    saved = {k: sys.modules.get(k) for k in stubs}
    sys.modules.update(stubs)
    try:
        loader = SourceFileLoader("agent_oposs_nfm_t", str(AGENT))
        spec = importlib.util.spec_from_loader(loader.name, loader)
        module = importlib.util.module_from_spec(spec)
        loader.exec_module(module)
        return module
    finally:
        for key, value in saved.items():
            if value is None:
                sys.modules.pop(key, None)
            else:
                sys.modules[key] = value


@pytest.fixture(scope="module")
def agent():
    return _load_agent()


@pytest.fixture(scope="module")
def check():
    spec = importlib.util.spec_from_file_location("test_oposs_nfm_t_check_e2e", CHECK)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# --- NFM-T REST answers --------------------------------------------------------

ALARMS = {"response": {"data": [
    {"neName": "OTN-ZH-01", "neId": "100/1", "severity": "minor",
     "additionalText": "Fan unit 2 speed low"},
    {"neName": "OTN-ZH-01", "neId": "100/1", "severity": "critical",
     "additionalText": "Loss of signal on 1/2/C1"},
    {"neName": "OTN-BE-02", "neId": "100/2", "severity": "major",
     "additionalText": "Signal degrade on 1/3/C1"},
    # A management system alarm: its NE is not in the node list
    {"neName": "MNC-FM", "neId": "9/1", "severity": "major",
     "additionalText": "Database backup failed"},
    # An adapter alarm without neName
    {"neId": "NSP-ADAPTER-7", "severity": "minor", "additionalText": "Adapter restarted"},
]}}

NODES = {"items": [
    {"guiLabel": "OTN-ZH-01", "id": "100/1"},
    {"guiLabel": "OTN-BE-02", "id": "100/2"},
    {"guiLabel": "OTN-GE-03", "id": "100/3"},
]}

PATH_ZH_BE = {
    "id": "4711", "guiLabel": "ZH-BE 100G", "operationalState": "Up",
    "alarmState": "Cleared", "alarmSeverity": "Cleared", "aPortLabel": "1/2/C1",
    "zPortLabel": "1/3/C1", "effectiveRate": "100GbE", "a1NodeName": "OTN-ZH-01",
    "z1NodeName": "OTN-BE-02", "pathType": "ODU4",
}
PATH_ZH_GE = {
    "id": "4712", "guiLabel": "ZH-GE 10G", "operationalState": "Down",
    "alarmState": "Raised", "alarmSeverity": "Critical", "aPortLabel": "1/4/C1",
    "zPortLabel": "1/1/C2", "effectiveRate": "10GbE", "a1NodeName": "OTN-ZH-01",
    "z1NodeName": "OTN-GE-03",
}
PATHS = {"items": [PATH_ZH_BE, PATH_ZH_GE, {"guiLabel": "path without id"}]}


class _Response:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code
        self.text = json.dumps(payload)

    def json(self):
        return self._payload


class _Calls(list):
    """The requests the agent made; .answers is what the server returns."""


@pytest.fixture
def nfmt(agent, monkeypatch):
    """An NFM-T server; returns the list of requests the agent made."""
    calls = _Calls()
    answers = {
        "FaultManagement/rest/api/v2/alarms/details": ALARMS,
        "oms1350/data/otn/node/": NODES,
        "oms1350/data/otn/connection/path": PATHS,
    }

    def post(url, **kwargs):
        calls.append(("POST", url, kwargs))
        if url.endswith("auth/token"):
            return _Response({"access_token": "tok-1", "token_type": "Bearer"})
        return _Response({})

    def request(method, url, **kwargs):
        calls.append((method, url, kwargs))
        for path, payload in answers.items():
            if url.endswith(path):
                return _Response(payload)
        return _Response({"error": "not found"}, 404)

    monkeypatch.setattr(agent.socket, "gethostbyname", lambda host: "192.0.2.20")
    monkeypatch.setattr(agent.requests, "post", post)
    monkeypatch.setattr(agent.requests, "request", request)
    monkeypatch.setattr(agent.time, "sleep", lambda s: None)
    calls.answers = answers
    return calls


def _run(agent, capsys, *extra):
    argv = ["-u", "monitor", "-p", "secret", *extra, "nfmt.example.net"]
    with pytest.raises(SystemExit) as exit_info:
        agent.main(argv)
    return exit_info.value.code, capsys.readouterr().out


def _sections(output):
    """Split agent output into {piggyback host or None: {section: rows}}.

    Every section is sep(0), so a line is a row with one element.
    """
    hosts = {None: {}}
    host, section = None, None
    for line in output.splitlines():
        if line.startswith("<<<<") and line.endswith(">>>>"):
            host = line[4:-4] or None
            hosts.setdefault(host, {})
            section = None
        elif line.startswith("<<<") and line.endswith(">>>"):
            section = line[3:-3].split(":")[0]
            hosts[host][section] = []
        else:
            hosts[host][section].append([line])
    return hosts


# --- arguments ---------------------------------------------------------------


def test_argument_defaults(agent):
    args = agent.parse_arguments(["-u", "monitor", "-p", "secret", "nfmt.example.net"])
    assert (args.port, args.no_cert_check, args.retries) == (443, False, 3)
    assert (args.severity_critical, args.severity_major, args.severity_minor) == ("crit", "warn", "ok")


def test_unknown_severity_state_is_rejected(agent):
    with pytest.raises(SystemExit):
        agent.parse_arguments(["-u", "u", "-p", "p", "--severity-major", "red", "h"])


# --- talking to NFM-T ----------------------------------------------------------


def test_agent_authenticates_reads_and_revokes(agent, nfmt, capsys):
    code, _ = _run(agent, capsys, "--port", "8443")
    assert code == 0
    urls = [(method, url) for method, url, _ in nfmt]
    base = "https://nfmt.example.net:8443/"
    assert urls == [
        ("POST", base + "rest-gateway/rest/api/v1/auth/token"),
        ("GET", base + "FaultManagement/rest/api/v2/alarms/details"),
        ("GET", base + "oms1350/data/otn/node/"),
        ("GET", base + "oms1350/data/otn/connection/path"),
        ("POST", base + "rest-gateway/rest/api/v1/auth/revocation"),
    ]
    assert nfmt[1][2]["headers"]["authorization"] == "Bearer tok-1"
    assert all(kwargs["verify"] is True for _, _, kwargs in nfmt)


def test_no_cert_check_disables_verification(agent, nfmt, capsys):
    _run(agent, capsys, "--no-cert-check")
    assert all(kwargs["verify"] is False for _, _, kwargs in nfmt)


# --- output format -------------------------------------------------------------


def test_output_has_one_piggyback_block_per_node(agent, nfmt, capsys):
    _, out = _run(agent, capsys)
    hosts = _sections(out)
    assert list(hosts) == [None, "OTN-ZH-01", "OTN-BE-02", "OTN-GE-03"]
    assert list(hosts[None]) == ["oposs_nfm_t"]
    for node in ("OTN-ZH-01", "OTN-BE-02", "OTN-GE-03"):
        assert list(hosts[node]) == ["oposs_nfm_t_node", "oposs_nfm_t_service"]
    assert out.endswith("<<<<>>>>\n")


def test_agent_status_and_unassigned_alarms(agent, nfmt, capsys):
    _, out = _run(agent, capsys)
    (row,) = _sections(out)[None]["oposs_nfm_t"]
    assert json.loads(row[0]) == {
        "node_count": 3,
        "status": "ok",
        "unassigned_alarms": [
            {"neName": "MNC-FM", "severity": "major", "state": 1, "summary": "Database backup failed"},
            {"neName": "NSP-ADAPTER-7", "severity": "minor", "state": 0, "summary": "Adapter restarted"},
        ],
    }


def test_node_alarms_sorted_by_severity(agent, nfmt, capsys):
    _, out = _run(agent, capsys)
    (row,) = _sections(out)["OTN-ZH-01"]["oposs_nfm_t_node"]
    assert json.loads(row[0])["alarms"] == [
        {"severity": "critical", "state": 2, "summary": "Loss of signal on 1/2/C1"},
        {"severity": "minor", "state": 0, "summary": "Fan unit 2 speed low"},
    ]


def test_node_without_alarms_gets_a_placeholder(agent, nfmt, capsys):
    _, out = _run(agent, capsys)
    (row,) = _sections(out)["OTN-GE-03"]["oposs_nfm_t_node"]
    assert json.loads(row[0])["alarms"] == [{"severity": "ok", "state": 0, "summary": "No active Alarms"}]


def test_paths_appear_on_both_end_nodes(agent, nfmt, capsys):
    _, out = _run(agent, capsys)
    hosts = _sections(out)
    services = {host: [json.loads(r[0]) for r in hosts[host]["oposs_nfm_t_service"]]
                for host in ("OTN-ZH-01", "OTN-BE-02", "OTN-GE-03")}
    assert [(s["id"], s["role"]) for s in services["OTN-ZH-01"]] == [("4711", "a"), ("4712", "a")]
    assert [(s["id"], s["role"]) for s in services["OTN-BE-02"]] == [("4711", "z")]
    assert [(s["id"], s["role"]) for s in services["OTN-GE-03"]] == [("4712", "z")]
    # Only the fields the check reads travel, not the whole API object
    assert "pathType" not in services["OTN-ZH-01"][0]


def test_severity_mapping_reaches_the_alarms(agent, nfmt, capsys):
    _, out = _run(agent, capsys, "--severity-minor", "warn", "--severity-major", "unknown")
    alarms = json.loads(_sections(out)["OTN-ZH-01"]["oposs_nfm_t_node"][0][0])["alarms"]
    assert [a["state"] for a in alarms] == [2, 1]
    (status,) = _sections(out)[None]["oposs_nfm_t"]
    assert [a["state"] for a in json.loads(status[0])["unassigned_alarms"]] == [3, 1]


@pytest.mark.xfail(strict=True, reason="BUG: the agent gives a Nokia 'warning' alarm state UNKNOWN; "
                   "the README and the check's own severity map say WARN")
def test_warning_alarm_is_warn(agent):
    fetcher = agent.nfmTFetcher("test", "u", "p")
    assert fetcher._alarm_state("warning") == agent.CHECK_MK_WARN


def test_cleared_alarm_is_ok(agent):
    fetcher = agent.nfmTFetcher("test", "u", "p")
    assert fetcher._alarm_state("Cleared") == agent.CHECK_MK_OK
    assert fetcher._alarm_state(None) == agent.CHECK_MK_OK


# --- errors ----------------------------------------------------------------------


def _error_row(out):
    (row,) = _sections(out)[None]["oposs_nfm_t"]
    return json.loads(row[0])


def test_dns_failure_reports_a_connection_error(agent, nfmt, monkeypatch, capsys):
    def fail(host):
        raise agent.socket.gaierror(-2, "Name or service not known")

    monkeypatch.setattr(agent.socket, "gethostbyname", fail)
    _, out = _run(agent, capsys)
    row = _error_row(out)
    assert row["status"] == "error"
    assert row["error_type"] == "CONNECTION_ERROR"
    assert "DNS resolution failed for host 'nfmt.example.net'" in row["error_message"]


def test_bad_credentials_report_an_auth_error(agent, nfmt, monkeypatch, capsys):
    monkeypatch.setattr(agent.requests, "post", lambda url, **kw: _Response({}, 401))
    _, out = _run(agent, capsys)
    assert _error_row(out)["error_type"] == "AUTH_ERROR"


def test_api_failure_reports_a_fetch_error(agent, nfmt, capsys):
    nfmt.answers.pop("oms1350/data/otn/node/")
    _, out = _run(agent, capsys)
    row = _error_row(out)
    assert row["error_type"] == "FETCH_ERROR"
    assert "Failed to fetch nodes" in row["error_message"]


def test_no_nodes_reports_an_error(agent, nfmt, capsys):
    nfmt.answers["oms1350/data/otn/node/"] = {"items": []}
    _, out = _run(agent, capsys)
    assert "No nodes found" in _error_row(out)["error_message"]


def test_connection_retries_then_gives_up(agent, nfmt, monkeypatch, capsys):
    attempts = []

    def refuse(url, **kwargs):
        attempts.append(url)
        raise agent.requests.ConnectionError("refused")

    monkeypatch.setattr(agent.requests, "post", refuse)
    _, out = _run(agent, capsys, "--retries", "2")
    assert len(attempts) == 2
    assert _error_row(out)["error_type"] == "CONNECTION_ERROR"


@pytest.mark.xfail(strict=True, reason="BUG: the agent exits 2 after printing its error section; "
                   "Checkmk discards the output of a special agent that exits non-zero, "
                   "so NFM-T AGENT STATUS never shows the error")
def test_error_output_reaches_checkmk(agent, nfmt, monkeypatch, capsys):
    monkeypatch.setattr(agent.requests, "post", lambda url, **kw: _Response({}, 401))
    code, out = _run(agent, capsys)
    assert _error_row(out)["status"] == "error"
    # cmk/fetchers/_program.py (2.4.0): a non-zero exit code raises
    # MKFetcherError("Agent exited with code ...") and drops stdout
    assert code == 0


# --- agent output through the check ------------------------------------------


def test_check_reads_the_agent_output(agent, check, nfmt, capsys):
    _, out = _run(agent, capsys)
    hosts = _sections(out)

    status = check.parse_oposs_nfm_t(hosts[None]["oposs_nfm_t"])
    assert [s.item for s in check.discover_oposs_nfm_t(status)] == ["AGENT STATUS", "System Alarms"]
    assert list(check.check_oposs_nfm_t("AGENT STATUS", status)) == [
        Result(state=State.OK, summary="NFM-T agent running, monitoring 3 nodes")]
    system = [r for r in check.check_oposs_nfm_t("System Alarms", status) if isinstance(r, Result)]
    assert State.worst(*(r.state for r in system)) is State.WARN

    zh = check.parse_oposs_nfm_t_node(hosts["OTN-ZH-01"]["oposs_nfm_t_node"])
    zh_out = [r for r in check.check_oposs_nfm_t_node("Fault Manager Alarms", zh) if isinstance(r, Result)]
    assert State.worst(*(r.state for r in zh_out)) is State.CRIT

    ge = check.parse_oposs_nfm_t_service(hosts["OTN-GE-03"]["oposs_nfm_t_service"])
    assert [s.item for s in check.discover_oposs_nfm_t_service(ge)] == ["4712"]
    assert list(check.check_oposs_nfm_t_service("4712", {}, ge)) == [
        Result(state=State.UNKNOWN, summary="ZH-GE 10G [10GbE] (1/4/C1 <-> 1/1/C2) (not Up: Down)")]


def test_check_reads_the_agent_error(agent, check, nfmt, monkeypatch, capsys):
    monkeypatch.setattr(agent.requests, "post", lambda url, **kw: _Response({}, 401))
    _, out = _run(agent, capsys)
    section = check.parse_oposs_nfm_t(_sections(out)[None]["oposs_nfm_t"])
    (result,) = check.check_oposs_nfm_t("AGENT STATUS", section)
    assert result.state is State.CRIT
    assert result.summary.startswith("AUTH_ERROR: ")


# --- packaging -------------------------------------------------------------------


def test_agent_is_executable_in_git():
    # Checkmk runs libexec/agent_oposs_nfm_t directly; without the
    # executable bit the special agent fails with "Permission denied"
    rel = AGENT.relative_to(ROOT).as_posix()
    mode = subprocess.run(["git", "-C", str(ROOT), "ls-files", "-s", rel],
                          capture_output=True, text=True, check=True).stdout.split()[0]
    assert mode == "100755"
    assert os.access(AGENT, os.X_OK)
