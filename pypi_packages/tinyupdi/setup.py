from setuptools import setup

setup(
    name='tinyupdi',
    version='1.5.0',    
    description='Minimal UPDI Programming Tool for tinyAVR',
    url='https://github.com/wagiminator/MCU-Flash-Tools',
    author='Stefan Wagner',
    author_email='wagiminator@web.de',
    license='MIT License',
    packages=['tinyupdi'],
    install_requires=[
        'pyserial',                   
    ],
)