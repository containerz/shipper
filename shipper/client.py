# coding: utf-8
# Licensed under the Apache License, Version 2.0 (the "License")
# See LICENSE for details

"""Twisted based client with paralell execution in mind and fixes
quirks of the official docker-py client.
"""

import re
import json
import logging
import logging.handlers
from functools import partial
from copy import copy
from collections import namedtuple

from twisted.internet import reactor
from twisted.web.client import HTTPConnectionPool
from twisted.internet import threads

import treq

from .utils import parse_volumes
from .container import Container, container_config
from .image import Image
from .host import parse_hosts
from .pretty import  images_to_ascii_table, containers_to_ascii_table
from .build import parse_build
from .parallel import blocking_call, Call
from .errors import assert_status


class Shipper(object):
    """Shipper is a docker client that supports parallel execution,
    streaming replies and logging.
    """

    pool = None
    log = None

    def __init__(
        self, hosts=("http://localhost:4243",), version="1.3", timeout=None):
        self.hosts = parse_hosts(hosts)
        self.version = version
        self.timeout = timeout

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

    def build(self, path=None, tag=None, quiet=False, fobj=None):
        """Run build of a container from buildfile
        that can be passed as local/remote path or file object(fobj)
        """
        archive, remote = parse_build(path, fobj)
        params = {
            'q': quiet
        }
        if remote:
            params['remote'] = remote
        if tag:
            params['t'] = tag

        headers = {}
        if not remote:
            headers = {'Content-Type': 'application/tar'}

        containers = {}
        def on_content(host, line):
            if line:
                match = re.search(r'Successfully built ([0-9a-f]+)', line)
                if match:
                    containers[id(host)] = match.group(1)
                self.log.debug("{}: {}".format(host, line.strip()))

        calls = []
        for host in self.hosts:
            calls.append(
                Call(
                    fn=treq.post,
                    kwargs=dict(
                        url=self._make_url(host.url, 'build'),
                        data=archive,
                        params=params,
                        headers=headers,
                        pool=self.pool)))

        responses = blocking_call(reactor, calls, timeout=self.timeout)

        calls = []
        for host, response in zip(self.hosts, responses):
            calls.append(
                Call(fn=treq.collect,
                     args=[response, partial(on_content, host)]))

        blocking_call(reactor, calls, timeout=self.timeout)

        if len(containers) != len(self.hosts):
            raise RuntimeError("Build Failed!")

        out = []
        for host, response in zip(self.hosts, responses):
            out.append(
                Response(host=host,
                         code=response.code,
                         content=containers[id(host)]))

        for r in out:
            assert_status(r.code, "{}: {}".format(r.host, r.content))

        return out

    def images(self, name=None, quiet=False,
               all=False, viz=False, pretty=False):

        path = "images/viz" if viz else "images/json"
        params = {
            'only_ids': 1 if quiet else 0,
            'all': 1 if all else 0,
            'params': name
        }

        responses = self._request(
            method=treq.get,
            requests=[(host, path) for host in self.hosts],
            params=params,
            expect_json=not viz)

        images = []
        for r in responses:
            for i in r.content:
                images.append(Image(r.host, i))

        if pretty:
            return images_to_ascii_table(_grouped_by_host(images))
        else:
            return images


    def containers(self, quiet=False, all=False, trunc=True, latest=False,
        since=None, before=None, limit=-1, pretty=False, running=None, image=None):
        params = {
            'limit': 1 if latest else limit,
            'only_ids': 1 if quiet else 0,
            'all': 1 if all else 0,
            'trunc_cmd': 1 if trunc else 0,
            'since': since,
            'before': before
        }
        path = 'containers/ps'
        responses = self._get(
            requests=[(host, path) for host in self.hosts],
            params=params)

        containers = _containers_from_responses(responses)

        if running != None:
            if running:
                f = lambda x: x.is_running
            else:
                f = lambda x: x.is_stopped
            containers = filter(f, containers)

        if image != None:
            f = lambda x: re.match(image, x.image)
            containers = filter(f, containers)

        if pretty:
            return containers_to_ascii_table(
                _grouped_by_host(containers))
        else:
            return containers

    def run(self, image, command, **kwargs):
        """Creates a container and runs it
        """
        once = kwargs.pop('once', False)
        hosts = copy(self.hosts)
        if once:
            containers = _grouped_by_host(self.containers(running=True))
            for host, values in containers.iteritems():
                if _find_container(values, image, command):
                    print "Removing:", host, image
                    hosts.remove(host)
                    self.log.debug(
                        "Container {} {} is running on {}".format(
                            image, host, command))

        if not hosts:
            return

        volumes, binds = parse_volumes(kwargs.pop('volumes', []))
        kwargs['volumes'] = volumes
        kwargs['hosts'] = hosts
        containers = self.create_container(image, command, **kwargs)

        self.start(*containers, binds=binds)
        self.log.debug("Containers({}) {} {} started".format(
                containers, image, command))


    def create_container(self, image, command, **kwargs):
        hosts = kwargs.pop('hosts')
        config = container_config(image, command, **kwargs)
        return self.create_container_from_config(config, hosts)


    def create_container_from_config(self, config, hosts=None):
        return _containers_from_responses(self._post(
            requests=[(host, "containers/create") for host in hosts],
            data=config,
            post_json=True))

    def start(self, *args, **kwargs):
        start_config = {}
        binds = kwargs.pop('binds', None)
        if binds:
            start_config['Binds'] = binds

        self.log.debug("Starting {}".format(args))
        self._post(
            requests=[(c.host, "containers/{}/start".format(c.id)) for c in args],
            data=start_config,
            post_json=True,
            expect_json=False)

    def stop(self, *args, **kwargs):
        self.log.debug("Stopping {}".format(args))
        self._post(
            requests=[(c.host, "containers/{}/stop".format(c.id)) for c in args],
            params={'t': kwargs.get('wait_seconds', 5)},
            expect_json=False)


    def _request(self, method, requests, **kwargs):
        params = copy(kwargs.get('params', {}))
        for key, val in kwargs.get('params', {}).iteritems():
            if val is None:
                del params[key]
        kwargs['params'] = params
        expect_json = kwargs.pop('expect_json', True)
        kwargs['pool'] = self.pool

        post_json = kwargs.pop('post_json', False)
        if post_json:
            headers = kwargs.setdefault('headers', {})
            headers['Content-Type'] = ['application/json']
            kwargs['data'] = json.dumps(kwargs['data'])

        # first get responses
        calls = []
        for host, path in requests:
            new_args = copy(kwargs)
            new_args['url'] = self._make_url(host.url, path)
            calls.append(Call(method, kwargs=new_args))
        responses = blocking_call(reactor, calls, timeout=self.timeout)

        # collect replies
        collect = treq.json_content if expect_json else treq.content
        calls = [Call(fn=collect, args=[r]) for r in responses]
        values = blocking_call(reactor, calls, timeout=self.timeout)

        out = []
        for (host, path), response, value in zip(requests, responses, values):
            out.append(Response(host=host, code=response.code, content=value))

        for r in out:
            assert_status(r.code, "{}: {}".format(r.host, r.content))

        return out

    def _get(self, **kwargs):
        return self._request(treq.get, **kwargs)

    def _post(self, **kwargs):
        return self._request(treq.post, **kwargs)

    def _make_url(self, url, method):
        return "{}/v{}/{}".format(url, self.version, method)

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
        h = logging.handlers.SysLogHandler(address='/dev/log')
        h.setLevel(logging.DEBUG)

        h.setFormatter(formatter)
        log.addHandler(h)


Response = namedtuple("Response", "host code content")

def _grouped_by_host(values):
    grouped = {}
    for v in values:
        grouped.setdefault(v.host, []).append(v)
    return grouped

def _find_container(containers, image, command):
    image, command = image.strip().lower(), command.strip().lower()
    for container in containers:
        if image == container.image and command == container.command:
            return container

def _containers_from_responses(responses):
    containers = []
    for r in responses:
        if isinstance(r.content, list):
            vals = r.content
        else:
            vals = [r.content]
        for c in vals:
            containers.append(Container(r.host, c))
    return containers

