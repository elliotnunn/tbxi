# Thanks to Chris Warrick for script installation tips
# https://chriswarrick.com/blog/2014/09/15/python-apps-the-right-way-entry_points-and-scripts/

import argparse
import sys
import os
from os import path
import shutil

from .slow_lzss import decompress

from . import dispatcher


def main(args=None):
    if args is None: args = sys.argv[1:]

    descriptions = {
        'dump': '''Break a ROM file into rebuildable parts. Any ROM
        released since the 660AV/840AV ("SuperMario") can be processed,
        including NewWorld ROMs. Because successive ROM formats tended
        to wrap layers around old ones, the image is dumped
        recursively.''',
        'build': '''Recreate a dumped ROM file. With minor exceptions,
        the result should be identical to the original.'''
    }

    for key in list(descriptions):
        descriptions[key] = ' '.join(descriptions[key].split())

    if not args or args[0] not in descriptions:
        print('usage: tbxi <command> [...]')
        print()
        print('The Mac OS Toolbox Imager')
        print()
        print('commands:')
        for k, v in descriptions.items():
            print('  ' + k.ljust(8) + ' ' + v.partition('.')[0])
        exit(1)

    command = args.pop(0)
    parser = argparse.ArgumentParser(prog='tbxi ' + command, description=descriptions[command])

    if command == 'dump':
        parser.add_argument('file', metavar='<input-file>', help='original file')
        parser.add_argument('-o', dest='output', metavar='<output-file>', help='destination (default: <input-file>.src)')
        args = parser.parse_args(args)

        if not args.output: args.output = args.file + '.src'

        with open(args.file, 'rb') as f:
            try:
                shutil.rmtree(args.output)
            except FileNotFoundError:
                pass

            dispatcher.dump(f.read(), args.output, toplevel=True)

    elif command == 'build':
        parser.add_argument('dir', metavar='<input-dir>', help='source directory')
        parser.add_argument('-o', dest='output', metavar='<output-file>', help='destination (default: <input-dir>.build)')
        args = parser.parse_args(args)

        with open(args.output, 'wb') as f:
            f.write(dispatcher.build(args.dir))


if __name__ == "__main__":
    main()
