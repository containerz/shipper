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

import inspect
from collections import namedtuple

Arg = namedtuple("Arg", "name default")
NoDefault = object()

def generate(parser, *fn):
    subparsers = parser.add_subparsers(help="Yo")
    for fn in fn:
        _from_function(subparsers, fn)

def _from_function(subparsers, fn):
    arguments = _inspect_arguments(fn)
    parser = subparsers.add_parser(fn.__name__, help=fn.__doc__)
    parser.set_defaults(fn=fn)
    for a in arguments:
        if a.default is NoDefault:
            parser.add_argument(a.name)
        else:
            if a.default in (True, False):
                parser.add_argument(
                    "--{}".format(a.name),
                    choices=["yes","no"],
                    default="yes" if a.default else "no")
            else:
                parser.add_argument("--{}".format(a.name), default=a.default)

    def call(args):
        kwargs = {}
        for a in arguments:
            kwargs[a.name] = getattr(args, a.name)
            if a.default in (True, False):
                kwargs[a.name] = kwargs[a.name].lower().strip() == "yes"
        return fn(**kwargs)

    parser.set_defaults(fn=call)

def _inspect_arguments(fn):
    spec = inspect.getargspec(fn)
    sdefaults = list(spec.defaults or [])
    defaults = ([NoDefault] * (len(spec.args) - len(sdefaults))) + sdefaults
    parsed = []
    for arg, default in zip(spec.args, defaults):
        parsed.append(Arg(name=arg, default=default))

    return parsed
