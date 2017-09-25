from setuptools import setup

reqs = [line.strip() for line in open('requirements.txt')]

def readme():
    with open('README.md') as f:
        return f.read()

kwargs = {
    'name': 'gwc',
    'author': 'Micah Wengren',
    'author_email': 'micah.wengren@gmail.com',
    'url': 'https://github.com/mwengren/gwc',
    'description': 'Base python module to manage update of a GeoWebCache layer\'s time filter parameters for nowCOAST',
    'long_description': 'readme()',
    'entry_points': {
        'console_scripts': [
            'gwc=gwc.gwc:main',
        ]
    },
    'classifiers': [
        'Development Status :: 2 - Pre-Alpha',
        'Intended Audience :: Developers',
        'Intended Audience :: Science/Research',
        'License :: OSI Approved :: MIT License',
        'Operating System :: POSIX',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3.5',
        'Topic :: Scientific/Engineering',
        'Topic :: Scientific/Engineering :: GIS'
    ],
    'packages': ['gwc'],
    'package_data': {

    },
    'version': '0.1.0',
}

kwargs['install_requires'] = reqs

setup(**kwargs)
