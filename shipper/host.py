# coding: utf-8
# Licensed under the Apache License, Version 2.0 (the "License")
# See LICENSE for details

import re
from urlparse import urlparse, urlunparse


def parse_hosts(hosts, default_port=4243):
    """Converts hosts in free form to list of urls
    """
    out = []
    for param in (hosts or []):

        if isinstance(param, (tuple, list)):
            if len(param) != 2:
                raise ValueError("Param should be (host, port)")
            host, port = param
            out.append(Host("http://{}:{}".format(host, port)))

        elif isinstance(param, str):
            if not (param.startswith("http://") or
                    param.startswith("https://")):
                param = "http://{}".format(param)

            if not re.search(r":\d+", param):
                param = "{}:{}".format(param, default_port)
            out.append(Host(param))
        else:
            raise ValueError(
                "Unsupported parameter type: {}".format(type(param)))
    return out


class Host(object):
    """Represents docker-enabled host.
    Is hasheable, can be put into dictionaries.
    """
    def __init__(self, url):
        self.a = urlparse(url)

    @property
    def url(self):
        return urlunparse(self.a)

    def __str__(self):
        return "Host({})".format(self.a.netloc)

    def __repr__(self):
        return "Host({})".format(self.a.netloc)

    def __hash__(self):
        return hash(str(self.a))

    def __eq__(self, other):
        return str(self.a) == other
