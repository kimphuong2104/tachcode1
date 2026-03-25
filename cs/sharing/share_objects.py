#!/usr/bin/env powerscript
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2020 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/
#
"""
"Share" context operation for business objects

example usage:

.. code-block:: python

    from cs.sharing.share_objects import WithSharing
    from cdb.objects.org import Organization


    class MyOrg(Organization, WithSharing):
        pass

"""

from __future__ import absolute_import

from cs.sharing.groups import RecipientCollection

__docformat__ = "restructuredtext en"

OP_NAME = "cdb_share_objects"
OP_URL = "/share_objects"


class WithSharing(object):
    # basic support
    def on_cdb_share_objects_now(self, ctx):
        show_dialog(self, ctx)

    def getSubject(self, sharingGroup=None):
        return getSubject(self, sharingGroup)

    def getResponsibleSubjects(self, sharingGroup):
        "support for ObjectSharingGroup 'Responsible'"
        return RecipientCollection(objects=self.Subject.getPersons()).subjects


def show_dialog(obj, ctx):
    objects = [o.cdb_object_id for o in obj.PersistentObjectsFromContext(ctx)]
    ctx.url(OP_URL + "?attachments=%s" % (",".join(objects)), icon="elements_share")


def getSubject(obj, sharingGroup=None):
    return [(obj.subject_id, obj.subject_type)]
