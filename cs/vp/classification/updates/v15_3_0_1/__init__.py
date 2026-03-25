# !/usr/bin/env powerscript
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 1990 - 2013 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

from cdb import sqlapi


class UpdateSMLDecomposition(object):
    """ The SML decompositions needs to be updated after the module
        cdb.sml has been moved to cs.vp.classification.sml
    """

    def run(self):
        pynames = [
            # (identifier, fqpyname_generator)
            ("cdbsml_cgroup", "cs.vp.classification.sml.rebuild_smldecomp"),
            ("cdbsml_propcat", "cs.vp.classification.sml.CatDecompBuilder.rebuild_decomposition")
        ]

        for identifier, fqpyname_generator in pynames:
            stmt = "cdb_decomp SET fqpyname_generator='{fqpyname_generator}' " \
                   "WHERE identifier='{identifier}'".format(identifier=identifier,
                                                            fqpyname_generator=fqpyname_generator)
            sqlapi.SQLupdate(stmt)


pre = []
post = [UpdateSMLDecomposition]


if __name__ == '__main__':
    for UT in post:
        UT().run()
