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
'''In this file are implemented the classes and method 
   relative to the module notion of salomeTools
'''

import src

def get_module_config(config, module_name, version):
    '''Get the specific configuration of a module from the global configuration
    
    :param config Config: The global configuration
    :param module_name str: The name of the module
    :param version str: The version of the module
    :return: the specific configuration of the module
    :rtype: Config
    '''
    vv = version
    # substitute some character with _
    for c in ".-": vv = vv.replace(c, "_")
    full_module_name = module_name + '_' + vv

    mod_info = None
    # If it exists, get the information of the module_version
    if full_module_name in config.MODULES:
        # returns specific information for the given version
        mod_info = config.MODULES[full_module_name]    
    # Get the standard informations
    elif module_name in config.MODULES:
        # returns the generic information (given version not found)
        mod_info = config.MODULES[module_name]
    
    # merge opt_depend in depend
    if mod_info is not None and 'opt_depend' in mod_info:
        for depend in mod_info.opt_depend:
            if depend in config.MODULES:
                mod_info.depend.append(depend,'')
    return mod_info

def get_modules_infos(lmodules, config):
    '''Get the specific configuration of a list of modules
    
    :param lmodules List: The list of module names
    :param config Config: The global configuration
    :return: the list of tuples 
             (module name, specific configuration of the module)
    :rtype: [(str, Config)]
    '''
    modules_infos = []
    # Loop on module names
    for mod in lmodules:
        # Get the version of the module from the application definition
        version_mod = config.APPLICATION.modules[mod][0]
        # Get the specific configuration of the module
        mod_info = get_module_config(config, mod, version_mod)
        if mod_info is not None:
            modules_infos.append((mod, mod_info))
        else:
            msg = _("The %s module has no definition in the configuration.") % mod
            raise src.SatException(msg)
    return modules_infos


def module_is_sample(module_info):
    '''Know if a module has the sample type
    
    :param module_info Config: The configuration specific to 
                               the module to be prepared
    :return: True if the module has the sample type, else False
    :rtype: boolean
    '''
    mtype = module_info.module_type
    return mtype.lower() == 'sample'