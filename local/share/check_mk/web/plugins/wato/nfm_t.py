#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (C) 2025 OETIKER+PARTNER AG - License: GNU General Public License v2


from cmk.gui.i18n import _
from cmk.gui.plugins.wato.special_agents.common import RulespecGroupDatasourcePrograms
from cmk.gui.plugins.wato.utils import (
    HostRulespec,
    MigrateToIndividualOrStoredPassword,
    rulespec_registry,
)
from cmk.gui.valuespec import Dictionary, DropdownChoice, TextInput

def _valuespec_special_agents_nfm_t():
    return Dictionary(
        elements=[
            (
                "username", 
                TextInput(
                    title=_("Username"),
                    allow_empty=False)
            ),
            (
                "password",
                MigrateToIndividualOrStoredPassword(
                    title=_("Password"),
                    allow_empty=False,
                ),
            ),
        ],
        required_keys=["username", "password"],
        title=_("NFM-T Monitor"),
        help=_("This rule selects the nfm_t special agent for an existing Checkmk host"),
    )


rulespec_registry.register(
    HostRulespec(
        group=RulespecGroupDatasourcePrograms,
        name="special_agents:nfm_t",
        valuespec=_valuespec_special_agents_nfm_t,
    )
)
