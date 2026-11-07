"""The rule form builds and matches what the agent call and the agent read."""

import importlib.util
import pathlib
import sys

import pytest
from cmk.rulesets.v1.form_specs import Dictionary, Password, SingleChoice
from cmk.rulesets.v1.rule_specs import SpecialAgent
from cmk.server_side_calls.v1 import HostConfig, IPv4Config, Secret, SpecialAgentCommand
from test_agent import _load_agent

ROOT = pathlib.Path(__file__).resolve().parent.parent
PLUGIN = ROOT / "local/lib/python3/cmk_addons/plugins/oposs_nfm_t"


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def rulesets():
    return _load(PLUGIN / "rulesets/oposs_nfm_t.py", "test_oposs_nfm_t_rulesets")


@pytest.fixture(scope="module")
def ssc():
    return _load(PLUGIN / "server_side_calls/oposs_nfm_t.py", "test_oposs_nfm_t_ssc")


@pytest.fixture(scope="module")
def agent():
    return _load_agent()


@pytest.fixture(scope="module")
def form(rulesets):
    return rulesets.rule_spec_special_agent_oposs_nfm_t.parameter_form()


# --- special agent rule --------------------------------------------------------


def test_special_agent_form_builds(rulesets, form):
    assert isinstance(rulesets.rule_spec_special_agent_oposs_nfm_t, SpecialAgent)
    assert isinstance(form, Dictionary)
    assert set(form.elements) == {"username", "password", "port", "no_cert_check", "severity_mapping"}
    assert isinstance(form.elements["password"].parameter_form, Password)
    assert form.elements["port"].parameter_form.prefill.value == 443


def test_rule_and_agent_call_share_a_name(rulesets, ssc):
    assert rulesets.rule_spec_special_agent_oposs_nfm_t.name == ssc.special_agent_oposs_nfm_t.name


def test_rule_names_the_libexec_agent(ssc):
    assert (PLUGIN / f"libexec/agent_{ssc.special_agent_oposs_nfm_t.name}").is_file()


def test_form_fields_are_the_agent_call_parameters(form, ssc):
    assert set(form.elements) == set(ssc.Params.model_fields)


def _severity_forms(form):
    return form.elements["severity_mapping"].parameter_form.elements


def test_every_severity_is_one_the_agent_takes(form, agent):
    severities = set(_severity_forms(form))
    assert severities == set(agent.DEFAULT_SEVERITY_STATE) == {"critical", "major", "minor"}


def test_every_state_choice_is_one_the_agent_takes(form, agent):
    for element in _severity_forms(form).values():
        choice = element.parameter_form
        assert isinstance(choice, SingleChoice)
        assert {e.name for e in choice.elements} == set(agent.STATE_NAME_TO_INT)


def test_rule_defaults_are_the_agent_defaults(form, agent):
    defaults = {s: e.parameter_form.prefill.value for s, e in _severity_forms(form).items()}
    assert defaults == {"critical": "crit", "major": "warn", "minor": "ok"}
    assert {s: agent.STATE_NAME_TO_INT[v] for s, v in defaults.items()} == agent.DEFAULT_SEVERITY_STATE
    args = agent.parse_arguments(["-u", "u", "-p", "p", "h"])
    assert {s: getattr(args, f"severity_{s}") for s in defaults} == defaults


# --- agent call ----------------------------------------------------------------

HOST = HostConfig(name="nfmt.example.net", ipv4_config=IPv4Config(address="192.0.2.20"))
PASSWORD = Secret(7)


def _command(ssc, **params):
    params = {"username": "monitor", "password": PASSWORD, "no_cert_check": False, **params}
    (command,) = ssc.special_agent_oposs_nfm_t(params, HOST)
    assert isinstance(command, SpecialAgentCommand)
    return command.command_arguments


def test_password_goes_in_plain(ssc):
    # unsafe() asks Checkmk for the plain text on the command line (pass_safely=False);
    # the agent reads it from -p and has no password store lookup of its own
    (secret,) = [a for a in _command(ssc) if isinstance(a, Secret)]
    assert secret == Secret(7, pass_safely=False)


def test_minimal_command(ssc):
    assert _command(ssc) == ["-u", "monitor", "-p", PASSWORD.unsafe(), "nfmt.example.net"]


def test_full_command(ssc):
    args = _command(ssc, port=8443, no_cert_check=True,
                    severity_mapping={"critical": "crit", "major": "crit", "minor": "warn"})
    assert args == [
        "-u", "monitor", "-p", PASSWORD.unsafe(), "--port", "8443", "--no-cert-check",
        "--severity-critical", "crit", "--severity-major", "crit", "--severity-minor", "warn",
        "nfmt.example.net",
    ]


def test_command_uses_host_name_not_address(ssc):
    # The certificate names the host, not its address
    args = _command(ssc)
    assert args[-1] == "nfmt.example.net"
    assert "192.0.2.20" not in args


def test_agent_accepts_the_command(ssc, agent):
    args = _command(ssc, port=8443, no_cert_check=True,
                    severity_mapping={"critical": "unknown", "major": "ok", "minor": "warn"})
    # Checkmk puts the plain password in place of the Secret before it runs the agent
    parsed = agent.parse_arguments([a if isinstance(a, str) else "secret" for a in args])
    assert (parsed.port, parsed.no_cert_check, parsed.hostaddress) == (8443, True, "nfmt.example.net")
    assert (parsed.severity_critical, parsed.severity_major, parsed.severity_minor) == ("unknown", "ok", "warn")
