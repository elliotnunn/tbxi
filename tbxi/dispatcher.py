import importlib

from subprocess import run, PIPE

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


def build_path(p):
    parent = path.dirname(path.abspath(p))
    name = path.basename(path.abspath(p))

    # try building the file from a directory
    for np in [p + '.src', p]:
        try:
            data = build_dir(p)
        except WrongFormat:
            pass
        else:
            break
    else:
        # fall back on just reading the file (boring, I know!)
        with open(p, 'rb') as f:
            data = f.read()

    # Search the directory of the file for executable patches
    for sib in sorted(os.scandir(parent), key=lambda ent: ent.name):
        # Does the filename match?
        if sib.name.startswith(name) and 'patch' in sib.name[len(name):]:
            # This is a bit unsafe, so prompt the user (to pipe in `yes`...)
            if input('Apply %s to %s? [y/N]' % (sib.name, name)).lower().startswith('y'):
                result = run([sib.path], cwd=parent, stdin=data, stdout=PIPE, check=True)
                data = result.stdout

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
            did_dump = True
            break
        except WrongFormat:
            pass
