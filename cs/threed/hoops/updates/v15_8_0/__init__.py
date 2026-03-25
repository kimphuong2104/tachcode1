# !/usr/bin/env powerscript
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/


class MigrateViewVisibilities(object):
    """
    Migrate geometry nodes to visibilities
    """

    def run(self):
        import collections
        import json
        from cdb import sqlapi
        from cdb import util
        from cs.threed.hoops import markup

        GEOMETRY_NODE_TYPES = ["visibilityExceptions", "hiddenNodes", "transparentNodes"]

        sqlapi.SQLupdate("threed_hoops_view SET default_visibility = '1' WHERE default_visibility IS NULL")

        all_views = markup.View.Query()
        geom_nodes = markup.GeometryNode.KeywordQuery(
            parent_object_id=[view.cdb_object_id for view in all_views])

        geom_nodes_by_view_id = collections.defaultdict(list)
        for node in geom_nodes:
            geom_nodes_by_view_id[node.parent_object_id].append(node)

        visibilities_by_view_id = collections.defaultdict(dict)
        for view_id, nodes in geom_nodes_by_view_id.items():
            for node_type in GEOMETRY_NODE_TYPES:
                visibilities_by_view_id[view_id][node_type] = [
                    int(n.node_id) for n in nodes if n.relationship == node_type
                ]

        for view_id, visibilities in visibilities_by_view_id.items():
            visibilities_str = json.dumps(visibilities)
            util.text_write("threed_hoops_view_visibilities", ['view_object_id'], [view_id], visibilities_str)


pre = []
post = [MigrateViewVisibilities]

if __name__ == "__main__":
    MigrateViewVisibilities().run()
