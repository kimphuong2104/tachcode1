# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com


from cdb.comparch import content, modules, protocol

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"


class EnsureTaskContexts:
    """Always re-insert new cs.taskmanager contexts"""

    __tables__ = [
        "cs_tasks_context_tree",
        "cs_tasks_context_tree_relships",
    ]

    def run(self):
        protocol.logMessage(f"reverting patches in {self.__tables__}")

        for module in modules.Module.Query("module_id LIKE 'cs.pcs.%'"):
            for table_name in self.__tables__:
                content_filter = content.ModuleContentFilter([table_name])
                mc = modules.ModuleContent(
                    module.module_id,
                    module.std_conf_exp_dir,
                    content_filter,
                )
                reverted = 0

                for mod_content in mc.getItems(table_name).values():
                    try:
                        mod_content.insertIntoDB()  # Effectively revert patch
                        reverted += 1
                    except Exception:  # nosec # noqa: E722
                        pass  # Already there

                if reverted:
                    protocol.logMessage(
                        f"  {module.module_id}: reverted {reverted} patches"
                    )


pre = []
post = [EnsureTaskContexts]
