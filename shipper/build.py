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
import os.path
import tarfile

from StringIO import StringIO


class DockerFile(object):
    """Represents the docker file that can be either
    * a remote http, https, or git url
    * a local url
    * or a local tar archive
    """
    def __init__(self, path=None, fobj=None):
        self.archive, self.url  = _parse_build(path, fobj)

    @property
    def is_remote(self):
        return bool(self.url)

    @property
    def is_local(self):
        return self.archive is not None



def _parse_build(path=None, fobj=None):
    """Parses build parameters. Returns tuple
    (archive, remote)

    Where archive is a tar archive and remote is remote url if set.
    One of the tuple elements will be null

    """
    if path:
        for prefix in ('http://', 'https://', 'github.com/', 'git://'):
            if path.startswith(prefix):
                return None, path
        if path.startswith("~"):
            path = os.path.expanduser(path)
        return _archive_from_folder(path), None
    else:
        if not fobj:
            raise ValueError("Set path or fobj")
        return _archive_from_file(fobj), None


def _archive_from_folder(path):
    memfile = StringIO()
    try:
        t = tarfile.open(mode='w', fileobj=memfile)
        t.add(path, arcname='.')
        return memfile.getvalue()
    finally:
        memfile.close()


def _archive_from_file(dockerfile):
    memfile = StringIO()
    try:
        t = tarfile.open(mode='w', fileobj=memfile)
        if isinstance(dockerfile, StringIO):
            dfinfo = tarfile.TarInfo('Dockerfile')
            dfinfo.size = dockerfile.len
        else:
            dfinfo = t.gettarinfo(fileobj=dockerfile, arcname='Dockerfile')
        t.addfile(dfinfo, dockerfile)
        return memfile.getvalue()
    finally:
        memfile.close()

