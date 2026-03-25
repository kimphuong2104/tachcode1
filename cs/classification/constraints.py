# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2016 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

"""
Module constraints

This is the documentation for the constraints module.
"""

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

# Some imports

from cdb.objects import core
from cdb.objects import references
from cdb.objects import expressions

fClassificationClass = expressions.Forward("cs.classification.classes.ClassificationClass")
fConstraint = expressions.Forward("cs.classification.constraints.Constraint")


class Constraint(core.Object):
    __maps_to__ = "cs_classification_constraint"
    __classname__ = "cs_classification_constraint"

    Class = references.Reference_1(
        fClassificationClass,
        fClassificationClass.cdb_object_id == fConstraint.classification_class_id
    )

    def _clear_constraints_cache(self, ctx):
        from cs.classification.validation import ClassificationValidator
        ClassificationValidator.reload_constraints()

    event_map = {
        (('modify', 'create', 'copy', 'delete'), 'post'): '_clear_constraints_cache'
    }
