# coding: utf-8
# Licensed under the Apache License, Version 2.0 (the "License")
# See LICENSE for details

from twisted.trial import unittest
from datetime import datetime
from shipper import utils
from calendar import timegm
import mock


class ShipperUtilsTestCase(unittest.TestCase):
    """
    Tests for the various utils
    """

    def test_from_epoch(self):
        """
        Test conversion from unix epoch seconds to
        reasonable times
        """
        # invalid leads to none value?
        self.assertRaises(ValueError, utils.from_epoch, 'invalid')

        now = datetime(2013, 3, 4, 1, 2, 3, 0)
        epoch_now = timegm(now.timetuple())
        self.assertEqual(now, utils.from_epoch(epoch_now))

    def test_human_size(self):
        """
        Makes sure human_size converts properly
        """
        self.assertEquals("0 bytes", utils.human_size(0))
        self.assertEquals("1 byte", utils.human_size(1))
        self.assertEquals("5 bytes", utils.human_size(5))
        self.assertEquals("1023 bytes", utils.human_size(1023))
        self.assertEquals("1 KB", utils.human_size(1024))
        self.assertEquals("1.5 KB", utils.human_size(1024 * 1.5))
        self.assertEquals("1.7 MB", utils.human_size(1024 * 1024 * 1.7))
        self.assertEquals("5.2 GB", utils.human_size(1024 * 1024 * 1024 * 5.2))
        self.assertEquals(
            "1.2 TB", utils.human_size(1024 * 1024 * 1024 * 1024 * 1.2))

    @mock.patch('shipper.utils.datetime')
    def test_time_ago(self, m):
        """Testing sane formatting for times
        """
        m.utcnow = mock.Mock(return_value=datetime(2013, 3, 4, 1, 2, 3, 0))
        self.assertEqual(
            "59 days ago", utils.time_ago(datetime(2013, 1, 4, 1, 2, 3, 0)))

    def test_parse_volumes_invalid_params(self):
        self.assertEquals(
            ({}, []), utils.parse_volumes(None))

        self.assertEquals(
            ({}, []), utils.parse_volumes(""))

    def test_parse_volumes(self):
        """Parsing volumes parameter
        """
        volumes, binds = utils.parse_volumes(["/home/local:/home/container"])
        self.assertEquals({"/home/container": {}}, volumes)
        self.assertEquals(["/home/local:/home/container"], binds)

        volumes, binds = utils.parse_volumes(
            ["/home/local:/home/container", "/container"])
        self.assertEquals(
            {"/home/container", "/container"}, set(volumes.keys()))
        self.assertEquals(["/home/local:/home/container"], binds)

    def test_parse_ports(self):
        """Parsing port mappings
        """
        exposed, binds = utils.parse_ports(["80:80"])
        self.assertEquals(
            {'80/tcp': [{'HostIp': '', 'HostPort': '80'}]}, binds)
        self.assertEquals({'80/tcp': {}}, exposed)

        exposed, binds = utils.parse_ports(["8125:8125/udp"])
        self.assertEquals(
            {'8125/udp': [{'HostIp': '', 'HostPort': '8125'}]}, binds)
        self.assertEquals({'8125/udp': {}}, exposed)
