lazycli
=======
lazycli is a module which provides a decorator which will generate cli
scripts from function signatures. The intention is to allow the creation
of cli-scripts with as little extra work as possible. It was orinally
going to be called ``sig2cli``, but someone else already `had the same
idea`_ and got the name on PyPI in ten months before I did.

The one and only goal of lazycli is to facilitate the creation of CLI
interfaces with *minimum effort*.

lazycli wraps ``argparse`` from the Python standard library and exposes
some parts of the `argparse api`_. The abstraction it provides is a
little leaky, but it's not too bad, because it's relativey simple and is
not intended to provide the full range functionality. If you need
flexibility, use ``argparse`` directly or something more powerful like
click_.

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
- Parameters with boolean default values are treated as flags and don't
  accept additional arguments.
- A ``.run`` function is tacked on to the ``cp`` function which
  triggers argument parsing applies the results to ``cp``. ``cp`` itself
  is unaltered and can be called elsewhere if desired.

I'm not entirely sure how useful this last point is, since script
entry-point functions tend not to be very general-purpose, but, eh, who
knows.

Be aware that, presently, ``**kwargs``-style parameters are ignored
altogether by lazycli. This may change in the future if I decide to
work on sub-parsers. Honestly, the point of this module is to avoid
typing, and doing sub-parsers sounds like a lot of typing.
