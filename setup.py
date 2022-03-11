from setuptools import setup, find_packages


def readme():
    return open('README.md', 'r').read()


setup(
    name='discover-overlay',
    author='trigg',
    author_email='',
    version='0.4.5',
    description='Voice chat overlay',
    long_description=readme(),
    long_description_content_type='text/markdown',
    url='https://github.com/trigg/Discover',
    packages=find_packages(),
    include_package_data=True,
    data_files=[
        ('share/applications', [
            'discover_overlay.desktop'
        ]),
        ('share/icons/hicolor/256x256/apps', ['discover-overlay.png', 'discover-overlay-tray.png', 'discover-overlay-default.png']),
        ('share/icons/hicolor/scalable/apps', ['discover-overlay.svg', 'discover-overlay-tray.svg', 'discover-overlay-default.svg']),
        ('share/metainfo', [
            'discover_overlay.appdata.xml'
        ])
    ],
    install_requires=[
        'PyGObject>=3.22',
        'websocket-client',
        'pyxdg',
        'requests',
        'python-pidfile>=3.0.0',
        'pillow',
        'python-xlib',
    ],
    entry_points={
        'console_scripts': [
            'discover-overlay = discover_overlay.discover_overlay:entrypoint',
        ]
    },
    classifiers=[
        'Development Status :: 4 - Beta',
        'Environment :: X11 Applications :: GTK',
        'Intended Audience :: End Users/Desktop',
        'License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)',
        'Operating System :: POSIX :: Linux',
        'Programming Language :: Python :: 3 :: Only',
        'Topic :: Communications :: Chat',
        'Topic :: Communications :: Conferencing',
    ],
    keywords='discord overlay voice linux',
    license='GPLv3+',
)
