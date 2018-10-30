#!/usr/bin/env python3
import lazycli


@lazycli.script
def script(version=False):
    if version:
        return 1.0


@script.subcommand
def hello(name, greeting="Hello", caps=False):
    return greet(name, greeting, caps)


@script.subcommand
def goodbye(name, greeting="Goodbye", caps=False):
    return greet(name, greeting, caps)


def greet(name, greeting, caps):
    if caps:
        return f'{greeting}, {name}!'.upper()
    return f'{greeting}, {name}!'


if __name__ == '__main__':
    script.run()
