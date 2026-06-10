#!/usr/bin/env python3
# Copyright (C) 2025 OETIKER+PARTNER AG - License: GNU General Public License v2

"""
Ruleset configuration for NFM-T special agent
Provides GUI configuration form for NFM-T monitoring parameters
"""

from cmk.rulesets.v1 import Title, Help, Label
from cmk.rulesets.v1.form_specs import (
    BooleanChoice,
    DefaultValue,
    DictElement,
    Dictionary,
    Integer,
    Password,
    SingleChoice,
    SingleChoiceElement,
    String,
    migrate_to_password,
    validators,
)
from cmk.rulesets.v1.rule_specs import SpecialAgent, Topic


def _state_choice(title: Title, default: str) -> SingleChoice:
    """Dropdown mapping a Nokia severity to a Checkmk monitoring state."""
    return SingleChoice(
        title=title,
        elements=[
            SingleChoiceElement(name="ok", title=Title("OK")),
            SingleChoiceElement(name="warn", title=Title("WARN")),
            SingleChoiceElement(name="crit", title=Title("CRITICAL")),
            SingleChoiceElement(name="unknown", title=Title("UNKNOWN")),
        ],
        prefill=DefaultValue(default),
    )


def _formspec():
    return Dictionary(
        title=Title("OPOSS NFM-T Monitor"),
        help_text=Help("Configure monitoring of Nokia NFM-T managed nodes via REST API"),
        elements={
            "username": DictElement(
                parameter_form=String(
                    title=Title("Username"),
                    help_text=Help("API username for NFM-T authentication"),
                    custom_validate=[validators.LengthInRange(min_value=1)],
                ),
                required=True,
            ),
            "password": DictElement(
                parameter_form=Password(
                    title=Title("Password"),
                    help_text=Help("API password for NFM-T authentication"),
                    migrate=migrate_to_password,  # Handles migration from old format
                ),
                required=True,
            ),
            "port": DictElement(
                parameter_form=Integer(
                    title=Title("TCP Port"),
                    help_text=Help("TCP port for NFM-T API (default: 443)"),
                    prefill=DefaultValue(443),
                    custom_validate=[validators.NetworkPort()],
                ),
                required=False,
            ),
            "no_cert_check": DictElement(
                parameter_form=BooleanChoice(
                    title=Title("SSL certificate verification"),
                    label=Label("Disable SSL certificate verification"),
                    help_text=Help("Skip SSL certificate verification for HTTPS connections (insecure, use only for testing)"),
                    prefill=DefaultValue(False),
                ),
                required=True,
            ),
            "severity_mapping": DictElement(
                parameter_form=Dictionary(
                    title=Title("Fault-management alarm severity mapping"),
                    help_text=Help(
                        "Map Nokia NFM-T fault-management alarm severities to Checkmk "
                        "monitoring states. Applies to the node 'Fault Manager Alarms' "
                        "and the 'System Alarms' services only, not to the connection-path "
                        "services. An alarm mapped to OK is still listed but does not affect "
                        "the service state (e.g. to silence noisy 'minor' alarms)."
                    ),
                    elements={
                        "critical": DictElement(
                            parameter_form=_state_choice(
                                Title("Nokia 'critical' maps to"), "crit"
                            ),
                            required=True,
                        ),
                        "major": DictElement(
                            parameter_form=_state_choice(
                                Title("Nokia 'major' maps to"), "warn"
                            ),
                            required=True,
                        ),
                        "minor": DictElement(
                            parameter_form=_state_choice(
                                Title("Nokia 'minor' maps to"), "ok"
                            ),
                            required=True,
                        ),
                    },
                ),
                required=False,
            ),
        },
    )


# CRITICAL: Variable name must be: rule_spec_special_agent_{name}
# Name must match special_agent_{name} in server_side_calls
rule_spec_special_agent_oposs_nfm_t = SpecialAgent(
    name="oposs_nfm_t",
    title=Title("OPOSS NFM-T Monitor"),
    topic=Topic.GENERAL,
    parameter_form=_formspec,
)
