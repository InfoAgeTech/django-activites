from __future__ import unicode_literals

import os

from setuptools import find_packages
from setuptools import setup


classifiers = [
    'Environment :: Web Environment',
    'Framework :: Django',
    'Intended Audience :: Developers',
    'License :: OSI Approved :: MIT License',
    'Operating System :: OS Independent',
    'Programming Language :: Python',
    'Programming Language :: Python :: 3.3',
    'Programming Language :: Python :: 3.4',
    'Topic :: Internet :: WWW/HTTP',
    'Topic :: Internet :: WWW/HTTP :: Dynamic Content'
]

README = open(os.path.join(os.path.dirname(__file__), 'README.md')).read()

setup(
    name='django-activities',
    version='1.0.1-dev',
    description='Activities app for django',
    author='Troy Grosfield',
    maintainer='Troy Grosfield',
    url='https://github.com/infoagetech/django-activities',
    license='MIT',
    packages=find_packages(),
    include_package_data=True,
    zip_safe=False,
    setup_requires=[
        'django >= 1.7',
        'django-core >= 1.0'
    ],
    classifiers=classifiers
)
