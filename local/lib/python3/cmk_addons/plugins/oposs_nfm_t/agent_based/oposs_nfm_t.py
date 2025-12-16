#!/usr/bin/env python3
# Copyright (C) 2025 OETIKER+PARTNER AG - License: GNU General Public License v2

"""
Check plugin for NFM-T monitoring
Processes data from NFM-T special agent and checks node status based on alarms
Supports piggyback for individual nodes with their alarms and services
"""

import json
from typing import Any, Mapping

from cmk.agent_based.v2 import (
    AgentSection,
    CheckPlugin,
    CheckResult,
    DiscoveryResult,
    Metric,
    Result,
    Service,
    State,
    StringTable,
)

Section = Mapping[str, Any]

# Severity mapping for alarms
SEVERITY_MAP = {
    "ok": State.OK,
    "cleared": State.OK,
    "major": State.CRIT,
    "critical": State.CRIT,
    "minor": State.WARN,
    "warning": State.WARN,
}


# =============================================================================
# SECTION 1: Main NFM-T Agent Status (on NFM-T host)
# =============================================================================

def parse_oposs_nfm_t(string_table: StringTable) -> Section:
    """Parse the agent status output"""
    parsed = {
        "status": "unknown",
        "node_count": 0,
        "error": None,
        "unassigned_alarms": []
    }

    try:
        for row in string_table:
            try:
                data = json.loads(row[0])
                parsed["status"] = data.get("status", "unknown")
                parsed["node_count"] = data.get("node_count", 0)
                parsed["unassigned_alarms"] = data.get("unassigned_alarms", [])
                if data.get("status") == "error":
                    parsed["error"] = f"{data.get('error_type', 'ERROR')}: {data.get('error_message', 'Unknown error')}"
            except json.JSONDecodeError:
                pass
    except Exception:
        pass

    return parsed


def discover_oposs_nfm_t(section: Section) -> DiscoveryResult:
    """Discover the NFM-T agent status and system alarms services"""
    yield Service(item="AGENT STATUS")
    # Discover system alarms service if there are unassigned alarms
    if section.get("unassigned_alarms"):
        yield Service(item="System Alarms")


def check_oposs_nfm_t(item: str, section: Section) -> CheckResult:
    """Check the NFM-T agent status or system alarms"""
    if item == "AGENT STATUS":
        if section.get("error"):
            yield Result(
                state=State.CRIT,
                summary=section["error"]
            )
            return

        if section.get("status") == "ok":
            yield Result(
                state=State.OK,
                summary=f"NFM-T agent running, monitoring {section.get('node_count', 0)} nodes"
            )
        else:
            yield Result(
                state=State.UNKNOWN,
                summary=f"NFM-T agent status: {section.get('status', 'unknown')}"
            )
        return

    if item == "System Alarms":
        # Show unassigned alarms (e.g., MNC-FM system alarms)
        unassigned = section.get("unassigned_alarms", [])
        if not unassigned:
            yield Result(
                state=State.OK,
                summary="No system alarms"
            )
            return

        alarm_count = 0
        error_count = 0
        warning_count = 0

        for alarm in unassigned:
            severity = alarm.get("severity", "ok").lower()
            ne_name = alarm.get("neName", "unknown")
            state = SEVERITY_MAP.get(severity, State.UNKNOWN)

            if state != State.OK:
                alarm_count += 1
                if state == State.CRIT:
                    error_count += 1
                elif state == State.WARN:
                    warning_count += 1

            yield Result(
                state=state,
                summary=f"[{ne_name}] {alarm.get('summary', 'Unknown alarm')} [{severity}]"
            )

        yield Metric(name="oposs_nfm_t_system_alarm_count", value=alarm_count)
        yield Metric(name="oposs_nfm_t_system_error_count", value=error_count)
        yield Metric(name="oposs_nfm_t_system_warning_count", value=warning_count)


agent_section_oposs_nfm_t = AgentSection(
    name="oposs_nfm_t",
    parse_function=parse_oposs_nfm_t,
)

check_plugin_oposs_nfm_t = CheckPlugin(
    name="oposs_nfm_t",
    service_name="NFM-T %s",
    discovery_function=discover_oposs_nfm_t,
    check_function=check_oposs_nfm_t,
)


# =============================================================================
# SECTION 2: Node Alarms (piggyback to individual nodes)
# =============================================================================

def parse_oposs_nfm_t_node(string_table: StringTable) -> Section:
    """Parse the node alarms output"""
    parsed = {"alarms": []}

    try:
        for row in string_table:
            try:
                data = json.loads(row[0])
                parsed["alarms"] = data.get("alarms", [])
            except json.JSONDecodeError:
                pass
    except Exception:
        pass

    return parsed


def discover_oposs_nfm_t_node(section: Section) -> DiscoveryResult:
    """Discover the Fault Manager Alarms service for this node"""
    # Always discover if we have the section
    yield Service(item="Fault Manager Alarms")


def check_oposs_nfm_t_node(item: str, section: Section) -> CheckResult:
    """Check the alarms for this node"""
    alarms = section.get("alarms", [])

    if not alarms:
        yield Result(
            state=State.OK,
            summary="No alarms"
        )
        return

    # Process alarms and count by severity
    alarm_count = 0
    error_count = 0
    warning_count = 0

    for alarm in alarms:
        severity = alarm.get("severity", "ok").lower()
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
    yield Metric(name="oposs_nfm_t_alarm_count", value=alarm_count)
    yield Metric(name="oposs_nfm_t_error_count", value=error_count)
    yield Metric(name="oposs_nfm_t_warning_count", value=warning_count)


agent_section_oposs_nfm_t_node = AgentSection(
    name="oposs_nfm_t_node",
    parse_function=parse_oposs_nfm_t_node,
)

check_plugin_oposs_nfm_t_node = CheckPlugin(
    name="oposs_nfm_t_node",
    service_name="NFM-T %s",
    discovery_function=discover_oposs_nfm_t_node,
    check_function=check_oposs_nfm_t_node,
)


# =============================================================================
# SECTION 3: Services (piggyback to individual nodes)
# =============================================================================

def parse_oposs_nfm_t_service(string_table: StringTable) -> Section:
    """Parse the services output - one JSON line per service"""
    parsed = {"services": {}}

    try:
        for row in string_table:
            try:
                data = json.loads(row[0])
                service_id = data.get("id")
                if service_id:
                    parsed["services"][service_id] = data
            except json.JSONDecodeError:
                pass
    except Exception:
        pass

    return parsed


def discover_oposs_nfm_t_service(section: Section) -> DiscoveryResult:
    """Discover services for this node"""
    for service_id, service_data in section.get("services", {}).items():
        yield Service(
            item=service_id,
            parameters={"guiLabel": service_data.get("guiLabel", "")}
        )


def check_oposs_nfm_t_service(item: str, params: Mapping[str, Any], section: Section) -> CheckResult:
    """Check the status of a service"""
    service = section.get("services", {}).get(item)

    if not service:
        yield Result(
            state=State.UNKNOWN,
            summary=f"Service {item} not found"
        )
        return

    operational_state = service.get("operationalState", "")
    alarm_severity = service.get("alarmSeverity", "Cleared").lower()
    gui_label = service.get("guiLabel", "")
    a_port = service.get("aPortLabel", "")
    z_port = service.get("zPortLabel", "")
    effective_rate = service.get("effectiveRate", "")
    role = service.get("role", "")

    # Build info text
    info_parts = []
    if gui_label:
        info_parts.append(gui_label)
    if effective_rate:
        info_parts.append(f"[{effective_rate}]")
    if a_port and z_port:
        info_parts.append(f"({a_port} <-> {z_port})")

    info_text = " ".join(info_parts) if info_parts else f"Service {item}"

    # Check operational state first
    if operational_state != "Up":
        yield Result(
            state=State.UNKNOWN,
            summary=f"{info_text} (not Up: {operational_state})"
        )
        return

    # Map alarm severity to state
    state = SEVERITY_MAP.get(alarm_severity, State.UNKNOWN)

    # Build summary
    if state == State.OK:
        summary = f"{info_text} - OK"
    else:
        summary = f"{info_text} - {service.get('alarmState', 'Unknown')} [{alarm_severity}]"

    yield Result(
        state=state,
        summary=summary
    )


agent_section_oposs_nfm_t_service = AgentSection(
    name="oposs_nfm_t_service",
    parse_function=parse_oposs_nfm_t_service,
)

check_plugin_oposs_nfm_t_service = CheckPlugin(
    name="oposs_nfm_t_service",
    service_name="NFM-T Service %s",
    discovery_function=discover_oposs_nfm_t_service,
    check_function=check_oposs_nfm_t_service,
    check_default_parameters={},
)
