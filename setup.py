#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import re
from io import open

from setuptools import setup


def get_version(package):
    """
    Return package version as listed in `__version__` in `init.py`.
    """
    init_py = open(os.path.join(package, '__init__.py')).read()
    return re.search("__version__ = ['\"]([^'\"]+)['\"]", init_py).group(1)

version = get_version('drf_writeable_nested')

with open('README.md', encoding='utf-8') as f:
      long_description = f.read()

setup(
    name='drf_writeable_nested',
    version=version,
    url='http://github.com/Brogency/drf-writeable-nested',
    license='BSD',
    description=(
        'Writeable nested helpers for django-rest-framework\'s serializers'),
    long_description=long_description,
    keywords=('drf restframework rest_framework django_rest_framework'
              ' serializers drf_writeable_nested'),
    author='Bro.engineering',
    author_email='drfwriteablenested@bro.engineering',
    packages=['drf_writeable_nested'],
    zip_safe=False,
    classifiers=[
        'Development Status :: Development Status :: 4 - Beta',
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
