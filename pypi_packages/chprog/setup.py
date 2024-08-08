from setuptools import setup

setup(
    name='chprog',
    version='2.5.0',    
    description='USB Programming Tool for WCH Microcontrollers',
    url='https://github.com/wagiminator/MCU-Flash-Tools',
    author='Stefan Wagner',
    author_email='wagiminator@web.de',
    license='MIT License',
    packages=['chprog'],
    install_requires=[
        'pyusb',                   
    ],
)
