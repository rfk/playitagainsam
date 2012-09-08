
import unittest
import os

import playitagainsam


class PackagingRelatedTests(unittest.TestCase):
    """Various "tests" to ensure things get packages correctly."""

    def test_that_makes_README_match_docstring(self):
        """Ensure that the README is in sync with the docstring."""
        join = os.path.join
        dirname = os.path.dirname
        readme = join(dirname(dirname(dirname(__file__))), "README.rst")
        docstring = playitagainsam.__doc__.strip() + "\n"
        docstring = docstring.encode("utf8")
        if not os.path.isfile(readme):
            f = open(readme, "wb")
            f.write(docstring)
            f.close()
        else:
            f = open(readme, "rb")
            if f.read() != docstring:
                f.close()
                f = open(readme, "wb")
                f.write(docstring)
                f.close()
