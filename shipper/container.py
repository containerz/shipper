# coding: utf-8
# Licensed under the Apache License, Version 2.0 (the "License")
# See LICENSE for details

import six
import shlex

from .utils import from_epoch


def container_config(image, command, **kwargs):
    """Maker for container config that is understood
    by docker API
    """
    if isinstance(command, six.string_types):
        command = shlex.split(command)
    get = kwargs.get
    return {
        'Hostname': get('hostname'),
        'PortSpecs': get('ports'),
        'User': get('user'),
        'Tty': get('tty', False),
        'OpenStdin': get('stdin_open', False),
        'Memory': get('mem_limit', 0),
        'AttachStdin': get('attach_stdin', False),
        'AttachStdout': get('attach_stdout', False),
        'AttachStderr': get('attach_stderr', False),
        'Env': get('environment'),
        'Cmd': command,
        'Dns': get('dns'),
        'Image': image,
        'Volumes': get('volumes'),
        'VolumesFrom': get('volumes_from'),
    }

class Container(dict):
    """Helper wrapper around container dictionary
    to ease access to certain properties
    """
    def __init__(self, host, values):
        dict.__init__(self)
        self.update(values)
        self.host = host

    def __str__(self):
        return "Container(host={}, values={})".format(
            self.host, dict.__str__(self))

    @property
    def id(self):
        return self.get('Id')

    @property
    def command(self):
        return (self.get('Command') or "").strip()

    @property
    def is_running(self):
        return self.status.startswith("Up")

    @property
    def is_stopped(self):
        return self.status.startswith("Exit")

    @property
    def image(self):
        return (self.get('Image') or "").strip()

    @property
    def created(self):
        return from_epoch(self['Created'])

    @property
    def status(self):
        return self.get("Status") or ""

    @property
    def ports(self):
        return self['Ports']