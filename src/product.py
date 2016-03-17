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
'''In this file are implemented the classes and methods 
   relative to the product notion of salomeTools
'''

import src

AVAILABLE_VCS = ['git', 'svn', 'cvs']

def get_product_config(config, product_name):
    '''Get the specific configuration of a product from the global configuration
    
    :param config Config: The global configuration
    :param product_name str: The name of the product
    :return: the specific configuration of the product
    :rtype: Config
    '''
    
    # Get the version of the product from the application definition
    version = config.APPLICATION.products[product_name]
    # if no version, then take the default one defined in the application
    if isinstance(version, bool): 
        version = config.APPLICATION.tag      
    
    # Define debug and dev modes
    # Get the tag if a dictionary is given in APPLICATION.products for the
    # current product 
    debug = 'no'
    dev = 'no'
    if isinstance(version, src.pyconf.Mapping):
        dic_version = version
        # Get the version/tag
        if not 'tag' in dic_version:
            version = config.APPLICATION.tag
        else:
            version = dic_version.tag
        
        # Get the debug if any
        if 'debug' in dic_version:
            debug = dic_version.debug
        
        # Get the dev if any
        if 'dev' in dic_version:
            dev = dic_version.dev
    
    vv = version
    # substitute some character with _ in order to get the correct definition
    # in config.PRODUCTS. This is done because the pyconf tool does not handle
    # the . and - characters 
    for c in ".-": vv = vv.replace(c, "_")
    full_product_name = product_name + '_' + vv

    prod_info = None
    # If it exists, get the information of the product_version
    if full_product_name in config.PRODUCTS:
        # returns specific information for the given version
        prod_info = config.PRODUCTS[full_product_name]    
    # Get the standard informations
    elif product_name in config.PRODUCTS:
        # returns the generic information (given version not found)
        prod_info = config.PRODUCTS[product_name]
    
    # merge opt_depend in depend
    if prod_info is not None and 'opt_depend' in prod_info:
        for depend in prod_info.opt_depend:
            if depend in config.PRODUCTS:
                prod_info.depend.append(depend,'')
    
    # In case of a product get with a vcs, put the tag (equal to the version)
    if prod_info is not None and prod_info.get_source in AVAILABLE_VCS:
        
        if prod_info.get_source == 'git':
            prod_info.git_info.tag = version
        
        if prod_info.get_source == 'svn':
            prod_info.svn_info.tag = version
        
        if prod_info.get_source == 'cvs':
            prod_info.cvs_info.tag = version
    
    # In case of a fixed product, define the install_dir (equal to the version)
    if prod_info is not None and prod_info.get_source=="fixed":
        prod_info.install_dir = version
    
    # Check if the product is defined as native in the application
    if prod_info is not None:
        if version == "native":
            prod_info.get_source = "native"
        elif prod_info.get_source == "native":
            msg = _("The product %(prod)s has version %(ver)s but is declared"
                    " as native in its definition" %
                { 'prod': prod_info.name, 'ver': version})
            raise src.SatException(msg)

    # If there is no definition but the product is declared as native,
    # construct a new defifnition containing only the get_source key
    if prod_info is None and version == "native":
        prod_info = src.pyconf.Config()
        prod_info.name = product_name
        prod_info.get_source = "native"
    
    # Set the debug and dev keys
    if prod_info is not None:
        prod_info.debug = debug
        prod_info.dev = dev
        
    return prod_info

def get_products_infos(lproducts, config):
    '''Get the specific configuration of a list of products
    
    :param lproducts List: The list of product names
    :param config Config: The global configuration
    :return: the list of tuples 
             (product name, specific configuration of the product)
    :rtype: [(str, Config)]
    '''
    products_infos = []
    # Loop on product names
    for prod in lproducts:       
        # Get the specific configuration of the product
        prod_info = get_product_config(config, prod)
        if prod_info is not None:
            products_infos.append((prod, prod_info))
        else:
            msg = _("The %s product has no definition in the configuration.") % prod
            raise src.SatException(msg)
    return products_infos


def product_is_sample(product_info):
    '''Know if a product has the sample type
    
    :param product_info Config: The configuration specific to 
                               the product
    :return: True if the product has the sample type, else False
    :rtype: boolean
    '''
    ptype = product_info.type
    return ptype.lower() == 'sample'

def product_is_fixed(product_info):
    '''Know if a product is fixed
    
    :param product_info Config: The configuration specific to 
                               the product
    :return: True if the product is fixed, else False
    :rtype: boolean
    '''
    get_src = product_info.get_source
    return get_src.lower() == 'fixed'

def product_is_native(product_info):
    '''Know if a product is native
    
    :param product_info Config: The configuration specific to 
                               the product
    :return: True if the product is native, else False
    :rtype: boolean
    '''
    get_src = product_info.get_source
    return get_src.lower() == 'native'

def product_is_dev(product_info):
    '''Know if a product is in dev mode
    
    :param product_info Config: The configuration specific to 
                               the product
    :return: True if the product is in dev mode, else False
    :rtype: boolean
    '''
    dev = product_info.dev
    return dev.lower() == 'yes'

def product_is_debug(product_info):
    '''Know if a product is in debug mode
    
    :param product_info Config: The configuration specific to 
                               the product
    :return: True if the product is in debug mode, else False
    :rtype: boolean
    '''
    debug = product_info.debug
    return debug.lower() == 'yes'