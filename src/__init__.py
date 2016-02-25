#!/usr/bin/env python
#-*- coding:utf-8 -*-
#  Copyright (C) 2010-2013  CEA/DEN
#
#  This library is free software; you can redistribute it and/or
#  modify it under the terms of the GNU Lesser General Public
#  License as published by the Free Software Foundation; either
#  version 2.1 of the License.
#
#  This library is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
#  Lesser General Public License for more details.
#
#  You should have received a copy of the GNU Lesser General Public
#  License along with this library; if not, write to the Free Software
#  Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307 USA

import os
import shutil
import errno
import stat

from . import pyconf
from . import architecture
from . import printcolors
from . import options
from . import system
from . import ElementTree
from . import logger
from . import module

OK_STATUS = "OK"
KO_STATUS = "KO"
NA_STATUS = "NA"

class SatException(Exception):
    '''rename Exception Class
    '''
    pass

def ensure_path_exists(p):
    '''Create a path if not existing
    
    :param p str: The path.
    '''
    if not os.path.exists(p):
        os.makedirs(p)
        
def check_config_has_application( config, details = None ):
    '''check that the config has the key APPLICATION. Else raise an exception.
    
    :param config class 'common.pyconf.Config': The config.
    '''
    if 'APPLICATION' not in config:
        message = _("An APPLICATION is required. Use 'config --list' to get"
                    " the list of available applications.\n")
        if details :
            details.append(message)
        raise SatException( message )

def config_has_application( config ):
    return 'APPLICATION' in config
    
def print_info(logger, info):
    '''Prints the tuples that are in info variable in a formatted way.
    
    :param logger Logger: The logging instance to use for the prints.
    :param info list: The list of tuples to display
    '''
    # find the maximum length of the first value of the tuples in info
    smax = max(map(lambda l: len(l[0]), info))
    # Print each item of info with good indentation
    for i in info:
        sp = " " * (smax - len(i[0]))
        printcolors.print_value(logger, sp + i[0], i[1], 2)
    logger.write("\n", 2)

##
# Utils class to simplify path manipulations.
class Path:
    def __init__(self, path):
        self.path = str(path)

    def __add__(self, other):
        return Path(os.path.join(self.path, str(other)))

    def __abs__(self):
        return Path(os.path.abspath(self.path))

    def __str__(self):
        return self.path

    def __eq__(self, other):
        return self.path == other.path

    def exists(self):
        return self.islink() or os.path.exists(self.path)

    def islink(self):
        return os.path.islink(self.path)

    def isdir(self):
        return os.path.isdir(self.path)

    def list(self):
        return [Path(p) for p in os.listdir(self.path)]

    def dir(self):
        return Path(os.path.dirname(self.path))

    def base(self):
        return Path(os.path.basename(self.path))

    def make(self, mode=None):
        os.makedirs(self.path)        
        if mode:
            os.chmod(self.path, mode)
        
    def chmod(self, mode):
        os.chmod(self.path, mode)

    def rm(self):    
        if self.islink():
            os.remove(self.path)
        else:
            shutil.rmtree( self.path, onerror = handleRemoveReadonly )

    def copy(self, path, smart=False):
        if not isinstance(path, Path):
            path = Path(path)

        if os.path.islink(self.path):
            return self.copylink(path)
        elif os.path.isdir(self.path):
            return self.copydir(path, smart)
        else:
            return self.copyfile(path)

    def smartcopy(self, path):
        return self.copy(path, True)

    def readlink(self):
        if self.islink():
            return os.readlink(self.path)
        else:
            return False

    def symlink(self, path):
        try:
            os.symlink(str(path), self.path)
            return True
        except:
            return False

    def copylink(self, path):
        try:
            os.symlink(os.readlink(self.path), str(path))
            return True
        except:
            return False

    def copydir(self, dst, smart=False):
        try:
            names = self.list()

            if not dst.exists():
                dst.make()

            for name in names:
                if name == dst:
                    continue
                if smart and (str(name) in [".git", "CVS", ".svn"]):
                    continue
                srcname = self + name
                dstname = dst + name
                srcname.copy(dstname, smart)
            return True
        except:
            return False

    def copyfile(self, path):
        try:
            shutil.copy2(self.path, str(path))
            return True
        except:
            return False

def handleRemoveReadonly(func, path, exc):
    excvalue = exc[1]
    if func in (os.rmdir, os.remove) and excvalue.errno == errno.EACCES:
        os.chmod(path, stat.S_IRWXU| stat.S_IRWXG| stat.S_IRWXO) # 0777
        func(path)
    else:
        raise