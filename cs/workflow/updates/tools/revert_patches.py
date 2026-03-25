# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2019 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

from cdb.comparch import content
from cdb.comparch import modules
from cdb.comparch import protocol

__revision__ = "$Id: "
__docformat__ = "restructuredtext en"


def revert_deleted_patch(module_id, table, **kwargs):
    m = modules.Module.ByKeys(module_id)
    content_filter = content.ModuleContentFilter([table])
    mc = modules.ModuleContent(
        m.module_id,
        m.std_conf_exp_dir,
        content_filter
    )

    for mod_content in mc.getItems(table).values():
        mod_keys = {
            key: mod_content.getAttr(key)
            for key in list(kwargs)
        }
        if mod_keys == kwargs:
            try:
                # Effectively revert patch
                mod_content.insertIntoDB()
                protocol.logMessage(
                    "reverted DELETED patch "
                    "(module {}, table {}, keys {})".format(
                        module_id,
                        table,
                        kwargs
                    ),
                )
            except Exception as e:
                protocol.logError(
                    "could not revert DELETED patch "
                    "(module {}, table {}, keys {})".format(
                        module_id,
                        table,
                        kwargs
                    ),
                    details_longtext="{}".format(e),
                )
