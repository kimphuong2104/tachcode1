# !/usr/bin/env powerscript
# -*- python -*- coding: UTF-8 -*-
#
# Copyright (C) 2014 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

"""
Adds cdb file types supported as export file types by the hoops converter.
"""


__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

from cdb import constants
from cdb.objects.cdb_filetype import CDB_FileType
from cdb.platform.mom import SimpleArguments
from cdbwrapc import Operation


if __name__ == "__main__":

    FILE_TYPES = {
        "Hoops:HWF": {"ft_description": "Hoops Web Format",
                      "ft_std_suffix": ".hwf"},
        "Hoops:SCZ": {"ft_description": "Hoops:Stream Cache Zip",
                      "ft_std_suffix": ".scz"},
        "Hoops:XML": {"ft_description": "Hoops Model Map",
                      "ft_std_suffix": ".xml"},
        "PRC": {"ft_description": "Product Representation Compact",
                "ft_std_suffix": ".prc"},
        }

    DEFAULT_FT_ATTRS = {
        "ft_editable_fname": 1,
        "ft_genonlycad": 0,
        "ft_handle_dups": 0,
        "ft_indexable": 0,
        "ft_lock_policy": 0,
        "ft_mimetype": "",
        "ft_offeronimport": 0,
        "ft_preview_type": "",
        "ft_previewable": 0,
        "ft_scale_preview": 0,
        "ft_subtype": "",
        "cdb::argument.show_lock_message": "LOCK",
        "cdb::argument.dok_edit_mode": "None",
        "cdb::argument.dok_print_mode": "None",
        }

    for ft_name, ft_attrs in FILE_TYPES.items():
        if CDB_FileType.ByKeys(ft_name):
            print("The CDB file type '%s' already exists. Please ensure its compatibility "\
                "with the hoops module and converter!" % ft_name)
        else:
            print("Creating the CDB file type '%s'.." % ft_name)
            attrs = {"ft_name": ft_name}
            attrs.update(ft_attrs)
            attrs.update(DEFAULT_FT_ATTRS)
            op = Operation(constants.kOperationNew, "cdb_filetype", SimpleArguments(**attrs))
            op.run()
