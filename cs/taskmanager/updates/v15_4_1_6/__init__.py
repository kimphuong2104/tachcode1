# coding: utf-8

from cdb import transaction
from cdb.comparch import get_dev_namespace, protocol
from cs.taskmanager.conf import Attribute


class DeleteTagMappings(object):
    """
    Delete attribute mappings for ``cs_tasks_col_tags`` because they're now
    hard-coded ("managed") by |cs.taskmanager|.
    """

    __tags_col_oid__ = "01e638a1-3dec-11e6-b6df-00aa004d0001"

    def _get_mapping(self):
        return Attribute.KeywordQuery(column_object_id=self.__tags_col_oid__)

    def _delete_attribute(self, attr):
        if get_dev_namespace() != "cs":
            attr.Delete()  # only in customer instances

            protocol.logMessage(
                "removed obsolete attribute mapping "
                "{0.TaskClass.classname}.{0.propname}".format(attr)
            )

    def run(self):
        with transaction.Transaction():
            for attr in self._get_mapping():
                self._delete_attribute(attr)


pre = []
post = [DeleteTagMappings]

if __name__ == "__main__":
    DeleteTagMappings().run()
