# coding: utf-8
# Licensed under the Apache License, Version 2.0 (the "License")
# See LICENSE for details

from twisted.trial import unittest
from shipper.host import Host, parse_hosts


class ShipperHostTestCase(unittest.TestCase):
    """
    Tests for the various utils
    """

    def test_host_comparison(self):
        """Ensure that hosts can be compared"""
        H = Host

        self.assertEqual(H("http://localhost"), H("http://localhost"))
        self.assertEqual(
            H("https://localhost:1234"), H("https://localhost:1234"))
        self.assertEqual(
            hash(H("https://localhost")), hash(H("https://localhost")))
        self.assertNotEqual(
            H("https://google.com:1234"), H("http://google.com:1234"))

        self.assertEqual(
            "http://google.com:1234", H("http://google.com:1234").url)

    def test_host_mapping(self):
        """Ensure that hosts can be used in hashes
        """
        H = Host
        a, b = H("http://google.com"), H("http://yahoo.com")
        vals = {a: 1, b: 2}
        self.assertEqual(1, vals[a])
        self.assertEqual(2, vals[b])

    def test_parse_hosts_invalid(self):
        """Invalid hosts of all sorts should be handled corectly
        """
        self.assertEqual([], parse_hosts(None))
        self.assertEqual([], parse_hosts(""))


    def test_parse_hosts(self):
        """Parse hosts strings into structured objects"""
        H = Host
        ph = parse_hosts

        self.assertEqual(
            [H("http://google.com:1234")],
            ph(["google.com"], default_port=1234))

        self.assertEqual(
            [H("http://google.com:1389")],
            ph(["google.com:1389"]))

        self.assertEqual(
            [H("http://google.com:1871")],
            ph([("google.com", 1871)]))

        self.assertEqual(
            [H("https://google.com:123")],
            ph(["https://google.com"], default_port=123))
