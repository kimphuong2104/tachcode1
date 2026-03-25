import pytest

from cdb import ddl, sqlapi, testcase, util
from cs.pcs.costs.updates.v15_1_1 import InitSortableIDForCdbpcs_costsheet_prot


def setUpModule():
    "ensure DB connection is available"
    testcase.run_level_setup()


@pytest.mark.acceptance
class InitSortableIDIntegration(testcase.RollbackTestCase):
    __table_name__ = "cdbpcs_costsheet_prot"

    def _reload_table(self):
        util.tables.reload(self.__table_name__)
        return ddl.Table(self.__table_name__)

    def _add_column(self, column):
        table = self._reload_table()
        if not table.hasColumn(column.colname):
            table.addAttributes(column)

    def _drop_column(self, colname):
        table = self._reload_table()
        if table.hasColumn(colname):
            table.dropAttributes(colname)

    def _setup_table_scheme(self):
        sqlapi.SQLdelete(f"FROM {self.__table_name__}")
        self._drop_column("cdbprot_zaehler")
        self._add_column(ddl.Integer("cdbprot_zaehler"))
        table = self._reload_table()
        table.setPrimaryKey(ddl.PrimaryKey("cdbprot_zaehler"))
        self._drop_column("cdbprot_sortable_id")
        self._add_column(ddl.Char("cdbprot_sortable_id", 31, 0))

    def _update_table_entries(self, no_of_entries):
        count = 0
        for _ in range(no_of_entries):
            count += 1
            sqlapi.SQLinsert(
                f"INTO {self.__table_name__} (cdbprot_altstat, cdbprot_zaehler)"
                f" VALUES ({count}, {count})"
            )

    def test_project_initSortableID(self):
        self._setup_table_scheme()
        self._update_table_entries(6)
        InitSortableIDForCdbpcs_costsheet_prot().run()
        self.assertTrue(util.column_exists(self.__table_name__, "cdbprot_sortable_id"))
        self.assertFalse(util.column_exists(self.__table_name__, "cdbprot_zaehler"))
        sql_entries = sqlapi.RecordSet2(
            sql=f"SELECT * FROM {self.__table_name__} WHERE cdbprot_altstat IN ('2', '5')"
            f" ORDER BY cdbprot_sortable_id"
        )
        self.assertEqual(
            sql_entries[0].cdbprot_sortable_id, "0000000000000000000000000000002"
        )
        self.assertEqual(
            sql_entries[1].cdbprot_sortable_id, "0000000000000000000000000000005"
        )
