# coding: utf-8
# Licensed under the Apache License, Version 2.0 (the "License")
# See LICENSE for details

"""Twisted based client with paralell execution in mind and fixes
quirks of the official docker-py client.
"""

import re
import logging
import logging.handlers
import socket
from copy import copy
from collections import namedtuple

from twisted.internet import reactor
from twisted.web.client import HTTPConnectionPool
from twisted.internet import threads
from twisted.internet import defer

from .utils import parse_volumes, parse_ports
from .container import Container, ContainerConfig
from .image import Image
from .host import parse_hosts
from .pretty import  images_to_ascii_table, containers_to_ascii_table
from .client import Client
from .build import DockerFile


class Shipper(object):
    """Shipper is a class providing parallelized operations
    docker client on multiple hosts and various shortcuts and
    convenience methods on top of the raw docker client.
    """

    pool = None
    log = None

    @classmethod
    def startup(cls):
        """Initiates connection pool and logging.

        We can not use persisten connections here as docker server
        has some troubles with those
        """
        cls.pool = HTTPConnectionPool(reactor, persistent=False)
        cls._init_logging()

    @classmethod
    def shutdown(cls):
        """Shuts down connection pool"""
        threads.blockingCallFromThread(
            reactor, cls.pool.closeCachedConnections)

    def __init__(self, hosts=None, version="1.6", timeout=None,
                 client_builder=None):
        self.hosts = parse_hosts(hosts or ["localhost"])

        if client_builder is None:
            client_builder = Client
        self.c = client_builder(
            version, timeout, log=self.log, pool=self.pool)

        self.version = version
        self.timeout = timeout

    def build(self, path=None, fobj=None, tag=None, quiet=False, nocache=False, rm=False):
        """Run build of a container from buildfile
        that can be passed as local/remote path or file object(fobj)
        """
        dockerfile = DockerFile(path, fobj)
        def call():
            deferreds = []
            for host in self.hosts:
                deferreds.append(
                    self.c.build(
                        host, dockerfile, tag=tag, quiet=quiet, nocache=nocache, rm=rm))
            return defer.gatherResults(deferreds, consumeErrors=True)

        responses = threads.blockingCallFromThread(reactor, call)
        return [Response(h, 200, r) for h, r in zip(self.hosts, responses)]


    def parallel(self, method, params):
        def call():
            if isinstance(params, dict):
                # we assume that it's all the same call to all default hosts
                # with the same arguments
                deferreds = [method(h, **copy(params)) for h in self.hosts]
            elif isinstance(params, list):
                # we assume that it's a list of tuples (host, kwargs)
                # (useful in case if you have parallel calls to
                # different endpoints)
                deferreds = []
                for host, kwargs in params:
                    deferreds.append(method(host, **copy(kwargs)))

            return defer.gatherResults(deferreds, consumeErrors=True)

        return threads.blockingCallFromThread(reactor, call)

    def images(self, **kwargs):
        pretty = kwargs.pop('pretty', False)
        responses = self.parallel(self.c.images, kwargs)

        images = _flatten(responses, self.hosts, Image)
        if pretty:
            return images_to_ascii_table(_grouped_by_host(images))
        else:
            return images

    def containers(self, **kwargs):
        pretty = kwargs.pop('pretty', False)
        running = kwargs.pop('running', True)
        image = kwargs.pop('image', None)
        command = kwargs.pop('command', None)
        responses = self.parallel(self.c.containers, kwargs)

        containers = _flatten(responses, self.hosts, Container)

        if running != None:
            if running:
                f = lambda x: x.is_running
            else:
                f = lambda x: x.is_stopped
            containers = filter(f, containers)

        if image != None:
            f = lambda x: re.match(image, x.image)
            containers = filter(f, containers)

        if command != None:
            f = lambda x: re.match(command, x.command)
            containers = filter(f, containers)

        if pretty:
            return containers_to_ascii_table(_grouped_by_host(containers))
        else:
            return containers

    def create_container(self, config, hosts=None, name=None):
        hosts = hosts or self.hosts
        kwargs = [(host, {"config": config, "name": name}) for host in hosts]
        responses = self.parallel(self.c.create_container, kwargs)
        return _flatten(responses, hosts, Container)


    def start(self, *containers, **kwargs):
        self.log.debug("Starting {}".format(containers))
        _, port_binds = parse_ports(kwargs.get('ports', []))
        kwargs = [(c.host, {"container": c,
                            "binds": kwargs.get("binds"),
                            "port_binds": port_binds,
                            "links": kwargs.get("links", [])})
                  for c in containers]
        self.parallel(self.c.start, kwargs)

    def stop(self, *containers, **kwargs):
        self.log.debug("Stopping {}".format(containers))
        stop_args = [(c.host, {
                    "container": c,
                    "wait_seconds": kwargs.get('wait_seconds', 5)
                 })
                 for c in containers]
        self.parallel(self.c.stop, stop_args)
        return containers

    def attach(self, *containers, **kwargs):
        self.log.debug("Attaching to {}".format(containers))
        calls = []
        for c in containers:
            kw = copy(kwargs)
            kw['container'] = c
            calls.append((c.host, kw))
        self.parallel(self.c.attach, calls)
        return containers

    def wait(self, *containers):
        """
        Blocks until all the container stop, and returns a list of
        tuples of the container and a JSON blob containing its status code.
        """
        calls = []
        hosts = []
        for c in containers:
            calls.append((c.host, {'container': c}))
            hosts.append(c.host)
        responses = self.parallel(self.c.wait, calls)
        return zip(containers, responses)

    def inspect(self, *containers):
        calls = []
        hosts = []
        for c in containers:
            calls.append((c.host, {'container': c}))
            hosts.append(c.host)
        responses = self.parallel(self.c.inspect, calls)
        return _flatten(responses, hosts, Container)

    def run(self, image, command, **kwargs):
        """Creates a container and runs it
        """
        hosts = copy(self.hosts)
        once = kwargs.pop('once', False)
        detailed = kwargs.pop('detailed', False)
        if once:
            containers = self.containers(
                image=image, command=command, running=True)
            for host, values in _grouped_by_host(containers).iteritems():
                if len(values):
                    hosts.remove(host)
                    self.log.debug(
                        "Container {} {} is already running on {}".format(
                            image, host, command))
        if not hosts:
            return []

        volumes, binds = parse_volumes(kwargs.pop('volumes', []))
        kwargs['volumes'] = volumes
        config = ContainerConfig(image, command, **kwargs)
        containers = self.create_container(
            config, hosts=hosts, name=kwargs.get('name'))

        self.start(*containers,
                    binds=binds,
                    ports=kwargs.get('ports', []),
                    links=kwargs.get('links', []))
        self.log.debug("Containers({}) {} {} started".format(
                containers, image, command))

        if detailed:
            return self.inspect(*containers)
        return containers


    @classmethod
    def _init_logging(cls, **kwargs):
        cls.log = logging.getLogger("shipper")
        cls.log.setLevel(logging.DEBUG)

        formatter = logging.Formatter(
            "%(levelname)-5.5s PID:%(process)d [%(name)s] %(message)s")
        cls._add_console_output(cls.log, formatter)
        cls._add_syslog_output(cls.log, formatter)


    @classmethod
    def _add_console_output(cls, log, formatter):
        # create console handler and set level to debug
        h = logging.StreamHandler()
        h.setLevel(logging.DEBUG)

        # create formatter
        h.setFormatter(formatter)
        log.addHandler(h)


    @classmethod
    def _add_syslog_output(cls, log, formatter):
        try:
            h = logging.handlers.SysLogHandler(address='/dev/log')
            h.setLevel(logging.DEBUG)

            h.setFormatter(formatter)
            log.addHandler(h)
        except socket.error:
            # Skip setting up syslog if /dev/log doesn't exist
            pass


Response = namedtuple("Response", "host code content")

def _grouped_by_host(values):
    grouped = {}
    for v in values:
        grouped.setdefault(v.host, []).append(v)
    return grouped

def _flatten(values, hosts, cls):
    out = []
    for h, host_values in zip(hosts, values):
        if not isinstance(host_values, list):
            host_values = [host_values]
        for value in host_values:
            out.append(cls(h, value))
    return out
