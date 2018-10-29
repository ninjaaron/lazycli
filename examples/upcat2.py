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
