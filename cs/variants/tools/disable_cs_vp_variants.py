# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2019 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

from cdb import sqlapi, transactions

# Exported objects
__all__ = ["disable_cs_vp_variants"]


def disable_cs_vp_variants():
    with transactions.Transaction():
        # === Operations ===

        # product

        # All operations assigned to cs.vp.variants
        #
        # - Gefilterte Produktstruktur
        # - Stücklistenvergleich
        # - Stücklistenreport
        # - Variantenmatrix
        # - Upload csv to client
        #
        sqlapi.SQLdelete(
            " FROM cdb_op_owner WHERE classname = 'cdbvp_product' and cdb_module_id = 'cs.vp.variants'"
        )

        # Produktübersicht
        sqlapi.SQLdelete(
            " FROM cdb_op_owner WHERE classname = 'cdbvp_product' and name = 'cdbvp_product'"
        )

        # Varianteneditor
        sqlapi.SQLdelete(
            " FROM cdb_op_owner WHERE classname = 'cdbvp_product' and name = 'cdbvp_product_view'"
        )

        # cs.viewstation
        # disable *all* operations for viewstation on product
        sqlapi.SQLdelete(
            " FROM cdb_op_owner WHERE classname = 'cdbvp_product' and cdb_module_id = 'cs.viewstation'"
        )

        # part

        # All operations assigned to cs.vp.variants
        #
        # - Variantenmanagement / gefilterte Stückliste
        # - Stücklistenposition anzeigen
        #
        sqlapi.SQLdelete(
            " FROM cdb_op_owner WHERE classname = 'part' and cdb_module_id = 'cs.vp.variants'"
        )

        # bom_item

        # - Show SAP Selection Condition
        sqlapi.SQLdelete(
            " FROM cdb_op_owner WHERE classname = 'bom_item' and cdb_module_id = 'cs.vp.variants'"
        )

        # === Relationships ===

        # All relationships with specific referer
        sqlapi.SQLdelete(
            "FROM cdb_rs_owner WHERE name IN (SELECT name FROM cdb_relships WHERE cdb_module_id = \
            'cs.vp.variants' AND referer IN ('bom_item', 'part', 'cdbvp_product'))"
        )

        # === Reports ===

        sqlapi.SQLdelete(
            "FROM cdbxml_report_grant WHERE cdb_module_id = 'cs.vp.variants'"
        )

        # === Menu ===

        # Catalog properties in the catalog management
        sqlapi.SQLdelete(
            "FROM cdb_tree_owner WHERE id = '58c7edde-4732-11e1-98c0-001bfc744136'"
        )

        # === Class Attributes ===

        # bom_item
        sqlapi.SQLupdate(
            "cdbdd_field SET db_default = NULL WHERE classname = 'bom_item' AND  \
            (field_name = 'cdbvp_positionstyp' OR field_name = 'cdbvp_has_condition')"
        )


if __name__ == "__main__":
    disable_cs_vp_variants()
