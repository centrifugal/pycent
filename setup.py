import os
import sys
from setuptools import setup


if sys.argv[-1] == 'test':
    status = os.system('python tests/tests.py')
    sys.exit(1 if status > 127 else status)


requirements = ['six>=1.3.0']
if sys.version_info[:2] in ((2, 6),):
    # argparse has been added in Python 3.2 / 2.7
    requirements.append('argparse>=1.2.1')


def long_description():
    return "python tools to communicate with Centrifuge"


setup(
    name='cent',
    version='0.0.9',
    description="python tools to communicate with Centrifuge",
    long_description=long_description(),
    url='https://github.com/FZambia/cent',
    download_url='https://github.com/FZambia/cent',
    author="Alexandr Emelin",
    author_email='frvzmb@gmail.com',
    license='http://www.apache.org/licenses/LICENSE-2.0',
    packages=['cent'],
    entry_points={
        'console_scripts': [
            'cent = cent.console:run',
        ],
    },
    install_requires=requirements,
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2.6',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3.3',
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
