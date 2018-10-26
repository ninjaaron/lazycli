# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
import argparse
import collections
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


ArgType = collections.namedtuple('ArgType', 'iterable, constructor')


def real_type(T):
    if T is object or issubclass(T, t.Mapping):
        return ArgType(False, json.loads)

    if issubclass(T, (io.IOBase, str)):
        return ArgType(False, T)

    if issubclass(T, t.Sequence):
        return ArgType(True, None)

    return ArgType(False, T)


def typing_type(T):
    iterable, _ = real_type(T.__origin__)
    if iterable:
        try:
            subscript = T.__args__[0]
            _, constructor = real_type(subscript)
            return ArgType(True, constructor)
        except IndexError:
            return ArgType(True, None)

    return ArgType(False, None)


def annotation_type(annotation):
    if inspect.isfunction(annotation) or inspect.isbuiltin(annotation):
        return ArgType(False, annotation)
    if isinstance(annotation, type):
        return real_type(annotation)
    return typing_type(annotation)


def varargs_type(param):
    if param.annotation is param.empty:
        return ArgType(True, None)

    _, constructor = annotation_type(param.annotation)
    return ArgType(True, constructor)


def default_type(default):
    iterable, constructor = real_type(type(default))
    if iterable:
        try:
            _, constructor = real_type(type(default[0]))
        except IndexError:
            pass
    return ArgType(iterable, constructor)


def infer_type(param, positional=False):
    if param.kind is param.VAR_POSITIONAL:
        return varargs_type(param)

    if param.annotation is not param.empty:
        return annotation_type(param.annotation)

    if positional:
        return ArgType(False, None)

    return default_type(param.default)


def add_arg(parser, name, param, kwargs, shortflag=None, positional=True):
    iterable, constructor = infer_type(param, positional)
    if iterable:
        kwargs['nargs'] = '*'
    if constructor:
        kwargs['type'] = constructor
        tname = 'json' if constructor == json.loads else constructor.__name__
        kwargs['help'] = 'type: ' + tname

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
        add_arg(parser, param.name, param, {}, positional=True)


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


def script(func):
    def run(*args, **kwargs):
        """run as cli script. *args and **kwargs are pased to
        ArgumentParser.parse_args
        """
        # build the parser from signature
        sig = inspect.signature(func)
        positionals, flags, options = sort_params(sig.parameters.values())
        parser = argparse.ArgumentParser(description=func.__doc__, **kwargs)
        mkpositional(positionals, parser)
        mkflags(flags, parser)
        mkoptions(options, parser)

        # parse into a dictionary
        args = vars(parser.parse_args(*args, **kwargs))

        # map args back onto the signature.
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
