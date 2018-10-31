lazycli
=======
lazycli is a module which provides a decorator which will generate cli
scripts from function signatures. The intention is to allow the creation
of cli-scripts with as little extra work as possible. It was originally
going to be called ``sig2cli``, but someone else already `had the same
idea`_ and got the name on PyPI in ten months before I did.

The one and only goal of lazycli is to facilitate the creation of CLI
interfaces with *minimum effort*.

lazycli wraps ``argparse`` from the Python standard library and exposes
some parts of the `argparse api`_. The abstraction it provides is a
little leaky, but it's not too bad, because it's relatively simple and
is not intended to provide the full range functionality. If you need
flexibility, use ``argparse`` directly or something more powerful like
click_.

.. _had the same idea: https://github.com/PaoloSarti/sig2cli
.. _argparse api: https://docs.python.org/3/library/argparse.html
.. _click: https://click.palletsprojects.com/

.. contents::

Basics
------
Consider this simple clone of the ``cp`` command, ``cp.py``:

.. code:: Python

  #!/usr/bin/env python3
  import lazycli
  import shutil
  import sys


  @lazycli.script
  def cp(*src, dst, recursive=False):
      """copy around files"""
      for path in src:
          try:
              shutil.copy2(path, dst)
          except IsADirectoryError as err:
              if recursive:
                  shutil.copytree(path, dst)
              else:
                  print(err, file=sys.stderr)


  if __name__ == '__main__':
      cp.run()

.. code:: sh

  $ ./cp.py -h
  usage: cp.py [-h] [-r] [src [src ...]] dst

  copy around files

  positional arguments:
    src
    dst

  optional arguments:
    -h, --help       show this help message and exit
    -r, --recursive

It works like you'd expect. I chose ``cp`` because shutil_ can do all
the heavy lifting, and the body of the function isn't important. The
important thing in this script are these three lines:

.. code:: python

  @lazycli.script
  def cp(*src, dst, recursive=False):

  # ... and ...

  cp.run()

- All parameters without defaults become positional arguments.
- All parameters with defaults become optional arguments.
- ``*args`` arguments will translate into variadic arguments at the
  command line as well. *There can always be zero of them.*
- Parameters with boolean default values are treated as boolean flags
  and don't accept arguments.
- Short versions of flags are generated automatically from the first
  letter of the parameter.
- A ``.run`` function is tacked on to the ``cp`` function which
  triggers argument parsing and applies the results to ``cp``. The
  ``cp`` function itself is unaltered and can be called elsewhere if
  desired.

I'm not entirely sure how useful this last point is, since script
entry-point functions tend not to be very general-purpose, but, eh, who
knows.

Be aware that, presently, ``**kwargs``-style parameters are ignored
by lazycli.

**Note on short flags:**
  Short flags are generated for optional arguments based on the first
  letter of parameter names. If that flag has been used by a previous
  parameter, the flag will be uppercased. If that has already been used,
  no short flag is generated. Because of this, changing the order of
  arguments can potentially break the backward compatibility of your
  CLI.

**Note on boolean defaults:**
  A boolean default set to ``False`` produces the output seen above. If
  we change the parameter default to ``recursive=True``, the name of the
  flag is inverted:

  .. code::

    optional arguments:
      -h, --help          show this help message and exit
      -r, --no-recursive

.. _shutil: https://docs.python.org/3/library/shutil.html

Types
-----
lazycli attempts to determine argument types based first on type
annotations in the function signature and then based on the type of the
default argument.

- If the type of parameter is an iterable (besides mappings, strings and
  files), it will become a variadic when interpreted. If it's a
  subscripted type from the typing_ module, like
  ``typing.Iterable[int]``, the subscript will be used as the type.
- If the type is determined to be a mapping or is annotated as
  ``object``, the argument should be a json literal (though it could
  theoretically be a string, number, array or object).

The inferred type is then used as a constructor to parse the argument
string. This means only constructors that can take strings as input may
be used.

.. code:: python

  #!/usr/bin/env python3
  import typing as t
  import lazycli

  @lazycli.script
  def mysum(numbers: t.List[float]):
      return sum(numbers)

  if __name__ == '__main__':
      mysum.run()


.. code:: sh

  $ ./sum.py -h
  usage: sum.py [-h] [numbers [numbers ...]]

  positional arguments:
    numbers     type: float

  optional arguments:
    -h, --help  show this help message and exit

  $ ./sum.py 5 8
  13.0

Though the style is questionable, this means you can use arbitrary
callables as type annotations:

.. code:: python

  
  #!/usr/bin/env python3
  import sys
  import lazycli


  @lazycli.script
  def upcat(
          infile: open = sys.stdin,
          outfile: lambda f: open(f, 'w') = sys.stdout
  ):
      """cat, but upper-cases everything."""
      for line in infile:
          outfile.write(line.upper())


  if __name__ == '__main__':
      upcat.run()

.. code:: sh

  usage: upcat.py [-h] [-i INFILE] [-o OUTFILE]

  cat, but upper-cases everything.

  optional arguments:
    -h, --help            show this help message and exit
    -i INFILE, --infile INFILE
                          type: open; default: <stdin>
    -o OUTFILE, --outfile OUTFILE
                          type: <lambda>; default: <stdout>

This looks pretty bad, and mypy_ is going to hate it. A better way to
do this is probably just parsing the string inside the script.

However, because the pattern of having an optional file argument and
falling back to standard streams is so common, ``lazycli`` provides
special classes for making this less ugly:

.. code:: Python

  #!/usr/bin/env python3
  import sys
  from lazycli import script, ReadFile, WriteFile


  @script
  def upcat2(infile:ReadFile=sys.stdin, outfile:WriteFile=sys.stdout):
      """cat, but upper-cases everything."""
      for line in infile:
          outfile.write(line.upper())


  if __name__ == '__main__':
      upcat2.run()


These classes will provide users more helpful type information and will
return true if used in instance checks of text file types (including
``sys.{stdin,stdout,stderr}`` and non-bytes output of the ``open``
builtin function). These classes don't create instances of themselves,
but rather instances of ``io.TextIOWrapper``. However, they still break
mypy. Funny how metaclasses will do that.

.. _typing: https://docs.python.org/3/library/typing.html
.. _mypy: http://mypy-lang.org/

Output
------
So far, output has simply been printed. However, If the function has a
return value, that will also be printed. If it is an iterable (besides a
string or mapping), each item will be printed on a new line.

Subcommands
-----------
I'll expand this section of the documentation later, but here's a sample
script, modeled on info in this `blog post`_

.. code:: Python

  #!/usr/bin/env python3
  import lazycli


  @lazycli.script
  def script(version=False):
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

Notice that the subcommands have a ``**kwargs`` argument. This is to
catch any arguments set in the top-level command. The implementation of
of subcommands is still in development.

.. code:: shell

  $ ./test_sub.py -h
  usage: test_sub.py [-h] [-v] {hello,goodbye} ...

  positional arguments:
    {hello,goodbye}

  optional arguments:
    -h, --help       show this help message and exit
    -v, --version
  $
  $
  $ ./test_sub.py hello -h
  usage: test_sub.py hello [-h] [-c] [-g GREETING] name

  positional arguments:
    name

  optional arguments:
    -h, --help            show this help message and exit
    -c, --caps
    -g GREETING, --greeting GREETING
                          default: Hello

.. _blog post:
  https://realpython.com/comparing-python-command-line-parsing-libraries-argparse-docopt-click/
