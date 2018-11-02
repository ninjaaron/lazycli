# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
import argparse
import collections
import json
import inspect
import io
import libaaron
import functools
from typing import Sequence, Mapping, Iterable


class FileMeta(type):
    def __subclasscheck__(self, subclass):
        return issubclass(subclass, io.TextIOBase)

    def __instancecheck__(self, instance):
        return isinstance(instance, io.TextIOBase)


class FileBase(metaclass=FileMeta):
    def __new__(cls, filename):
        return open(filename, cls.mode)


class ReadFile(FileBase):
    mode = 'r'


class WriteFile(FileBase):
    mode = 'w'


class AppendFile(FileBase):
    mode = 'a'


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
        elif param.annotation is bool or isinstance(param.default, bool):
            flags.append((param, getshortflag(param.name[0], shortflags)))
        elif param.default == param.empty:
            positionals.append(param)
        else:
            options.append((param, getshortflag(param.name[0], shortflags)))

    return positionals, flags, options


ArgType = collections.namedtuple('ArgType', 'iterable, constructor')


def real_type(T):
    if T is object or issubclass(T, Mapping):
        return ArgType(False, json.loads)

    if issubclass(T, (io.IOBase, str)):
        return ArgType(False, T)

    if issubclass(T, Sequence):
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
    if default is None:
        return ArgType(False, None)
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


class Script:
    def __init__(self, function=None, parser=argparse.ArgumentParser):
        """make a parser for a script.
        """
        self.function = function
        self.parsertype = parser

    @libaaron.reify
    def parser(self):
        if not self.function:
            return self.parsertype()
        sig = inspect.signature(self.function)
        self.positionals, self.flags, self.options = sort_params(
            sig.parameters.values())
        parser = self.parsertype(description=self.function.__doc__)
        mkpositional(self.positionals, parser)
        mkflags(self.flags, parser)
        mkoptions(self.options, parser)
        return parser

    @property
    def params(self):
        yield from self.positionals
        yield from (i[0] for i in self.flags)
        yield from (i[0] for i in self.options)

    @libaaron.reify
    def subparsers(self):
        return self.parser.add_subparsers()

    def run(self, *args, **kwargs):
        args = {
            k.replace('-', '_'): v for k, v in
            vars(self.parser.parse_args(*args, **kwargs)).items()
        }
        delegate = args.pop('_func', None)
        if delegate:
            top_args = {p.name: args.pop(p.name) for p in self.params}
        else:
            top_args = args
        funcs = [(self._func, top_args)] if self.function else []

        if delegate:
            funcs.append((delegate, args))

        for func, args in funcs:
            out = func(args)

            if isinstance(out, Iterable) and not isinstance(
                    out, (str, Mapping)):
                print(*out, sep='\n')
            elif out is not None:
                print(out)

    def _func(self, args):
        # map args back onto the signature.
        pargs = []
        for param in self.positionals:
            if param.kind == param.VAR_POSITIONAL:
                pargs.extend(args.pop(param.name))
            elif param.kind == param.POSITIONAL_OR_KEYWORD:
                pargs.append(args.pop(param.name))

        for key, value in args.items():
            if key.startswith('no_'):
                args[key[3:]] = args.pop(key)
                continue

        return self.function(*pargs, **args)

    def subcommand(self, func):
        subparser = functools.partial(
            self.subparsers.add_parser, func.__name__)
        subscript = Script(func, subparser)
        subscript.parser.set_defaults(_func=subscript._func)
        return func


def script(func=None):
    scrpt = Script(func)
    if func:
        func.run = scrpt.run
        func.subcommand = scrpt.subcommand
        func._script = scrpt
        return func
    return scrpt
