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
