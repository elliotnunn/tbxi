import importlib

import os
from os import path


FORMATS = '''
    bootinfo
    parcels
    powerpc
    supermario
'''.split()


class WrongFormat(Exception):
    pass


def build_dir(p):
    for fmt in FORMATS:
        mod = importlib.import_module('..%s_build' % fmt, __name__)
        try:
            data = mod.build(p)
        except WrongFormat:
            continue

        print(fmt)
        return data

    raise WrongFormat


def build(p):
    parent = path.dirname(path.abspath(p))
    name = path.basename(path.abspath(p))

    # try building the file from a directory
    for np in [p + '.src', p]:
        try:
            data = build_dir(np)
        except WrongFormat:
            pass
        else:
            break
    else:
        # fall back on just reading the file (boring, I know!)
        with open(p, 'rb') as f:
            data = f.read()

    return data


def dump(binary, dest_path, toplevel=False):
    if not toplevel:
        with open(dest_path, 'wb') as f:
            f.write(binary)

        dest_path += '.src'

    for fmt in FORMATS:
        mod = importlib.import_module('..%s_dump' % fmt, __name__)
        try:
            mod.dump(binary, dest_path)
            print(fmt)
            break
        except WrongFormat:
            pass
