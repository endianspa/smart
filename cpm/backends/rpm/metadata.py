from cpm.cache import PackageInfo, Loader
from cpm.packageflags import PackageFlags
from cpm.backends.rpm import *
from cpm import *
import posixpath
import locale
import rpm
import os

from xml.parsers import expat

NS_COMMON = "http://linux.duke.edu/metadata/common"
NS_RPM    = "http://linux.duke.edu/metadata/rpm"

class RPMMetaDataPackageInfo(PackageInfo):

    def __init__(self, package, info):
        PackageInfo.__init__(self, package)
        self._info = info

    def getURL(self):
        return self._info.get("location")

    def getSize(self):
        return self._info.get("size")

    def getDescription(self):
        return self._info.get("description")

    def getSummary(self):
        return self._info.get("summary")

    def getGroup(self):
        return self._info.get("group")

    def getMD5(self):
        return self._info.get("md5")

    def getSHA(self):
        return self._info.get("sha")


class RPMMetaDataLoader(Loader):
 
    COMPMAP = { "EQ":"=", "LT":"<", "LE":"<=", "GT":">", "GE":">="}

    def __init__(self, filename, baseurl):
        Loader.__init__(self)
        self._filename = filename
        self._baseurl = baseurl

        self._queue = []
        self._data = None

        self._fileprovides = {}

        self._name = None
        self._version = None
        self._arch = None

        self._reqdict = {}
        self._prvdict = {}
        self._upgdict = {}
        self._cnfdict = {}
        self._filedict = {}

        self._info = {}

        self._skip = None

        self._starthandler = {}
        self._endhandler = {}

        for ns, attr in ((NS_COMMON, "MetaData"),
                         (NS_COMMON, "Package"),
                         (NS_COMMON, "Name"),
                         (NS_COMMON, "Arch"),
                         (NS_COMMON, "Version"),
                         (NS_COMMON, "Summary"),
                         (NS_COMMON, "Description"),
                         (NS_COMMON, "Size"),
                         (NS_COMMON, "Location"),
                         (NS_COMMON, "Format"),
                         (NS_COMMON, "Group"),
                         (NS_COMMON, "CheckSum"),
                         (NS_RPM, "Entry"),
                         (NS_RPM, "Requires"),
                         (NS_RPM, "Provides"),
                         (NS_RPM, "Conflicts"),
                         (NS_RPM, "Obsoletes")):
            handlername = "_handle%sStart" % attr
            handler = getattr(self, handlername, None)
            nsattr = "%s %s" % (ns, attr.lower())
            if handler:
                self._starthandler[nsattr] = handler
            handlername = "_handle%sEnd" % attr
            handler = getattr(self, handlername, None)
            if handler:
                self._endhandler[nsattr] = handler
            setattr(self, attr.upper(), nsattr)

    def reset(self):
        Loader.reset(self)
        del self._queue[:]
        self._resetPackage()
        self._fileprovides.clear()

    def _resetPackage(self):
        self._data = None
        self._name = None
        self._version = None
        self._arch = None
        self._reqdict.clear()
        self._prvdict.clear()
        self._upgdict.clear()
        self._cnfdict.clear()
        self._filedict.clear()
        self._info = {}

    def _startElement(self, name, attrs):
        if self._skip:
            return
        handler = self._starthandler.get(name)
        if handler:
            handler(name, attrs)
        self._data = None
        self._queue.append((name, attrs))

    def _endElement(self, name):
        if self._skip:
            if name == self._skip:
                self._skip = None
                _name = None
                while _name != name:
                    _name, attrs = self._queue.pop()
            return
        _name, attrs = self._queue.pop()
        assert _name == name
        handler = self._endhandler.get(name)
        if handler:
            handler(name, attrs, self._data)
        self._data = None

    def _charData(self, data):
        self._data = data

    def _handleArchEnd(self, name, attrs, data):
        if rpm.archscore(data) == 0:
            self._skip = self.PACKAGE
        else:
            self._arch = data

    def _handleNameEnd(self, name, attrs, data):
        self._name = data

    def _handleVersionEnd(self, name, attrs, data):
        e = attrs.get("epoch")
        if e:
            self._version = "%s:%s-%s" % (e, attrs.get("ver"), attrs.get("rel"))
        else:
            self._version = "%s-%s" % (attrs.get("ver"), attrs.get("rel"))

    def _handleSummaryEnd(self, name, attrs, data):
        self._info["summary"] = data

    def _handleDescriptionEnd(self, name, attrs, data):
        self._info["description"] = data

    def _handleSizeEnd(self, name, attrs, data):
        self._info["size"] = int(attrs.get("package"))
        self._info["installed_size"] = int(attrs.get("installed"))

    def _handleCheckSumEnd(self, name, attrs, data):
        self._info[attrs.get("type")] = data

    def _handleLocationEnd(self, name, attrs, data):
        self._info["location"] = posixpath.join(self._baseurl,
                                                attrs.get("href"))

    def _handleGroupEnd(self, name, attrs, data):
        self._info["group"] = data

    def _handleEntryEnd(self, name, attrs, data):
        name = attrs.get("name")
        if not name or name[:7] in ("rpmlib(", "config("):
            return
        if "ver" in attrs:
            e = attrs.get("epoch")
            v = attrs.get("ver")
            r = attrs.get("rel")
            version = v
            if e:
                version = "%s:%s" % (e, version)
            if r:
                version = "%s-%s" % (version, r)
            if "flags" in attrs:
                relation = self.COMPMAP.get(attrs.get("flags"))
            else:
                relation = None
        else:
            version = None
            relation = None
        lastname = self._queue[-1][0]
        if lastname == self.REQUIRES:
            self._reqdict[(RPMRequires, name, relation, version)] = True
        elif lastname == self.PROVIDES:
            if name[0] == "/":
                self._filedict[name] = True
            else:
                if name == self._name and version == self._version:
                    Prv = RPMNameProvides
                else:
                    Prv = RPMProvides
                self._prvdict[(Prv, name, version)] = True
        elif lastname == self.OBSOLETES:
            tup = (RPMObsoletes, name, relation, version)
            self._upgdict[tup] = True
            self._cnfdict[tup] = True
        elif lastname == self.CONFLICTS:
            self._cnfdict[(RPMConflicts, name, relation, version)] = True

    def _handleFileEnd(self, name, attrs, data):
        if lastname == self.PROVIDES:
            self._prvdict[(RPMProvides, data, None, None)]

    def _handlePackageStart(self, name, attrs):
        if attrs.get("type") != "rpm":
            self._skip = self.PACKAGE

    def _handlePackageEnd(self, name, attrs, data):
        name = self._name
        version = self._version

        obstup = (RPMObsoletes, name, '<', version)
        self._upgdict[obstup] = True
        self._fpkg.name = name
        self._fpkg.version = version
        if not self._pkgflags.test("multi-version", self._fpkg):
            self._cnfdict[obstup] = True

        reqargs = [x for x in self._reqdict
                   if (RPMProvides, x[1], x[3]) not in self._prvdict]
        prvargs = self._prvdict.keys()
        cnfargs = self._cnfdict.keys()
        upgargs = self._upgdict.keys()

        pkg = self.newPackage((RPMPackage, name,
                               "%s.%s" % (version, self._arch)),
                               prvargs, reqargs, upgargs, cnfargs)
        pkg.loaders[self] = self._info

        self._fileprovides.setdefault(pkg, []).extend(self._filedict.keys())

        self._resetPackage()
        
    def load(self):
        self._pkgflags = PackageFlags(sysconf.get("package-flags", {}))
        self._fpkg = RPMFlagPackage()
        self._progress = iface.getProgress(self._cache)

        parser = expat.ParserCreate(namespace_separator=" ")
        parser.StartElementHandler = self._startElement
        parser.EndElementHandler = self._endElement
        parser.CharacterDataHandler = self._charData
        parser.returns_unicode = False

        try:
            RPMPackage.ignoreprereq = True
            parser.ParseFile(open(self._filename))
        finally:
            RPMPackage.ignoreprereq = False

    def loadFileProvides(self, fndict):
        for pkg in self._fileprovides:
            for fn in self._fileprovides[pkg]:
                if fn in fndict:
                    self.newProvides(pkg, (RPMProvides, fn))

    def getInfo(self, pkg):
        return RPMMetaDataPackageInfo(pkg, pkg.loaders[self])

    def getLoadSteps(self):
        return 0

# vim:ts=4:sw=4:et
