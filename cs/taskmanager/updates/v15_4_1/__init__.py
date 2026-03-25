#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

from cdb import transaction
from cdb.comparch import get_dev_namespace, protocol
from cdb.platform.mom.entities import Class
from cdb.platform.mom.fields import DDDateField
from cs.taskmanager.conf import Attribute
from cs.taskmanager.updates import compile_headers


def _get_parent_classnames(leaf):
    """
    Returns set of classname ``leaf`` and all names of its parent classes.
    """
    parents = set()
    for parent in Class.KeywordQuery(classname=leaf):
        parents = parents.union(parent.getBaseClassNames())
    return {leaf}.union(parents)


class InitializeDeadline(object):
    """
    Initialize ``cs_tasks_class.deadline`` from legacy configuration (if
    existing).

    For each non-compatible deadline (e.g. not a native date attribute), log a
    warning.
    """

    __deadline_col_oid__ = "96e333a1-3deb-11e6-bec7-00aa004d0001"

    def _get_mapping(self):
        return Attribute.KeywordQuery(column_object_id=self.__deadline_col_oid__)

    def _is_date_attr(self, attr):
        # date field has to be configured in this class or one of its parents
        return (
            len(
                DDDateField.KeywordQuery(
                    classname=_get_parent_classnames(attr.TaskClass.classname),
                    field_name=attr.propname,
                )
            )
            == 1
        )

    def _init_deadline(self, attr):
        if self._is_date_attr(attr):
            attr.TaskClass.Update(deadline=attr.propname)

            if get_dev_namespace() != "cs":
                attr.Delete()  # only in customer instances

            protocol.logMessage(
                "{0.TaskClass.classname}.{0.propname} " "initialized.".format(attr)
            )
        else:
            protocol.logWarning(
                "{0.TaskClass.classname}.{0.propname} is not a native date "
                "attribute. Deadline not initialized.".format(attr)
            )

    def run(self):
        with transaction.Transaction():
            for attr in self._get_mapping():
                self._init_deadline(attr)

        compile_headers()


pre = []
post = [InitializeDeadline]
