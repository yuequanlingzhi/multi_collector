from setuptools import setup, find_packages

# ✅ 直接手动指定版本号，避免 build.properties 报错
__version__ = '1.6.3'  # 或你当前库的真实版本号

setup(
    name='pymoduleconnector',
    version=__version__,
    description='A Python wrapper for XeThru ModuleConnector',
    long_description='',
    long_description_content_type='text/markdown',
    author='Novelda AS',
    author_email='support@xethru.com',
    url='http://community.xethru.com',
    packages=find_packages(include=['pymoduleconnector', 'pymoduleconnector.*']),
    include_package_data=True,
    zip_safe=False,
    install_requires=[],
    extras_require={
        'auto': ['pyserial']
    },
    entry_points={
        'console_scripts': [
            'xt_x2m200resp=pymoduleconnector.examples.x2m200_respiration_example:main',
        ],
    },
    classifiers=[
        'Programming Language :: Python :: 3',
        'Operating System :: Microsoft :: Windows',
    ],
    python_requires='>=3.6',
)
