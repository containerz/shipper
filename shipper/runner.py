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

import argparse
import inspect
from threading import Thread

from twisted.internet import reactor

from . import auto
from . import Shipper

functions = []

def command(fn):
    """Decorator that just register the function
    as the command for the runner
    """
    functions.append(fn)
    return fn

def run(*args):
    """Gets the functions directly via arguments, or indirectly
    via command decorator and builds command line utility
    executing the functions as command line parameters.
    """
    global functions
    functions = functions + list(args)

    parser = argparse.ArgumentParser(
        description=_info())

    auto.generate(parser, *functions)

    args = parser.parse_args()
    function = args.fn

    Shipper.startup()
    failed = []
    def call(*args, **kwargs):
        try:
            function(*args, **kwargs)
        except:
            failed.append(True)
        else:
            failed.append(False)
        

    t = Thread(target=call, args=(args,))
    t.daemon = True
    t.start()

    def waiter(th):
        th.join()
        Shipper.shutdown()
        reactor.callFromThread(reactor.stop)

    w = Thread(target=waiter, args=(t,))
    w.daemon = True
    w.start()

    reactor.run()

    if failed[0]:
        print "Fail"
        exit(-1)
    else:
        print "Success"

def _info():
    """Returns the module doc string"""
    frm = inspect.stack()[-1]
    mod = inspect.getmodule(frm[0])
    return mod.__doc__ or ""

