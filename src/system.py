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

'''
In this file : all functions that do a system call, 
like open a browser or an editor, or call a git command
'''

import os
import subprocess
import time
import tarfile

import debug as DBG
import utilsSat as UTS

from . import printcolors

def show_in_editor(editor, filePath, logger):
    '''open filePath using editor.
    
    :param editor str: The editor to use.
    :param filePath str: The path to the file to open.
    '''
    # default editor is vi
    if editor is None or len(editor) == 0:
        editor = 'vi'
    
    if '%s' not in editor:
        editor += ' %s'

    try:
        # launch cmd using subprocess.Popen
        cmd = editor % filePath
        logger.write('Launched command:\n' + cmd + '\n', 5)
        p = subprocess.Popen(cmd, shell=True)
        p.communicate()
    except:
        logger.write(printcolors.printcError(_("Unable to edit file %s\n") 
                                             % filePath), 1)


def git_extract(from_what, tag, where, logger, environment=None):
  '''Extracts sources from a git repository.

  :param from_what str: The remote git repository.
  :param tag str: The tag.
  :param where str: The path where to extract.
  :param logger Logger: The logger instance to use.
  :param environment src.environment.Environ: The environment to source when extracting.
  :return: True if the extraction is successful
  :rtype: boolean
  '''
  DBG.write("git_extract", [from_what, tag, str(where)])
  if not where.exists():
    where.make()
  if tag == "master" or tag == "HEAD":
    cmd = r"""
set -x
git clone %(remote)s %(where)s
"""
    cmd = cmd % {'remote': from_what, 'tag': tag, 'where': str(where)}
  else:
    # NOTICE: this command only works with recent version of git
    #         because --work-tree does not work with an absolute path
    where_git = os.path.join(str(where), ".git")

    cmd = r"""
set -x
rmdir %(where)s
git clone %(remote)s %(where)s && \
git --git-dir=%(where_git)s --work-tree=%(where)s checkout %(tag)s
"""
    cmd = cmd % {'remote': from_what,
                 'tag': tag,
                 'where': str(where),
                 'where_git': where_git}


  logger.logTxtFile.write("\n" + cmd + "\n")
  logger.logTxtFile.flush()

  DBG.write("cmd", cmd)

  # git commands may fail sometimes for various raisons (big module, network troubles, tuleap maintenance)
  # therefore we give several tries
  i_try=0
  max_number_of_tries=3
  sleep_delay=30  # seconds
  while (True):
    i_try+=1
    rc = UTS.Popen(cmd, cwd=str(where.dir()), env=environment.environ.environ, logger=logger)
    if rc.isOk() or (i_try>=max_number_of_tries):
        break
    logger.write('\ngit command failed! Wait %d seconds and give an other try (%d/%d)\n' % (sleep_delay,i_try+1,max_number_of_tries), 3)
    time.sleep(sleep_delay) # wait a little

  return rc.isOk()

  """
  res = subprocess.call(command,
                        cwd=str(where.dir()),
                        env=environment.environ.environ,
                        shell=True,
                        stdout=logger.logTxtFile,
                        stderr=subprocess.STDOUT)
  return (res == 0)
  """



def git_extract_sub_dir(from_what, tag, where, sub_dir, logger, environment=None):
  '''Extracts sources from a subtree sub_dir of a git repository.

  :param from_what str: The remote git repository.
  :param tag str: The tag.
  :param where str: The path where to extract.
  :param sub_dir str: The relative path of subtree to extract.
  :param logger Logger: The logger instance to use.
  :param environment src.environment.Environ: The environment to source when extracting.
  :return: True if the extraction is successful
  :rtype: boolean
  '''
  strWhere = str(where)
  tmpWhere = strWhere + '_tmp'
  parentWhere = os.path.dirname(strWhere)
  if not os.path.exists(parentWhere):
    logger.error("not existing directory: %s" % parentWhere)
    return False
  if os.path.isdir(strWhere):
    logger.error("do not override existing directory: %s" % strWhere)
    return False
  aDict = {'remote': from_what,
           'tag': tag,
           'sub_dir': sub_dir,
           'where': strWhere,
           'parentWhere': parentWhere,
           'tmpWhere': tmpWhere,
           }
  DBG.write("git_extract_sub_dir", aDict)

  cmd = r"""
set -x
export tmpDir=%(tmpWhere)s && \
rm -rf $tmpDir
git clone %(remote)s $tmpDir && \
cd $tmpDir && \
git checkout %(tag)s && \
mv %(sub_dir)s %(where)s && \
git log -1 > %(where)s/README_git_log.txt && \
rm -rf $tmpDir
""" % aDict
  DBG.write("cmd", cmd)

  for nbtry in range(0,3): # retries case of network problem
    rc = UTS.Popen(cmd, cwd=parentWhere, env=environment.environ.environ, logger=logger)
    if rc.isOk(): break
    time.sleep(30) # wait a little

  return rc.isOk()

def archive_extract(from_what, where, logger):
    '''Extracts sources from an archive.
    
    :param from_what str: The path to the archive.
    :param where str: The path where to extract.
    :param logger Logger: The logger instance to use.
    :return: True if the extraction is successful
    :rtype: boolean
    '''
    try:
        archive = tarfile.open(from_what)
        for i in archive.getmembers():
            archive.extract(i, path=str(where))
        return True, os.path.commonprefix(archive.getnames())
    except Exception as exc:
        logger.write("archive_extract: %s\n" % exc)
        return False, None

def cvs_extract(protocol, user, server, base, tag, product, where,
                logger, checkout=False, environment=None):
    '''Extracts sources from a cvs repository.
    
    :param protocol str: The cvs protocol.
    :param user str: The user to be used.
    :param server str: The remote cvs server.
    :param base str: .
    :param tag str: The tag.
    :param product str: The product.
    :param where str: The path where to extract.
    :param logger Logger: The logger instance to use.
    :param checkout boolean: If true use checkout cvs.
    :param environment src.environment.Environ: The environment to source when
                                                extracting.
    :return: True if the extraction is successful
    :rtype: boolean
    '''

    opttag = ''
    if tag is not None and len(tag) > 0:
        opttag = '-r ' + tag

    cmd = 'export'
    if checkout:
        cmd = 'checkout'
    elif len(opttag) == 0:
        opttag = '-DNOW'
    
    if len(protocol) > 0:
        root = "%s@%s:%s" % (user, server, base)
        command = "cvs -d :%(protocol)s:%(root)s %(command)s -d %(where)s %(tag)s %(product)s" % \
            { 'protocol': protocol, 'root': root, 'where': str(where.base()),
              'tag': opttag, 'product': product, 'command': cmd }
    else:
        command = "cvs -d %(root)s %(command)s -d %(where)s %(tag)s %(base)s/%(product)s" % \
            { 'root': server, 'base': base, 'where': str(where.base()),
              'tag': opttag, 'product': product, 'command': cmd }

    logger.write(command + "\n", 5)

    if not where.dir().exists():
        where.dir().make()

    logger.logTxtFile.write("\n" + command + "\n")
    logger.logTxtFile.flush()        
    res = subprocess.call(command,
                          cwd=str(where.dir()),
                          env=environment.environ.environ,
                          shell=True,
                          stdout=logger.logTxtFile,
                          stderr=subprocess.STDOUT)
    return (res == 0)

def svn_extract(user,
                from_what,
                tag,
                where,
                logger,
                checkout=False,
                environment=None):
    '''Extracts sources from a svn repository.
    
    :param user str: The user to be used.
    :param from_what str: The remote git repository.
    :param tag str: The tag.
    :param where str: The path where to extract.
    :param logger Logger: The logger instance to use.
    :param checkout boolean: If true use checkout svn.
    :param environment src.environment.Environ: The environment to source when
                                                extracting.
    :return: True if the extraction is successful
    :rtype: boolean
    '''
    if not where.exists():
        where.make()

    if checkout:
        command = "svn checkout --username %(user)s %(remote)s %(where)s" % \
            { 'remote': from_what, 'user' : user, 'where': str(where) }
    else:
        command = ""
        if os.path.exists(str(where)):
            command = "/bin/rm -rf %(where)s && " % \
                { 'remote': from_what, 'where': str(where) }
        
        if tag == "master":
            command += "svn export --username %(user)s %(remote)s %(where)s" % \
                { 'remote': from_what, 'user' : user, 'where': str(where) }       
        else:
            command += "svn export -r %(tag)s --username %(user)s %(remote)s %(where)s" % \
                { 'tag' : tag, 'remote': from_what, 'user' : user, 'where': str(where) }
    
    logger.logTxtFile.write(command + "\n")
    
    logger.write(command + "\n", 5)
    logger.logTxtFile.write("\n" + command + "\n")
    logger.logTxtFile.flush()
    res = subprocess.call(command,
                          cwd=str(where.dir()),
                          env=environment.environ.environ,
                          shell=True,
                          stdout=logger.logTxtFile,
                          stderr=subprocess.STDOUT)
    return (res == 0)
