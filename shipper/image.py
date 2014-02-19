# coding: utf-8
# Licensed under the Apache License, Version 2.0 (the "License")
# See LICENSE for details

from .utils import from_epoch


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
