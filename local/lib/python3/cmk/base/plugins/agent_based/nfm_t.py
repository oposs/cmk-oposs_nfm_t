#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (C) 2025 OETIKER+PARTNER AG - License: GNU General Public License v2

import json
from typing import Any, Mapping, Dict, List
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
    """Parse the agent output and structure it for discovery and checks"""
    parsed = {
        "inventory": [],
        "result": {},
        "error": None
    }
    
    try:
        for row in string_table:
            try:
                data = json.loads(row[0])
                node = data.get('node')
                
                if not node:
                    # Skip entries without a node name
                    continue
                
                parsed['inventory'].append(node)
                parsed['result'][node] = data
                
                # Check if this is an agent error node
                if node == "NFM-T_AGENT" and data.get('alarms'):
                    for alarm in data['alarms']:
                        if alarm.get('severity') in ['critical', 'major'] and 'Error' in alarm.get('summary', ''):
                            parsed['error'] = alarm.get('summary')
            except json.JSONDecodeError as e:
                # Log the error but continue parsing other rows
                if debug.enabled():
                    print(f"DEBUG: Error parsing JSON: {e}")
                    print(f"DEBUG: Problematic row: {row}")
    except Exception as e:
        if debug.enabled():
            print(f"DEBUG: Exception in parse_nfm_t: {e}")
    
    return parsed


def discover_nodes(section: Section) -> DiscoveryResult:
    """Discover NFM-T nodes as services"""
    if debug.enabled():
        print("DEBUG Discover Section:")
        pprint(section)
    
    # Always yield the agent status service regardless of errors
    yield Service(
        item="AGENT STATUS",
        parameters={"_is_agent_status": True},
    )
    
    # Yield other nodes
    for node in section['inventory']:
        if node != "NFM-T_AGENT":  # Skip the agent status node as it's handled separately
            yield Service(
                item=node,
                parameters=section['result'][node],
            )


# Expanded severity map to include more statuses
SEVERITY_MAP = {
    "ok": State.OK,
    "major": State.CRIT,
    "critical": State.CRIT,
    "minor": State.WARN,
    "warning": State.WARN,
    # Default to UNKNOWN for any other severity
}


def check_nfm_t(item: Any, section: Section) -> CheckResult:
    """Check the status of NFM-T nodes"""
    if item == "AGENT STATUS":
        # Special handling for agent status
        agent_data = section['result'].get("NFM-T_AGENT", {})
        
        # First check for explicit agent errors
        if agent_data:
            for alarm in agent_data.get('alarms', []):
                severity = alarm.get('severity', 'ok').lower()
                summary_prepped = alarm.get('summary', '')[:100].split('\n')[0]
                yield Result(
                    state=SEVERITY_MAP.get(severity, State.UNKNOWN),
                    summary=summary_prepped,
                )
            return
        elif section.get('error'):
            # Fallback if there's an error but no agent data
            yield Result(
                state=State.CRIT,
                summary=section['error']
            )
            return
            
        # If we got here, there are no explicit agent errors
        
        # Check if we have any nodes at all (empty data is suspicious)
        if not section['inventory']:
            yield Result(
                state=State.WARN,
                summary="NFM-T agent returned no nodes - possibly incomplete data"
            )
            return
            
        # Everything looks good
        yield Result(
            state=State.OK,
            summary=f"NFM-T agent is running properly, monitoring {len(section['inventory'])} nodes"
        )
        return
    
    # Regular node check
    result = section['result'].get(item, {})
    if debug.enabled():
        print("DEBUG Check Section for item", item)
        pprint(result)
    
    if not result:
        # Node not found in the data
        yield Result(
            state=State.UNKNOWN,
            summary=f"Node {item} not found in NFM-T data"
        )
        return
    
    # Check if we have any alarms for this node
    alarms = result.get('alarms', [])
    if not alarms:
        yield Result(
            state=State.OK,
            summary="No alarms for this node"
        )
        return
    
    # Process alarms
    alarm_count = 0
    error_count = 0
    warning_count = 0
    
    for alarm in alarms:
        severity = alarm.get('severity', 'ok').lower()
        state = SEVERITY_MAP.get(severity, State.UNKNOWN)
        
        if state != State.OK:
            alarm_count += 1
            if state == State.CRIT:
                error_count += 1
            elif state == State.WARN:
                warning_count += 1
        
        yield Result(
            state=state,
            summary=f"{alarm.get('summary', 'Unknown alarm')} [{severity}]"
        )
    
    # Add metrics
    yield Metric(
        name="alarm_count",
        value=alarm_count,
    )
    yield Metric(
        name="error_count",
        value=error_count,
    )
    yield Metric(
        name="warning_count",
        value=warning_count,
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