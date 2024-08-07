from setuptools import setup

setup(
    name='stc8usb',
    version='1.4.0',    
    description='USB Programming Tool for STC8H8KxxU Microcontrollers',
    url='https://github.com/wagiminator/MCU-Flash-Tools',
    author='Stefan Wagner',
    author_email='wagiminator@web.de',
    license='MIT License',
    packages=['stc8usb'],
    install_requires=[
        'hid',                   
    ],
)