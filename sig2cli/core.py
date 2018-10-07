# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
import argparse
import functools
import json
import inspect
import typing as t


def sort_params(params):
    positionals = []
    flags = []
    options = []
    kwargs = False
    for param in params:
        if param.kind == param.VAR_KEYWORD:
            kwargs = True
        elif param.annotation is bool or isinstance(param.default, bool):
            flags.append(param)
        elif param.default == param.empty:
            positionals.append(param)
        else:
            options.append(param)

    return positionals, flags, options, kwargs


def isiterable(param, T):
    if param.kind == param.VAR_POSITIONAL:
        return True
    try:
        return issubclass(T, t.Iterable) \
            and not issubclass(T, (str, t.Mapping))
    except TypeError:
        return isinstance(param.default, t.Iterable) \
            and not isinstance(param.default, (str, t.Mapping))


def ismapping(param, T):
    try:
        return issubclass(T, t.Mapping)
    except TypeError:
        return isinstance(param.default, t.Mapping)


def add_arg(parser, name, param, kwargs):
    T = None if param.annotation is param.empty else param.annotation
    if isiterable(param, T):
        kwargs['nargs'] = '*'

    elif T is object or ismapping(param, T):
        kwargs['type'] = json.loads

    elif hasattr(T, '__origin__') and issubclass(T.__origin__, t.Iterable):
            kwargs['nargs'] = '*'
            if not isinstance(T.__args__[0], t.TypeVar):
                kwargs['type'] = T.__args__[0]

    else:
        kwargs['type'] = T or \
            (
                None if param.default is param.empty or param.default is None
                else type(param.default)
            )

    parser.add_argument(name.replace('_', '-'), **kwargs)


def mkpositional(params, parser):
    for param in params:
        add_arg(parser, param.name, param, {})


def mkflags(params, parser):
    for param in params:
        kwargs = {'action': 'store_true'}
        name = '--'
        if param.default is True:
            name += 'no-'
            kwargs['action'] = 'store_false'
        name += param.name
        parser.add_argument(name.replace('_', '-'), **kwargs)


def mkoptions(params, parser):
    for param in params:
        add_arg(parser, '--' + param.name, param, {'default': param.default})


def script(func=None, shortflags=None, **kwargs):
    if func is None:
        return functools.partial(script, shortflags, **kwargs)

    sig = inspect.signature(func)
    positionals, flags, options, kw = sort_params(sig.parameters.values())
    parser = argparse.ArgumentParser(
        description=func.__doc__,
        **kwargs
    )
    mkpositional(positionals, parser)
    mkflags(flags, parser)
    mkoptions(options, parser)

    def run(*args, **kwargs):
        """run as cli script. *args and **kwargs are pased to
        ArgumentParser.parse_args
        """
        args = parser.parse_args(*args, **kwargs)
        args = vars(args)
        pargs = []
        for param in positionals:
            if param.kind == param.VAR_POSITIONAL:
                pargs.extend(args.pop(param.name))
            elif param.kind == param.POSITIONAL_OR_KEYWORD:
                pargs.append(args.pop(param.name))

        for key, value in args.items():
            if key.startswith('no_'):
                args[key[3:]] = args.pop(key)
                continue
        
        out = func(*pargs, **args)

        if isinstance(out, t.Iterable) and not isinstance(out, str):
            print(*out, sep='\n')
        elif out is not None:
            print(out)


    func.run = run
    
    return func
