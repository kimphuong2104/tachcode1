# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2016 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

from cs.documents import DocumentReference

def generateDocumentReference(parent, child, name, reltype="SolidWorks:ref"):
    DocumentReference.Create(
        z_nummer=parent.z_nummer,
        z_index=parent.z_index,
        z_nummer2=child.z_nummer,
        z_index2=child.z_index,
        logischer_name=name,
        reltype=reltype,
        cdb_link="0"
    )
