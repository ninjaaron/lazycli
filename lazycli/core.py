# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
import argparse
import json
import inspect
import io
import libaaron
import functools
import typing as t


# fake types
Iter = t.Iterable
PositionalParams = Iter[inspect.Parameter]
FlagsParams = Iter[t.Tuple[inspect.Parameter, t.Optional[str]]]
OptionParams = FlagsParams
Parser = argparse.ArgumentParser
HelpDict = t.Dict[str, str]


class FileBase(io.TextIOBase):
    """Children of this class really just pass the arguments from their
    constructor to `open`. There are no real instances of the the classes.
    the mode argument is determined in the child.
    """
    mode = ''

    def __new__(cls, filename: str):
        return open(filename, cls.mode)


class ReadFile(FileBase):
    """opens a file in text mode for reading"""
    mode = 'r'


class WriteFile(FileBase):
    """opens a file in text mode for writing (truncates)"""
    mode = 'w'


class AppendFile(FileBase):
    """opens a file in text mode for writing (appends)"""
    mode = 'a'


def getshortflag(char: str, shortflags: t.Set[str]) -> t.Optional[str]:
    """Check if a character has alread used as a short flag. If so, uppercase
    it, otherwise return the character. If the uppercase character is also
    used, return None. No shortflag is generated.

    char -- the character to use

    shortflags -- a set of flags already used. This function updates the set,
                  so usage should be like this:

    >>> used = set()
    >>> for char in 'abccdce':
    ...     flag = getshortflag(char, used)
    ...     # etc
    """
    if char in shortflags:
        char = char.upper()
        if char in shortflags:
            return None

    shortflags.add(char)
    return char


def sort_params(params: Iter[inspect.Parameter]) -> (
        t.Tuple[PositionalParams, FlagsParams, OptionParams]):
    positionals = []
    flags = []
    options = []
    shortflags: t.Set[str] = set()
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


class ArgType(t.NamedTuple):
    iterable: bool
    constructor: t.Optional[t.Callable[[str], t.Any]]


def real_type(T: t.Type) -> ArgType:
    """determine argument type from a concrete python type"""
    if T is object or issubclass(T, t.Mapping):
        return ArgType(False, json.loads)

    if issubclass(T, (io.IOBase, str)):
        return ArgType(False, T)

    if issubclass(T, t.Sequence):
        return ArgType(True, None)

    return ArgType(False, T)


def typing_type(T: t.Type) -> ArgType:
    """determine argument type from a type that is from the `typing` modlue"""
    iterable, _ = real_type(T.__origin__)
    if iterable:
        try:
            subscript = T.__args__[0]
            _, constructor = real_type(subscript)
            return ArgType(True, constructor)
        except IndexError:
            return ArgType(True, None)

    return ArgType(False, None)


def annotation_type(annotation: t.Type) -> ArgType:
    """determine argument type from type in annotation"""
    if inspect.isfunction(annotation) or inspect.isbuiltin(annotation):
        return ArgType(False, annotation)
    if isinstance(annotation, t.GenericMeta):
        return typing_type(annotation)
    if isinstance(annotation, t.Type):
        return real_type(annotation)
    return ArgType(False, None)


def varargs_type(param: inspect.Parameter) -> ArgType:
    """determine argument type for variadic positional parameter"""
    if param.annotation is param.empty:
        return ArgType(True, None)

    _, constructor = annotation_type(param.annotation)
    return ArgType(True, constructor)


def default_type(default) -> ArgType:
    """infer the type from the default argument"""
    if default is None:
        return ArgType(False, None)
    iterable, constructor = real_type(type(default))
    if iterable:
        try:
            _, constructor = real_type(type(default[0]))
        except IndexError:
            pass
    return ArgType(iterable, constructor)


def infer_type(param: inspect.Parameter, positional: bool = False) -> ArgType:
    """determine argument type from a function parameter"""
    if param.kind is param.VAR_POSITIONAL:
        return varargs_type(param)

    if param.annotation is not param.empty:
        return annotation_type(param.annotation)

    if positional:
        return ArgType(False, None)

    return default_type(param.default)


def add_arg(
        parser: Parser,
        name: str,
        param: inspect.Parameter,
        kwargs,
        help: HelpDict,
        shortflag: str = None,
        positional: bool = False
):
    """add an argument to the parser with the given name. additional info is
    derived from the function parameter. kwargs is a dictionary of keyword
    arguments that will be passed to add_arg. This dictionary will be mutated.
    """
    try:
        kwargs["help"] = help[name]
    except KeyError:
        pass

    iterable, constructor = infer_type(param, positional)
    if iterable:
        kwargs['nargs'] = '*'
    if constructor:
        kwargs['type'] = constructor
        tname = 'json' if constructor == json.loads else constructor.__name__
        tstring = 'type: ' + tname
        try:
            kwargs['help'] += '; ' + tstring
        except KeyError:
            kwargs['help'] = tstring

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


def mkpositional(params: PositionalParams, parser: Parser, help: HelpDict):
    """add positional parameters to the parser"""
    for param in params:
        add_arg(parser, param.name, param, {}, help, positional=True)


def mkflags(params: FlagsParams, parser: Parser, help: HelpDict):
    """add flags to the parser"""
    for param, shortflag in params:
        kwargs = {'action': 'store_true'}
        name = '--'
        if param.default and param.default is not param.empty:
            name += 'no-'
            kwargs['action'] = 'store_false'
        name += param.name
        try:
            kwargs['help'] = help[name]
        except KeyError:
            pass
        if shortflag:
            parser.add_argument(  # type: ignore
                '-' + shortflag, name.replace('_', '-'), **kwargs)
        else:
            parser.add_argument(  # type: ignore
                name.replace('_', '-'), **kwargs)


def mkoptions(params: OptionParams, parser: Parser, help: HelpDict):
    """add optional params to the parser"""
    for param, shortflag in params:
        add_arg(
            parser,
            '--' + param.name,
            param,
            {'default': param.default},
            help,
            shortflag,
        )


class Script:
    def __init__(
            self,
            function: t.Callable = None,
            parser: type = Parser,
            help: HelpDict = None,
    ):
        """make a parser for a script.
        """
        self.function = function
        self.parsertype = parser
        self.help = help or {}
        self.positionals = []
        self.flags = []
        self.options = []

    @libaaron.reify
    def parser(self) -> Parser:
        """returns the argparse.ArgumentParser for the instance"""
        if not self.function:
            return self.parsertype()
        sig = inspect.signature(self.function)
        self.positionals, self.flags, self.options = sort_params(
            sig.parameters.values())
        parser = self.parsertype(description=self.function.__doc__)
        mkpositional(self.positionals, parser, self.help)
        mkflags(self.flags, parser, self.help)
        mkoptions(self.options, parser, self.help)
        return parser

    @property
    def params(self) -> t.Iterator[inspect.Parameter]:
        """iterate over all parameters"""
        yield from self.positionals
        yield from (i[0] for i in self.flags)
        yield from (i[0] for i in self.options)

    @libaaron.reify
    def subparsers(self) -> Parser:
        """get a subparser for the instance"""
        return self.parser.add_subparsers()

    def run(self, *args, iterprint=False, **kwargs):
        """run the generated cli script. *args and **kwargs are passed to
        argparse.ArgumentParser.parse_args
        """
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

            if isinstance(out, Iter) and not isinstance(out, (str, t.Mapping)):
                if iterprint:
                    for line in out:
                        print(line)
                else:
                    print(*out, sep='\n')
            elif out is not None:
                print(out)

    def _func(self, args: t.MutableMapping):
        # map args back onto the signature.
        pargs = []  # type: t.List[t.Any]
        for param in self.positionals:
            if param.kind == param.VAR_POSITIONAL:
                pargs.extend(args.pop(param.name))
            elif param.kind == param.POSITIONAL_OR_KEYWORD:
                pargs.append(args.pop(param.name))

        for key, value in args.items():
            if key.startswith('no_'):
                args[key[3:]] = args.pop(key)
                continue

        return (self.function or (lambda: None))(*pargs, **args)

    def subcommand(
            self, func: t.Callable = None, help: HelpDict = None
    ) -> t.Callable:
        if not func:
            return functools.partial(self.subcommand, help=help)

        subparser = functools.partial(
            self.subparsers.add_parser, func.__name__
        )
        subscript = Script(func, subparser)
        subscript.parser.set_defaults(_func=subscript._func)
        return func


def script(func: t.Callable = None, help: HelpDict = None):
    if not func:
        return functools.partial(script, help=help)

    scrpt = Script(func, help=help)
    func.run = scrpt.run
    func.subcommand = scrpt.subcommand
    func._script = scrpt
    return func
