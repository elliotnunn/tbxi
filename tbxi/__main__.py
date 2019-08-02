# Thanks to Chris Warrick for script installation tips
# https://chriswarrick.com/blog/2014/09/15/python-apps-the-right-way-entry_points-and-scripts/

import argparse
import sys
import os
from os import path
import shutil
import macresources

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
        the result should be identical to the original. A NewWorld
        bootinfo file can be BinHex-encoded ('.hqx'), or have a '.idump'
        file created alongside.'''
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

            base, ext = path.splitext(args.file)
            if ext.lower() == '.hqx':
                import binhex
                hb = binhex.HexBin(f)
                data = hb.read()
                rsrc = list(macresources.parse_file(hb.read_rsrc()))

            else:
                data = f.read()
                rsrc = []

                if not rsrc:
                    try:
                        with open(args.file + '.rdump', 'rb') as f:
                            rsrc = list(macresources.parse_rez_code(f.read()))
                    except FileNotFoundError:
                        pass

                if not rsrc:
                    try:
                        with open(args.file + '/..namedfork/rsrc', 'rb') as f:
                            rsrc = list(macresources.parse_file(f.read()))
                    except FileNotFoundError:
                        pass

            tpl = (data, rsrc)

            dispatcher.dump(tpl, args.output, toplevel=True)

    elif command == 'build':
        parser.add_argument('dir', metavar='<input-dir>', help='source directory')
        parser.add_argument('-o', dest='output', metavar='<output-file>', help='destination (default: Mac OS ROM)')
        args = parser.parse_args(args)

        if not args.output: args.output = 'Mac OS ROM'

        data = dispatcher.build(args.dir)

        if isinstance(data, tuple):
            data, rsrc = data # unpack the resource list from the data fork
            base, ext = path.splitext(args.output)
            if ext.lower() == '.hqx':
                import binhex

                finfo = binhex.FInfo()
                finfo.Creator = b'chrp'
                finfo.Type = b'tbxi'
                finfo.Flags = 0

                # Special-casing for no-resource-fork
                rsrc = macresources.make_file(rsrc) if rsrc else b''

                bh = binhex.BinHex(('Mac OS ROM', finfo, len(data), len(rsrc)), args.output)
                bh.write(data)
                bh.write_rsrc(rsrc)
                bh.close()

                return # do not write the usual way

            else:
                rsrc = macresources.make_rez_code(rsrc, ascii_clean=True)

                # Special-casing for no-resource-fork
                if rsrc:
                    with open(args.output + '.rdump', 'wb') as f:
                        f.write(rsrc)
                else:
                    try:
                        os.remove(args.output + '.rdump')
                    except FileNotFoundError:
                        pass

                with open(args.output + '.idump', 'wb') as f:
                    f.write(b'tbxichrp')

        with open(args.output, 'wb') as f:
            f.write(data)


if __name__ == "__main__":
    main()
