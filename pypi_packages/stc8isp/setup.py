from setuptools import setup

setup(
    name='stc8isp',
    version='0.3.0',    
    description='Programming Tool for STC8G/8H Microcontrollers',
    url='https://github.com/wagiminator/MCU-Flash-Tools',
    author='Stefan Wagner',
    author_email='wagiminator@web.de',
    license='MIT License',
    packages=['stc8isp'],
    install_requires=[
        'pyserial',                   
    ],
)