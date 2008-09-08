#!/usr/bin/env python
#
# Copyright (c) 2005 Canonical
#
# Written by Gustavo Niemeyer <niemeyer@conectiva.com>
#
# This file is part of Smart Package Manager.
#
# Smart Package Manager is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License as published
# by the Free Software Foundation; either version 2 of the License, or (at
# your option) any later version.
#
# Smart Package Manager is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Smart Package Manager; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#
import tempfile
import unittest
import doctest
import shutil
import sys
import os

from smart.option import OptionParser
from smart import init, const, interface
from smart import *

import tests


USAGE=_("test.py [options] [<test filename>, ...]")


def find_tests(testpaths=()):
    """Find all test paths, or test paths contained in the provided sequence.

    @param testpaths: If provided, only tests in the given sequence will
                      be considered.  If not provided, all tests are
                      considered.
    @return: (unittests, doctests) tuple, with lists of unittests and
             doctests found, respectively.
    """
    topdir = os.path.abspath(os.path.dirname(__file__))
    testdir = os.path.dirname(tests.__file__)
    testpaths = set(testpaths)
    unittests = []
    doctests = []
    for root, dirnames, filenames in os.walk(testdir):
        for filename in filenames:
            filepath = os.path.join(root, filename)
            relpath = filepath[len(topdir)+1:]

            if filename == "__init__.py" or filename.endswith(".pyc"):
                # Skip non-tests.
                continue

            if testpaths:
                # Skip any tests not in testpaths.
                for testpath in testpaths:
                    if relpath.startswith(testpath):
                        break
                else:
                    continue

            if filename.endswith(".py"):
                unittests.append(relpath)
            elif filename.endswith(".txt"):
                doctests.append(relpath)

    return unittests, doctests


def parse_options(argv):
    parser = OptionParser(usage=USAGE)
    opts, args = parser.parse_args(argv)
    opts.args = args
    return opts


def main():

    datadir = tempfile.mkdtemp()

    try:
        const.DISTROFILE = "/non-existent/file"
        interface.getScreenWidth = lambda: 80

        tests.ctrl = init(datadir=datadir)
        opts = parse_options(sys.argv[1:])

        runner = unittest.TextTestRunner()
        loader = unittest.TestLoader()
        doctest_flags = doctest.ELLIPSIS

        unittests, doctests = find_tests(opts.args)

        class Summary:
            def __init__(self):
                self.total_failures = 0
                self.total_tests = 0
            def __call__(self, failures, tests):
                self.total_failures += failures
                self.total_tests += tests
                print "(failures=%d, tests=%d)" % (failures, tests)

        summary = Summary()

        if unittests:
            print "Running unittests..."
            for filename in unittests:
                print "[%s]" % filename
                modulename = filename[:-3].replace("/", ".")
                module = __import__(modulename, None, None, [filename])
                test = loader.loadTestsFromModule(module)
                result = runner.run(test)
                summary(len(result.failures), test.countTestCases())
                print

                shutil.rmtree(datadir)
                os.mkdir(datadir)

        if doctests:
            print "Running doctests..."
            for filename in doctests:
                print "[%s]" % filename
                summary(*doctest.testfile(filename, optionflags=doctest_flags))
                print

                shutil.rmtree(datadir)
                os.mkdir(datadir)

    finally:
        shutil.rmtree(datadir)

    print "Total failures: %d" % summary.total_failures
    print "Total tests: %d" % summary.total_tests

    return bool(summary.total_failures)

if __name__ == "__main__":
    status = main()
    sys.exit(status)

# vim:ts=4:sw=4:et
