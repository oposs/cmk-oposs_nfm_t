"""Metric names: all prefixed, and no translations for old names."""

import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent
PLUGIN = ROOT / "local/lib/python3/cmk_addons/plugins/oposs_nfm_t"
CHECK = PLUGIN / "agent_based/oposs_nfm_t.py"


def _emitted_metrics():
    return set(re.findall(r'Metric\(name="([a-z_]+)"', CHECK.read_text()))


def test_every_emitted_metric_is_prefixed():
    emitted = _emitted_metrics()
    assert len(emitted) == 6
    assert all(name.startswith("oposs_nfm_t_") for name in emitted)


def test_no_metric_translations():
    # The pre-1.0 metric alarm_count lived on "NFM-T <node>" services of the
    # NFM-T host; since 2.0.0 the node alarms are on piggyback hosts that
    # never had unprefixed metrics, so a translation reaches no RRD
    assert not list((PLUGIN / "graphing").glob("*.py"))
