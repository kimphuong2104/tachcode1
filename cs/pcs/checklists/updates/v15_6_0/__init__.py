#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

from cdb import ddl, sqlapi


class GradesNumbers2Words:
    """
    prevent patches of cdbpcs_rat_val user-readable names
    if previous value is the default (the ID)
    """

    def run(self):
        rating_ids = ["1", "2", "3", "4", "5", "6"]
        rating_value_en = ["One", "Two", "Three", "Four", "Five", "Six"]
        rating_value_de = ["Eins", "Zwei", "Drei", "Vier", "Fünf", "Sechs"]
        t = ddl.Table("cdbpcs_rat_val")
        if t.exists():
            for i, rating_id in enumerate(rating_ids):
                sqlapi.SQLupdate(
                    f"cdbpcs_rat_val SET rating_value_en='{rating_value_en[i]}', "
                    f"rating_value_de='{rating_value_de[i]}' "
                    f"WHERE rating_id='{rating_id}' AND name='Grades'"
                )


class RatingColors:
    "prevent patches of cdbpcs_rat_val.color if previously empty"

    def run(self):
        updates = [
            ("1", "elements-success"),
            ("2", "elements-success"),
            ("3", "elements-info"),
            ("4", "elements-info"),
            ("5", "elements-danger"),
            ("6", "elements-danger"),
            ("clear", ""),
            ("nicht_relevant", "gray"),
        ]

        t = ddl.Table("cdbpcs_rat_val")
        if t.exists():
            for rating_id, color in updates:
                sqlapi.SQLupdate(
                    f"cdbpcs_rat_val SET color='{color}' "
                    "WHERE (color = '' OR color IS NULL)"
                    f"AND rating_id='{rating_id}' "
                    "AND name='Grades'"
                )


pre = []
post = [GradesNumbers2Words, RatingColors]
