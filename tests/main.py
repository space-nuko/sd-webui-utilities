#!/usr/bin/env python

import sys
import os.path
import unittest

sys.path.insert(0, os.path.dirname(__file__) + os.sep + "..")
import test_import_to_hydrus

def suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.defaultTestLoader.loadTestsFromName("test_import_to_hydrus"))
    return suite

if __name__ == '__main__':
    runner = unittest.TextTestRunner()
    runner.run(suite())
