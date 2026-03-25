# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

import logging

from cdb import i18n
from cdb.objects import fields

from cs.vp import bom
from cs.vp import items
from cs.vp import utils
from cs.vp.bom import bomqueries


class BomItemAttributeAccessor(object):

    def __init__(self, bom_item_rec, item_rec=None, ignore_errors=True):
        """"
        This attribute accessor can be used with an einzelteile_v record to access any kind of bom_item attribute.

        The accessor can also be used with a einzelteile record with the following limitations:
        - Joined and virtual attributes are not accessible
        - Mapped attributes based on joined attributes don't work

        To make joined part attributes accessible, the corresponding part record can be specified by the
        optional item_rec parameter. The part record can be an teile_stamm record or a part_v record.
        If a teile_stamm record is used, chained joined attributes don't work (attributes joined by the part
        and then joined by the bom_item).

        If the ignore_errors flag is true, inaccessible attributes will not lead to an error but the error with
        it's full tracback is logged. En empty string is retured as valiue is this case.
        """

        self.ignore_errors = ignore_errors
        self.bom_item_rec = bom_item_rec
        self.item_rec = item_rec

    def _get_value(self, field_descriptor):
        if isinstance(field_descriptor, fields.JoinedAttributeDescriptor) and \
                field_descriptor.source_adef.getClassDef().getPrimaryTable() == 'teile_stamm' and self.item_rec:
            v = self.item_rec[field_descriptor.source_adef.getName()]
        elif isinstance(field_descriptor, fields.MappedAttributeDescriptor):
            mapped_attr = field_descriptor.ma
            keyval = self.bom_item_rec[mapped_attr.getReferer()]
            keyval = "" if keyval is None else "%s" % keyval
            v = mapped_attr.getValue(keyval)
        else:
            v = self.bom_item_rec[field_descriptor.name]
        return v if v is not None else ""

    def __getitem__(self, name):
        v = ""
        try:
            field_descriptor = bom.AssemblyComponent.GetFieldByName(name)
            if isinstance(field_descriptor, fields.MultiLangAttributeDescriptor):
                v = self._get_value(field_descriptor.getLanguageField())
                if not v:
                    for language in i18n.FallbackLanguages():
                        fd = field_descriptor.getLanguageField(language)
                        if fd:
                            v = self._get_value(fd)
                            if v:
                                break
            else:
                v = self._get_value(field_descriptor)
        except Exception:
            if self.ignore_errors:
                logging.exception("BomItemAttributeAccessor: Failed to access attribute %s" % name)
            else:
                raise
        return v

    def as_dict(self):
        result = dict(self.bom_item_rec)
        for name in bomqueries.get_multilang_attribute_names():
            result[name] = self[name]
        return result


class BomSearch(object):
    def __init__(self, root, condition="", bom_enhancement=None):
        self.root = root
        self.condition = condition.lower()
        self.bom_enhancement = bom_enhancement

    def get_results(self):
        """
        Perform a text search on a bom.
        The search string is mapped against the description tag of the bom components.

        We only match bom components, but the result will be the complete paths from the root node
        to the matched component. This way the front-end knows where to find the matches.

        :returns: list of paths (with each path being a list of Redord's). An empty path is referencing the root node
        """

        # The dictionary matches bom_item object IDs to a boolean value. It indicates whether the BOM item is
        # matched or not. We use it to avoid multiple checks in case a BOM item multiple times. Building the
        # description tag can be expensive, so we prefer to avoid doing it more than once.
        matches = {}

        # result is the list of the complete paths to the matched BOM items.
        result = []

        bom_node_tag = utils.get_description_tag('bom_node_tag_web_search')
        part_attributes = [fd.name for fd in items.Item.GetTableKeys()]
        flat_bom = bomqueries.flat_bom_dict(
            self.root,
            part_attributes=part_attributes,
            bom_enhancement=self.bom_enhancement,
        )

        def search_in_bom(path, item_or_comp):
            for comp in flat_bom[(item_or_comp.teilenummer, item_or_comp.t_index)]:
                bom_item_object_id = comp['cdb_object_id']
                if bom_item_object_id not in matches:
                    description = bom_node_tag % BomItemAttributeAccessor(comp, comp)
                    matches[bom_item_object_id] = self.condition in description.lower()

                comp_path = path + [comp]
                if matches[bom_item_object_id]:
                    result.append(comp_path)

                search_in_bom(comp_path, comp)

        # An empty path is referencing the root part, since there is no assembly component referencing it and
        # we don't want to have heterogeneous search results.
        root_path = []
        # Check condition for the root item.
        if self.condition in self.root.GetDescription().lower():
            result.append(root_path)

        search_in_bom(root_path, self.root)

        result.sort(key=bomqueries.get_path_sort_key)
        return result
