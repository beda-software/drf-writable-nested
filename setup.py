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


version = get_version('drf_writable_nested')
with open('README.md') as f:
    long_description = f.read()


setup(
    name='drf-writable-nested',
    version=version,
    url='http://github.com/beda-software/drf-writable-nested',
    license='BSD',
    description=(
        'Writable nested helpers for django-rest-framework\'s serializers'),
    long_description=long_description,
    long_description_content_type='text/markdown',
    keywords=('drf restframework rest_framework django_rest_framework'
              ' serializers drf_writable_nested'),
    author='beda.software',
    author_email='drfwritablenested@beda.software',
    packages=['drf_writable_nested'],
    zip_safe=False,
    python_requires='>=3.5',
    classifiers=[
        'Development Status :: 4 - Beta',
        'Environment :: Web Environment',
        'Framework :: Django',
        'Framework :: Django :: 2.2',
        'Framework :: Django :: 3.0',
        'Framework :: Django :: 3.1',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3 :: Only',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Topic :: Internet :: WWW/HTTP',
    ]
)
