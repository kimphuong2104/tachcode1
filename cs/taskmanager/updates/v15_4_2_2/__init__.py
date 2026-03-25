# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2019 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

__revision__ = "$Id: "
__docformat__ = "restructuredtext en"

import json

from cdb import transaction
from cdb.comparch import protocol
from cs.taskmanager.user_views import UserView


class InitializeAbsenceFilter(object):
    """
    Initialize filter condition "consider_absence" in user views with
    ``True``.
    """

    def run(self):
        all_user_views = UserView.Query()

        with transaction.Transaction():
            for user_view in all_user_views:
                self.migrate(user_view)

    def migrate(self, user_view):
        condition = json.loads(user_view.GetText(user_view.__condition_attr__))
        if condition.get("consider_absence", None) is None:
            condition["consider_absence"] = True

            user_view.SetText(user_view.__condition_attr__, json.dumps(condition))
            protocol.logMessage("updated user view '{}'".format(user_view.name_en))


pre = []
post = [InitializeAbsenceFilter]


if __name__ == "__main__":
    InitializeAbsenceFilter().run()
