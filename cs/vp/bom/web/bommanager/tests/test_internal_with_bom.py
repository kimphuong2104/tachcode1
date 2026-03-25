import json

from cdb import constants
from cdb import tools
from cdb.objects import operations
from cdb.objects.org import Organization
from cdb.testcase import RollbackTestCase
from cs.platform.web.root import Root
from webtest import TestApp as Client

from cs.vp import bom, items
from cs.vp.bom.tests import generateAssemblyComponent
from cs.vp.bom.web import utils as bom_web_utils
from cs.vp.bom.web.bommanager import utils as bommanager_utils
from cs.vp.bom.web.bommanager.tests.test_internal import (
    create_bommanager_internal_model,
)
from cs.vp.items.tests import generateItem
from cs.vp.variants.tests import (
    generateProductWithEnumValues,
    generateVariantForProduct,
)
from tests.accepttests.steps.common import generateStringPredicate


class BomCreateTest(RollbackTestCase):
    def create_ebom(self):
        # ebom
        #  |---- ebom-a
        #  |      |---- ebom-c
        #  |      |---- ebom-d
        #  |---- ebom-b
        #  |      |---- ebom-c
        #  |      |---- ebom-d
        #  |---- ebom-c
        #  |---- ebom-d

        self.ebom = generateItem(benennung="EBOM")
        self.maxbom = self.ebom
        self.ebom_a = generateItem(benennung="ebom_a")
        self.ebom_b = generateItem(benennung="ebom_b")
        self.ebom_c = generateItem(benennung="ebom_c")
        self.ebom_d = generateItem(benennung="ebom_d")

        self.bom_item_a = generateAssemblyComponent(self.ebom, self.ebom_a)
        self.bom_item_b = generateAssemblyComponent(self.ebom, self.ebom_b)
        self.bom_item_a_c = generateAssemblyComponent(self.ebom_a, self.ebom_c)
        generateAssemblyComponent(self.ebom_a, self.ebom_d)
        generateAssemblyComponent(self.ebom_b, self.ebom_c)
        generateAssemblyComponent(self.ebom_b, self.ebom_d)
        self.bom_item_c = generateAssemblyComponent(self.ebom, self.ebom_c)
        self.bom_item_d = generateAssemblyComponent(self.ebom, self.ebom_d)

    def create_mbom(self):
        # mbom
        #  |---- mbom-1
        #  |      |---- ebom-a
        #  |      |      |---- ebom-c
        #  |      |      |---- ebom-d
        #  |      |---- ebom-b
        #  |             |2x-- ebom-c
        #  |             |---- ebom-d
        #  |---- ebom-c
        #  |---- ebom-d

        ebom = items.Item.ByKeys(
            teilenummer=self.ebom.teilenummer, t_index=self.ebom.t_index
        )

        mbom = ebom.generate_mbom(question_copy_stl_relship_1st_level=1)
        if mbom:
            self.mbom = mbom
            self.mbom_1 = generateItem(
                type_object_id=bom.get_mbom_bom_type().cdb_object_id, benennung="mbom_1"
            )
            self.mbom_comp_1 = generateAssemblyComponent(self.mbom, self.mbom_1)

            for teilenummer, t_index in [
                (self.ebom_a.teilenummer, self.ebom_a.t_index),
                (self.ebom_b.teilenummer, self.ebom_b.t_index),
            ]:
                comp = bom.AssemblyComponent.ByKeys(
                    baugruppe=self.mbom.teilenummer,
                    b_index=self.mbom.t_index,
                    teilenummer=teilenummer,
                    t_index=t_index,
                )
                if comp:
                    operations.operation(
                        constants.kOperationCopy,
                        comp,
                        baugruppe=self.mbom_1.teilenummer,
                        b_index=self.mbom_1.t_index,
                    )
                    operations.operation(constants.kOperationDelete, comp)
        else:
            self.mbom = None
            self.mbom_1 = None
            self.mbom_comp_1 = None

    def setUp(self):
        super(BomCreateTest, self).setUp()
        self.create_ebom()
        self.create_mbom()


class TestInternalWithBomCreateTest(BomCreateTest):
    def setUp(self):
        super(TestInternalWithBomCreateTest, self).setUp()

        self.test_org_1 = operations.operation(
            constants.kOperationNew, Organization, name="test org 1", org_type="Partner"
        )
        self.test_org_2 = operations.operation(
            constants.kOperationNew, Organization, name="test org 2", org_type="Partner"
        )
        self.test_org_3 = operations.operation(
            constants.kOperationNew, Organization, name="test org 3", org_type="Partner"
        )

    def make_request(self, bom_enhancement_data=None):
        c = Client(Root())

        data = {
            "parents": [
                {
                    "teilenummer": self.ebom.teilenummer,
                    "t_index": self.ebom.t_index,
                }
            ]
        }
        if bom_enhancement_data is not None:
            data["bomEnhancementData"] = bom_enhancement_data

        response = c.post(
            f"/internal/bommanager/{self.ebom.cdb_object_id}/+boms", json.dumps(data)
        )

        return response.json

    def prepare_dublicated_bom_positions(self):
        # ebom
        #  |---- ebom-a
        #  |      |---- ebom-c
        #  |      |---- ebom-d
        #  |---- ebom-b
        #  |      |---- ebom-c
        #  |      |---- ebom-d
        #  |---- ebom-c
        #  |---- ebom-d (default site)
        #  |---- ebom-d-2 (test site 1)
        #  |---- ebom-d-3 (test site 2)

        self.ebom_d_2 = generateItem(benennung="ebom_d_2")
        self.bom_item_d_2 = generateAssemblyComponent(
            self.ebom, self.ebom_d_2, position=self.bom_item_d.position
        )

        self.ebom_d_3 = generateItem(benennung="ebom_d_3")
        self.bom_item_d_3 = generateAssemblyComponent(
            self.ebom, self.ebom_d_3, position=self.bom_item_d.position
        )

        self.ebom_d_2.site_object_id = self.test_org_1.cdb_object_id
        self.ebom_d_3.site_object_id = self.test_org_2.cdb_object_id

    def test_site_bom_filter_no_site(self):
        "If no site is given to filter the result, all positions are included in the result"
        self.prepare_dublicated_bom_positions()

        model = create_bommanager_internal_model(self.ebom.cdb_object_id)
        info = model.bom_info([self.ebom])[0]

        all_pkeys = [(i["teilenummer"], i["t_index"]) for i in info]
        self.assertIn((self.ebom_d.teilenummer, self.ebom_d.t_index), all_pkeys)
        self.assertIn((self.ebom_d_2.teilenummer, self.ebom_d_2.t_index), all_pkeys)
        self.assertIn((self.ebom_d_3.teilenummer, self.ebom_d_3.t_index), all_pkeys)

    def test_site_bom_filter_different_site(self):
        """
        If a site is given to filter the result, and no position is assigned to that site, only for the fallback site
        (empty site) the from_other_site flag is False.
        """

        self.prepare_dublicated_bom_positions()

        model = create_bommanager_internal_model(
            self.ebom.cdb_object_id
        )
        model.bom_enhancement.initialize_plugins_with_rest_data(
            {"cs.vp.siteBomAttributePlugin": {"cdb_object_id": self.test_org_3.cdb_object_id}})

        info = model.bom_info([self.ebom])[0]

        from_other_site = [
            (i["teilenummer"], i["t_index"]) for i in info if i["from_other_site"]
        ]
        self.assertNotIn(
            (self.ebom_d.teilenummer, self.ebom_d.t_index), from_other_site
        )
        self.assertIn(
            (self.ebom_d_2.teilenummer, self.ebom_d_2.t_index), from_other_site
        )
        self.assertIn(
            (self.ebom_d_3.teilenummer, self.ebom_d_3.t_index), from_other_site
        )

    def test_site_bom_filter_different_site2(self):
        """
        Test for MatchSelectedSitesFilter with site alternatives and fallback logic.
        If a site is given to filter the result, and no position is assigned to that site, only for the fallback site
        the from_other_site flag is False.
        """

        self.prepare_dublicated_bom_positions()

        # setup MatchSelectedSitesFilter
        prev_filter_cls = bommanager_utils._filter_class
        tmp_filter = tools.getObjectByName(
            "cs.vp.bom.web.bommanager.utils.MatchSelectedSitesFilter"
        )
        bommanager_utils._filter_class = tmp_filter

        try:
            model = create_bommanager_internal_model(
                self.ebom.cdb_object_id
            )
            model.bom_enhancement.initialize_plugins_with_rest_data(
                {"cs.vp.siteBomAttributePlugin": {"cdb_object_id": self.test_org_3.cdb_object_id}})

            info = model.bom_info([self.ebom])[0]

            from_other_site = [
                (i["teilenummer"], i["t_index"]) for i in info if i["from_other_site"]
            ]
            self.assertNotIn(
                (self.ebom_d.teilenummer, self.ebom_d.t_index), from_other_site
            )
            self.assertIn(
                (self.ebom_d_2.teilenummer, self.ebom_d_2.t_index), from_other_site
            )
            self.assertIn(
                (self.ebom_d_3.teilenummer, self.ebom_d_3.t_index), from_other_site
            )
        finally:
            bommanager_utils._filter_class = prev_filter_cls

    def test_site_bom_filter_same_site(self):
        """
        If a site is given to filter the result, non matching positions should be marked with the from_other_site Flag.
        Matching positions are positions with an empty site or with the given site.
        Note that the StandardSiteFilter does not support the alternatives logic. So if a position with an empty site
        and a position with an exactly matching site exists, for both the from_other_site Flag is False.
        """

        self.prepare_dublicated_bom_positions()

        model = create_bommanager_internal_model(
            self.ebom.cdb_object_id
        )
        model.bom_enhancement.initialize_plugins_with_rest_data(
            {"cs.vp.siteBomAttributePlugin": {"cdb_object_id": self.test_org_1.cdb_object_id}})

        info = model.bom_info([self.ebom])[0]

        # nothing should be filered out
        all_pkeys = [(i["teilenummer"], i["t_index"]) for i in info]
        self.assertIn((self.ebom_d.teilenummer, self.ebom_d.t_index), all_pkeys)
        self.assertIn((self.ebom_d_2.teilenummer, self.ebom_d_2.t_index), all_pkeys)
        self.assertIn((self.ebom_d_3.teilenummer, self.ebom_d_3.t_index), all_pkeys)

        # ... but positions from other sites should be marked by the from_other_site flag
        from_other_site = [
            (i["teilenummer"], i["t_index"]) for i in info if i["from_other_site"]
        ]
        self.assertNotIn(
            (self.ebom_d.teilenummer, self.ebom_d.t_index), from_other_site
        )
        self.assertNotIn(
            (self.ebom_d_2.teilenummer, self.ebom_d_2.t_index), from_other_site
        )
        self.assertIn(
            (self.ebom_d_3.teilenummer, self.ebom_d_3.t_index), from_other_site
        )

    def test_site_bom_filter_same_site2(self):
        """
        Test for MatchSelectedSitesFilter with site alternatives and fallback logic.
        If a site is given to filter the result, and a position with multiple parts has one part assigned to that site,
        the other parts are marked by the from_other_site flag.
        """

        self.prepare_dublicated_bom_positions()

        # setup MatchSelectedSitesFilter
        prev_filter_cls = bommanager_utils._filter_class
        tmp_filter = tools.getObjectByName(
            "cs.vp.bom.web.bommanager.utils.MatchSelectedSitesFilter"
        )
        bommanager_utils._filter_class = tmp_filter

        try:
            model = create_bommanager_internal_model(
                self.ebom.cdb_object_id
            )
            model.bom_enhancement.initialize_plugins_with_rest_data(
                {"cs.vp.siteBomAttributePlugin": {"cdb_object_id": self.test_org_1.cdb_object_id}})

            info = model.bom_info([self.ebom])[0]

            # nothing should be filered out
            all_pkeys = [(i["teilenummer"], i["t_index"]) for i in info]
            self.assertIn((self.ebom_d.teilenummer, self.ebom_d.t_index), all_pkeys)
            self.assertIn((self.ebom_d_2.teilenummer, self.ebom_d_2.t_index), all_pkeys)
            self.assertIn((self.ebom_d_3.teilenummer, self.ebom_d_3.t_index), all_pkeys)

            # ... but positions from other sites should be marked by the from_other_site flag
            from_other_site = [
                (i["teilenummer"], i["t_index"]) for i in info if i["from_other_site"]
            ]
            self.assertIn(
                (self.ebom_d.teilenummer, self.ebom_d.t_index), from_other_site
            )
            self.assertNotIn(
                (self.ebom_d_2.teilenummer, self.ebom_d_2.t_index), from_other_site
            )
            self.assertIn(
                (self.ebom_d_3.teilenummer, self.ebom_d_3.t_index), from_other_site
            )

        finally:
            bommanager_utils._filter_class = prev_filter_cls

    def test_site_bom_filter_no_matching_site(self):
        """
        If a site is given to filter the result, no positions match this site and there is no fallback site,
        all positions should be marked with the from_other_site Flag.
        """
        self.prepare_dublicated_bom_positions()

        self.ebom_d.site_object_id = self.test_org_3.cdb_object_id

        different_org = operations.operation(
            constants.kOperationNew,
            Organization,
            name="different org",
            org_type="Partner",
        )

        model = create_bommanager_internal_model(
            self.ebom.cdb_object_id
        )
        model.bom_enhancement.initialize_plugins_with_rest_data(
            {"cs.vp.siteBomAttributePlugin": {"cdb_object_id": different_org.cdb_object_id}})


        info = model.bom_info([self.ebom])[0]

        from_other_site = [
            (i["teilenummer"], i["t_index"]) for i in info if i["from_other_site"]
        ]
        self.assertIn((self.ebom_d.teilenummer, self.ebom_d.t_index), from_other_site)
        self.assertIn(
            (self.ebom_d_2.teilenummer, self.ebom_d_2.t_index), from_other_site
        )
        self.assertIn(
            (self.ebom_d_3.teilenummer, self.ebom_d_3.t_index), from_other_site
        )

    def test_site_bom_filter_no_matching_site2(self):
        """
        Test for MatchSelectedSitesFilter with site alternatives and fallback logic.
        If a site is given to filter the result, no positions match this site and there is no fallback site,
        all positions should be marked with the from_other_site Flag.
        """
        self.prepare_dublicated_bom_positions()

        self.ebom_d.site_object_id = self.test_org_3.cdb_object_id

        different_org = operations.operation(
            constants.kOperationNew,
            Organization,
            name="different org",
            org_type="Partner",
        )

        # setup MatchSelectedSitesFilter
        prev_filter_cls = bommanager_utils._filter_class
        tmp_filter = tools.getObjectByName(
            "cs.vp.bom.web.bommanager.utils.MatchSelectedSitesFilter"
        )
        bommanager_utils._filter_class = tmp_filter
        try:
            model = create_bommanager_internal_model(
                self.ebom.cdb_object_id
            )
            model.bom_enhancement.initialize_plugins_with_rest_data(
                {"cs.vp.siteBomAttributePlugin": {"cdb_object_id": different_org.cdb_object_id}})

            info = model.bom_info([self.ebom])[0]

            from_other_site = [
                (i["teilenummer"], i["t_index"]) for i in info if i["from_other_site"]
            ]
            self.assertIn(
                (self.ebom_d.teilenummer, self.ebom_d.t_index), from_other_site
            )
            self.assertIn(
                (self.ebom_d_2.teilenummer, self.ebom_d_2.t_index), from_other_site
            )
            self.assertIn(
                (self.ebom_d_3.teilenummer, self.ebom_d_3.t_index), from_other_site
            )
        finally:
            bommanager_utils._filter_class = prev_filter_cls

    def test_site_bom_filter_no_matching_site_with_forg(self):
        """
        Test for MatchSelectedSitesFilter with site alternatives and fallback logic.
        While the 'forg' property is set to a fallback site and another site is given to filter the result,
        no positions match this site and there are position that have the fallback site assigned, those are not filtered out.
        """
        self.prepare_dublicated_bom_positions()

        fallback_site = self.test_org_1
        bom_web_utils.fallback_site = fallback_site.cdb_object_id

        self.ebom_d.site_object_id = fallback_site.cdb_object_id

        different_org = operations.operation(
            constants.kOperationNew,
            Organization,
            name="different org",
            org_type="Partner",
        )

        # setup MatchSelectedSitesFilter
        prev_filter_cls = bommanager_utils._filter_class
        tmp_filter = tools.getObjectByName(
            "cs.vp.bom.web.bommanager.utils.MatchSelectedSitesFilter"
        )
        bommanager_utils._filter_class = tmp_filter

        try:
            model = create_bommanager_internal_model(
                self.ebom.cdb_object_id
            )
            model.bom_enhancement.initialize_plugins_with_rest_data(
                {"cs.vp.siteBomAttributePlugin": {"cdb_object_id": different_org.cdb_object_id}})

            info = model.bom_info([self.ebom])[0]

            from_other_site = [
                (i["teilenummer"], i["t_index"]) for i in info if i["from_other_site"]
            ]
            self.assertNotIn(
                (self.ebom_d.teilenummer, self.ebom_d.t_index), from_other_site
            )
            self.assertNotIn(
                (self.ebom_d_2.teilenummer, self.ebom_d_2.t_index), from_other_site
            )
            self.assertIn(
                (self.ebom_d_3.teilenummer, self.ebom_d_3.t_index), from_other_site
            )
        finally:
            bom_web_utils.fallback_site = ""
            bommanager_utils._filter_class = prev_filter_cls

    def test_cs_vp_variants_filter(self):
        product = generateProductWithEnumValues()
        variant = generateVariantForProduct(product)
        generateStringPredicate(self.bom_item_a, product, "False")

        response_json = self.make_request(
            bom_enhancement_data={
                "cs.vp.variantFilterProductContext": {
                    "product_object_id": variant["product_object_id"],
                },
                "cs.vp.variantFilterContext": {
                    "variant_id": variant["cdb_object_id"],
                },
            },
        )
        self.assertEqual(2, len(response_json))

        first_level = response_json[1]
        self.assertEqual(4, len(first_level))

        for each in first_level:
            expected_in_variant = True

            if each["teilenummer"] == self.bom_item_a.teilenummer:
                expected_in_variant = False

            self.assertEqual(expected_in_variant, each["in_variant"])


class MissingMappingSearch(BomCreateTest):
    def make_request(self):
        c = Client(Root())
        activeBomType = {"cdb_object_id": bom.get_mbom_bom_type().cdb_object_id}
        response = c.post(
            "/internal/bommanager/search/%s/+mapping" % (self.mbom.cdb_object_id),
            json.dumps({"activeBomType": activeBomType}),
        )
        return response.json

    def test_pure_mbom(self):
        # clean and correct mbom
        # mbom
        #  |---- mbom-1 <----------------- pure mbom, no mapping tag (default)
        #  |      |---- ebom-a
        #  |      |      |---- ebom-c
        #  |      |      |---- ebom-d
        #  |      |---- ebom-b
        #  |             |---- ebom-c
        #  |             |---- ebom-d
        #  |---- ebom-c
        #  |---- ebom-d
        result = self.make_request()
        self.assertListEqual([], result)

    def test_ebom_without_mapping_tag_and_type_ebom(self):
        # mbom
        #  |---- mbom-1
        #  |      |---- ebom-a <--- mbom_mapping_tag='', type_object_id='',depends_on=None
        #  |      |      |---- ebom-c
        #  |      |      |---- ebom-d
        #  |      |---- ebom-b
        #  |             |---- ebom-c
        #  |             |---- ebom-d
        #  |---- ebom-c
        #  |---- ebom-d
        comp = bom.AssemblyComponent.ByKeys(
            baugruppe=self.mbom_1.teilenummer,
            b_index=self.mbom_1.t_index,
            teilenummer=self.ebom_a.teilenummer,
            t_index=self.ebom_a.t_index,
        )
        comp.mbom_mapping_tag = None
        result = self.make_request()

        self.assertEqual(len(result), 1)
        path = result[0]

        self.assertEqual(path[0]["teilenummer"], self.mbom.teilenummer)
        self.assertEqual(path[1]["teilenummer"], self.mbom_1.teilenummer)
        self.assertEqual(path[2]["teilenummer"], self.ebom_a.teilenummer)

    def test_ebom_without_mapping_tag_and_type_mbom(self):
        # mbom
        #  |---- mbom-1
        #  |      |---- ebom-a <--- mbom_mapping_tag='', type_object_id='mbom',depends_on='x'
        #  |      |      |---- ebom-c
        #  |      |      |---- ebom-d
        #  |      |---- ebom-b
        #  |             |---- ebom-c
        #  |             |---- ebom-d
        #  |---- ebom-c
        #  |---- ebom-d
        comp = bom.AssemblyComponent.ByKeys(
            baugruppe=self.mbom_1.teilenummer,
            b_index=self.mbom_1.t_index,
            teilenummer=self.ebom_a.teilenummer,
            t_index=self.ebom_a.t_index,
        )
        comp.mbom_mapping_tag = None
        comp.Item.cdb_depends_on = "x"
        comp.Item.type_object_id = bom.get_mbom_bom_type().cdb_object_id
        result = self.make_request()

        self.assertEqual(len(result), 1)
        path = result[0]

        self.assertEqual(path[0]["teilenummer"], self.mbom.teilenummer)
        self.assertEqual(path[1]["teilenummer"], self.mbom_1.teilenummer)
        self.assertEqual(path[2]["teilenummer"], self.ebom_a.teilenummer)

    def test_ebom_in_ebom_without_mapping_tag(self):
        # mbom
        #  |---- mbom-1
        #  |      |---- ebom-a
        #  |      |      |---- ebom-c  <--------------- removed mbom_mapping_tag
        #  |      |      |---- ebom-d
        #  |      |---- ebom-b
        #  |             |---- ebom-c
        #  |             |---- ebom-d
        #  |---- ebom-c
        #  |---- ebom-d
        comp = bom.AssemblyComponent.ByKeys(
            baugruppe=self.ebom_a.teilenummer,
            b_index=self.ebom_a.t_index,
            teilenummer=self.bom_item_a_c.teilenummer,
            t_index=self.bom_item_a_c.t_index,
        )
        comp.mbom_mapping_tag = None
        result = self.make_request()
        self.assertListEqual([], result)

    def test_ebom_in_mbom_without_mapping_tag(self):
        # mbom
        #  |---- mbom-1
        #  |      |---- ebom-a
        #  |      |      |---- ebom-c
        #  |      |      |---- ebom-d
        #  |      |---- ebom-b
        #  |             |---- ebom-c
        #  |             |---- ebom-d
        #  |---- ebom-c
        #  |---- ebom-d  <--------------- removed mbom_mapping_tag
        comp = bom.AssemblyComponent.ByKeys(
            baugruppe=self.mbom.teilenummer,
            b_index=self.mbom.t_index,
            teilenummer=self.ebom_d.teilenummer,
            t_index=self.ebom_d.t_index,
        )
        comp.mbom_mapping_tag = None
        result = self.make_request()

        self.assertEqual(len(result), 1)
        path = result[0]

        self.assertEqual(path[0]["teilenummer"], self.mbom.teilenummer)
        self.assertEqual(path[1]["teilenummer"], self.ebom_d.teilenummer)
