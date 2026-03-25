# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
from cdb import fls, sig, sqlapi, util
from cdb.objects.core import ByID
from cs.platform.web.rest.app import get_collection_app
from cs.requirements import RQMSpecification, RQMSpecObject, TargetValue

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

FILES_CRITERION_DIFF_PLUGIN_ID = 'files'


class DiffFileAPIModel (object):

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
    def fast_file_diff_ids(cls, left_spec, right_spec, settings=None, additional_conditions=None):
        """ Searches all objects (their ids) that have different files (added, deleted, changed)
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
                FILES_CRITERION_DIFF_PLUGIN_ID in criterions_per_class[x.__maps_to__]
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
            AND (
                EXISTS ( -- existing on booth sides but changed case
                    SELECT 1 FROM cdb_file f_right INNER JOIN cdb_file f_left
                        ON f_right.cdbf_name = f_left.cdbf_name
                    WHERE
                        f_left.cdbf_object_id = left_side.cdb_object_id
                    AND
                        f_right.cdbf_object_id = right_side.cdb_object_id
                    AND
                        (
                            f_left.cdbf_hash != f_right.cdbf_hash
                        )
                ) OR EXISTS ( -- existing only on one side
                    {added_or_deleted_stmt}
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
                AND (
                    EXISTS ( -- existing on booth sides but changed case
                        SELECT 1 FROM cdb_file f_right INNER JOIN cdb_file f_left
                            ON f_right.cdbf_name = f_left.cdbf_name
                        WHERE
                            f_left.cdbf_object_id = left_side.cdb_object_id
                        AND
                            f_right.cdbf_object_id = right_side.cdb_object_id
                        AND
                            (
                                f_left.cdbf_hash != f_right.cdbf_hash
                            )
                    ) OR EXISTS ( -- existing only on one side
                        {added_or_deleted_stmt}
                    )
                )
                """

            added_or_deleted_stmt = """
                SELECT 1 FROM
                    (
                        SELECT * from cdb_file WHERE cdbf_object_id=left_side.cdb_object_id
                    ) f_left
                FULL OUTER JOIN
                    (
                        SELECT * from cdb_file WHERE cdbf_object_id=right_side.cdb_object_id
                    ) f_right
                ON
                    f_left.cdbf_name=f_right.cdbf_name AND
                    f_left.cdbf_object_id!=f_right.cdbf_object_id
                WHERE (
                            (
                                f_left.cdbf_object_id IS NULL AND
                                f_right.cdbf_object_id IN (
                                    left_side.cdb_object_id,
                                    right_side.cdb_object_id
                                )
                            )
                        OR
                            (
                                f_right.cdbf_object_id IS NULL AND
                                f_left.cdbf_object_id IN (
                                    left_side.cdb_object_id,
                                    right_side.cdb_object_id
                                )
                            )
                    )
            """
            sqlite_added_or_deleted_stmt = """
             -- full outer join emulation for sqlite to find new/deleted ones
                SELECT 1 FROM (
                    SELECT
                        f_left.cdbf_object_id as left_object_id,
                        f_right.cdbf_object_id as right_object_id
                    FROM cdb_file f_left LEFT JOIN cdb_file f_right
                        ON
                            f_left.cdbf_name=f_right.cdbf_name AND
                            f_left.cdbf_object_id=left_side.cdb_object_id AND
                            f_right.cdbf_object_id IN (NULL, right_side.cdb_object_id)
                        WHERE f_left.cdbf_object_id=left_side.cdb_object_id
                    UNION ALL
                    SELECT
                        f_left.cdbf_object_id as left_object_id,
                        f_right.cdbf_object_id as right_object_id
                    FROM cdb_file f_left LEFT JOIN cdb_file f_right
                        ON
                            f_left.cdbf_name=f_right.cdbf_name AND
                            f_left.cdbf_object_id=right_side.cdb_object_id AND
                            f_right.cdbf_object_id IN (NULL, left_side.cdb_object_id)
                        WHERE f_left.cdbf_object_id=right_side.cdb_object_id
                ) AS added_or_removed WHERE right_object_id IS NULL
            """

            def get_added_or_deleted_stmt():
                return (
                    sqlite_added_or_deleted_stmt if sqlapi.SQLdbms() == sqlapi.DBMS_SQLITE else
                    added_or_deleted_stmt
                )

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
                added_or_deleted_stmt=get_added_or_deleted_stmt(),
                additional_condition=additional_condition
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

    def diff(self, languages, request):
        # Result dictionary
        diff_dict = {
            "changedFiles": False,
            "files": {}
        }

        if not self.empty_element:
            # Retrieve files
            left_files = self.left_object.Files
            right_files = self.right_object.Files
            # Transform into a dict with key = filename and values = hash and size
            left_files_object = {
                single_file.cdbf_name: {
                    "hash": single_file.cdbf_hash,
                    "size": single_file.cdbf_fsize,
                    "url": request.link(single_file, app=get_collection_app(request))
                } for single_file in left_files
            }
            right_files_object = {
                single_file.cdbf_name: {
                    "hash": single_file.cdbf_hash,
                    "size": single_file.cdbf_fsize,
                    "url": request.link(single_file, app=get_collection_app(request))
                } for single_file in right_files
            }
            unique_keys_set = list(set(left_files_object).union(set(right_files_object)))
            for key in unique_keys_set:
                diff_dict["files"][key] = {}
                if key not in right_files_object.keys() and key in left_files_object.keys():
                    # File deleted
                    diff_dict["files"][key]["status"] = "del"
                    diff_dict["files"][key]["url_A"] = left_files_object[key]["url"]
                    diff_dict["files"][key]["url_B"] = ""
                    diff_dict["changedFiles"] = True
                elif key in right_files_object.keys() and key not in left_files_object.keys():
                    # File created
                    diff_dict["files"][key]["status"] = "new"
                    diff_dict["files"][key]["url_A"] = ""
                    diff_dict["files"][key]["url_B"] = right_files_object[key]["url"]
                    diff_dict["changedFiles"] = True
                elif key in right_files_object.keys() and key in left_files_object.keys():
                    # File exists in both states
                    if (
                        left_files_object[key]["hash"] == right_files_object[key]["hash"] and
                        left_files_object[key]["size"] == right_files_object[key]["size"]
                    ):
                        diff_dict["files"][key]["status"] = "same"
                        diff_dict["files"][key]["url_A"] = left_files_object[key]["url"]
                        diff_dict["files"][key]["url_B"] = right_files_object[key]["url"]
                    else:
                        diff_dict["files"][key]["status"] = "diff"
                        diff_dict["files"][key]["url_A"] = left_files_object[key]["url"]
                        diff_dict["files"][key]["url_B"] = right_files_object[key]["url"]
                        diff_dict["changedFiles"] = True
        return diff_dict


@sig.connect(RQMSpecification, "rqm_diff_plugins", "init")
def register_diff_plugin(registry):
    registry.register_criterion([
        RQMSpecification,
        RQMSpecObject,
        TargetValue
    ], FILES_CRITERION_DIFF_PLUGIN_ID, util.get_label('web.rqm_diff.files'))


@sig.connect(RQMSpecification, "rqm_diff_plugins", "search", 'files')
def search(left_spec, right_spec, settings):
    return DiffFileAPIModel.fast_file_diff_ids(left_spec, right_spec, settings)
