from setuptools import setup, Extension

from os import path
this_directory = path.abspath(path.dirname(__file__))
with open(path.join(this_directory, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()

setup_args = dict(
    name='tbxi',
    long_description=long_description,
    long_description_content_type='text/markdown',
    version='0.7',
    author='Elliot Nunn',
    author_email='elliotnunn@fastmail.com',
    description='Tools to compile and inspect Macintosh ROM images',
    url='https://github.com/elliotnunn/tbxi',
    classifiers=[
        'Programming Language :: Python :: 3 :: Only',
        'Programming Language :: C',
        'Operating System :: OS Independent',
        'Intended Audience :: Developers',
        'Topic :: Software Development :: Build Tools',
        'License :: OSI Approved :: MIT License',
    ],
    zip_safe=True,
    packages=['tbxi'],
    entry_points=dict(console_scripts=['tbxi = tbxi.__main__:main']),
    ext_modules=[Extension('tbxi.fast_lzss', ['speedups/fast_lzss.c'])],
)

# http://charlesleifer.com/blog/misadventures-in-python-packaging-optional-c-extensions/

# Yes, it might be a bit extreme to catch SystemExit to find a compiler error...

try:
    setup(**setup_args)
except (SystemExit, Exception):
    setup_args.pop('ext_modules')
    setup(**setup_args)
