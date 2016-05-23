#!/usr/bin/env python
#-*- coding:utf-8 -*-
#  Copyright (C) 2010-2012  CEA/DEN
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

import unittest
import os
import sys

# get execution path
testdir = os.path.dirname(os.path.realpath(__file__))
sys.path.append(os.path.join(testdir, '..', '..'))
sys.path.append(os.path.join(testdir, '..', '_testTools'))
sys.path.append(os.path.join(testdir, '..', '..','commands'))

from salomeTools import Sat
import HTMLTestRunner

class TestSource(unittest.TestCase):
    '''Test of the source command
    '''
    
    def test_environ_no_option(self):
        '''Test the environ command without any option
        '''
        OK = 'KO'
        
        appli = 'appli-test'

        file_env_name = 'env_launch.sh'
        
        sat = Sat()
        sat.config(appli)

        expected_file_path = os.path.join(sat.cfg.APPLICATION.workdir, file_env_name)

        if os.path.exists(expected_file_path):
            os.remove(expected_file_path)

        sat.environ(appli)

        if os.path.exists(expected_file_path):
            OK = 'OK'

        # pyunit method to compare 2 str
        self.assertEqual(OK, 'OK')

    def test_environ_option_products(self):
        '''Test the environ command with option --products
        '''
        OK = 'KO'
        
        appli = 'appli-test'
        product_name = 'PRODUCT_GIT'
        
        file_env_name = 'env_launch.sh'
        
        sat = Sat()
        sat.config(appli)

        expected_file_path = os.path.join(sat.cfg.APPLICATION.workdir, file_env_name)

        if os.path.exists(expected_file_path):
            os.remove(expected_file_path)

        sat.environ(appli + ' --products ' + product_name)

        if os.path.exists(expected_file_path):
            OK = 'OK'

        # pyunit method to compare 2 str
        self.assertEqual(OK, 'OK')        

    def test_environ_option_target(self):
        '''Test the environ command with option --target
        '''
        OK = 'KO'
        
        appli = 'appli-test'
        
        file_env_name = 'env_launch.sh'
        
        sat = Sat()
        sat.config(appli)

        expected_file_path = os.path.join('.', file_env_name)
        expected_file_path2 = os.path.join('.', 'env_build.sh')

        if os.path.exists(expected_file_path):
            os.remove(expected_file_path)

        sat.environ(appli + ' --target .')

        if os.path.exists(expected_file_path):
            OK = 'OK'

        if os.path.exists(expected_file_path):
            os.remove(expected_file_path)
            os.remove(expected_file_path2)

        # pyunit method to compare 2 str
        self.assertEqual(OK, 'OK') 

    def test_environ_option_prefix(self):
        '''Test the environ command with option --prefix
        '''
        OK = 'KO'
        
        appli = 'appli-test'
        prefix = 'TEST'
        file_env_name = prefix + '_launch.sh'
        
        sat = Sat()
        sat.config(appli)

        expected_file_path = os.path.join(sat.cfg.APPLICATION.workdir, file_env_name)

        if os.path.exists(expected_file_path):
            os.remove(expected_file_path)

        sat.environ(appli + ' --prefix ' + prefix)

        if os.path.exists(expected_file_path):
            OK = 'OK'

        # pyunit method to compare 2 str
        self.assertEqual(OK, 'OK') 

    def test_environ_option_shell(self):
        '''Test the environ command with option --shell
        '''
        OK = 'KO'
        
        appli = 'appli-test'
        shell = 'bat'
        file_env_name = 'env_launch.bat'
        
        sat = Sat()
        sat.config(appli)

        expected_file_path = os.path.join(sat.cfg.APPLICATION.workdir, file_env_name)

        if os.path.exists(expected_file_path):
            os.remove(expected_file_path)

        sat.environ(appli + ' --shell ' + shell)

        if os.path.exists(expected_file_path):
            OK = 'OK'

        # pyunit method to compare 2 str
        self.assertEqual(OK, 'OK') 

# test launch
if __name__ == '__main__':
    HTMLTestRunner.main()
