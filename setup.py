from setuptools import setup, find_packages


setup(
    name='mma_monitor',
    version='1.0',
    packages=find_packages(),
    long_description=open('README.md').read(),
    install_requires=['logbook', 'requests-html', 'ujson', 'guessit'],
    entry_points={
      'console_scripts': [
          'mma_monitor = mma_monitor.monitor:main'
      ]
    }
)
