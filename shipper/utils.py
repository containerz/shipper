"""
Copyright [2013] [Rackspace]

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

import time
import six
import shlex
import re

from urlparse import urlparse, urlunparse
from datetime import datetime
from StringIO import StringIO
from contextlib import closing

import ago
from texttable import Texttable as TextTable


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
        return None


def human_size(num):
    """Converts bytes to human readable bytes reprsentation
    """
    for x in ['bytes','KB','MB','GB']:
        if num < 1024.0 and num > -1024.0:
            return "%3.1f%s" % (num, x)
        num /= 1024.0
    return "%3.1f%s" % (num, 'TB')


def time_ago(dt):
    diff = datetime.utcnow() - dt
    return ago.human(diff, precision=1)


def parse_volumes(vals):
    """Parses volumes into volumes to attach and binds
    """
    volumes = {}
    binds = []
    for string in vals:
        out = string.split(":", 1)
        if len(out) == 2:
            binds.append(string)
            destination = out[1]
            volumes[destination] = {}
        else:
            volumes[string] = {}
    return volumes, binds


def container_config(
    image,
    command,
    hostname=None,
    user=None,
    detach=False,
    stdin_open=False,
    tty=False,
    mem_limit=0,
    ports=None,
    environment=None,
    dns=None,
    volumes=None,
    volumes_from=None):
    if isinstance(command, six.string_types):
        command = shlex.split(command)
    return {
        'Hostname': hostname,
        'PortSpecs': ports,
        'User': user,
        'Tty': tty,
        'OpenStdin': stdin_open,
        'Memory':mem_limit,
        'AttachStdin': False,
        'AttachStdout': False,
        'AttachStderr': False,
        'Env': environment,
        'Cmd': command,
        'Dns': dns,
        'Image': image,
        'Volumes': volumes,
        'VolumesFrom': volumes_from,
    }

def images_to_ascii_table(images):
    with closing(StringIO()) as out:
        for host, values in images.iteritems():
            out.write(str(host) + "\n")
            t = TextTable()
            t.set_deco(TextTable.HEADER)
            t.set_cols_dtype(['t'] *5)
            t.set_cols_align(["l"] *5)
            rows = []
            rows.append(['Repository', 'Tag', 'Id', 'Created', 'Size'])
            for image in values:
                rows.append([
                    image.repository or '<none>',
                    image.tag or '<none>',
                    image.id[:12],
                    time_ago(image.created),
                    human_size(image.size)
                    ])
            t.add_rows(rows)
            out.write(t.draw() + "\n\n")
        return out.getvalue()

def containers_to_ascii_table(containers):
    with closing(StringIO()) as out:
        for host, values in containers.iteritems():
            out.write("[" + str(host) + "] \n")
            t = TextTable(max_width=400)
            t.set_deco(TextTable.HEADER)
            t.set_cols_dtype(['t'] * 6)
            t.set_cols_align(["l"] * 6)
            t.set_cols_width([12, 25, 25, 15, 20, 15])
            rows = []
            rows.append(
                ['Id', 'Image', 'Command', 'Created', 'Status', 'Ports'])
            for container in values:
                rows.append([
                        container.id[:12],
                        container.image,
                        container.command[:20],
                        time_ago(container.created),
                        container.status,
                        container.ports
                        ])
            t.add_rows(rows)
            out.write(t.draw() + "\n\n")
        return out.getvalue()

def stripped(*args):
    return [a.strip() for a in args]

class Host(object):
    def __init__(self, url):
        self.a = urlparse(url)

    @property
    def url(self):
        return urlunparse(self.a)

    def __str__(self):
        return "Host({})".format(self.a.netloc)

    def __repr__(self):
        return "Host({})".format(self.a.netloc)

    def __hash__(self):
        return hash(str(self.a))

    def __eq__(self, other):
        return str(self.a) == other


def parse_hosts(hosts, default_port=4243):
    """
    Converts hosts in free form to list of urls
    """
    out = []
    for param in hosts:
        if isinstance(param, (tuple, list)):
            if len(param) != 2:
                raise ValueError("Param should be (host, port)")
            host, port = param
            out.append(Host("http://{}:{}".format(host, port)))
        elif isinstance(param, str):
            if not (param.startswith("http://") or param.startswith("https://")):
                param = "http://{}".format(param)

            if not re.search(r":\d+", param):
                param = "{}:{}".format(param, default_port)
            out.append(Host(param))
        else:
            raise ValueError(
                "Unsupported parameter type: {}".format(type(param)))
    return out
