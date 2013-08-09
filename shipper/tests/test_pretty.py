# coding: utf-8
# Licensed under the Apache License, Version 2.0 (the "License")
# See LICENSE for details

from twisted.trial import unittest
from datetime import datetime
from calendar import timegm

from shipper import pretty, client, utils


class ShipperPrettyTestCase(unittest.TestCase):
    """
    Tests pretty printing of images and containers
    """

    def test_pretty_print_images(self):
        images = [client.Image]
