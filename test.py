#!/usr/bin/env python3
import lazycli
import argparse


@lazycli.script
def main(arg, number=1, more:tuple=(max,)):
    print((arg, n, more))


if __name__ == '__main__':
    main.run()
