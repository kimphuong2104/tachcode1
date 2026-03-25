#!/usr/bin/env powerscript
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 2013 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#

__revision__ = "$Id$"

from cdb.classbody import classbody
from cdb.objects import Forward, Object, Reference_1, Reference_N, ReferenceMethods_N
from cs.pcs.projects import Project
from cs.vp.products import Product

ProjectLink = Forward(__name__ + ".ProjectLink")


class ProjectLink(Object):
    __maps_to__ = "cdbvp_project2product"
    __classname__ = "cdbvp_project2product"

    Product = Reference_1(Product, ProjectLink.cdbvp_product_id)
    Project = Reference_1(Project, ProjectLink.cdb_project_id)


@classbody
class Product(object):
    ProjectLinks = Reference_N(
        ProjectLink, ProjectLink.cdbvp_product_id == Product.cdb_object_id
    )

    def _getProjects(self):
        return [p.Project for p in self.ProjectLinks]

    Projects = ReferenceMethods_N(Project, _getProjects)
