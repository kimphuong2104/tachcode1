# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 2021 CONTACT Software GmbH
# All rights reserved.

from cdb.platform.mom.entities import Class
from cdb.platform.mom.fields import DDJoinedField

_Joined_Part_Fields = {}


def get_joined_part_fields(classname):
    if not classname:
        return []
    joined_fields = _Joined_Part_Fields.get(classname, None)
    if joined_fields is None:
        part_base_class = Class.ByKeys('part')
        part_classnames = (part_base_class.getSubClassNames() + [part_base_class.classname])
        joined_fields = []
        clazz = Class.ByKeys(classname)
        for field in clazz.DDAllFields:
            if isinstance(field, DDJoinedField):
                if field.joined_classname in part_classnames:
                    joined_fields.append({
                        "field_name": field.field_name,
                        "joined_field_name": field.joined_field_name
                    })
        _Joined_Part_Fields[classname] = joined_fields
    return joined_fields


def set_dlg_joined_part_fields(ctx, obj, item):
    if ctx and obj:
        classname = obj.cdb_classname if obj.HasField("cdb_classname") else getattr(obj, "__classname__", None)
        joined_fields = get_joined_part_fields(classname)
        attrs = ctx.dialog.get_attribute_names()
        for joined_field in joined_fields:
            if joined_field["field_name"] in attrs:
                if item:
                    ctx.set(joined_field["field_name"], item[joined_field["joined_field_name"]])
                else:
                    ctx.set(joined_field["field_name"], None)
