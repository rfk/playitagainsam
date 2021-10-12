#
#  This is the setuptools script for "playitagainsam".
#  Originally developed by Ryan Kelly, 2012.
#
#  This script is placed in the public domain.
#

import os
import sys
setup_kwds = {}

#  Use setuptools is available, so we have `python setup.py test`.
#  We also need it for 2to3 integration on python3.
#  Otherwise, fall back to plain old distutils.
try:
    from setuptools import setup
except ImportError:
    if sys.version_info > (3,):
        raise RuntimeError("python3 support requires setuptools")
    from distutils.core import setup
else:
    setup_kwds["test_suite"] = "playitagainsam.tests"

HERE = os.path.abspath(os.path.dirname(__file__))

#  Extract the docstring and version declaration from the module.
#  To avoid errors due to missing dependencies or bad python versions,
#  we explicitly read the file contents up to the end of the version
#  delcaration, then exec it ourselves.
src = open(os.path.join(HERE, "playitagainsam", "__init__.py"))
info = {}
lines = []
for ln in src:
    lines.append(ln)
    if "__version__" in ln:
        for ln in src:
            if "__version__" not in ln:
                break
            lines.append(ln)
        break
exec("".join(lines),info)


NAME = "playitagainsam"
VERSION = info["__version__"]
DESCRIPTION = "record and replay interactive terminal sessions"
LONG_DESC = info["__doc__"]
AUTHOR = "Ryan Kelly"
AUTHOR_EMAIL = "ryan@rfk.id.au"
URL="https://github.com/rfk/playitagainsam"
LICENSE = "MIT"
KEYWORDS = "shell record presentation tutorial"
CLASSIFIERS = [
    "Programming Language :: Python",
    "Programming Language :: Python :: 2",
    "Programming Language :: Python :: 2.7",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.5",
    "License :: OSI Approved",
    "License :: OSI Approved :: MIT License",
    "Development Status :: 4 - Beta",
    "Intended Audience :: Developers",
]


setup(name=NAME,
      version=VERSION,
      author=AUTHOR,
      author_email=AUTHOR_EMAIL,
      url=URL,
      description=DESCRIPTION,
      long_description=LONG_DESC,
      license=LICENSE,
      keywords=KEYWORDS,
      packages=["playitagainsam"],
      scripts=["scripts/pias"],
      install_requires=["psutil>=2.0", "six"],
      classifiers=CLASSIFIERS,
      **setup_kwds
     )
