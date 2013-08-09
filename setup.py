from setuptools import setup, find_packages

setup(name='shipper',
      version='0.1a',
      description="Pythonic Docker Container Manager",
      author='Sasha Klizhentas',
      author_email='sasha.klizhentas@rackspace.com',
      url='http://www.mailgun.com',
      license='APACHE2',
      packages=find_packages(exclude=['ez_setup', 'examples', 'tests']),
      include_package_data=True,
      zip_safe=True,
      install_requires=[
          "nose==1.3.0",
          "mock==1.0.1",
          "docker-py==0.1.2",
          "treq==0.2.0",
          "ago==0.0.5",
          "texttable==0.8.1",
      ])


