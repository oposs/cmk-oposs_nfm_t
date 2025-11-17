#!/usr/bin/env python3
# Copyright (C) 2025 OETIKER+PARTNER AG - License: GNU General Public License v2

"""
Ruleset configuration for NFM-T special agent
Provides GUI configuration form for NFM-T monitoring parameters
"""

from cmk.rulesets.v1 import Title, Help
from cmk.rulesets.v1.form_specs import (
    DefaultValue,
    DictElement,
    Dictionary,
    Password,
    String,
    migrate_to_password,
    validators,
)
from cmk.rulesets.v1.rule_specs import SpecialAgent, Topic


def _formspec():
    return Dictionary(
        title=Title("NFM-T Monitor"),
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
                parameter_form=String(
                    title=Title("TCP Port"),
                    help_text=Help("TCP port for NFM-T API (default: 443)"),
                    prefill=DefaultValue("443"),
                    custom_validate=[validators.NetworkPort()],
                ),
                required=False,
            ),
        },
    )


# CRITICAL: Variable name must be: rule_spec_special_agent_{name}
# Name must match special_agent_{name} in server_side_calls
rule_spec_special_agent_oposs_nfm_t = SpecialAgent(
    name="oposs_nfm_t",
    title=Title("NFM-T Monitor"),
    topic=Topic.GENERAL,
    parameter_form=_formspec,
)
