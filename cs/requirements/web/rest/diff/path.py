# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2018 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
from webob.exc import HTTPForbidden
from cs.requirements.web.rest.diff.main import DiffAPI
from cs.requirements.web.rest.diff.deleted_model import DiffDeletedAPIModel
from cs.requirements.web.rest.diff.matching_model import DiffMatchingAPIModel
from cs.requirements.web.rest.diff.metadata_model import DiffMetadataAPIModel
from cs.requirements.web.rest.diff.richtext_model import DiffRichTextAPIModel
from cs.requirements.web.rest.diff.requirements_model import RequirementsModel
from cs.requirements.web.rest.diff.header_model import DiffHeaderAPIModel
from cs.requirements.web.rest.diff.classification_model import DiffClassificationAPIModel
from cs.requirements.web.rest.diff.file_model import DiffFileAPIModel
from cs.requirements.web.rest.diff.acceptance_criterion_model import DiffAcceptanceCriterionAPIModel
from cs.requirements.web.rest.diff.diff_indicator_model import DiffIndicatorAPIModel

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"


@DiffAPI.path(path="header/{left_cdb_object_id}/{right_cdb_object_id}", model=DiffHeaderAPIModel)
def get_header_diff_model(left_cdb_object_id, right_cdb_object_id):
    model = DiffHeaderAPIModel(left_cdb_object_id, right_cdb_object_id)
    if not model.check_access():
        raise HTTPForbidden
    else:
        return model


@DiffAPI.path(path="richtext/{left_cdb_object_id}/{right_cdb_object_id}", model=DiffRichTextAPIModel)
def get_richtext_diff_model(left_cdb_object_id, right_cdb_object_id):
    model = DiffRichTextAPIModel(left_cdb_object_id, right_cdb_object_id)
    if not model.check_access():
        raise HTTPForbidden
    else:
        return model


@DiffAPI.path(path="metadata/{left_cdb_object_id}/{right_cdb_object_id}", model=DiffMetadataAPIModel)
def get_metadata_diff_model(left_cdb_object_id, right_cdb_object_id):
    model = DiffMetadataAPIModel(left_cdb_object_id, right_cdb_object_id)
    if not model.check_access():
        raise HTTPForbidden
    else:
        return model


@DiffAPI.path(path="classification/{left_cdb_object_id}/{right_cdb_object_id}", model=DiffClassificationAPIModel)
def get_classification_diff_model(left_cdb_object_id, right_cdb_object_id):
    model = DiffClassificationAPIModel(left_cdb_object_id, right_cdb_object_id)
    if not model.check_access():
        raise HTTPForbidden
    else:
        return model


@DiffAPI.path(path="file/{left_cdb_object_id}/{right_cdb_object_id}", model=DiffFileAPIModel)
def get_file_diff_model(left_cdb_object_id, right_cdb_object_id):
    model = DiffFileAPIModel(left_cdb_object_id, right_cdb_object_id)
    if not model.check_access():
        raise HTTPForbidden
    else:
        return model


@DiffAPI.path(path="acceptancecriterion/{left_cdb_object_id}/{right_cdb_object_id}", model=DiffAcceptanceCriterionAPIModel)
def get_acceptance_criterion_diff_model(left_cdb_object_id, right_cdb_object_id):
    model = DiffAcceptanceCriterionAPIModel(left_cdb_object_id, right_cdb_object_id)
    if not model.check_access():
        raise HTTPForbidden
    else:
        return model


@DiffAPI.path(
    path="matching/{left_specification_object_id}/{right_specification_object_id}/{right_cdb_object_id}/{target_side}",
    model=DiffMatchingAPIModel
)
def get_matching_diff_model(left_specification_object_id, right_specification_object_id, right_cdb_object_id, target_side):
    model = DiffMatchingAPIModel(left_specification_object_id, right_specification_object_id, right_cdb_object_id, target_side)
    if not model.check_access():
        raise HTTPForbidden
    else:
        return model


@DiffAPI.path(path="deleted/{left_cdb_object_id}/{right_cdb_object_id}", model=DiffDeletedAPIModel)
def get_deleted_model(left_cdb_object_id, right_cdb_object_id):
    model = DiffDeletedAPIModel(left_cdb_object_id, right_cdb_object_id)
    if not model.check_access():
        raise HTTPForbidden
    else:
        return model


@DiffAPI.path(path="requirements/{right_cdb_object_id}", model=RequirementsModel)
def get_requirements(right_cdb_object_id):
    model = RequirementsModel(right_cdb_object_id)
    if not model.check_access():
        raise HTTPForbidden
    else:
        return model


@DiffAPI.path(path="indicator/{left_cdb_object_id}/{right_cdb_object_id}",
              model=DiffIndicatorAPIModel)
def get_diff_indicators(left_cdb_object_id, right_cdb_object_id):
    model = DiffIndicatorAPIModel(left_cdb_object_id, right_cdb_object_id)
    if not model.check_access():
        raise HTTPForbidden
    else:
        return model
