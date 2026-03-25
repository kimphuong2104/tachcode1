#!/usr/bin/env powerscript
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

from cdb.sqlapi import NULL, SQLupdate

from cs.pcs.checklists import Checklist, ChecklistItem


class AdjustRatingIDOfCLsAndCLIs:
    def run(self):
        condition1 = (Checklist.rating_id == "") | (Checklist.rating_id == NULL)
        checklists = Checklist.Query(condition1)
        for checklist in checklists:
            checklist.rating_id = "clear"

        condition2 = (ChecklistItem.rating_id == "") | (ChecklistItem.rating_id == NULL)
        checklist_items = ChecklistItem.Query(condition2)
        for checklist_item in checklist_items:
            checklist_item.rating_id = "clear"


class AdjustEvaluatorOfCLIs:
    """
    Set Evaluator to '' in case the rating was set to 'Not Evaluated'.
    """

    def run(self):
        condition = (
            (ChecklistItem.rating_id == "")
            | (ChecklistItem.rating_id == NULL)
            | (ChecklistItem.rating_id == "clear")
        )
        checklist_items = ChecklistItem.Query(condition)
        for checklist_item in checklist_items:
            checklist_item.evaluator = ""


class MarkIrrelevantRatings:
    """
    Mark some ratings to be displayed greyed-out in the UI.
    Because of a database default value, these come in patched.
    This effectively reverts to the product values.
    """

    def run(self):
        SQLupdate(
            "cdbpcs_rat_val SET irrelevant = 1 WHERE rating_id = 'nicht_relevant'"
        )


class SetRedGreenYellowDescription:
    """
    Make sure new rating scheme descriptions do not produce patches.
    Because these are descriptive and not functional, overwriting customized
    descriptions is an acceptable tradeoff for less update friction.
    """

    DESCRIPTIONS = [
        ("Grades", "Rating with german school grades from 1 (best) to 6 (worst)"),
        (
            "RedGreenYellow",
            "Rating with traffic light colors (Red, Green, Yellow) "
            'and simple "dot" icons',
        ),
    ]

    def run(self):
        for name, description in self.DESCRIPTIONS:
            SQLupdate(
                f"cdbpcs_rat_def SET description = '{description}' "
                f"WHERE name = '{name}'"
            )


class CorrectTemplateValues:
    def correct_template(self, table_name):
        update_sql = f"""{table_name} SET template = 0
                    WHERE template is NULL"""
        SQLupdate(update_sql)

    def run(self):
        self.correct_template("cdbpcs_checklst")
        self.correct_template("cdbpcs_cl_item")


pre = []
post = [
    AdjustRatingIDOfCLsAndCLIs,
    MarkIrrelevantRatings,
    SetRedGreenYellowDescription,
    AdjustEvaluatorOfCLIs,
    CorrectTemplateValues,
]
