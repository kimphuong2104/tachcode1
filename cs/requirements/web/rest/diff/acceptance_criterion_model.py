# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

from cdb import fls, sig, util
from cdb.objects.core import ByID
from cs.platform.web import uisupport
from cs.requirements import RQMSpecification, RQMSpecObject

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"


ACCEPTANCE_CRITERION_DIFF_PLUGIN_ID = 'acceptancecriterion'


class DiffAcceptanceCriterionAPIModel (object):

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

    def diff(self, languages):
        fls.allocate_license('RQM_070')
        from cs.requirements.web.rest.diff.header_model import DiffHeaderAPIModel
        diff_dict = {
            "changedAC": False,
            "target_values": {}
        }
        if not self.empty_element:
            # List objects
            left_target_values = self.left_object.TargetValues
            right_target_values = self.right_object.TargetValues
            # Transform into dict
            left_target_values_dict = {
                target_value.ce_baseline_origin_id: {
                    "object": target_value,
                    "desc": target_value.GetDescription(),
                    "url": uisupport.get_ui_link(request=None, target_obj=target_value)
                } for target_value in left_target_values
            }

            right_target_values_dict = {
                target_value.ce_baseline_origin_id: {
                    "object": target_value,
                    "desc": target_value.GetDescription(),
                    "url": uisupport.get_ui_link(request=None, target_obj=target_value)
                } for target_value in right_target_values
            }

            # Set with unique keys:
            unique_keys_set = list(set(left_target_values_dict).union(set(right_target_values_dict)))

            changed_ids = DiffHeaderAPIModel.fast_diff_ids(
                left_object=self.left_object,
                right_object=self.right_object,
                languages=languages,
                only_tv_ids=True
            )

            if changed_ids:
                diff_dict["changedAC"] = True

            for key in unique_keys_set:
                diff_dict["target_values"][key] = {}
                if key not in right_target_values_dict.keys() and key in left_target_values_dict.keys():
                    # Target Value deleted
                    diff_dict["target_values"][key]["status"] = "del"
                    diff_dict["target_values"][key]["desc"] = left_target_values_dict[key]["desc"]
                    diff_dict["target_values"][key]["url_A"] = left_target_values_dict[key]["url"]
                    diff_dict["target_values"][key]["url_B"] = ""
                    diff_dict["changedAC"] = True
                elif key in right_target_values_dict.keys() and key not in left_target_values_dict.keys():
                    # Target Value created
                    diff_dict["target_values"][key]["status"] = "new"
                    diff_dict["target_values"][key]["desc"] = right_target_values_dict[key]["desc"]
                    diff_dict["target_values"][key]["url_A"] = ""
                    diff_dict["target_values"][key]["url_B"] = right_target_values_dict[key]["url"]
                    diff_dict["changedAC"] = True
                else:
                    right_target_value = right_target_values_dict[key]['object']
                    diff_dict["target_values"][key]["status"] = (
                        "diff" if right_target_value.cdb_object_id in changed_ids else "same"
                    )
                    diff_dict["target_values"][key]["desc_r"] = left_target_values_dict[key]["desc"]
                    diff_dict["target_values"][key]["desc_l"] = right_target_values_dict[key]["desc"]
                    diff_dict["target_values"][key]["url_A"] = left_target_values_dict[key]["url"]
                    diff_dict["target_values"][key]["url_B"] = right_target_values_dict[key]["url"]

        return diff_dict


@sig.connect(RQMSpecification, "rqm_diff_plugins", "init")
def register_diff_plugin(registry):
    registry.register_criterion([
        RQMSpecObject
    ], ACCEPTANCE_CRITERION_DIFF_PLUGIN_ID, util.get_label('web.rqm_diff.acceptance_criteria'))
