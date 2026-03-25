# -*- mode: python; coding: utf-8 -*-
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
from cdb import fls
from cdb.objects.core import ByID
from cs.requirements import RQMSpecification, RQMSpecObject, TargetValue
from cs.requirements.web.rest.diff.acceptance_criterion_model import \
    ACCEPTANCE_CRITERION_DIFF_PLUGIN_ID
from cs.requirements.web.rest.diff.classification_model import \
    DiffClassificationAPIModel
from cs.requirements.web.rest.diff.deleted_model import DiffDeletedAPIModel
from cs.requirements.web.rest.diff.diff_indicator_model import \
    DiffIndicatorAPIModel
from cs.requirements.web.rest.diff.file_model import DiffFileAPIModel
from cs.requirements.web.rest.diff.metadata_model import DiffMetadataAPIModel
from cs.requirements.web.rest.diff.richtext_model import DiffRichTextAPIModel

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"


class DiffHeaderAPIModel (object):

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
    def fast_diff_ids(cls, left_object, right_object, languages, all_results=True, only_tv_ids=False):
        from cs.requirements.web.rest.diff.diff_indicator_model import DiffCriterionRegistry
        fls.allocate_license('RQM_070')
        changed_ids = set()
        additional_conditions = {}
        if isinstance(left_object, RQMSpecObject):
            left_spec = left_object.Specification
            right_spec = right_object.Specification
            req_condition = str(RQMSpecObject.cdb_object_id.one_of(
                left_object.cdb_object_id, right_object.cdb_object_id
            ))
            req_left_and_right_condition = " AND ".join(
                [
                    req_condition.replace('cdb_object_id',
                                          'left_side.cdb_object_id'),
                    req_condition.replace('cdb_object_id',
                                          'right_side.cdb_object_id')
                ]
            )
            tv_condition = str(TargetValue.requirement_object_id.one_of(
                left_object.cdb_object_id, right_object.cdb_object_id
            ))
            tv_left_and_right_condition = " AND ".join(
                [
                    tv_condition.replace(
                        'requirement_object_id',
                        'left_side.requirement_object_id'
                    ),
                    tv_condition.replace(
                        'requirement_object_id',
                        'right_side.requirement_object_id'
                    )
                ]
            )
            delete_api_model = DiffDeletedAPIModel(
                left_spec.cdb_object_id,
                right_spec.cdb_object_id,
                left_spec,
                right_spec,
            )
            new_tv_ids, deleted_tv_ids = DiffIndicatorAPIModel.get_added_and_deleted_tvs(
                delete_api_model,
                additional_condition=tv_condition.replace(
                    'requirement_object_id',
                    'left_side.requirement_object_id'
                )
            )
            changed_ids = new_tv_ids + deleted_tv_ids
            if changed_ids and not all_results:
                return list(changed_ids)
            else:
                changed_ids = set(changed_ids)
            criterions = [
                x.get('id') for x in DiffCriterionRegistry.get_criterions(RQMSpecObject)
            ]
            settings = DiffCriterionRegistry.get_settings_by_criterions(criterions, languages)
            settings['criterions_per_class'][RQMSpecification.__maps_to__] = []
            additional_conditions = {
                RQMSpecObject.__maps_to__: req_left_and_right_condition,
                TargetValue.__maps_to__: tv_left_and_right_condition
            }
            if only_tv_ids:
                settings['criterions_per_class'][RQMSpecObject.__maps_to__] = []
        elif isinstance(left_object, TargetValue):
            left_spec = left_object.Specification
            right_spec = right_object.Specification
            req_condition = str(RQMSpecObject.cdb_object_id.one_of(
                left_object.requirement_object_id, right_object.requirement_object_id
            ))
            req_left_and_right_condition = " AND ".join(
                [
                    req_condition.replace('cdb_object_id',
                                          'left_side.cdb_object_id'),
                    req_condition.replace('cdb_object_id',
                                          'right_side.cdb_object_id')
                ]
            )
            tv_condition = str(TargetValue.cdb_object_id.one_of(
                left_object.cdb_object_id, right_object.cdb_object_id
            ))
            tv_left_and_right_condition = " AND ".join(
                [
                    tv_condition.replace(
                        'cdb_object_id',
                        'left_side.cdb_object_id'
                    ),
                    tv_condition.replace(
                        'cdb_object_id',
                        'right_side.cdb_object_id'
                    )
                ]
            )
            criterions = [
                x.get('id') for x in DiffCriterionRegistry.get_criterions(TargetValue)
            ] + [ACCEPTANCE_CRITERION_DIFF_PLUGIN_ID]
            settings = DiffCriterionRegistry.get_settings_by_criterions(criterions, languages)
            settings['criterions_per_class'][RQMSpecification.__maps_to__] = []
            settings['criterions_per_class'][RQMSpecObject.__maps_to__] = []
            additional_conditions = {
                RQMSpecObject.__maps_to__: req_left_and_right_condition,
                TargetValue.__maps_to__: tv_left_and_right_condition
            }
        else:
            left_spec = left_object
            right_spec = right_object
            criterions = [
                x.get('id') for x in DiffCriterionRegistry.get_criterions(RQMSpecification)
            ]
            settings = DiffCriterionRegistry.get_settings_by_criterions(criterions, languages)
            settings['criterions_per_class'][RQMSpecObject.__maps_to__] = []
            settings['criterions_per_class'][TargetValue.__maps_to__] = []
        diff_plugin_kwargs = dict(
            left_spec=left_spec,
            right_spec=right_spec,
            settings=settings,
            additional_conditions=additional_conditions
        )
        # richtext check
        different_richtext_ids = DiffRichTextAPIModel.fast_rich_text_diff_ids(
            **diff_plugin_kwargs
        )
        changed_ids.update(different_richtext_ids.get('changed_ids'))
        if changed_ids and not all_results:
            return list(changed_ids)
        # metadata check
        different_metadata_ids = DiffMetadataAPIModel.fast_metadata_diff_ids(
            **diff_plugin_kwargs
        )
        changed_ids.update(different_metadata_ids.get('changed_ids'))
        if changed_ids and not all_results:
            return list(changed_ids)
        # classification check
        different_classification_ids = DiffClassificationAPIModel.fast_classification_diff_ids(
            **diff_plugin_kwargs
        )
        changed_ids.update(different_classification_ids.get('changed_ids'))
        if changed_ids and not all_results:
            return list(changed_ids)
        # file check
        different_file_ids = DiffFileAPIModel.fast_file_diff_ids(
            **diff_plugin_kwargs
        )
        changed_ids.update(different_file_ids.get('changed_ids'))
        return list(changed_ids)

    def diff(self, languages):
        return self.fast_diff_ids(self.left_object, self.right_object, languages, all_results=False)
