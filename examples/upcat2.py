#!/usr/bin/env python3
import sys
from lazycli import script, ReadFile


@script
def upcat(
        infile: ReadFile  = sys.stdin,
        outfile: lambda f: open(f, 'w') = sys.stdout
):
    """cat, but upper-cases everything."""
    for line in infile:
        outfile.write(line.upper())


if __name__ == '__main__':
    upcat.run()
