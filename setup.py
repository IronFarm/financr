from distutils.core import setup

setup(
    name='financr',
    version='1.0',
    packages=['financr'],
    url='',
    license='',
    author='Carl Jeske',
    author_email='carljeske@googlemail.com',
    description='Hargreaves Lansdown Account History Viewer',
    requires=['pandas>=0.18.1', 'requests>=2.12.4', 'lxml>=3.6.4', 'bokeh>=0.12.2']
)
