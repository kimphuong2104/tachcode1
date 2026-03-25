# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2020 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
from cdb import fls, sqlapi
from cdb.lru_cache import lru_cache
from cs.requirements import RQMSpecification, RQMSpecObject
from cs.tools.semanticlinks import SemanticLink, SemanticLinkType

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"


@lru_cache()
def get_copy_link_types(classname):
    copied_to_links = SemanticLinkType.KeywordQuery(
        subject_object_classname=classname,
        object_object_classname=classname,
        name='Copied to'
    )
    if len(copied_to_links) == 1:
        copied_to_link = copied_to_links[0]
    else:
        raise ValueError('multiple copied to link types')
    copy_of_links = SemanticLinkType.KeywordQuery(
        subject_object_classname=classname,
        object_object_classname=classname,
        name='Copy of'
    )
    if len(copy_of_links) == 1:
        copy_of_link = copied_to_links[0]
    else:
        raise ValueError('multiple copy of link types')
    return copied_to_link, copy_of_link


class DiffDeletedAPIModel(object):

    def __init__(self, left_specification_object_id, right_specification_object_id,
                 left_spec=None, right_spec=None):
        self.left_specification_object_id = left_specification_object_id
        self.right_specification_object_id = right_specification_object_id
        self.left_spec = (
            RQMSpecification.ByKeys(cdb_object_id=self.left_specification_object_id)
            if left_spec is None else left_spec
        )
        self.right_spec = (
            RQMSpecification.ByKeys(cdb_object_id=self.right_specification_object_id)
            if right_spec is None else right_spec
        )

    def check_access(self):
        if (
            self.left_spec and self.left_spec.CheckAccess('read') and
            self.right_spec and self.right_spec.CheckAccess('read')
        ):
            return True
        else:
            return False

    def get_deleted_object_ids(
            self,
            switch_left_and_right=False,
            entity=None,
            additional_condition=None
    ):
        """ provides the object ids of objects which are in the left but not the right side"""
        fls.allocate_license('RQM_070')
        if entity is None:
            entity = RQMSpecObject
        if self.left_spec == self.right_spec:
            return []  #
        if additional_condition is None:
            additional_condition = "1=1"
        base_stmt = """
            SELECT left_side.cdb_object_id FROM {table} left_side
            WHERE
                left_side.specification_object_id='{spec_left_id}'
            AND
                {additional_condition}
            AND not EXISTS (
                  SELECT 1 FROM {table} right_side
                      WHERE
                          right_side.specification_object_id='{spec_right_id}'
                      AND
                          left_side.ce_baseline_origin_id=right_side.ce_baseline_origin_id
                  )
        """
        if not switch_left_and_right:
            stmt = base_stmt.format(
                table=entity.__maps_to__,
                spec_left_id=self.left_spec.cdb_object_id,
                spec_right_id=self.right_spec.cdb_object_id,
                additional_condition=additional_condition
            )
        else:
            stmt = base_stmt.format(
                table=entity.__maps_to__,
                spec_left_id=self.right_spec.cdb_object_id,
                spec_right_id=self.left_spec.cdb_object_id,
                additional_condition=additional_condition
            )
        rs = sqlapi.RecordSet2(sql=stmt)
        deleted_ids = []
        for r in rs:
            deleted_ids.append(r['cdb_object_id'])
        if len(deleted_ids) == 0:
            return []

        copied_to_link, copy_of_link = get_copy_link_types(entity.__classname__)
        copy_link = copied_to_link if switch_left_and_right else copy_of_link
        right_ids = (
            self.right_spec.Requirements.cdb_object_id
            if entity == RQMSpecObject else
            self.right_spec.TargetValues.cdb_object_id
        )
        stmt = """select object_object_id from cdb_semantic_link
            where {object_object_condition}
            AND link_type_object_id='{link_type_object_id}'
            AND {subject_object_condition}"""
        stmt = stmt.format(
            object_object_condition=SemanticLink.object_object_id.one_of(*right_ids),
            subject_object_condition=SemanticLink.subject_object_id.one_of(*deleted_ids),
            link_type_object_id=copy_link.cdb_object_id
        )
        semantically_linked_ids = set()
        rs = sqlapi.RecordSet2(sql=stmt)
        for r in rs:
            semantically_linked_ids.add(r['object_object_id'])
        deleted_ids = [x for x in deleted_ids if x not in semantically_linked_ids]
        return deleted_ids
