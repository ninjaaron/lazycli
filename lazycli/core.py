# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
import argparse
import functools
import json
import inspect
import io
import string
import typing as t
alpha = set(string.ascii_letters)


def getshortflag(char, shortflags):
    if char in shortflags:
        char = char.upper()
        if char in shortflags:
            return None

    shortflags.add(char)
    return char


def sort_params(params):
    positionals = []
    flags = []
    options = []
    shortflags = set()
    for param in params:
        if param.kind is param.VAR_KEYWORD:
            pass
        if param.annotation is bool or isinstance(param.default, bool):
            flags.append((param, getshortflag(param.name[0], shortflags)))
        elif param.default == param.empty:
            positionals.append(param)
        else:
            options.append((param, getshortflag(param.name[0], shortflags)))

    return positionals, flags, options


def isiterable(param, T):
    if param.kind == param.VAR_POSITIONAL:
        return True
    try:
        return issubclass(T, t.Iterable) \
            and not issubclass(T, (str, t.Mapping, io.IOBase))
    except (TypeError, AttributeError):
        return isinstance(param.default, t.Iterable) \
            and not isinstance(param.default, (str, t.Mapping, io.IOBase))


def ismapping(param, T):
    try:
        return issubclass(T, t.Mapping)
    except (TypeError, AttributeError):
        return isinstance(param.default, t.Mapping)


def add_arg(parser, name, param, kwargs, shortflag=None):
    T = None if param.annotation is param.empty else param.annotation
    if isiterable(param, T):
        kwargs['nargs'] = '*'
        if T:
            kwargs['type'] = T

    if T is object or ismapping(param, T):
        kwargs['type'] = json.loads
        kwargs.setdefault('help', 'json')

    elif hasattr(T, '__origin__') and issubclass(T.__origin__, t.Iterable):
        kwargs['nargs'] = '*'
        innerT = T.__args__[0]
        if not isinstance(innerT, t.TypeVar):
            if T is object or ismapping(param, T):
                kwargs['type'] = json.loads
                kwargs.setdefault('help', 'type: json')
            else:
                kwargs['type'] = innerT
    else:
        if T:
            kwargs['type'] = T
        elif not (param.default is param.empty or param.default is None):
            kwargs['type'] = type(param.default)

    if 'help' not in kwargs:
        try:
            _type = kwargs['type']
            if isinstance(_type, type):
                kwargs['help'] = str('type: ' + _type.__name__)
        except (KeyError, AttributeError):
            pass

    if param.default is not param.empty:
        defstr = 'default: %s' % getattr(param.default, 'name', param.default)
        try:
            kwargs['help'] += '; ' + defstr
        except KeyError:
            kwargs['help'] = defstr

    if shortflag:
        parser.add_argument('-' + shortflag, name.replace('_', '-'), **kwargs)
    else:
        parser.add_argument(name.replace('_', '-'), **kwargs)


def mkpositional(params, parser):
    for param in params:
        add_arg(parser, param.name, param, {})


def mkflags(params, parser):
    for param, shortflag in params:
        kwargs = {'action': 'store_true'}
        name = '--'
        if param.default and param.default is not param.empty:
            name += 'no-'
            kwargs['action'] = 'store_false'
        name += param.name
        if shortflag:
            parser.add_argument(
                '-' + shortflag, name.replace('_', '-'), **kwargs)
        else:
            parser.add_argument(name.replace('_', '-'), **kwargs)


def mkoptions(params, parser):
    for param, shortflag in params:
        add_arg(
            parser,
            '--' + param.name,
            param,
            {'default': param.default},
            shortflag
        )


def script(func=None, **kwargs):
    if func is None:
        return functools.partial(script, **kwargs)

    def run(*args, **kwargs):
        """run as cli script. *args and **kwargs are pased to
        ArgumentParser.parse_args
        """
        sig = inspect.signature(func)
        positionals, flags, options = sort_params(sig.parameters.values())
        parser = argparse.ArgumentParser(description=func.__doc__, **kwargs)
        mkpositional(positionals, parser)
        mkflags(flags, parser)
        mkoptions(options, parser)

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
        if isinstance(out, t.Iterable) and not isinstance(
                out, (str, t.Mapping)):
            print(*out, sep='\n')
        elif out is not None:
            print(out)

    func.run = run
    return func
