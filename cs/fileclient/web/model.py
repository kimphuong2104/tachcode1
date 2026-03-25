# -*- python -*- coding: UTF-8 -*-
#
# Copyright (C) CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

from __future__ import unicode_literals

from webob import exc as webobexc

import logging
import six

from cdb import util
from cdb.objects.cdb_file import CDB_File

LOG = logging.getLogger(__name__)


class DummyContext(object):

    def __init__(self, **args):
        for k, v in args.iteritems():
            setattr(self, k, v)


class EditFileObject(object):

    def __init__(self, extra_parameters):
        self.oid = extra_parameters.pop("oid", None)

        self.fobj = None
        if self.oid:
            self.fobj = CDB_File.ByKeys(self.oid)

        self.extra_parameters = extra_parameters

    # API Calls

    def get_presigned_blob_write_url(self):
        if self.fobj:
            return {"url": self.fobj.presigned_blob_write_url()}
        else:
            raise webobexc.HTTPNotFound()

    def put_blob_id(self):
        from cdb.platform.mom.hooks import PowerscriptHook
        from cdb.objects.cdb_file import FileChanges
        # The query must contain the required params, else 400
        cdbf_blob_id = self.extra_parameters.get("cdbf_blob_id")
        cdbf_size = self.extra_parameters.get("cdbf_size")
        cdbf_fdate = self.extra_parameters.get("cdbf_fdate")
        cdbf_hash = self.extra_parameters.get("cdbf_hash")
        if not cdbf_blob_id or not cdbf_size or not cdbf_fdate or not cdbf_hash:
            raise webobexc.HTTPBadRequest()
        if self.fobj:
            self.fobj.writeFileHistory(DummyContext(action="modify"))
            self.fobj.deleteDerivedFiles()

            cc = CDB_File.MakeChangeControlAttributes()
            if six.PY2:
                cdbf_fsize = long(cdbf_size)  # noqa: F821
            else:
                cdbf_fsize = int(cdbf_size)
            self.fobj.Update(cdbf_blob_id=cdbf_blob_id,
                             cdbf_size=cdbf_size,
                             cdbf_fsize=cdbf_fsize,
                             cdb_mdate=cc["cdb_mdate"],
                             cdb_mpersno=cc["cdb_mpersno"],
                             cdbf_fdate=cdbf_fdate,
                             cdbf_hash=cdbf_hash)

            file_changes = FileChanges()
            file_changes.addFile(self.fobj.cdb_object_id, "modify")
            callables = PowerscriptHook.get_active_callables("FCUploadFiles")
            for c in callables:
                c(file_changes)

        else:
            raise webobexc.HTTPNotFound()


class UnboundQuery(object):

    def __init__(self, extra_parameters):
        self.extra_parameters = extra_parameters

    # API Calls

    def get_property(self):
        name = self.extra_parameters.get("name")
        if not name:
            raise webobexc.HTTPBadRequest()
        value = util.get_prop(name)
        return value
