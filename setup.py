#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import re
from io import open

from setuptools import setup


try:
    from pypandoc import convert

    def read_md(f):
        return convert(f, 'rst')
except ImportError:
    print("warning: pypandoc module not found,"
          " could not convert Markdown to RST")

    def read_md(f):
        return open(f, 'r', encoding='utf-8').read()


def get_version(package):
    """
    Return package version as listed in `__version__` in `init.py`.
    """
    init_py = open(os.path.join(package, '__init__.py')).read()
    return re.search("__version__ = ['\"]([^'\"]+)['\"]", init_py).group(1)

version = get_version('drf_writable_nested')


setup(
    name='drf-writable-nested',
    version=version,
    url='http://github.com/beda-software/drf-writable-nested',
    license='BSD',
    description=(
        'Writable nested helpers for django-rest-framework\'s serializers'),
    long_description=read_md('README.md'),
    keywords=('drf restframework rest_framework django_rest_framework'
              ' serializers drf_writable_nested'),
    author='beda.software',
    author_email='drfwritablenested@beda.software',
    packages=['drf_writable_nested'],
    zip_safe=False,
    classifiers=[
        'Development Status :: 4 - Beta',
        'Environment :: Web Environment',
        'Framework :: Django',
        'Framework :: Django :: 1.8',
        'Framework :: Django :: 1.9',
        'Framework :: Django :: 1.10',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Topic :: Internet :: WWW/HTTP',
    ]
)
