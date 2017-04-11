import os
import sys
from setuptools import setup


if sys.argv[-1] == 'test':
    status = os.system('python tests/tests.py')
    sys.exit(1 if status > 127 else status)


requirements = ['requests', 'urllib3']
if sys.version_info[:2] in ((2, 6),):
    requirements.append('argparse>=1.2.1')


def long_description():
    return "python tools to communicate with Centrifugo"


setup(
    name='cent',
    version='2.0.2',
    description="python tools to communicate with Centrifugo",
    long_description=long_description(),
    url='https://github.com/leopeng1995/cent',
    download_url='https://github.com/leopeng1995/cent',
    author="Alexandr Emelin, Leo Peng",
    author_email='frvzmb@gmail.com, leopeng1995@hotmail.com',
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
        'Programming Language :: Python :: 2.6',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
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
