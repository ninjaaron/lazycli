#!/usr/bin/env python3
import lazycli
import argparse


@lazycli.script
def main(*args, arg, number=1, more:tuple=(max,)):
    return repr([args, arg, number, more])


if __name__ == '__main__':
    main.run()
