# coding: utf-8
# Licensed under the Apache License, Version 2.0 (the "License")
# See LICENSE for details

import mock

from twisted.internet.defer import maybeDeferred, succeed
from twisted.trial.unittest import TestCase

from shipper.client import Client
from shipper.shipper import Shipper


def _container(host, container_id):
    return mock.Mock(host=host, id=container_id)


class ShipperCommands(TestCase):
    """
    Tests commands (methods on Shipper)
    """
    def setUp(self):
        """
        Wraps treq so that actual calls are mostly made, but that certain
        results can be stubbed out
        """
        self.client = mock.Mock(Client)
        self.shipper = Shipper(
            client_builder=lambda *args, **kwargs: self.client)

        # this just runs the call and
        def _fake_blocking_call_from_thread(reactor, call, *args, **kwargs):
            d = maybeDeferred(call, *args, **kwargs)
            return self.successResultOf(d)

        self.blocking_call = mock.patch(
            'shipper.shipper.threads.blockingCallFromThread',
            side_effect = _fake_blocking_call_from_thread).start()
        self.addCleanup(mock.patch.stopall)

    def test_wait(self):
        """
        Client.wait is called for every host in Shipper, for every container
        passed to Shipper.wait.  The result is a list of results from all the
        hosts.
        """
        self.client.wait.side_effect = (
            lambda *args, **kwargs: succeed('wait_success'))

        containers = [_container('localhost:1234', '1'),
                      _container('localhost:2345', '2')]
        result = self.shipper.wait(*containers)

        self.client.wait.assert_has_calls([
            mock.call('localhost:1234', container=containers[0]),
            mock.call('localhost:2345', container=containers[1])])

        self.assertEqual(
            [(container, 'wait_success') for container in containers],
            result)
