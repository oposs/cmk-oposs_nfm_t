"""Tests for the NFM-T checks (run on the Checkmk server).

The sections come from the special agent agent_oposs_nfm_t. It writes every
section with `sep(0)` and one compact JSON object per line, so every row of
a string table holds exactly one JSON string:

    <<<oposs_nfm_t:sep(0)>>>            agent status and unassigned alarms
    <<<<node>>>>                        piggyback, one block per NFM-T node
    <<<oposs_nfm_t_node:sep(0)>>>       the alarms of that node
    <<<oposs_nfm_t_service:sep(0)>>>    one line per connection path
    <<<<>>>>

The rows below are written the way the agent writes them (sort_keys, compact
separators). The repository holds no captured agent output; the field names
and values follow what the agent reads from the NFM-T REST API.
"""

import importlib.util
import json
import pathlib
import re

import pytest
from cmk.agent_based.v2 import Metric, Result, Service, State

ROOT = pathlib.Path(__file__).resolve().parent.parent
CHECK = ROOT / "local/lib/python3/cmk_addons/plugins/oposs_nfm_t/agent_based/oposs_nfm_t.py"


def _load_check(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def check():
    return _load_check(CHECK, "test_oposs_nfm_t_check")


def _row(obj):
    """One string-table row, as the agent writes it."""
    return [json.dumps(obj, sort_keys=True, separators=(",", ":"))]


def _results(out):
    return [r for r in out if isinstance(r, Result)]


def _metrics(out):
    return {m.name: m.value for m in out if isinstance(m, Metric)}


def _worst(out):
    return State.worst(*(r.state for r in _results(out)))


# Alarms as the agent emits them: severity lower case, numeric Checkmk state
# from the default severity mapping (critical CRIT, major WARN, minor OK)
LOS = {"severity": "critical", "state": 2, "summary": "Loss of signal on 1/2/C1"}
DEGRADED = {"severity": "major", "state": 1, "summary": "Signal degrade on 1/3/C1"}
FAN = {"severity": "minor", "state": 0, "summary": "Fan unit 2 speed low"}
NO_ALARMS = {"severity": "ok", "state": 0, "summary": "No active Alarms"}

AGENT_OK = {
    "node_count": 3,
    "status": "ok",
    "unassigned_alarms": [
        {"neName": "MNC-FM", "severity": "major", "state": 1, "summary": "Database backup failed"},
        {"neName": "NSP-ADAPTER-7", "severity": "minor", "state": 0, "summary": "Adapter restarted"},
    ],
}
AGENT_ERROR = {"error_message": "Failed to connect to https://nfmt.example.net:443/: refused",
               "error_type": "CONNECTION_ERROR", "status": "error"}

PATH_UP = {
    "a1NodeName": "OTN-ZH-01", "aPortLabel": "1/2/C1", "alarmSeverity": "Cleared",
    "alarmState": "Cleared", "effectiveRate": "100GbE", "guiLabel": "ZH-BE 100G",
    "id": "4711", "operationalState": "Up", "role": "a", "z1NodeName": "OTN-BE-02",
    "zPortLabel": "1/3/C1",
}


# --- NFM-T host: AGENT STATUS and System Alarms ------------------------------


def test_parse_agent_status(check):
    section = check.parse_oposs_nfm_t([_row(AGENT_OK)])
    assert section["status"] == "ok"
    assert section["node_count"] == 3
    assert section["error"] is None
    assert [a["neName"] for a in section["unassigned_alarms"]] == ["MNC-FM", "NSP-ADAPTER-7"]


def test_discovery_with_unassigned_alarms(check):
    section = check.parse_oposs_nfm_t([_row(AGENT_OK)])
    assert list(check.discover_oposs_nfm_t(section)) == [
        Service(item="AGENT STATUS"), Service(item="System Alarms")]


def test_discovery_without_unassigned_alarms(check):
    section = check.parse_oposs_nfm_t([_row({**AGENT_OK, "unassigned_alarms": []})])
    assert list(check.discover_oposs_nfm_t(section)) == [Service(item="AGENT STATUS")]


def test_agent_status_ok(check):
    section = check.parse_oposs_nfm_t([_row(AGENT_OK)])
    assert list(check.check_oposs_nfm_t("AGENT STATUS", section)) == [
        Result(state=State.OK, summary="NFM-T agent running, monitoring 3 nodes")]


def test_agent_error_is_crit_with_the_reason(check):
    section = check.parse_oposs_nfm_t([_row(AGENT_ERROR)])
    assert list(check.check_oposs_nfm_t("AGENT STATUS", section)) == [
        Result(state=State.CRIT,
               summary="CONNECTION_ERROR: Failed to connect to https://nfmt.example.net:443/: refused")]


def test_agent_error_without_details(check):
    section = check.parse_oposs_nfm_t([_row({"status": "error"})])
    (result,) = check.check_oposs_nfm_t("AGENT STATUS", section)
    assert result == Result(state=State.CRIT, summary="ERROR: Unknown error")


def test_unknown_agent_status_is_unknown(check):
    section = check.parse_oposs_nfm_t([_row({"status": "starting"})])
    assert list(check.check_oposs_nfm_t("AGENT STATUS", section)) == [
        Result(state=State.UNKNOWN, summary="NFM-T agent status: starting")]


@pytest.mark.parametrize("table", [[], [["not json"]], [["{\"status\": "]], [[]]],
                         ids=["empty", "garbage", "truncated", "empty-row"])
def test_garbage_agent_status_is_unknown(check, table):
    section = check.parse_oposs_nfm_t(table)
    assert section["status"] == "unknown"
    assert list(check.check_oposs_nfm_t("AGENT STATUS", section)) == [
        Result(state=State.UNKNOWN, summary="NFM-T agent status: unknown")]


def test_system_alarms_follow_the_agent_state(check):
    section = check.parse_oposs_nfm_t([_row(AGENT_OK)])
    out = list(check.check_oposs_nfm_t("System Alarms", section))
    assert _results(out) == [
        Result(state=State.WARN, summary="[MNC-FM] Database backup failed [major]"),
        Result(state=State.OK, summary="[NSP-ADAPTER-7] Adapter restarted [minor]"),
    ]
    # The alarm mapped to OK is listed but not counted
    assert _metrics(out) == {"oposs_nfm_t_system_alarm_count": 1,
                             "oposs_nfm_t_system_error_count": 0,
                             "oposs_nfm_t_system_warning_count": 1}


def test_system_alarm_crit(check):
    alarm = {"neName": "MNC-FM", "severity": "critical", "state": 2, "summary": "Disk full"}
    section = check.parse_oposs_nfm_t([_row({**AGENT_OK, "unassigned_alarms": [alarm]})])
    out = list(check.check_oposs_nfm_t("System Alarms", section))
    assert _worst(out) is State.CRIT
    assert _metrics(out)["oposs_nfm_t_system_error_count"] == 1


def test_system_alarms_gone(check):
    section = check.parse_oposs_nfm_t([_row({**AGENT_OK, "unassigned_alarms": []})])
    assert list(check.check_oposs_nfm_t("System Alarms", section)) == [
        Result(state=State.OK, summary="No system alarms")]


# --- piggyback node: Fault Manager Alarms ------------------------------------


def test_node_always_discovers_one_service(check):
    section = check.parse_oposs_nfm_t_node([_row({"alarms": [NO_ALARMS]})])
    assert list(check.discover_oposs_nfm_t_node(section)) == [Service(item="Fault Manager Alarms")]


def test_node_without_active_alarms(check):
    # The agent sends a placeholder alarm for a node without alarms
    section = check.parse_oposs_nfm_t_node([_row({"alarms": [NO_ALARMS]})])
    out = list(check.check_oposs_nfm_t_node("Fault Manager Alarms", section))
    assert _results(out) == [Result(state=State.OK, summary="No active Alarms [ok]")]
    assert _metrics(out) == {"oposs_nfm_t_alarm_count": 0, "oposs_nfm_t_error_count": 0,
                             "oposs_nfm_t_warning_count": 0}


def test_node_with_mixed_alarms(check):
    section = check.parse_oposs_nfm_t_node([_row({"alarms": [LOS, DEGRADED, FAN]})])
    out = list(check.check_oposs_nfm_t_node("Fault Manager Alarms", section))
    assert _results(out) == [
        Result(state=State.CRIT, summary="Loss of signal on 1/2/C1 [critical]"),
        Result(state=State.WARN, summary="Signal degrade on 1/3/C1 [major]"),
        Result(state=State.OK, summary="Fan unit 2 speed low [minor]"),
    ]
    assert _metrics(out) == {"oposs_nfm_t_alarm_count": 2, "oposs_nfm_t_error_count": 1,
                             "oposs_nfm_t_warning_count": 1}


def test_node_warn_only(check):
    section = check.parse_oposs_nfm_t_node([_row({"alarms": [DEGRADED]})])
    out = list(check.check_oposs_nfm_t_node("Fault Manager Alarms", section))
    assert _worst(out) is State.WARN


def test_alarm_mapped_to_unknown_counts_as_alarm_only(check):
    # severity_mapping can map a severity to UNKNOWN; the agent then sends 3
    alarm = {**FAN, "state": 3}
    section = check.parse_oposs_nfm_t_node([_row({"alarms": [alarm]})])
    out = list(check.check_oposs_nfm_t_node("Fault Manager Alarms", section))
    assert _worst(out) is State.UNKNOWN
    assert _metrics(out) == {"oposs_nfm_t_alarm_count": 1, "oposs_nfm_t_error_count": 0,
                             "oposs_nfm_t_warning_count": 0}


@pytest.mark.parametrize("severity, state", [
    ("critical", State.CRIT), ("major", State.CRIT), ("minor", State.WARN),
    ("warning", State.WARN), ("cleared", State.OK), ("indeterminate", State.UNKNOWN)])
def test_alarm_without_agent_state_uses_the_static_map(check, severity, state):
    alarm = {"severity": severity, "summary": "x"}
    section = check.parse_oposs_nfm_t_node([_row({"alarms": [alarm]})])
    (result,) = _results(check.check_oposs_nfm_t_node("Fault Manager Alarms", section))
    assert result.state is state


def test_alarm_with_garbage_state_uses_the_static_map(check):
    alarm = {"severity": "Critical", "state": "high", "summary": "x"}
    section = check.parse_oposs_nfm_t_node([_row({"alarms": [alarm]})])
    (result,) = _results(check.check_oposs_nfm_t_node("Fault Manager Alarms", section))
    assert result == Result(state=State.CRIT, summary="x [critical]")


@pytest.mark.parametrize("table", [[], [["garbage"]], [_row({"alarms": []})]],
                         ids=["empty", "garbage", "no-alarms"])
def test_node_without_alarm_data(check, table):
    section = check.parse_oposs_nfm_t_node(table)
    assert list(check.check_oposs_nfm_t_node("Fault Manager Alarms", section)) == [
        Result(state=State.OK, summary="No alarms")]


# --- piggyback node: connection path services --------------------------------


def test_service_discovery_one_per_path(check):
    other = {**PATH_UP, "id": "4712", "guiLabel": "ZH-GE 10G"}
    section = check.parse_oposs_nfm_t_service([_row(PATH_UP), _row(other), _row({"guiLabel": "no id"})])
    assert list(check.discover_oposs_nfm_t_service(section)) == [
        Service(item="4711", parameters={"guiLabel": "ZH-BE 100G"}),
        Service(item="4712", parameters={"guiLabel": "ZH-GE 10G"}),
    ]


def test_service_up_and_cleared(check):
    section = check.parse_oposs_nfm_t_service([_row(PATH_UP)])
    assert list(check.check_oposs_nfm_t_service("4711", {}, section)) == [
        Result(state=State.OK, summary="ZH-BE 100G [100GbE] (1/2/C1 <-> 1/3/C1) - OK")]


@pytest.mark.parametrize("severity, state", [
    ("Minor", State.WARN), ("Warning", State.WARN), ("Major", State.CRIT),
    ("Critical", State.CRIT), ("Indeterminate", State.UNKNOWN)])
def test_service_alarm_severity(check, severity, state):
    path = {**PATH_UP, "alarmSeverity": severity, "alarmState": "Raised"}
    section = check.parse_oposs_nfm_t_service([_row(path)])
    assert list(check.check_oposs_nfm_t_service("4711", {}, section)) == [
        Result(state=state,
               summary=f"ZH-BE 100G [100GbE] (1/2/C1 <-> 1/3/C1) - Raised [{severity.lower()}]")]


def test_service_not_up_is_unknown(check):
    path = {**PATH_UP, "operationalState": "Down", "alarmSeverity": "Critical"}
    section = check.parse_oposs_nfm_t_service([_row(path)])
    assert list(check.check_oposs_nfm_t_service("4711", {}, section)) == [
        Result(state=State.UNKNOWN, summary="ZH-BE 100G [100GbE] (1/2/C1 <-> 1/3/C1) (not Up: Down)")]


def test_service_without_labels(check):
    path = {"id": "4711", "operationalState": "Up", "alarmSeverity": "Cleared"}
    section = check.parse_oposs_nfm_t_service([_row(path)])
    assert list(check.check_oposs_nfm_t_service("4711", {}, section)) == [
        Result(state=State.OK, summary="Service 4711 - OK")]


def test_vanished_service(check):
    section = check.parse_oposs_nfm_t_service([_row(PATH_UP), ["garbage"]])
    assert list(check.check_oposs_nfm_t_service("9999", {}, section)) == [
        Result(state=State.UNKNOWN, summary="Service 9999 not found")]


# --- plugin registration -----------------------------------------------------


def test_service_names(check):
    assert check.check_plugin_oposs_nfm_t.service_name == "NFM-T %s"
    assert check.check_plugin_oposs_nfm_t_node.service_name == "NFM-T %s"
    assert check.check_plugin_oposs_nfm_t_service.service_name == "NFM-T Service %s"


def test_section_names(check):
    assert check.agent_section_oposs_nfm_t.name == "oposs_nfm_t"
    assert check.agent_section_oposs_nfm_t_node.name == "oposs_nfm_t_node"
    assert check.agent_section_oposs_nfm_t_service.name == "oposs_nfm_t_service"

# --- version -----------------------------------------------------------------


def test_check_carries_the_released_version():
    # The publish check fails on main when a version file disagrees with
    # the newest released CHANGES.md heading.
    released = re.search(r"^## (\d+\.\d+\.\d+)", (ROOT / "CHANGES.md").read_text(),
                         flags=re.MULTILINE).group(1)
    assert re.search(rf'^__version__ = "{re.escape(released)}"$', CHECK.read_text(), flags=re.MULTILINE)


def test_release_writes_version_into_check(tmp_path):
    """Apply the version_files entry of .github/repo-infra.json to the check
    module, as Create release PR does (a multiline regex, first match)"""
    config = json.loads((ROOT / ".github/repo-infra.json").read_text())
    (spec,) = [f for f in config["version_files"] if (ROOT / f["path"]) == CHECK]
    stamped = re.sub(spec["pattern"], spec["replacement"].replace("$VERSION", "9.8.7"),
                     CHECK.read_text(), count=1, flags=re.MULTILINE)
    assert re.search(spec["verify"].replace("$VERSION", re.escape("9.8.7")), stamped, flags=re.MULTILINE)
    copy = tmp_path / "stamped_check.py"
    copy.write_text(stamped)
    assert _load_check(copy, "stamped_check").__version__ == "9.8.7"
