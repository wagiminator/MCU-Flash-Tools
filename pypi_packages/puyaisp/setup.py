from setuptools import setup

setup(
    name='puyaisp',
    version='1.4.0',    
    description='Programming Tool for PUYA PY32F0xx Microcontrollers',
    url='https://github.com/wagiminator/MCU-Flash-Tools',
    author='Stefan Wagner',
    author_email='wagiminator@web.de',
    license='MIT License',
    packages=['puyaisp'],
    install_requires=[
        'pyserial',                   
    ],
)