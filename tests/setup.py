"""
Setup configuration for FMS tests

This allows tests to be run with pytest from the project root.
"""

from setuptools import setup

setup(
    name='fms_tests',
    version='0.1.0',
    description='Test suite for Kitchmatics Fleet Management System',
    packages=['tests'],
    python_requires='>=3.8',
    install_requires=[
        'pytest>=7.0',
        'pytest-cov>=4.0',
    ],
)
