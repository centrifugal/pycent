import os
import sys
from setuptools import setup


if sys.argv[-1] == 'test':
    status = os.system('python tests/tests.py')
    sys.exit(1 if status > 127 else status)


requirements = ['requests']


def long_description():
    return "Python library to communicate with Centrifugo v3 HTTP API"


setup(
    name='cent',
    version='4.0.0',
    description="Python library to communicate with Centrifugo v3 HTTP API",
    long_description=long_description(),
    url='https://github.com/centrifugal/cent',
    download_url='https://github.com/centrifugal/cent',
    author="Alexandr Emelin",
    author_email='frvzmb@gmail.com',
    license='MIT',
    packages=['cent'],
    entry_points={
        'console_scripts': [
            'cent = cent.console:run',
        ],
    },
    install_requires=requirements,
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Environment :: Console',
        'Intended Audience :: Developers',
        'Intended Audience :: System Administrators',
        'License :: OSI Approved :: Apache Software License',
        'Topic :: Internet :: WWW/HTTP',
        'Topic :: Software Development',
        'Topic :: System :: Networking',
        'Topic :: Terminals',
        'Topic :: Text Processing',
        'Topic :: Utilities'
    ]
)
