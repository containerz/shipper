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

from .utils import (
    from_epoch,
    parse_hosts,
    container_config,
    images_to_ascii_table,
    containers_to_ascii_table,
    parse_volumes)

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
        cls.pool = HTTPConnectionPool(reactor, persistent=False)
        cls._init_logging()

    @classmethod
    def shutdown(cls):
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
        hosts = self.hosts
        if once:
            hosts = []
            containers = _grouped_by_host(self.containers(running=True))
            for host, values in containers.iteritems():
                if not _find_container(values, image, command):
                    hosts.append(host)
                    self.log.debug(
                        "Container {} {} is not running on {}".format(
                            image, host, command))
                else:
                    self.log.debug(
                        "Container {} {} is already running on {}".format(
                            image, host, command))

        volumes, binds = parse_volumes(kwargs.pop('volumes', []))
        kwargs['volumes'] = volumes
        kwargs['hosts'] = hosts
        containers = self.create_container(image, command, **kwargs)
        self.start(*containers, binds=binds)
        self.log.debug("Containers({}) {} {} started".format(
                containers, image, command))


    def create_container(self, image, command, hostname=None, user=None,
        detach=False, stdin_open=False, tty=False, mem_limit=0, ports=None,
        environment=None, dns=None, volumes=None, volumes_from=None,
                         hosts=None):
        config = container_config(image, command, hostname, user,
            detach, stdin_open, tty, mem_limit, ports, environment, dns,
            volumes, volumes_from)
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


Response = namedtuple("Response", "host code content")

class Container(dict):
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


class Image(dict):
    def __init__(self, host, values):
        dict.__init__(self)
        self.update(values)
        self.host = host

    def __str__(self):
        return "Image(host={}, values={})".format(
            self.host, dict.__str__(self))

    @property
    def repository(self):
        return self.get('Repository') or ''

    @property
    def tag(self):
        return self.get('Tag') or ''

    @property
    def created(self):
        return from_epoch(self['Created'])

    @property
    def id(self):
        return self.get('Id')

    @property
    def size(self):
        return self['Size']

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

