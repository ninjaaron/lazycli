#!/usr/bin/env python3
import typing as t
import lazycli

@lazycli.script(help={'numbers': "all the numbers you want to sum"})
def mysum(numbers: t.List[float]):
    return sum(numbers)

if __name__ == '__main__':
    mysum.run()
