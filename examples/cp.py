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
