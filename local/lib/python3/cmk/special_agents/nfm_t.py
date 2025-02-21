#!/usr/bin/env python3	
# Copyright (C) 2025 OETIIKER+PARTNER AG – License: GNU General Public License v2

"""
Special agent for monitoring NFM-T managed Nodes Check_MK.
"""

import argparse
import logging
import sys
import traceback
import os
import json
import base64
import urllib3
urllib3.disable_warnings()
import requests
from cmk.utils.password_store import replace_passwords
from pprint import pprint
import re
from datetime import datetime
import time

LOGGER = logging.getLogger(__name__)


def parse_arguments(argv):
    parser = argparse.ArgumentParser(description=__doc__)

    parser.add_argument("-u", "--username", required=True, type=str, help="user name")
    parser.add_argument(
        "-p", "--password", required=True, type=str, help="user password"
    )
    parser.add_argument(
        "-d", "--debug", action="store_true", help="Debug mode: raise Python exceptions"
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="count",
        help="Be more verbose (use twice for even more)",
    )
    parser.add_argument("hostaddress", help="nfm_t host name")

    args = parser.parse_args(argv)


    if args.verbose and args.verbose >= 2:
        fmt = "%(asctime)s %(levelname)s: %(name)s: %(filename)s: Line %(lineno)s %(message)s"
        lvl = logging.DEBUG
    elif args.verbose:
        fmt = "%(asctime)s %(levelname)s: %(message)s"
        lvl = logging.INFO
    else:
        fmt = "%(asctime)s %(levelname)s: %(message)s"
        lvl = logging.WARNING

    if args.debug:
        lvl = logging.DEBUG

    logging.basicConfig(level=lvl, format=fmt)

    return args


class nfmTFetcher:
    def __init__(self, hostaddress, username, password) -> None:  # type:ignore[no-untyped-def]

        self._endpoint = "https://%s/" % hostaddress
        self._testmode = hostaddress == "test"
        if self._testmode:
            return
        response = requests.post(
            self._endpoint + "rest-gateway/rest/api/v1/auth/token",
            headers={
                "content-type": "application/json",
                "accept": "application/json",
                "authorization": "Basic %s" % base64.b64encode(
                        f"{username}:{password}".encode("utf-8")
                    ).decode("utf-8"),
            },
            data=json.dumps(
                { "grant_type": "client_credentials" }
            ),
            verify=False,  # nosec
        )

        self._headers = {
            "content-type": "application/json",
            "accept": "application/json",
            "authorization": "Bearer %s" % response.json()["access_token"],
        }

    def __fetch_alarms(self):
        if self._testmode:
            return json.load(open("/tmp/nfm_t_alarms.json"))
        
        severity_levels = ['critical', 'major', 'minor']
        alarm_filter = ' or '.join(f"severity='{level}'" for level in severity_levels)
        encoded_filter = urllib3.parse.quote(alarm_filter)
        
        response = requests.get(
            f"{self._endpoint}FaultManagement/rest/api/v2/alarms/details?alarmFilter={encoded_filter}",
            headers=self._headers,
            verify=False,  # nosec
        )

        if response.status_code != 200:
            LOGGER.warning("response status code: %s", response.status_code)
            LOGGER.warning("response : %s", response.text)
            raise RuntimeError("Failed to fetch alarms")
        else:
            LOGGER.debug("success! response: %s", response.text)
            return response.json()
        
    def __fetch_nodes (self):
        if self._testmode:
            return json.load(open("/tmp/nfm_t_nodes.json"))
        response = requests.get(
            f"{self._endpoint}oms1350/data/otn/node/",
            headers=self._headers,
            verify=False,  # nosec
        )

        if response.status_code != 200:
            LOGGER.warning("response status code: %s", response.status_code)
            LOGGER.warning("response : %s", response.text)
            raise RuntimeError("Failed to fetch nodes")
        else:
            LOGGER.debug("success! response: %s", response.text)
            return response.json()
        
    def __fetch_services (self):
        if self._testmode:
            return json.load(open("/tmp/nfm_t_services.json"))
        response = requests.get(
            f"{self._endpoint}oms1350/data/otn/connection/path",
            headers=self._headers,
            verify=False,  # nosec
        )

        if response.status_code != 200:
            LOGGER.warning("response status code: %s", response.status_code)
            LOGGER.warning("response : %s", response.text)
            raise RuntimeError("Failed to fetch services")
        else:
            LOGGER.debug("success! response: %s", response.text)
            return response.json()
        
    def fetch(self):
        try:
            return self.__postprocess(
                self.__fetch_alarms(),
                self.__fetch_nodes(),
                self.__fetch_services(),
            )
        except Exception as e:
            LOGGER.warning("error processing response: %s", e)
            raise ValueError("Got invalid data from host")

    def __postprocess(self, alarms, nodes, services):
        SEVERITY_LEVELS = {
            'critical': 4,
            'major': 3,
            'minor': 2,
            'warning': 1,
            'ok': 0
        }

        node_status = {}
        # Sort alarms by severity in descending order
        sorted_alarms = sorted(
            alarms.get('response', {}).get('data', []),
            key=lambda x: SEVERITY_LEVELS.get(x.get('severity', 'ok'), 0),
            reverse=True
        )
        
        for alarm in sorted_alarms:
            ne_name = alarm['neName']
            current_severity = alarm.get('severity', 'ok').lower()
            
            if ne_name not in node_status:
                node_status[ne_name] = {
                    'severity': current_severity,
                    'alarms': []
                }
            
            node_status[ne_name]['alarms'].append({
                'summary': alarm.get('additionalText', 'No additional text'),
                'severity': current_severity
            })
            

        result = []
        for node in nodes.get('items', []):
            alarm_entries = []
            status = node_status.get(node['guiLabel'], {})
            if status.get('alarms'):
                alarm_entries = status['alarms']
            
            result.append({
                "node": node['guiLabel'],
                "alarms": alarm_entries if alarm_entries else [{'state': 'ok', 'summary': 'No active Alarms [ok]'}]
            })

        return result


def main(argv=None):
    replace_passwords()
    args = parse_arguments(argv or sys.argv[1:])
    sys.stdout.write("<<<nfm_t:sep(0)>>>\n")
    try:
        for session in nfmTFetcher(args.hostaddress, args.username, args.password).fetch():
            # turn the session content into a single line json string
            sys.stdout.write(json.dumps(session,sort_keys=True,separators=(',', ':')) + "\n")
    except Exception as e:
        formatted_traceback = traceback.format_exc()
        print(formatted_traceback)
        print(f"Error: {e}")
        sys.exit(1)

    sys.exit(0)
