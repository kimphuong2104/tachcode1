# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2016 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

from cdb import sqlapi
from cdb import ue
from cdb import util

from cdb.transactions import Transaction
from cs.classification.classes import ClassProperty


def update_excludes(class_property, exclude, value_ids):
    with Transaction():
        records = sqlapi.RecordSet2("cs_property_value_exclude",
                                    "classification_class_id='%s' AND class_property_id='%s'" % (
                                        class_property.classification_class_id,
                                        class_property.cdb_object_id))

        entries = dict([(record.property_value_id, record) for record in records])

        for value_id in value_ids:
            entry = entries.get(value_id, None)
            if 1 == exclude:
                class_property.reset_default_value(value_id)
                if entry:
                    entry.update(exclude=exclude)
                else:
                    ins = util.DBInserter("cs_property_value_exclude")
                    ins.add("classification_class_id", class_property.classification_class_id)
                    ins.add("class_property_id", class_property.cdb_object_id)
                    ins.add("property_value_id", value_id)
                    ins.add("property_id", class_property.catalog_property_id)
                    ins.add("exclude", exclude)
                    ins.insert()
            else:
                if entry:
                    entry.delete()


def doit(ctx):
    class_property = ClassProperty.ByKeys(cdb_object_id=ctx.parent.cdb_object_id)
    if class_property.external_modification_only:
        raise ue.Exception("cs_classification_external_class_not_modifiable")

    activate = 1 if ctx.action == "cs_classification_propval_excl" else 0

    value_ids = []
    for obj in ctx.objects:
        value_ids.append(obj.value_object_id)

    update_excludes(class_property, activate, value_ids)
    class_property.set_has_enum_values()

    ctx.refresh_tables(['cs_property_value_exclude', 'cs_property_value_exclude_v'])


if __name__ == '__main__':
    ue.run(doit, "cdbscript")
