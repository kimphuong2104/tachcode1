from __future__ import absolute_import

from cdb.objects.org import User
from cdb.platform import gui


class UserCatalog(gui.CDBCatalog):
    def handleSelection(self, selected_objects):
        objects = [
            User._FromObjectHandle(so)  # pylint: disable=protected-access
            for so in selected_objects
        ]
        self.setValue(
            "system:description", ";".join([obj.GetDescription() for obj in objects])
        )
