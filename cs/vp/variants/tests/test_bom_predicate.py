import unittest

from cdb.testcase import RollbackTestCase

from cs.vp import products
from cs.vp import items
from cs.vp import variants
from cs.vp import bom
from cs.vp.variants import filter as bom_filter


# SQL> SELECT cdb_object_id, code, name_de FROM cdbvp_product
# cdb_object_id                       |code                |name_de             |
# ------------------------------------+--------------------+--------------------+
# b637b76e-ca74-11e5-8bc0-cc3d8239ce24|TEST                |                    |
#
# SQL> SELECT id, name_de FROM cdbvp_property where product_object_id='b637b76e-ca74-11e5-8bc0-cc3d8239ce24'
# id|name_de|
# --+-------+
# 52|AA     |
# 50|A      |
# 51|AB     |
# 54|B      |
# 55|C      |
# 362|B1     |
# 363|B2     |
#
# SQL> select p.id, p.name_de, ed.value, ed.value_txt_de from cdbvp_enum_def ed INNER JOIN cdbvp_property p ON p.id=ed.id AND p.product_object_id=ed.product_object_id where p.product_object_id='b637b76e-ca74-11e5-8bc0-cc3d8239ce24'
# id|name_de|value|value_txt_de|
# --+-------+-----+------------+
# 52|AA     |73   |AA1         |
# 52|AA     |75   |AA2         |
# 52|AA     |77   |AA3         |
# 51|AB     |63   |AB1         |
# 51|AB     |65   |AB2         |
# 362|B1     |116  |1           |
# 362|B1     |118  |2           |
# 362|B1     |120  |3           |
# 362|B1     |122  |5           |
# 362|B1     |124  |8           |
# 362|B1     |126  |13          |
# 362|B1     |128  |21          |
# 363|B2     |0    |0           |
# 363|B2     |1    |1           |
#
# SQL> select expression, baugruppe, b_index, teilenummer from cdbvp_bom_predicate where cdb_classname='cdbvp_bom_string_predicate' and product_object_id='b637b76e-ca74-11e5-8bc0-cc3d8239ce24'
# expression |baugruppe|b_index|teilenummer|
# -----------+---------+-------+-----------+
# AB == "AB1"|9504558  |       |9502662    |
# bool(AB)   |9504558  |       |9502659    |
# bool(C)    |9504558  |       |9502661    |
# bool(C)    |9504558  |       |9502663    |
# B2 == 1    |9504558  |       |9502658    |
# B1 % 2 == 0|9504558  |       |9502660    |

def setup():
    from cdb import testcase
    testcase.run_level_setup()


# Tests
class test_bom_predicate(RollbackTestCase):

    def setUp(self):
        def fixture_installed():
            try:
                import cs.vptests
                return True
            except ImportError:
                return False

        if not fixture_installed():
            raise unittest.SkipTest("Fixture package cs.vptests not installed")

        super(test_bom_predicate, self).setUp()

        product = products.Product.ByKeys(
            cdb_object_id="b637b76e-ca74-11e5-8bc0-cc3d8239ce24")
        if not product:
            raise Exception(
                "Cannot find test data. Fixture package cs.vptests required.")
        self.product = product
        self.item = items.Item.ByKeys(teilenummer="9504558", t_index="")

    def _perform_test(self, props, teilenummer, expected):
        variant = variants.ProductVariant.CreateVariant(
            props,
            product_object_id=self.product.cdb_object_id
        )
        variant_filter = bom_filter.VariantBOMFilter(
            self.product.cdb_object_id,
            variant.id
        )
        bomitem = bom.AssemblyComponent.ByKeys(baugruppe="9504558", b_index="", teilenummer=teilenummer)
        assert bomitem, "Cannot find test data. Fixture package cs.vptests required."

        result = variant_filter.eval(
            bomitem.baugruppe, bomitem.b_index,
            bomitem.teilenummer, bomitem.t_index,
            bomitem.variante, bomitem.position
        )
        self.assertIs(result, expected)

    def test_bool_predicate_on_bool_variant(self):
        """For a variant which evaluates to true the predicate bool(C) should be true"""
        self._perform_test(
            props={55: True},
            teilenummer="9502661",
            expected=True
        )

    def test_bool_predicate_on_value_variant(self):
        """For a variant which evaluates to a value the predicate bool(AB) should be true"""
        self._perform_test(
            props={51: 63},
            teilenummer="9502659",
            expected=True
        )

    def test_bool_predicate_on_empty_variant(self):
        """For a variant which doesn't evaluate the predicate bool(C) should be false"""
        self._perform_test(
            props={51: 63},
            teilenummer="9502661",
            expected=False
        )

    def test_numeric_predicate_true(self):
        """For a variant which evaluate to 2 the predicate B1 % 2 == 0 should be true"""
        self._perform_test(
            props={362: 118},
            teilenummer="9502660",
            expected=True
        )

    def test_numeric_predicate_false(self):
        """For a variant which evaluate to 13 the predicate B1 % 2 == 0 should be false"""
        self._perform_test(
            props={362: 126},
            teilenummer="9502660",
            expected=False
        )

    def test_boolean_predicate_true(self):
        """For a variant which evaluate to 1 the predicate B2 == 1 should be true"""
        self._perform_test(
            props={363: 1},
            teilenummer="9502658",
            expected=True
        )

    def test_boolean_predicate_false(self):
        """For a variant which evaluate to 0 the predicate B2 == 1 should be false"""
        self._perform_test(
            props={363: 0},
            teilenummer="9502658",
            expected=False
        )


# Allow running this testfile directly
if __name__ == "__main__":
    unittest.main()
