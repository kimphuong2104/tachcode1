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
        protocol.logMessage("reverting patches in {}".format(self.__tables__))

        module = modules.Module.ByKeys("cs.actions")
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
                # pylint: disable=broad-except
                except Exception:  # nosec # noqa: E722
                    pass  # Already there

            if reverted:
                protocol.logMessage(
                    "  {}: reverted {} patches".format(module.module_id, reverted)
                )


pre = []
post = [EnsureTaskContexts]
