import importlib

from subprocess import run, PIPE

import fnmatch
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


def strip_patch_name_ext(name):
    # We need to match patch filenames to other filenames using fnmatch,
    # but first we need to remove '.patch.sh' or '.patch' from the title

    # If it isn't a patch, return None

    for i in range(2):
        name, ext = path.splitext(name)
        if ext.lower() == '.patch': return name


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

    # Search the directory of the file for executable patches
    for sib in sorted(os.scandir(parent), key=lambda ent: ent.name):
        # Does the filename match?
        pattern = strip_patch_name_ext(sib.name)
        if pattern and fnmatch.fnmatch(name, pattern):
            # This is a bit unsafe, so prompt the user (to pipe in `yes`...)
            if input('Apply %s to %s? [y/N] ' % (sib.name, name)).lower().startswith('y'):
                # The script is told the original filename, but it should READ FROM STDIN!
                cmd = [sib.path, name]

                # Run the script as a unixy filter
                result = run(cmd, cwd=parent, input=data, stdout=PIPE)

                # Return 0 to apply stdout, 1 to nop, anything else to fail
                if result.returncode == 0:
                    data = result.stdout
                elif result.returncode == 1:
                    pass
                else:
                    result.check_returncode()

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
