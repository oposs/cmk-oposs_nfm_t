"""Metric names: prefixed, and the pre-1.0 names translated to the current ones."""

import importlib.util
import pathlib
import re
import sys

import pytest
from cmk.graphing.v1 import translations

ROOT = pathlib.Path(__file__).resolve().parent.parent
PLUGIN = ROOT / "local/lib/python3/cmk_addons/plugins/oposs_nfm_t"
CHECK = PLUGIN / "agent_based/oposs_nfm_t.py"


@pytest.fixture(scope="module")
def graphing_objects():
    objects = []
    for path in sorted((PLUGIN / "graphing").glob("*.py")):
        name = "test_nfm_t_graphing_" + path.stem
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
        objects.extend(vars(module).values())
    return objects


def _emitted_metrics():
    return set(re.findall(r'Metric\(name="([a-z_]+)"', CHECK.read_text()))


def test_every_emitted_metric_is_prefixed():
    emitted = _emitted_metrics()
    assert len(emitted) == 6
    assert all(name.startswith("oposs_nfm_t_") for name in emitted)


def test_old_metrics_translate_to_emitted_names(graphing_objects):
    (translation,) = [o for o in graphing_objects if isinstance(o, translations.Translation)]
    assert translation.check_commands == [translations.PassiveCheck("oposs_nfm_t")]
    assert translation.translations == {
        "alarm_count": translations.RenameTo("oposs_nfm_t_alarm_count"),
        "error_count": translations.RenameTo("oposs_nfm_t_error_count"),
        "warning_count": translations.RenameTo("oposs_nfm_t_warning_count"),
    }
    targets = {t.metric_name for t in translation.translations.values()}
    assert targets <= _emitted_metrics()
