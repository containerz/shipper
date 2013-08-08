Shipper
-------

Shipper is a fabric for docker - library for orchestrating docker containers.
Supports parallel execution and can generate command line interface.

Setup
-----

```shell
git clone ..
python setup.py develop
```

Status
------
Undergoing development. Is already useful for building dev environments.

Examples
--------

Define the commands that orchestrate your environments as python code

In file env.py:

```python
from shipper import Shipper, run, command

@command
def build(tag, path):
    s = Shipper()
    s.build(tag=tag, path=path)

@command
def ps(all=False, running=True):
    s = Shipper(["host-a", "host-b"])
    print s.containers(pretty=True, all=all, running=running)

@command
def start(image, command, ports=None):
    if ports:
        ports = ports.split(",")
    s = Shipper()
    s.run(image, command, ports=ports, once=True)

@command
def stop(image=None):
    s = Shipper()
    s.stop(*s.containers(image=image, running=True))

run()
```

Now you can use the env.py file as your command line tool, shipper has generated the command line interface.

```bash
python env.py ps --all
python env.py build base ~/images/base
python env.py build stop --image dev/.*
```
