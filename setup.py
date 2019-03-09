from setuptools import setup, Extension

setup_args = dict(
    name='tbxi',
    version='0.1',
    author='Elliot Nunn',
    author_email='elliotnunn@fastmail.com',
    description='Tools to compile and inspect Mac OS 8/9 NewWorld ROM images',
    url='https://github.com/elliotnunn/tbxi',
    classifiers=[
        'Programming Language :: Python :: Implementation :: CPython',
        'Programming Language :: C',
        'Operating System :: OS Independent',
        'Development Status :: 3 - Alpha',
    ],
    packages=['tbxi'],
    scripts=['bin/prclc', 'bin/prcldump'],
    ext_modules=[Extension('tbxi.fast_lzss', ['speedups/fast_lzss.c'])],
)

# http://charlesleifer.com/blog/misadventures-in-python-packaging-optional-c-extensions/

# Yes, it might be a bit extreme to catch SystemExit to find a compiler error...

try:
    setup(**setup_args)
except (SystemExit, Exception):
    setup_args.pop('ext_modules')
    setup(**setup_args)
else:
    exit()
