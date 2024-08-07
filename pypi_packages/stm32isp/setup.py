from setuptools import setup

setup(
    name='stm32isp',
    version='0.8.0',    
    description='Programming Tool for some STM32 Microcontrollers',
    url='https://github.com/wagiminator/MCU-Flash-Tools',
    author='Stefan Wagner',
    author_email='wagiminator@web.de',
    license='MIT License',
    packages=['stm32isp'],
    install_requires=[
        'pyserial',                   
    ],
)