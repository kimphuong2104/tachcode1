# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 2023 CONTACT Software GmbH.
# All rights reserved.
# https://www.contact-software.com/

"""
Module applrpcutils

This is the documentation for the applrpcutils module.
"""

from __future__ import absolute_import


__docformat__ = "restructuredtext en"


# Exported objects
__all__ = []

import base64
import os
import tempfile
import six
import zlib


class RemoteFile(object):
    def __init__(self, file_id, local_fname, filetype):
        """
        Represents a local file
        :param file_id: str: unique ID in request
        :param local_name: local filename to access the file
        :param filetype: filtype for creation in CDB
        """
        self.file_id = file_id
        self.local_fname = local_fname
        self.filetype = filetype

    def to_json_struct(self):
        """
        generates json rpc compatible structure from given input
        :returns None on failure else:
          {"fileid": <id>,
           "fcontent": <base64 compressed file content>,
           "filetype": <filetype for cdb>,
           "extension": <extension of file>
          }
        """
        json_data = None
        if self.local_fname and os.path.isfile(self.local_fname) and self.file_id:
            with open(self.local_fname, "rb") as f:
                cdata = zlib.compress(f.read())
                if six.PY3:
                    b64_data = base64.standard_b64encode(cdata).decode("utf-8")
                else:
                    b64_data = base64.standard_b64encode(cdata)
                cdata = None
                json_data = {
                    "fileid": self.file_id,
                    "fcontent": b64_data,
                    "filetype": self.filetype,
                    "extension": os.path.splitext(self.local_fname)[1],
                }
        return json_data

    @classmethod
    def from_json_struct(cls, json_struct):
        """
        reads json info and returns Remotefile instance
        remove content from json_struct if file was written to disc
        """
        remote_file = None
        content = json_struct.get("fcontent")
        if six.PY3:
            content = content.encode("utf-8")
        file_id = json_struct.get("fileid")
        filetype = json_struct.get("filetype")
        extension = json_struct.get("extension")
        if content and file_id:
            fhandle, fname = tempfile.mkstemp(suffix=extension)
            b64decoded = base64.standard_b64decode(content)
            tfile = os.fdopen(fhandle, "wb")
            tfile.write(zlib.decompress(b64decoded))
            tfile.close()
            del json_struct["fcontent"]
            remote_file = cls(file_id, fname, filetype)
        return remote_file


class ApplRemoteRpc(object):
    @classmethod
    def to_json(cls, parameter, files):
        """
        :param parameter: json compatible structure
        :param files: List of RemoteFiles or None
        """
        json_files = None
        if files is not None:
            json_files = [f.to_json_struct() for f in files]
        json_data = {"parameter": parameter, "files": json_files}
        return json_data

    @classmethod
    def from_json(cls, json_data):
        """
        :param json_data: Import json struct

        :return parameter dict and list of RemoteFiles
        """
        files = []
        parameter = json_data["parameter"]
        json_files = json_data.get("files")
        if json_files:
            files = [RemoteFile.from_json_struct(json_f) for json_f in json_files]
        return parameter, files
