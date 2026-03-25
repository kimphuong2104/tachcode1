#!/usr/bin/env python
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 1990 - 2013 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#
"""
Module portfolios_vp

Schnittstellenmodul portfolio - vp
"""

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

# Some imports
from cs.tools import powerreports as PowerReports

from cdb import sqlapi
from cdb import CADDOK
from cdb import auth
from cdb import ue
from cdb import util
from cdb import sig

from cdb.objects import ByID
from cdb.objects import NULL
from cdb.classbody import classbody

from cs.portfolios import Portfolio
from cs.portfolios import PortfolioFolder

import os
import time
import re


# ==============================================================================
# Report Growth-Share Matrix
# ==============================================================================

class GrowthShareMatrix(PowerReports.CustomDataProvider):
    """Custom Data Provider for the Growth-Share matrix of Portfolio folders"""
    CARD = PowerReports.CARD_N
    CALL_CARD = PowerReports.CARD_1

    def getSchema(self):
        from cs.vp.products import Product
        schema = PowerReports.XSDType(self.CARD, Product)
        schema.add_attr("growth", sqlapi.SQL_FLOAT)
        schema.add_attr("share", sqlapi.SQL_FLOAT)
        schema.add_attr("turnover", sqlapi.SQL_FLOAT)

        return schema

    def getData(self, parent_result, source_args, **kwargs):
        from cs.metrics import qualitycharacteristics as QualityCharacteristics

        # Get the portfolio folder
        folder_or_portfolio = None
        if isinstance(parent_result, PowerReports.ReportData):
            folder_or_portfolio = parent_result.getObject()
        if folder_or_portfolio is None:
            raise RuntimeError("This provider needs a portfolio "
                               "or a portfolio folder as parameter")

        growth_def = QualityCharacteristics.ObjectQCDefinition.ByKeys(identifier="EMG")
        share_def = QualityCharacteristics.ObjectQCDefinition.ByKeys(identifier="RMS")
        turnover_def = QualityCharacteristics.ObjectQCDefinition.ByKeys(identifier="TPY")

        if not growth_def or not share_def:
            raise RuntimeError("This provider needs the quality characteristics"
                               " EMG and RMS")

        growth_def_id = growth_def.cdb_object_id
        share_def_id = share_def.cdb_object_id
        turnover_def_id = turnover_def.cdb_object_id

        result = PowerReports.ReportDataList(self)
        for product in folder_or_portfolio.AllProducts:
            data = PowerReports.ReportData(self, product)
            has_growth = False
            has_share = False

            growths = product.ObjectQualityCharacteristics.KeywordQuery(cdbqc_def_object_id=growth_def_id)
            if growths and growths[0].act_value != NULL:
                growth = growths[0].act_value / 100.0
                data["growth"] = growth
                has_growth = True

            shares = product.ObjectQualityCharacteristics.KeywordQuery(cdbqc_def_object_id=share_def_id)
            if shares and shares[0].act_value != NULL:
                share = shares[0].act_value / 100.0
                data["share"] = share
                has_share = True

            turnovers = product.ObjectQualityCharacteristics.KeywordQuery(cdbqc_def_object_id=turnover_def_id)
            turnover = turnovers[0].act_value if turnovers else 0
            data["turnover"] = turnover if turnover else 0.1

            if has_growth and has_share:
                result.append(data)
        return result


@sig.connect(Portfolio, "growth_share_report", "now")
def portfolio_growth_share_report(self, ctx):
    Portfolio.generate_report({"name": "PortfolioGrowthShareMatrix",
                               "report_title": "PortfolioGrowthShareMatrix",
                               "iso_code": "de"},
                              ctx, [self], view=True)


@sig.connect(PortfolioFolder, "growth_share_report", "now")
def portfolio_folder_growth_share_report(self, ctx):
    PortfolioFolder.generate_report({"name": "GrowthShareMatrix",
                                     "report_title": "GrowthShareMatrix",
                                     "iso_code": "de"},
                                    ctx, [self], view=True)


# ==============================================================================
# Quality characteristics
# ==============================================================================

@classbody
class PortfolioFolder(object):
    def _get_non_invalid_products(self):
        from cs.vp.products import Product
        products = [x for x in [Product.ByKeys(object_id)
                           for object_id in self.FolderContents.cdb_content_id] if not x is None and x.status != 300]
        return products

    @staticmethod
    def number_of_products(qc):
        self = ByID(qc.cdbf_object_id)
        result = len(set([product.code
                          for product in self._get_non_invalid_products()]))

        result += self._get_childern_values(qc)
        return result

    @staticmethod
    def turnover_products_per_year(qc):
        from cs.metrics import qualitycharacteristics as QualityCharacteristics
        self = ByID(qc.cdbf_object_id)
        tpy_def = QualityCharacteristics.ObjectQCDefinition.ByKeys(identifier="TPY")

        result = 0
        for product in self._get_non_invalid_products():
            tpys = product.ObjectQualityCharacteristics.KeywordQuery(cdbqc_def_object_id=tpy_def.cdb_object_id)
            if tpys:
                tpy = tpys[0]
                tpy.Association.ComputationRule.compute(tpy)
                result += tpy.act_value

        result += self._get_childern_values(qc)
        return result
