# !/usr/bin/env powerscript
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 2020 CONTACT Software GmbH
# All rights reserved.
# https://www.contact.de/

"""
|cs.threed| provides the option to view and edit BCF (BIM Collaboration Format) files which
are used to exchange additional data for IFC models. 
This Data is divided into topics. That allows the information to be assigned to specific issues.

Changing pieces of this information in the :guilabel:`3D Cockpit` 
emits specific signals which can then be used to process these changes.
The data that is transmitted slightly differs based on the trigger event.

The following parts of data are transmitted by all of these signals as a `dict`:

+--------------+----------------------------------------------------------------+
| `ctx_object` | Contains the current context object                            |
+--------------+-----------+----------------------------------------------------+
| `data`       | `meta`    | `bcf_filename`, `z_nummer`, `z_index` `topic_id`   |
|              +-----------+----------------------------------------------------+
|              | `changes` | Changes specific to the event                      |
+--------------+-----------+----------------------------------------------------+
"""

from zipfile import ZipFile
import os

from cdb import sig
from cdb.objects.pdd.Files import Sandbox

from cs.documents import Document

BCF_TOPIC_SAVED = sig.signal()
"""
This signal is emitted either when a new topic is created or the attributes of an existing topic are edited.

**Usage:**

.. code-block:: python

   from cdb import sig
   from cs.threed.hoops.bcf import BCF_TOPIC_SAVED

   @sig.connect(BCF_TOPIC_SAVED)
   def bcf_topic_saved(ctx_object, data):
      pass

**Data:**

+-----------+-----------------------+-----------------------------------------------------+
| `meta`    | `create_new_topic`    | Flag indicating creation of a new topic (`true`)    |
|           |                       | or saving to existing topic (false)                 |
+-----------+-----------------------+-----------------------------------------------------+
| `changes` | Topic Markup Attributes as defined in BCF Standard (v2.1)                   |
|           | (https://github.com/buildingSMART/BCF-XML/tree/v2.1/Documentation#topic)    |
+-----------+-----------------------------------------------------------------------------+
"""

BCF_TOPIC_VIEWPOINT_ADDED = sig.signal()
"""
This signal is emitted when a new viewpoint is created.

**Usage:**

.. code-block:: python

   from cdb import sig
   from cs.threed.hoops.bcf import BCF_TOPIC_VIEWPOINT_ADDED

   @sig.connect(BCF_TOPIC_VIEWPOINT_ADDED)
   def add_viewpoint(ctx_object, data):
      pass

**Data:**

+-----------+-------------------+---------------------+----------------------------------------------------------------------------------+
| `changes` | `snapshot`        | `filename`          | Snapshot filename                                                                |
|           |                   +---------------------+----------------------------------------------------------------------------------+
|           |                   | `data`              | PNG as list of bytes                                                             |
|           +-------------------+---------------------+----------------------------------------------------------------------------------+
|           | `viewpoint`       | Viewpoint data as defined in BCF Standard (v2.1)                                                       |
|           |                   | (https://github.com/buildingSMART/BCF-XML/tree/v2.1/Documentation#visualization-information-bcfv-file) |
|           +-------------------+---------------------+----------------------------------------------------------------------------------+
|           | `markupViewpoint` | `guid`              | UUID of the viewpoint / snapshot relation                                        |
|           |                   +---------------------+----------------------------------------------------------------------------------+
|           |                   | `index`             | Viewpoint index                                                                  |
|           |                   +---------------------+----------------------------------------------------------------------------------+
|           |                   | `snapshotFilename`  | Snapshot filename                                                                |
|           |                   +---------------------+----------------------------------------------------------------------------------+
|           |                   | `viewpointFilename` | Viewpoint filename                                                               |
+-----------+-------------------+---------------------+----------------------------------------------------------------------------------+

"""

BCF_TOPIC_COMMENT_ADDED = sig.signal()
"""
This signal is emitted when a comment is added to the selected viewpoint.

**Usage:**

.. code-block:: python

   from cdb import sig
   from cs.threed.hoops.bcf import BCF_TOPIC_COMMENT_ADDED

   @sig.connect(BCF_TOPIC_COMMENT_ADDED)
   def add_comment(ctx_object, data):
      pass

**Data:**

+-----------+-----------------+----------------------------------------------------+
| `changes` | `author`        | CDB username of the author                         |
|           +-----------------+----------------------------------------------------+
|           | `date`          | Creation date                                      |
|           +-----------------+----------------------------------------------------+
|           | `guid`          | Comment UUID                                       |
|           +-----------------+----------------------------------------------------+
|           | `text`          | Comment text                                       |
|           +-----------------+----------------------------------------------------+
|           | `viewpointGuid` | UUID of the viewpoint, the comment is assigned to  |
+-----------+-----------------+----------------------------------------------------+
"""

def save_topic(ctx_object, request):
    data = request.json
    sig.emit(BCF_TOPIC_SAVED)(ctx_object, data)


def add_viewpoint(ctx_object, request):
    data = request.json
    sig.emit(BCF_TOPIC_VIEWPOINT_ADDED)(ctx_object, data)


def add_comment(ctx_object, request):
    data = request.json
    sig.emit(BCF_TOPIC_COMMENT_ADDED)(ctx_object, data)


def make_bcf_file(data):
    meta_data = data['meta']
    bcf_filename = meta_data['bcf_filename']
    z_nummer = meta_data['z_nummer']
    z_index = meta_data['z_index']

    markup_filename = "markup.bcf"

    topics = data['bcf']

    with Sandbox() as sb:
        bcf_path = os.path.join(sb.location, bcf_filename)

        bcf_zip = ZipFile(bcf_path, 'w')

        for t_idx, topic in topics.items():
            xml_markup = topic['markup']
            xml_viewpoints = topic['viewpoints']
            snapshots = topic['snapshots']

            markup_path = os.path.join(sb.location, markup_filename)

            with open(markup_path, "w") as f:
                f.write(xml_markup)
                f.close()

            for key in xml_viewpoints.keys():
                with open(os.path.join(sb.location, key), "w") as f:
                    f.write(xml_viewpoints[key])
                    f.close()

            for idx, snap in snapshots.items():
                with open(os.path.join(sb.location, idx), "wb") as f:
                    binary = bytearray(snap)
                    f.write(binary)
                    f.close()

            bcf_zip.write(markup_path, os.path.join(t_idx, markup_filename))

            for key in xml_viewpoints.keys():
                bcf_zip.write(os.path.join(sb.location, key), os.path.join(t_idx, key))

            for idx, snap in snapshots.items():
                bcf_zip.write(os.path.join(sb.location, idx), os.path.join(t_idx, idx))

        bcf_zip.close()

        d = Document.ByKeys(z_nummer=z_nummer, z_index=z_index)
        for f in d.Files.KeywordQuery(cdbf_name=bcf_filename):
            f.checkin_file(bcf_path)


@sig.connect(BCF_TOPIC_SAVED)
def bcf_topic_saved(ctx_object, data):
    make_bcf_file(data)


@sig.connect(BCF_TOPIC_VIEWPOINT_ADDED)
def bcf_topic_viewpoint_added(ctx_object, data):
    make_bcf_file(data)


@sig.connect(BCF_TOPIC_COMMENT_ADDED)
def bcf_topic_comment_added(ctx_object, data):
    make_bcf_file(data)
