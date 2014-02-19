# coding: utf-8
# Licensed under the Apache License, Version 2.0 (the "License")
# See LICENSE for details

import six
import shlex

from .utils import from_epoch, parse_ports


class ContainerConfig(dict):
    """Container configuration helper.
    """
    def __init__(self, image, command, **kwargs):
        dict.__init__(self)
        self.host = None

        if isinstance(command, six.string_types):
            command = shlex.split(command)

        get = kwargs.get
        exposed_ports, _ = parse_ports(get('ports', []))
        self.update({
            'Hostname': get('hostname'),
            'ExposedPorts': exposed_ports,
            'User': get('user'),
            'Tty': get('tty', False),
            'OpenStdin': get('open_stdin', False),
            'Memory': get('mem_limit', 0),
            'AttachStdin': get('stdin', False),
            'AttachStdout': get('stdout', False),
            'AttachStderr': get('stderr', False),
            'Env': get('environment'),
            'Cmd': command,
            'Dns': get('dns'),
            'Image': image,
            'Volumes': get('volumes'),
            'VolumesFrom': get('volumes_from'),
            'StdinOnce': get('stdin_once', False)
        })

    def to_json(self):
        return self


class Container(dict):
    """Helper wrapper around container dictionary
    to ease access to certain properties
    """
    def __init__(self, host, values):
        dict.__init__(self)
        self.host = host
        self.update(values)

    def __str__(self):
        return "Container(host={}, {})".format(
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

    @property
    def ip(self):
        return self['NetworkSettings']['IPAddress']
