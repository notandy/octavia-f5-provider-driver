# Copyright 2018 SAP SE
# Copyright (c) 2014-2018, F5 Networks, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

from oslo_config import cfg
from oslo_log import log as logging

from octavia_f5.common import constants
from octavia_f5.restclient.as3classes import Monitor
from octavia_f5.utils import driver_utils as utils

CONF = cfg.CONF
LOG = logging.getLogger(__name__)
UDP_CHECK = "#!/bin/sh\n/usr/bin/nc -uzv -w1 $1 $2 > /dev/null && echo up"


def get_name(healthmonitor_id):
    return "{}{}".format(constants.PREFIX_HEALTH_MONITOR, healthmonitor_id)


def get_monitors(health_monitor, members):
    # Check if all members have a custom address/port, so we could just adapt the monitor
    monitor_addresses = [member.monitor_address for member in members]
    monitor_ports = [member.monitor_port for member in members]

    ref_addr = monitor_addresses[0] or None
    ref_port = monitor_ports[0] or None

    if all(x == ref_addr for x in monitor_addresses) and all(x == ref_port for x in monitor_ports):
        return [(get_name(health_monitor.id),
                 get_monitor(health_monitor, ref_addr, ref_port))]

    # Create the standard health monitor without custom addresses/ports
    entities = [(get_name(health_monitor.id), get_monitor(health_monitor))]

    # Create additional custom health monitors with custom addresses/ports
    for member in members:
        # Custom member address
        if not utils.pending_delete(member) and (member.monitor_address or member.monitor_port):
            member_hm = get_monitor(health_monitor,
                                    member.monitor_address,
                                    member.monitor_port)
            name = get_name(member.id)
            entities.append((name, member_hm))

    return entities


def get_monitor(health_monitor, target_address=None, target_port=None):
    args = dict()

    # Standard Octavia monitor types
    if health_monitor.type == 'HTTP':
        args['monitorType'] = 'http'
    elif health_monitor.type == 'HTTPS':
        args['monitorType'] = 'https'
    elif health_monitor.type == 'PING':
        args['monitorType'] = 'icmp'
    elif health_monitor.type == 'TCP':
        args['monitorType'] = 'tcp'
        args['send'] = ''
        args['receive'] = ''
    elif health_monitor.type == 'TLS-HELLO':
        args['monitorType'] = 'tcp'
        args['send'] = ''
        args['receive'] = ''
    elif health_monitor.type == 'UDP-CONNECT':
        args['monitorType'] = 'external'
        args['script'] = UDP_CHECK
        args['receive'] = 'up'

    # F5 specific monitory types
    elif health_monitor.type == 'SIP':
        args['monitorType'] = 'sip'
    elif health_monitor.type == 'SMTP':
        args['monitorType'] = 'smtp'
    elif health_monitor.type == 'TCP-HALF_OPEN':
        args['monitorType'] = 'tcp-half-open'
    elif health_monitor.type == 'LDAP':
        args['monitorType'] = 'ldap'
    elif health_monitor.type == 'DNS':
        args['monitorType'] = 'dns'
        args['queryName'] = health_monitor.domain_name
    # No Health monitor type available
    else:
        return {}

    if health_monitor.type == 'HTTP' or health_monitor.type == 'HTTPS':
        http_version = '1.0'
        if health_monitor.http_version:
            http_version = health_monitor.http_version
        send = "{} {} HTTP/{}\\r\\n".format(
            health_monitor.http_method,
            health_monitor.url_path,
            http_version
            )
        if health_monitor.domain_name:
            send += "Host: {}\\r\\n\\r\\n".format(
                health_monitor.domain_name)
        else:
            send += "\\r\\n"

        args['send'] = send
        args['receive'] = _get_recv_text(health_monitor)

    if health_monitor.delay:
        args["interval"] = health_monitor.delay
    if health_monitor.timeout:
        timeout = (int(health_monitor.fall_threshold) *
                   int(health_monitor.timeout))
        args["timeout"] = timeout
    if health_monitor.rise_threshold:
        time_until_up = (int(health_monitor.rise_threshold) *
                         int(health_monitor.timeout))
        args["timeUntilUp"] = time_until_up
    if target_address:
        args["targetAddress"] = target_address
    if target_port:
        args["targetPort"] = target_port

    return Monitor(**args)


def _get_recv_text(healthmonitor):
    http_version = "1.(0|1)"
    if healthmonitor.http_version:
        http_version = "{:1.1f}".format(healthmonitor.http_version)

    try:
        if healthmonitor.expected_codes.find(",") > 0:
            status_codes = healthmonitor.expected_codes.split(',')
            recv_text = "HTTP/{} ({})".format(
                http_version, "|".join(status_codes))
        elif healthmonitor.expected_codes.find("-") > 0:
            status_range = healthmonitor.expected_codes.split('-')
            start_range = status_range[0]
            stop_range = status_range[1]
            recv_text = "HTTP/{} [{}-{}]".format(
                        http_version, start_range, stop_range
            )
        else:
            recv_text = "HTTP/{} {}".format(
                http_version, healthmonitor.expected_codes)
    except Exception as exc:
        LOG.error(
            "invalid monitor expected_codes=%s, http_version=%s, defaulting to '%s': %s",
            healthmonitor.expected_codes, healthmonitor.http_version,
            CONF.f5_agent.healthmonitor_receive, exc)
        recv_text = CONF.f5_agent.healthmonitor_receive
    return recv_text
