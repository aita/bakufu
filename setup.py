from setuptools import setup
from bakufu import __version__


install_requires = [
    'psutil',
    'tornado>=4.0',
]

setup(
    name='bakufu',
    version=__version__,
    description=("Bakufu is a manager of multiple processes and sockets."),
    # long_description=README,
    # author="",
    # author_email="",
    include_package_data=True,
    zip_safe=False,
    # classifiers=[
    #       "Programming Language :: Python",
    #       "Programming Language :: Python :: 3.2",
    #       "Programming Language :: Python :: 3.3",
    #       "License :: OSI Approved :: Apache Software License"
    # ],
    install_requires=install_requires,
    test_suite='bakufu.tests',
    entry_points={
        'console_scripts':[
            'bakufud = bakufu.bakufud:main',
        ],
    },    
)