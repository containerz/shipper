# coding: utf-8
# Licensed under the Apache License, Version 2.0 (the "License")
# See LICENSE for details

from twisted.trial import unittest
from shipper.container import ContainerConfig


class ShipperContainerTestCase(unittest.TestCase):
    """
    Tests container wrappers
    """

    def test_container_config_defaults(self):
        """Makes sure defaults for container config function
        are sane.
        """
        config = ContainerConfig("shipper/base", "echo 'hi'")
        expected = {
            'AttachStderr': False,
            'AttachStdin': False,
            'AttachStdout': False,
            'Cmd': ['echo', 'hi'],
            'Dns': None,
            'Env': None,
            'Hostname': None,
            'Image': 'shipper/base',
            'Memory': 0,
            'OpenStdin': False,
            'StdinOnce': False,
            'ExposedPorts': {},
            'Tty': False,
            'User': None,
            'Volumes': None,
            'VolumesFrom': None
        }
        self.assertEqual(expected, config)


    def test_container_config(self):
        """Make sure all parameters are converted
        properly and to the right properties.
        """
        config = ContainerConfig(
            "shipper/base",
            "echo 'hi'",
            hostname="localhost",
            user="username",
            open_stdin=True,
            stderr=True,
            stdout=True,
            stdin=True,
            tty=True,
            mem_limit=1024,
            ports=["27017:27017"],
            environment=["a=b", "b=c"],
            dns=["8.8.8.8", "127.0.0.1"],
            volumes={"/home": {}},
            volumes_from="container")

        expected = {
            'AttachStderr': True,
            'AttachStdin': True,
            'AttachStdout': True,
            'Cmd': ['echo', 'hi'],
            'Dns': ['8.8.8.8', '127.0.0.1'],
            'Env': ['a=b', 'b=c'],
            'Hostname': 'localhost',
            'Image': 'shipper/base',
            'Memory': 1024,
            'OpenStdin': True,
            'StdinOnce': False,
            'ExposedPorts': {'27017/tcp': {}},
            'Tty': True,
            'User': 'username',
            'Volumes': {'/home': {}},
            'VolumesFrom': 'container'
        }
        self.assertEqual(expected, config)
