#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (C) 2025 OETIKER+PARTNER AG - License: GNU General Public License v2

import json
from typing import Any, Mapping
from pprint import pprint
from collections import namedtuple

from cmk.utils import debug
from cmk.base.plugins.agent_based.agent_based_api.v1 import register, Result, Metric, Service, State
from cmk.base.plugins.agent_based.agent_based_api.v1.type_defs import (
    CheckResult,
    DiscoveryResult,
    StringTable,
)

Section = Mapping[str, Any]


def parse_nfm_t(string_table: StringTable) -> Section:
    parsed = {
        "inventory": [],
        "result": {},
    }
    for row in string_table:
        data=json.loads(row[0])
        node = data['node']
        parsed['inventory'].append(node)
        parsed['result'][node] = data
    return parsed

def discover_nodes(section: Section) -> DiscoveryResult:
    if debug.enabled():
        print("DEBUG Discover Section:")
        pprint(section)
    for node in section['inventory']:
        yield Service(
            item=node,
            parameters=section['result'][node],
        )

SEVERITY_MAP = {
    "ok": State.OK,
    "major": State.CRIT,
    "critical": State.CRIT,
    "minor": State.WARN,
    "warning": State.WARN,
}

def check_nfm_t(item: Any, section: Section) -> CheckResult:
    result = section['result'].get(item, {})
    if debug.enabled():
        print("DEBUG Check Section:")
        pprint(item)
        pprint(result)
    for alarm in result.get('alarms',[]):
        severity = alarm.get('severity','ok')
        yield Result(
            state=SEVERITY_MAP[severity], 
            summary=f"{alarm['summary']} [{severity}]",
        )

    yield Metric(
            name="alarm_count",
            value=len(result['alarms']),
        )


register.agent_section(
    name="nfm_t",
    parse_function=parse_nfm_t,
)

register.check_plugin(
    name="nfm_t",
    service_name="NFM-T %s",
    discovery_function=discover_nodes,
    check_function=check_nfm_t,
)