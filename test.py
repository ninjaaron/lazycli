#!/usr/bin/env python3
import sig2cli
import argparse


@sig2cli.script
def main(arg, n=1, more:tuple=(max,)):
    print((arg, n, more))


if __name__ == '__main__':
    main.run()
