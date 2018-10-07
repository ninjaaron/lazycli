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


def add_arg(parser, name, param, kwargs):
    T = None if param.annotation is param.empty else param.annotation
    if param.kind == param.VAR_POSITIONAL or T is list:
        kwargs['nargs'] = '*'

    if T is None:
        pass
    elif hasattr(T, '_name'):
        if T._name in {'List', 'Iterable'}:
            kwargs['nargs'] = '*'
            if not isinstance(T.__args__[0], t.TypeVar):
                kwargs['type'] = T.__args__[0]

    elif T is object:
        kwargs['type'] = json.loads

    else:
        kwargs['type'] = T

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


def script(func):
    sig = inspect.signature(func)
    positionals, flags, options, kwargs = sort_params(sig.parameters.values())
    parser = argparse.ArgumentParser(description=func.__doc__)
    mkpositional(positionals, parser)
    mkflags(flags, parser)
    mkoptions(options, parser)

    @functools.wraps(parser.parse_args)
    def parse_args(*args, **kwargs):
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


    func.parse_args = parse_args
    
    return func


@script
def afunc(ham, *eggs, foo, bar='', baz:int=None, good_times=True):
    return ham, eggs, foo, bar, baz, good_times


afunc.parse_args()
