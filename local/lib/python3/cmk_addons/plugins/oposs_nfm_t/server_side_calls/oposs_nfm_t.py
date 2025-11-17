#!/usr/bin/env python3
# Copyright (C) 2025 OETIKER+PARTNER AG - License: GNU General Public License v2

"""
Server-side calls configuration for NFM-T special agent
Converts GUI ruleset parameters into command-line arguments
"""

from collections.abc import Iterator
from pydantic import BaseModel
from cmk.server_side_calls.v1 import (
    HostConfig,
    SpecialAgentCommand,
    SpecialAgentConfig,
)


class Params(BaseModel):
    """Type-safe parameter model matching the ruleset"""
    username: str
    password: tuple[str, str]  # ("password", "stored_password_id") or ("store", "id")
    port: str | None = None


def commands_function(
    params: Params,
    host_config: HostConfig,
) -> Iterator[SpecialAgentCommand]:
    """Build command-line arguments for the special agent"""

    # Build argument list
    args: list[str | tuple[str, str, str]] = [
        "-u", params.username,
        "-p", params.password,  # Tuple for password store
    ]

    # Optional port parameter
    if params.port:
        args.extend(["--port", params.port])

    # Host address (from CheckMK host config)
    args.append(host_config.primary_ip_config.address or host_config.name)

    yield SpecialAgentCommand(command_arguments=args)


# CRITICAL: Must be named special_agent_<name>
# Name must match: libexec/agent_<name>
special_agent_oposs_nfm_t = SpecialAgentConfig(
    name="oposs_nfm_t",
    parameter_parser=Params.model_validate,
    commands_function=commands_function,
)
