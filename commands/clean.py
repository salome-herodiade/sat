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

import re

import src

# Compatibility python 2/3 for input function
# input stays input for python 3 and input = raw_input for python 2
try: 
    input = raw_input
except NameError: 
    pass


# Define all possible option for the clean command :  sat clean <options>
parser = src.options.Options()
parser.add_option('p', 'products', 'list2', 'products',
    _('Optional: Products to clean. This option can be'
    ' passed several time to clean several products.'))
parser.add_option('s', 'sources', 'boolean', 'sources',
    _("Optional: Clean the product source directories."))
parser.add_option('b', 'build', 'boolean', 'build', 
    _("Optional: Clean the product build directories."))
parser.add_option('i', 'install', 'boolean', 'install', 
    _("Optional: Clean the product install directories."))
parser.add_option('a', 'all', 'boolean', 'all', 
    _("Optional: Clean the product source, build and install directories."))
parser.add_option('', 'sources_without_dev', 'boolean', 'sources_without_dev', 
    _("Optional: do not clean the products in development mode."))


def get_source_directories(products_infos, without_dev):
    """\
    Returns the list of directory source paths corresponding 
    to the list of product information given as input.
    If without_dev (bool) the dev products are ignored.
    
    :param products_infos list: The list of (name, config) corresponding to one
                                product.
    :param without_dev boolean: If True, then ignore the dev products.
    :return: the list of source paths.
    :rtype: list
    """
    l_dir_source = []
    for __, product_info in products_infos:
        if product_has_dir(product_info, without_dev):
            l_dir_source.append(src.Path(product_info.source_dir))
    return l_dir_source

def get_build_directories(products_infos):
    """\
    Returns the list of directory build paths corresponding to the list of 
    product information given as input.
    
    :param products_infos list: The list of (name, config) corresponding to one
                                product.
    :return: the list of build paths.
    :rtype: list
    """
    l_dir_build = []
    for __, product_info in products_infos:
        if product_has_dir(product_info):
            if "build_dir" in product_info:
                l_dir_build.append(src.Path(product_info.build_dir))
    return l_dir_build

def get_install_directories(products_infos):
    """\
    Returns the list of directory install paths corresponding to the list of 
    product information given as input.
    
    :param products_infos list: The list of (name, config) corresponding to one product.
    :return: the list of install paths.
    :rtype: list
    """
    l_dir_install = []
    for __, product_info in products_infos:
        if product_has_dir(product_info):
            l_dir_install.append(src.Path(product_info.install_dir))
    return l_dir_install

def product_has_dir(product_info, without_dev=False):
    """\
    Returns a boolean at True if there is a source, build and install
    directory corresponding to the product described by product_info.
    
    :param products_info Config: The config corresponding to the product.
    :return: True if there is a source, build and install directory corresponding to the product described by product_info.
    :rtype: boolean
    """
    if (src.product.product_is_native(product_info) or 
                            src.product.product_is_fixed(product_info)):
        return False
    if without_dev:
        if src.product.product_is_dev(product_info):
            return False
    return True
    
def suppress_directories(l_paths, logger):
    """Suppress the paths given in the list in l_paths.
    
    :param l_paths list: The list of Path to be suppressed
    :param logger Logger: The logger instance to use for the display and logging
    """    
    for path in l_paths:
        if not path.isdir():
            msg = _("Warning: the path %s does not "
                    "exists (or is not a directory)\n" % path.__str__())
            logger.write(src.printcolors.printcWarning(msg), 1)
        else:
            logger.write(_("Removing %s ...") % path.__str__())
            path.rm()
            logger.write('%s\n' % src.printcolors.printc(src.OK_STATUS), 3)

def description():
    """method called when salomeTools is called with --help option.
    
    :return: The text to display for the clean command description.
    :rtype: str
    """
    return _("""\
The clean command suppress the SOURCES, BUILD or INSTALL directories of the application products.
Use the options to define what directories you want to suppress and to set the list of products

example:
>> sat clean SALOME-xx --build --install --properties is_salome_module:yes
""")
  
def run(args, runner, logger):
    """\
    method called when salomeTools is called with clean parameter.
    """
    
    # Parse the options
    (options, args) = parser.parse_args(args)

    # check that the command has been called with an application
    src.check_config_has_application( runner.cfg )


    # Get the list of products to threat
    products_infos = src.product.get_products_list(options, runner.cfg, logger)

    # Construct the list of directories to suppress
    l_dir_to_suppress = []
    if options.all:
        l_dir_to_suppress += (get_source_directories(products_infos, 
                                            options.sources_without_dev) +
                             get_build_directories(products_infos) + 
                             get_install_directories(products_infos))
    else:
        if options.install:
            l_dir_to_suppress += get_install_directories(products_infos)
        
        if options.build:
            l_dir_to_suppress += get_build_directories(products_infos)
            
        if options.sources or options.sources_without_dev:
            l_dir_to_suppress += get_source_directories(products_infos, 
                                                options.sources_without_dev)
    
    if len(l_dir_to_suppress) == 0:
        logger.write(src.printcolors.printcWarning(_("Nothing to suppress\n")))
        logger.write(_("""\
Please specify what you want to suppress:
try 'sat --help clean' and 'sat clean ... --products ... --sources --build --install
"""))
        return
    
    # Check with the user if he really wants to suppress the directories
    if not runner.options.batch:
        logger.write(_("Remove the following directories ?\n"), 1)
        for directory in l_dir_to_suppress:
            logger.write("  %s\n" % directory, 1)
        rep = input(_("Are you sure you want to continue? [Yes/No] "))
        if rep.upper() != _("YES"):
            return 0
    
    # Suppress the list of paths
    suppress_directories(l_dir_to_suppress, logger)
    
    return 0
