from cdb.testcase import RollbackTestCase
from cs.platform.web.root import Root
from webtest import TestApp as Client

from cs.vp.bom.tests import (
    generateComponent,
    generateAssemblyComponent,
)
from cs.vp.bom.web.bommanager.internal import (
    _make_item_pk_statement,
    BommanagerInternalModel,
)
from cs.vp.items.tests import generateItem
from cs.vp.bom import enhancement


class TestRedirect(RollbackTestCase):
    def setUp(self):
        super(TestRedirect, self).setUp()
        self.item_with_index = generateItem(t_index="a")
        self.item_without_index = generateItem()

    def test_part_redirect_with_index(self):
        c = Client(Root())
        teilenummer = self.item_with_index.teilenummer
        index = self.item_with_index.t_index
        response = c.get(
            "/internal/bommanager/redirect/part/%s@%s" % (teilenummer, index)
        )
        self.assertEqual(302, response.status_int)
        self.assertEqual(
            "http://localhost/info/part/%s@%s" % (teilenummer, index),
            response.headers["Location"],
        )

    def test_part_redirect_without_index(self):
        c = Client(Root())
        teilenummer = self.item_without_index.teilenummer
        index = self.item_without_index.t_index
        response = c.get(
            "/internal/bommanager/redirect/part/%s@%s" % (teilenummer, index)
        )
        self.assertEqual(302, response.status_int)
        self.assertEqual(
            "http://localhost/info/part/%s@" % teilenummer, response.headers["Location"]
        )


class TestBomInfo(RollbackTestCase):
    def setUp(self):
        super(TestBomInfo, self).setUp()
        self.item_with_index = generateItem(t_index="a")
        self.additional_item_with_index = generateItem(t_index="b")
        self.assembly_component = generateAssemblyComponent(
            self.item_with_index, self.additional_item_with_index
        )

    def test_make_item_pk_statement_single_db_object(self):
        self.assertEqual(
            _make_item_pk_statement([self.item_with_index]),
            "(teilenummer='%s' AND t_index='%s')"
            % (self.item_with_index.teilenummer, self.item_with_index.t_index),
        )


def are_bom_items_equal(bom_item_a, bom_item_b):
    for each in [
        "teilenummer",
        "t_index",
        "baugruppe",
        "b_index",
        "variante",
        "position",
        "cdbvp_positionstyp",
        "cdbvp_has_condition",
    ]:
        if not bom_item_a[each] == bom_item_b[each]:
            return False

    return True
