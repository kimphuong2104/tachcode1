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


class MigrateUserViews(object):
    """
    Migrate filter conditions in user views to new schema.
    """

    __auth_persno__ = "$(persno)"

    def run(self):
        all_user_views = UserView.Query()

        with transaction.Transaction():
            for user_view in all_user_views:
                self.migrate(user_view)

        protocol.logMessage("updated {} user views".format(len(all_user_views)))

    def migrate(self, user_view):
        condition = json.loads(user_view.GetText(user_view.__condition_attr__))
        roles = condition.get("roles", False)
        users = condition.get("users", [])
        new_users = set(users).difference(
            [
                self.__auth_persno__,
            ]
        )

        if user_view.subject_type == "Person":
            new_users = new_users.difference(
                [
                    user_view.subject_id,
                ]
            )

        condition.update(
            {
                # initialize new fields
                "my_personal": self.__auth_persno__ in users,
                "my_roles": roles,
                "substitutes": True,
                "user_personal": True,
                "user_roles": roles,
                # remove logged-in user from "users"
                "users": list(new_users),
            }
        )
        if "roles" in list(condition):
            # delete obsolete field
            del condition["roles"]
        # ignore others (types, contexts, deadline)
        user_view.SetText(user_view.__condition_attr__, json.dumps(condition))


pre = []
post = [MigrateUserViews]

if __name__ == "__main__":
    MigrateUserViews().run()
