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

from Queue import Queue

from twisted.python import failure
from twisted.internet import defer

class Call(object):
    """Represents a call object - function to call, positional and keyword args
    """
    def __init__(self, fn, args=None, kwargs=None):
        self.fn = fn
        self.args = args or []
        self.kwargs = kwargs or {}


def blocking_call(reactor, calls, timeout=None):
    """Makes multiple network calls in parallel and
    blocks until all are done or timeout occurs
    (in this case raises an exception)
    """
    mapping = {}
    for call in calls:
        mapping[id(call)] = calls

    if len(mapping) != len(calls):
        raise ValueError("Each call object should be a separate instance!")

    queue = Queue()
    for call in calls:
        reactor.callFromThread(_make_call(queue, call))

    for i in range(len(calls)):
        key, result = queue.get()
        if isinstance(result, failure.Failure):
            result.raiseException()
        mapping[key] = result

    results = []
    for call in calls:
        results.append(mapping[id(call)])

    return results

def _make_call(queue, call):
    def f():
        result = defer.maybeDeferred(call.fn, *call.args, **call.kwargs)
        def put(v):
            queue.put((id(call), v))
        result.addBoth(put)
    return f

