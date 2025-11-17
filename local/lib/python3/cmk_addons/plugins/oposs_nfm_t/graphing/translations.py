#!/usr/bin/env python3
# Copyright (C) 2025 OETIKER+PARTNER AG - License: GNU General Public License v2

"""
Metric translations for NFM-T plugin
Preserves historical data when renaming metrics from unprefixed to prefixed names
"""

from cmk.graphing.v1 import translations

# Translation to preserve historical data during metric renaming
# Old metrics: alarm_count, error_count, warning_count
# New metrics: oposs_nfm_t_alarm_count, oposs_nfm_t_error_count, oposs_nfm_t_warning_count
translation_oposs_nfm_t = translations.Translation(
    name="oposs_nfm_t",
    check_commands=[translations.PassiveCheck("oposs_nfm_t")],
    translations={
        "alarm_count": translations.RenameTo("oposs_nfm_t_alarm_count"),
        "error_count": translations.RenameTo("oposs_nfm_t_error_count"),
        "warning_count": translations.RenameTo("oposs_nfm_t_warning_count"),
    },
)
