# coding: utf-8
# Licensed under the Apache License, Version 2.0 (the "License")
# See LICENSE for details

import time
import os.path
from datetime import datetime

import ago


def from_epoch(seconds):
    '''
    Converts epoch time (seconds since Jan 1, 1970) into a datetime object

    >>> from_epoch(1309856559)
    datetime.datetime(2011, 7, 5, 9, 2, 39)

    Returns None if 'seconds' value is not valid
    '''
    try:
        tm = time.gmtime(float(seconds))
        return datetime(
            tm.tm_year, tm.tm_mon, tm.tm_mday,
            tm.tm_hour, tm.tm_min, tm.tm_sec)
    except:
        raise ValueError(u"Invalid parameter: {}".format(seconds))


def human_size(num):
    """Converts bytes to human readable bytes reprsentation
    """
    if num == 0:
        return "0 bytes"
    if num == 1:
        return "1 byte"

    for x in ['bytes','KB','MB','GB']:
        if num < 1024.0 and num > -1024.0:
            if round(num) == num:
                return "%d %s" % (num, x)
            else:
                return "%3.1f %s" % (num, x)
        num /= 1024.0

    return "%3.1f %s" % (num, 'TB')


def time_ago(dt):
    """Returns human readable string saying how long
    ago the event happened, e.g. "1 hour ago"
    """
    diff = datetime.utcnow() - dt
    return ago.human(diff, precision=1)


def parse_volumes(vals):
    """Parses volumes into volumes to attach and binds from list
    of strings. Returns tuple with
    * {} - volumes to create on a container
    * [] - list of binds
    """
    volumes = {}
    binds = []
    for string in (vals or []):
        out = string.split(":", 1)
        if len(out) == 2:
            if string.startswith("~"):
                string = os.path.expanduser(string)
            binds.append(string)
            destination = out[1]
            volumes[destination] = {}
        else:
            volumes[string] = {}
    return volumes, binds


def parse_ports(vals):
    """
    Parses ports from format "hostPort:containerPort"
    into ExposedPorts and PortBindings tuples
    """
    exposed = {}
    bindings = {}

    for pair in vals:
        ports = pair.split(":")
        if len(ports) != 2:
            raise ValueError("Unspported format")

        host_port, container_port = ports
        if "/" in container_port:
            with_protocol = container_port.split("/")
            if len(with_protocol) != 2:
                raise ValueError("Unspported format")
            container_port, protocol = with_protocol
        else:
            protocol = "tcp"

        container_key = "{}/{}".format(container_port, protocol)
        exposed[container_key] = {}
        bindings.setdefault(container_key, []).append(
            {"HostIp": "", "HostPort": host_port})

    return (exposed, bindings)
