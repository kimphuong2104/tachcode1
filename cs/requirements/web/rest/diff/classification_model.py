# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

from cdb import fls, sig, sqlapi, util
from cdb.objects.core import ByID
from cs.classification import api
from cs.classification.rest.utils import ensure_json_serialiability
from cs.requirements import RQMSpecification, RQMSpecObject, TargetValue

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

CLASSIFICATION_CRITERION_DIFF_PLUGIN_ID = 'classification'


class DiffClassificationAPIModel (object):

    def __init__(self, left_cdb_object_id, right_cdb_object_id):
        self.left_cdb_object_id = left_cdb_object_id
        self.right_cdb_object_id = right_cdb_object_id
        if right_cdb_object_id == "null":
            # Right element is empty
            self.left_object = ByID(self.left_cdb_object_id)
            self.right_object = None
            self.empty_element = True
        else:
            if left_cdb_object_id == "null":
                # Left element is empty
                self.left_object = None
                self.right_object = ByID(self.right_cdb_object_id)
                self.empty_element = True
            else:
                self.left_object = ByID(self.left_cdb_object_id)
                self.right_object = ByID(self.right_cdb_object_id)
                self.empty_element = False

    def check_access(self):
        if (
            (
                self.empty_element and
                self.left_object and
                self.left_object.CheckAccess('read')
            ) or
            (
                self.empty_element and
                self.right_object and
                self.right_object.CheckAccess('read')
            ) or
            (
                self.left_object and self.left_object.CheckAccess('read') and
                self.right_object and self.right_object.CheckAccess('read')
            )
        ):
            access_granted = True
        else:
            access_granted = False
        return access_granted

    @classmethod
    def fast_classification_diff_ids(cls, left_spec, right_spec, settings=None, additional_conditions=None):
        """ Searches all objects (their ids) that have different classifications (based on checksum)
        compared to their counterpart within the given
        left and right specification object contexts.

        Per default: only requirement objects are searched,
            via settings also target values can be searched as well.
        """
        fls.allocate_license('RQM_070')
        if settings is None:
            settings = {}
        if additional_conditions is None:
            additional_conditions = {}
        attributes = ['cdb_object_id', 'requirement_object_id', 'pos']
        criterions_per_class = settings.get('criterions_per_class', {})
        entities_to_search_for = [
            x for x in [
                RQMSpecification,
                RQMSpecObject,
                TargetValue
            ] if (
                x.__maps_to__ in criterions_per_class and
                CLASSIFICATION_CRITERION_DIFF_PLUGIN_ID in criterions_per_class[x.__maps_to__]
            )
        ]
        changed_ids = set()
        changed_req_ids = set()
        changed_tv_ids = set()
        for entity in entities_to_search_for:
            additional_condition = additional_conditions.get(entity.__maps_to__, "1=1")
            changed_ids_stmt = """
            SELECT {columns} from {table} left_side, {table} right_side
            WHERE left_side.specification_object_id='{left_spec_id}'
            AND left_side.ce_baseline_origin_id=right_side.ce_baseline_origin_id
            AND right_side.specification_object_id='{right_spec_id}'
            AND {additional_condition}
            AND {classification_compare_condition}
            """
            classification_compare_condition = """
            (
                EXISTS (
                    SELECT 1 FROM (
	                    SELECT (
		                    SELECT checksum FROM cs_classification_checksum WHERE ref_object_id=left_side.cdb_object_id
	                    ) left_checksum, (
		                    SELECT checksum FROM cs_classification_checksum WHERE ref_object_id=right_side.cdb_object_id
	                    ) right_checksum FROM cs_classification_checksum WHERE ref_object_id IN (
		                    left_side.cdb_object_id, right_side.cdb_object_id
	                    )
                    ) ccc WHERE
	                    (ccc.left_checksum != ccc.right_checksum) OR 
                        (ccc.left_checksum IS NULL AND ccc.right_checksum IS NOT NULL) OR 
	                    (ccc.left_checksum IS NOT NULL AND ccc.right_checksum IS NULL)
                )
            )
            """
            if entity == RQMSpecification:
                changed_ids_stmt = """
                SELECT {columns} from {table} left_side, {table} right_side
                WHERE left_side.cdb_object_id='{left_spec_id}'
                AND left_side.ce_baseline_origin_id=right_side.ce_baseline_origin_id
                AND right_side.cdb_object_id='{right_spec_id}'
                AND {additional_condition}
                AND {classification_compare_condition}
                """
            changed_ids_stmt = changed_ids_stmt.format(
                table=entity.__maps_to__,
                columns=",".join([
                    "right_side.{attr} {attr}".format(attr=attr)
                    if hasattr(entity, attr) else
                    "NULL {attr}".format(attr=attr)
                    for attr in attributes
                ]),
                left_spec_id=left_spec.cdb_object_id,
                right_spec_id=right_spec.cdb_object_id,
                additional_condition=additional_condition,
                classification_compare_condition=classification_compare_condition
            )
            rs = sqlapi.RecordSet2(sql=changed_ids_stmt)
            for r in rs:
                cdb_object_id = r['cdb_object_id']
                requirement_object_id = r['requirement_object_id']
                tv_pos_id = r['pos']
                if requirement_object_id:
                    changed_tv_ids.add((cdb_object_id, requirement_object_id, tv_pos_id))
                    changed_req_ids.add(requirement_object_id)
                    changed_ids.add(requirement_object_id)
                else:
                    changed_req_ids.add(cdb_object_id)
                changed_ids.add(cdb_object_id)
        return {
            'changed_req_ids': changed_req_ids,
            'changed_tv_ids': changed_tv_ids,
            'changed_ids': changed_ids
        }

    def diff(self, languages):
        fls.allocate_license('RQM_070')
        compare_data = None
        if not self.empty_element:
            compare_data = api.compare_classification(
                self.left_object.cdb_object_id,
                self.right_object.cdb_object_id, with_metadata=True, narrowed=False
            )
        elif self.left_object is None and self.right_object is not None:
            compare_data = api.compare_classification(
                None,
                self.right_object.cdb_object_id, with_metadata=True, narrowed=False
            )
            compare_data["case"] = "new"
        elif self.right_object is None and self.left_object is not None:
            compare_data = api.compare_classification(
                self.left_object.cdb_object_id,
                None, with_metadata=True, narrowed=False
            )
            compare_data["case"] = "deleted"

        return ensure_json_serialiability(compare_data)


@sig.connect(RQMSpecification, "rqm_diff_plugins", "init")
def register_diff_plugin(registry):
    registry.register_criterion([
        RQMSpecification,
        RQMSpecObject,
        TargetValue
    ], CLASSIFICATION_CRITERION_DIFF_PLUGIN_ID, util.get_label('web.rqm_diff.classification'))


@sig.connect(RQMSpecification, "rqm_diff_plugins", "search", 'classification')
def search(left_spec, right_spec, settings):
    return DiffClassificationAPIModel.fast_classification_diff_ids(left_spec, right_spec, settings)
