from setuptools import setup

package = 'lazycli'
version = '0.6.1'
with open('README.rst') as fh:
    long_description = fh.read()

setup(name=package,
      version=version,
      description="generate command-line interfaces from function signatures",
      long_description=long_description,
      long_description_content_type='text/x-rst',
      url='https://github.com/ninjaaron/lazycli',
      packages=['lazycli'],
      install_requires=['libaaron'],
      python_requires='>=3.5')
