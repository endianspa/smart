from cpm.transaction import Transaction, PolicyUpgrade, UPGRADE
from cpm.cmdline import initCmdLine, confirmChanges
from cpm.matcher import MasterMatcher
from cpm.option import OptionParser
from cpm import *
import string
import re

USAGE="cpm upgrade [options] [packages]"

def parse_options(argv):
    parser = OptionParser(usage=USAGE)
    opts, args = parser.parse_args(argv)
    opts.args = args
    return opts

def main(opts):
    ctrl = initCmdLine(opts)
    ctrl.fetchRepositories()
    ctrl.loadCache()
    cache = ctrl.getCache()
    trans = Transaction(cache, PolicyUpgrade)
    pkgs = [x for x in cache.getPackages() if x.installed]
    if opts.args:
        newpkgs = []
        for arg in opts.args:
            matcher = MasterMatcher(arg)
            fpkgs = matcher.filter(pkgs)
            if not fpkgs:
                raise Error, "'%s' matches no installed packages" % arg
            newpkgs.extend(fpkgs)
        pkgs = dict.fromkeys(newpkgs).keys()
    for pkg in pkgs:
        trans.enqueue(pkg, UPGRADE)
    print "Computing upgrade..."
    trans.run()
    if not trans:
        print "No upgrades available!"
    elif confirmChanges(trans):
        #ctrl.commitTransaction(trans)
        ctrl.commitTransactionStepped(trans)

# vim:ts=4:sw=4:et
