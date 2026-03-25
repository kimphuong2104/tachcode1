# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2020 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
import collections

from cdb import fls, sqlapi
from cs.platform.web.rest.relship.main import _obj_from_handle
from cs.requirements import RQMSpecification, RQMSpecObject, TargetValue

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"


class RequirementsModel(object):

    def __init__(self, specification_object_id):
        self.specification_object_id = specification_object_id
        self.spec = RQMSpecification.ByKeys(cdb_object_id=self.specification_object_id)

    def check_access(self):
        if (
            self.specification_object_id and
            self.spec and self.spec.CheckAccess('read')
        ):
            return True
        else:
            return False

    def get_parents(self, cdb_object_id, parent_object_ids):
        fls.allocate_license('RQM_070')
        reqs = self.spec.Requirements.KeywordQuery(cdb_object_id=cdb_object_id)
        obj = None
        if reqs:
            obj = reqs[0]
        else:
            tvs = self.spec.TargetValues.KeywordQuery(cdb_object_id=cdb_object_id)
            if tvs:
                obj = tvs[0]
        if obj:
            # if the frontend already nows the whole parent information do not recalculate them
            if not parent_object_ids or not len(parent_object_ids) > 1:
                parent_object_ids = []
                while obj:
                    parent_object_ids.append(obj.cdb_object_id)
                    obj = obj._tree_up_reference()
                parent_object_ids.append('')
                parent_object_ids.reverse()
                return parent_object_ids

    def get_requirements(self, parent_object_id=None):
        fls.allocate_license('RQM_070')
        # navigate_relship ensures access permission within the kernel
        cdef = self.spec.GetClassDef()
        name = 'Requirements'
        rs_def = cdef.getRelationshipByRolename(name)
        if rs_def and rs_def.is_valid():
            rs_name = rs_def.get_identifier()
            spec_object_handle = self.spec.ToObjectHandle()
            args = {}
            if parent_object_id is not None:
                args['parent_object_id'] = parent_object_id
            return [
                _obj_from_handle(oh) for oh in spec_object_handle.navigate_Relship(
                    rs_name, args
                )
            ] + self.get_target_values(parent_object_id)

    def get_target_values(self, requirement_object_id=None):
        fls.allocate_license('RQM_070')
        # navigate_relship ensures access permission within the kernel
        cdef = self.spec.GetClassDef()
        name = 'TargetValues'
        rs_def = cdef.getRelationshipByRolename(name)
        if rs_def and rs_def.is_valid():
            rs_name = rs_def.get_identifier()
            spec_object_handle = self.spec.ToObjectHandle()
            args = {}
            if requirement_object_id is not None:
                args['requirement_object_id'] = requirement_object_id
            return [
                _obj_from_handle(oh) for oh in spec_object_handle.navigate_Relship(
                    rs_name, args
                )
            ]

    @classmethod
    def get_requirements_text_cache(cls, reqs, req_ids=None, languages=None, entity=None):
        fls.allocate_license('RQM_070')
        if not reqs and req_ids is None:
            return {}
        if entity is None:
            entity = RQMSpecObject
        cdb_object_ids = req_ids if req_ids is not None else [r['cdb_object_id'] for r in reqs]
        text_field_names = entity.GetTextFieldNames() if req_ids is not None else reqs[0].GetTextFieldNames()
        text_cache = collections.defaultdict(dict)
        for text_field_name in text_field_names:
            if (
                languages is not None and
                text_field_name.split('_')[-1] not in languages
            ):
                continue  # skip this long text language
            rs = sqlapi.RecordSet2(
                text_field_name,
                condition=RQMSpecObject.cdb_object_id.one_of(*cdb_object_ids),
                addtl='ORDER BY cdb_object_id, zeile'
            )
            for row in rs:
                if text_field_name not in text_cache[row['cdb_object_id']]:
                    text_cache[row['cdb_object_id']][text_field_name] = []
                text_cache[row['cdb_object_id']][text_field_name].append(row['text'])
        for oid in text_cache:
            for text_field_name in text_field_names:
                if text_field_name not in text_cache[oid]:
                    text_cache[oid][text_field_name] = ""
                else:
                    text_cache[oid][text_field_name] = "".join(text_cache[oid][text_field_name])
        return text_cache

    def get_requirements_target_value_cache(self, reqs):
        fls.allocate_license('RQM_070')
        cache = {}
        target_value_parent_ids = [r['cdb_object_id'] for r in reqs]
        for tv in sqlapi.RecordSet2(sql="SELECT cdb_object_id, requirement_object_id FROM cdbrqm_target_value WHERE %s ORDER BY pos, targetvalue_id" % TargetValue.requirement_object_id.one_of(*target_value_parent_ids)):
            cache[tv['requirement_object_id']] = tv['cdb_object_id']
        return cache
