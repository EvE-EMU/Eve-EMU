import os

from setuptools import find_packages, setup

from miningtaxes import __version__

# read the contents of your README file
this_directory = os.path.abspath(os.path.dirname(__file__))
with open(os.path.join(this_directory, "README.md"), encoding="utf-8") as f:
    long_description = f.read()

# allow setup.py to be run from any path
os.chdir(os.path.normpath(os.path.join(os.path.abspath(__file__), os.pardir)))

setup(
    name="aa_miningtaxes",
    version=__version__,
    packages=find_packages(),
    include_package_data=True,
    license="MIT",
    description="An Alliance Auth app that tracks and applies taxes for mining",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://gitlab.com/arctiru/aa-miningtaxes",
    author="Arc Tiru",
    author_email="arcturusstl@gmail.com",
    classifiers=[
        "Environment :: Web Environment",
        "Framework :: Django",
        "Framework :: Django :: 3.2",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Internet :: WWW/HTTP",
        "Topic :: Internet :: WWW/HTTP :: Dynamic Content",
    ],
    python_requires=">=3.11,<3.13",
    install_requires=[
        "allianceauth>=4.0",
        "allianceauth-app-utils>=1.25.0",
        "django-eveonline-sde>=0.0.1b9",
        "django-esi>=8",
        "django_celery_results>=2.5.1",
    ],
)
