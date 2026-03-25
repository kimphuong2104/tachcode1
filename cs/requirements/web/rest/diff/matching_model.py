# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2020 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
from webob.exc import HTTPBadRequest

from cdb import fls
from cdb.objects.core import ByID
from cs.requirements import RQMSpecification, RQMSpecObject, TargetValue

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"


class DiffMatchingAPIModel(object):

    def __init__(self, left_specification_object_id, right_specification_object_id, source_cdb_object_id, target_side):
        self.left_specification_object_id = left_specification_object_id
        self.right_specification_object_id = right_specification_object_id
        self.source_cdb_object_id = source_cdb_object_id
        self.left_spec = RQMSpecification.ByKeys(cdb_object_id=self.left_specification_object_id)
        self.right_spec = RQMSpecification.ByKeys(cdb_object_id=self.right_specification_object_id)
        self.source_obj = ByID(source_cdb_object_id)
        self.target_side = target_side

    def check_access(self):
        if (
            self.left_spec and self.left_spec.CheckAccess('read') and
            self.right_spec and self.right_spec.CheckAccess('read') and
            self.source_obj and self.source_obj.CheckAccess('read')
        ):
            return True
        else:
            return False

    def get_matching_object(self):
        fls.allocate_license('RQM_070')
        if self.left_spec == self.right_spec:
            return self.source_obj
        if self.target_side == 'left':
            spec_id_to_compare = self.left_specification_object_id
            linktype_name = 'Copy of'
        elif self.target_side == 'right':
            spec_id_to_compare = self.right_specification_object_id
            linktype_name = 'Copied to'
        else:
            raise HTTPBadRequest
        if isinstance(self.source_obj, RQMSpecification) and self.target_side == 'left':
            return self.left_spec
        elif isinstance(self.source_obj, RQMSpecification) and self.target_side == 'right':
            return self.right_spec
        else:
            if isinstance(self.source_obj, RQMSpecObject):
                semLinkTargetType = RQMSpecObject
            else:
                semLinkTargetType = TargetValue
            for sem_link in self.source_obj.SemanticLinks:
                if (
                    sem_link.linktype_name == linktype_name and
                    isinstance(sem_link.Object, semLinkTargetType) and
                    sem_link.Object.specification_object_id == spec_id_to_compare
                ):
                    return sem_link.Object

            for version in self.source_obj.AllVersions:
                if version.specification_object_id == spec_id_to_compare:
                    return version
            return None  # not found
