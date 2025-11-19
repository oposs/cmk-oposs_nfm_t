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
    Secret,
    SpecialAgentCommand,
    SpecialAgentConfig,
)


class Params(BaseModel):
    """Type-safe parameter model matching the ruleset"""
    username: str
    password: Secret
    port: int | None = None
    no_cert_check: bool = False


def commands_function(
    params: Params,
    host_config: HostConfig,
) -> Iterator[SpecialAgentCommand]:
    """Build command-line arguments for the special agent"""

    # Build argument list
    args = [
        "-u",
        params.username,
        "-p",
        params.password.unsafe(),  # Extract password from Secret
    ]

    # Optional port parameter
    if params.port:
        args.extend(["--port", str(params.port)])

    # Optional certificate verification disable
    if params.no_cert_check:
        args.append("--no-cert-check")

    # Host address (from CheckMK host config)
    args.append(host_config.name)

    yield SpecialAgentCommand(command_arguments=args)


# CRITICAL: Must be named special_agent_<name>
# Name must match: libexec/agent_<name>
special_agent_oposs_nfm_t = SpecialAgentConfig(
    name="oposs_nfm_t",
    parameter_parser=Params.model_validate,
    commands_function=commands_function,
)
