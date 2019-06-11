from setuptools import setup, Extension

setup_args = dict(
    name='tbxi',
    version='0.6',
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
