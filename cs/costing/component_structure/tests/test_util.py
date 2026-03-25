import mock
import unittest

from cs.costing.component_structure import util
from cs.pcs.projects.project_structure import util as pcs_util


class Utility(unittest.TestCase):
    @mock.patch.object(util, "get_flat_structure", return_value=(1, 2, 3))
    @mock.patch.object(util, "convert_records")
    @mock.patch.object(
        util, "resolve_structure", return_value=("foo_records", "foo_levels"))
    def test_resolve_component_structure(self, resolve_structure,
                                       convert_records, get_flat_structure):
        self.assertEqual(
            util.resolve_component_structure("foo", "getter", "req"),
            (convert_records.return_value, 1, 2, 3),
        )
        resolve_structure.assert_called_once_with(
            "foo", "cdbpco_calculation")
        convert_records.assert_called_once_with(
            "foo_records")
        get_flat_structure.assert_called_once_with(
            "foo_levels",
            convert_records.return_value,
            "getter", "req",
        )

    @mock.patch.object(util.sqlapi, "RecordSet2")
    @mock.patch.object(util.query_patterns, "load_query_pattern")
    @mock.patch.object(util, "get_query_pattern")
    def test_resolve_structure(self, get_query_pattern, load_query_pattern, recordSet2):
        "resolve structure"
        recordSet2.return_value = [
            mock.MagicMock(cdb_object_id="foo", table_name="bar", llevel="1")]
        # self.assertTupleEqual(
        #     util.resolve_structure("root", "table"),
        #     (
        #         recordSet2.return_value,
        #         [pcs_util.PCS_LEVEL("foo", "bar", 1)]
        #     ),
        # )
        # get_query_pattern.assert_called_once_with("structure", load_query_pattern)
        # recordSet2.assert_called_once()

    @mock.patch.object(util, "_get_oid_query_str", return_value = "foo_where")
    @mock.patch.object(util.sqlapi, "RecordSet2")
    @mock.patch.object(util, "get_query_pattern",
                       return_value=None)
    def test_resolve_structure_no_children(
            self, get_query_pattern, recordSet2, _get_oid_query_str
    ):
        "resolve structure without children"
        recordSet2.return_value = [
            mock.MagicMock(cdb_object_id="foo", table_name="bar", llevel="1")]
        self.assertTupleEqual(
            util.resolve_structure("A", "table"),
            (
                recordSet2.return_value,
                [pcs_util.PCS_LEVEL("foo", "bar", 1)]
            )
        )
        recordSet2.assert_called_once_with(
            sql="SELECT cdb_object_id, name, name AS ml_name_en,'' AS comp_object_id, '' AS quantity, " \
            "'' AS cdb_classname, 0 AS cloned, 0 as llevel, table as table_name FROM table " \
            "WHERE foo_where"
        )
        _get_oid_query_str.get_assert_called_once_with("A")


    @mock.patch.object(util, "_get_oid_query_str", side_effect=TypeError)
    @mock.patch.object(util, "get_query_pattern",
                       return_value=None)
    def test_resolve_resolve_structure_error(self, get_query_pattern,
                                   _get_oid_query_str):
        "fails if query cannot be constructed"
        with self.assertRaises(ValueError) as error:
            util.resolve_structure("A", "table")

        self.assertEqual(
            str(error.exception),
            "non-string oid value: A",
        )
        get_query_pattern.assert_called_once()
        _get_oid_query_str.assert_called_once_with(["A"])


    def test_convert_records(self):
        "converts records into cost_records"
        mock_record = mock.MagicMock(thead=mock.MagicMock(tname=""), table_name="foo")
        self.assertListEqual(
            util.convert_records([mock_record]),
            [pcs_util.PCS_RECORD("foo", mock_record)]
        )
        self.assertEqual(mock_record.thead.tname, "cdbpco_component")


    @mock.patch.object(util.sqlapi, "make_literals", side_effect=["1", "2", "3"])
    @mock.patch.object(util, "partition", return_value=[["1", "2"], ["3"]])
    def test_format_in_condition(self, partition, make_literals):
        "creates in condition for given query by partitioning oids in chunks"
        self.assertEqual(
            util.format_in_condition("{}", ["1", "2", "3"]),
            "1,2 OR 3"
        )
        partition.assert_called_once_with(["1", "2", "3"], 1000)
        make_literals.assert_has_calls([mock.call("1"), mock.call("2"), mock.call("3")])

    def test_format_in_condition_no_values(self):
        "returns 1=0 if no oids are given"
        self.assertEqual(
            util.format_in_condition("Not used", []),
            "1=0"
        )

    @mock.patch.object(util, "format_in_condition")
    @mock.patch.object(
        util.sqlapi, "RecordSet2",
        return_value=[mock.MagicMock(id="1"), mock.MagicMock(id="2"), mock.MagicMock(id="3")]
    )
    def test_filter_oid_with_read_access(self, recordSet2, format_in_condition):
        "returns only oids in list, where read access is granted"
        self.assertListEqual(
            ["1", "2", "3"],
            util.filter_oid_with_read_access(["1", "2", "3", "4"])
        )

        format_in_condition.assert_called_once_with("id in ({})", ["1", "2", "3", "4"])
        recordSet2.assert_called_once_with(
            "cdb_object", format_in_condition.return_value, access="read")

    @mock.patch.object(util, "format_in_condition", side_effect=TypeError)
    def test_filter_oid_with_read_access_error(self, format_in_condition):
        "raises ValueError when any oid is not a string value"
        with self.assertRaises(ValueError):
            util.filter_oid_with_read_access([1, 2, 3, 4])

    @mock.patch.object(util, "PCS_RECORD")
    @mock.patch.object(util, "format_in_condition")
    @mock.patch.object(util.sqlapi, "RecordSet2")
    @mock.patch.object(
        util, "_get_oids_by_relation",
        return_value=[("relation", ["1", "2", "3", "4"])]
    )
    def test_resolve_records(
        self, _get_oids_by_relation, recordSet2, format_in_condition, pcs_record
    ):
        "Resolves records based on given pcs_levels"
        rec_1 = mock.MagicMock()
        rec_1.thead.tname = "foo"
        rec_2 = mock.MagicMock()
        rec_2.thead.tname = "bar"
        rec_3 = mock.MagicMock()
        rec_3.thead.tname = "bam"
        rec_4 = mock.MagicMock()
        rec_4.thead.tname = "baz"
        recordSet2.return_value=[rec_1, rec_2, rec_3, rec_4]

        # self.assertListEqual(
        #     util.resolve_records("pcs_levels"),
        #     [
        #         pcs_record.return_value,
        #         pcs_record.return_value,
        #         pcs_record.return_value,
        #         pcs_record.return_value
        #     ]
        # )
        # _get_oids_by_relation.assert_called_once_with("pcs_levels")
        # q = "SELECT 'cdbpco_comp2component' as table_name, c.name, c.ml_name_en, c.cdb_classname, c.cloned, "\
        # "c2c.cdb_object_id, c2c.quantity, c2c.comp_object_id, c.cdb_tdate,c.different_part_costs,c.folder_object_id,c.hek,c.ml_name_cs,c.ml_name_es,c.ml_name_fr,c.ml_name_it,c.ml_name_ja,c.ml_name_ko,c.ml_name_pl,c.ml_name_pt,c.ml_name_tr,c.ml_name_zh,c.order_no,c.sort_order,c.cdb_cdate,c.cdb_cpersno,c.cdb_m2date,c.cdb_m2persno,c.cdb_mdate,c.cdb_mpersno,c.cdb_tpersno,c.cost_unit,c.costplant_object_id,c.curr_object_id,c.fek,c.machine_object_id,c.material_object_id,c.mek,c.mengeneinheit,c.subject_id,c.subject_type,c.t_index,c.technology_id,c.teilenummer,c.template_object_id,c.c_index,c.calc_curr_object_id,c.calc_name,c.cdb_obsolete,c.cdb_project_id,c.eop,c.i18n_benennung_de,c.i18n_benennung_en,c.materialnr_erp,c.part_mengeneinheit,c.part_object_id,c.schema_object_id,c.sop FROM cdbpco_comp2component c2c "\
        # "JOIN cdbpco_component_v c ON c2c.comp_object_id=c.cdb_object_id WHERE c2c.cdb_object_id IN ({})"
        # format_in_condition.assert_called_once_with(q, ["1", "2", "3", "4"])
        # pcs_record.assert_has_calls(
        #     [
        #         mock.call("relation", rec_1),
        #         mock.call("relation", rec_2),
        #         mock.call("relation", rec_3),
        #         mock.call("relation", rec_4)
        #     ]
        # )
        # self.assertListEqual(
        #     [
        #         rec_1.thead.tname, rec_2.thead.tname,
        #         rec_3.thead.tname, rec_4.thead.tname
        #     ],
        #     [
        #         "cdbpco_component", "cdbpco_component",
        #         "cdbpco_component", "cdbpco_component"
        #     ]
        # )

    @mock.patch.object(util, "format_in_condition", side_effect=TypeError)
    @mock.patch.object(util, "_get_oids_by_relation", return_value=[("relation", [1])])
    def test_resolve_records_error(self, _get_oids_by_relation, format_in_condition):
        "Raise ValueError, when resolved oids are non string values"
        pass
        # with self.assertRaises(ValueError):
        #     util.resolve_records("pcs_levels")

    @mock.patch.object(util, "pcs_record2rest_object")
    def test_rest_objects_by_restkey(self, pcs_record2rest_object):

        robj_foo = mock.MagicMock()
        robj_bar = mock.MagicMock()
        pcs_record2rest_object.side_effect = [robj_foo, robj_bar]

        record_foo = mock.MagicMock()
        record_foo.record.cdb_object_id = "foo"
        record_bar = mock.MagicMock()
        record_bar.record.cdb_object_id = "bar"
        pcs_records = [record_foo, record_bar]

        mapping_oids = {"foo": ["foo--1"], "bar": ["bar--1", "bar--2"]}
        mock_request = mock.MagicMock()

        self.assertDictEqual(
            util.rest_objects_by_restkey(pcs_records, mapping_oids, mock_request),
            {
                "foo--1": robj_foo,
                "bar--1": robj_bar,
                "bar--2": robj_bar,
            }
        )

        pcs_record2rest_object.assert_has_calls(
            [
                mock.call(record_foo, mock_request, {}),
                mock.call(record_bar, mock_request, {}),
            ]
        )
