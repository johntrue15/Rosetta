# -*- coding: utf-8 -*-
"""
X-radia Metadata Extractor - Package Setup
==========================================

This setup.py provides package installation and configuration.

Installation Methods:
    1. Development install (recommended):
       pip install -e .
    
    2. Standard install:
       pip install .
    
    3. From requirements only:
       pip install -r requirements.txt

Note: XradiaPy must be installed separately via Xradia Software Suite.
"""

from __future__ import print_function
import os
import sys
from setuptools import setup, find_packages

# Get the directory containing setup.py
HERE = os.path.abspath(os.path.dirname(__file__))

# Read the README for long description
def read_readme():
    """Read README file for long description"""
    readme_path = os.path.join(HERE, 'Readme.md')
    if os.path.exists(readme_path):
        try:
            with open(readme_path, 'r') as f:
                return f.read()
        except Exception:
            pass
    return "X-radia Metadata Extractor - TXRM file metadata processing tool"

# Read requirements.txt
def read_requirements():
    """Read requirements from requirements.txt"""
    req_path = os.path.join(HERE, 'requirements.txt')
    requirements = []
    if os.path.exists(req_path):
        try:
            with open(req_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    # Skip comments and empty lines
                    if line and not line.startswith('#'):
                        # Remove inline comments
                        if '#' in line:
                            line = line.split('#')[0].strip()
                        if line:
                            requirements.append(line)
        except Exception:
            pass
    return requirements

# Package metadata
PACKAGE_NAME = "xradia_metadata_extractor"
VERSION = "1.0.0"
DESCRIPTION = "X-radia Metadata Extractor - Extract and process metadata from TXRM files"
AUTHOR = "X-radia Metadata Team"
AUTHOR_EMAIL = "your.email@example.com"
URL = "https://github.com/yourusername/X-radia-metadata"
LICENSE = "MIT"

# Python version check
PYTHON_REQUIRES = ">=2.7, <3"
if sys.version_info[0] >= 3:
    print("=" * 60)
    print("WARNING: This package requires Python 2.7 for XradiaPy compatibility.")
    print("You are currently using Python {0}.{1}".format(
        sys.version_info[0], sys.version_info[1]))
    print("XradiaPy features will not work with Python 3.x")
    print("=" * 60)

# Core dependencies (excluding XradiaPy which must be installed separately)
INSTALL_REQUIRES = [
    "numpy>=1.16.0,<1.17.0",      # Last version supporting Python 2.7
    "configparser>=3.5.0",         # Backport of Python 3 configparser
    "future>=0.18.0",              # Python 2/3 compatibility layer
    "six>=1.16.0",                 # Python 2/3 compatibility utilities
]

# Optional dependencies
EXTRAS_REQUIRE = {
    'github': [
        'requests>=2.20.0',        # For GitHub integration
    ],
    'dev': [
        'pylint==1.9.5',           # Last version supporting Python 2.7
        'pytest>=4.6.0,<5.0.0',    # Last version supporting Python 2.7
    ],
    'subprocess': [
        'subprocess32>=3.5.0',     # Backport of Python 3 subprocess
    ],
}

# All optional dependencies
EXTRAS_REQUIRE['all'] = sum(EXTRAS_REQUIRE.values(), [])

# Package classifiers
CLASSIFIERS = [
    "Development Status :: 4 - Beta",
    "Intended Audience :: Science/Research",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: MIT License",
    "Operating System :: OS Independent",
    "Programming Language :: Python :: 2",
    "Programming Language :: Python :: 2.7",
    "Topic :: Scientific/Engineering",
    "Topic :: Scientific/Engineering :: Image Processing",
    "Topic :: Utilities",
]

# Keywords for package discovery
KEYWORDS = [
    "txrm",
    "metadata",
    "xradia",
    "zeiss",
    "x-ray",
    "tomography",
    "ct",
    "image-processing",
]

# Entry points for command-line scripts
ENTRY_POINTS = {
    'console_scripts': [
        'xradia-metadata=new_enhanced_interactive.main:main',
        'xradia-check=system_check:main',
    ],
}

# Package data files to include
PACKAGE_DATA = {
    '': [
        'contacts.csv',
        'requirements.txt',
        '.env.example',
    ],
}

# Data files to install
DATA_FILES = [
    ('', ['contacts.csv', 'requirements.txt', '.env.example']),
]

# Setup configuration
setup(
    # Basic package information
    name=PACKAGE_NAME,
    version=VERSION,
    description=DESCRIPTION,
    long_description=read_readme(),
    long_description_content_type="text/markdown",
    
    # Author information
    author=AUTHOR,
    author_email=AUTHOR_EMAIL,
    url=URL,
    license=LICENSE,
    
    # Package discovery
    packages=find_packages(exclude=['tests', 'tests.*', 'scripts']),
    py_modules=['system_check', 'setup_wizard', 'main'],
    
    # Dependencies
    install_requires=INSTALL_REQUIRES,
    extras_require=EXTRAS_REQUIRE,
    python_requires=PYTHON_REQUIRES,
    
    # Entry points
    entry_points=ENTRY_POINTS,
    
    # Package data
    package_data=PACKAGE_DATA,
    include_package_data=True,
    
    # Metadata
    classifiers=CLASSIFIERS,
    keywords=KEYWORDS,
    
    # Options
    zip_safe=False,
)
