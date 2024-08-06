from setuptools import setup

setup(
    name='rvprog',
    version='1.5.0',    
    description='Programming Tool for WCH-LinkE and CH32Vxxx and CH32Xxxx',
    url='https://github.com/wagiminator/MCU-Flash-Tools',
    author='Stefan Wagner',
    author_email='wagiminator@web.de',
    license='MIT License',
    packages=['rvprog'],
    install_requires=[
        'pyusb',                   
    ],
)