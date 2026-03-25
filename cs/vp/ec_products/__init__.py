# !/usr/bin/env powerscript
# -*- python -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 2013 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/


from cdb import classbody
from cdb import sqlapi
from cdb import util

from cdb.objects import Reference_N
from cdb.objects import Forward
from cs.tools import powerreports

from cs.vp.products import Product
from cs.vp import products
from cs.ec import EngineeringChange

from cs.metrics.qualitycharacteristics import QCDefinition
from cs.metrics import qualitycharacteristics

from cs.ec import get_pydate_format
from cs.ec import get_pydatetime_format
from functools import reduce


fEngineeringChange = Forward("cs.ec.EngineeringChange")
fProduct = Forward("cs.vp.products.Product")


@classbody.classbody
class Product(object):
    EngineeringChanges = Reference_N(fEngineeringChange,
                                     fEngineeringChange.product_object_id == fProduct.cdb_object_id)


# Metrics

def compute_number_of_ecs(qc, ec_state):
    conditions = []

    for grouping in qc.Groupings:
        field = getattr(Product, grouping.attribute_name)
        conditions.append(field == grouping.attribute_value)

    if conditions:
        pr_condition = reduce(lambda x: x & x, conditions)
        pr_stmt = "SELECT cdb_object_id FROM {classname} WHERE {condition}".format(
            classname=Product.__classname__,
            condition=str(pr_condition))

        ecs = EngineeringChange.Query(EngineeringChange.ec_state == ec_state)\
            .Query("product_object_id IN (%s)" % pr_stmt)
        return len(ecs)


def compute_number_of_ecrs(qc):
    return compute_number_of_ecs(qc, "ECR")


def compute_number_of_ecos(qc):
    return compute_number_of_ecs(qc, "ECO")


# Reports

class NumberOfECsReport(powerreports.CustomDataProvider):
    CARD = powerreports.CARD_N
    CALL_CARD = powerreports.CARD_0

    _STATE_PROPS = {"ECR": ("#ECRS", "cdbec_number_of_ecrs"),
                    "ECO": ("#ECOS", "cdbec_number_of_ecos")}

    def getSchema(self):
        schema = powerreports.XSDType(self.CARD)
        schema.add_attr("maturity", sqlapi.SQL_CHAR)
        schema.add_attr("ec_state", sqlapi.SQL_CHAR)
        schema.add_attr("value", sqlapi.SQL_FLOAT)
        return schema

    def _get_data_for_state(self, ec_state):
        qccode, state_label = self._STATE_PROPS[ec_state]
        state_name = util.get_label(state_label)

        result = powerreports.ReportDataList(self)

        qcdef = QCDefinition.ByKeys(identifier=qccode)
        if qcdef:
            for qc in qcdef.QualityCharacteristics:
                maturity = ""
                grps = qc.Groupings.KeywordQuery(attribute_name="maturity")
                if grps:
                    matobj = products.Maturity.ByKeys(grps[0].attribute_value)
                    if matobj:
                        maturity = matobj.Name['']

                data = powerreports.ReportData(self)
                data["maturity"] = maturity
                data["ec_state"] = state_name
                data["value"] = qc.act_value

                result.append(data)

        return result

    def getData(self, parent_result, source_args, **kwargs):
        return self._get_data_for_state("ECR") + self._get_data_for_state("ECO")


class NumberOfECsHistory(powerreports.CustomDataProvider):
    CARD = powerreports.CARD_N
    CALL_CARD = powerreports.CARD_0

    _STATE_PROPS = {"ECR": ("#ECRS", "cdbec_number_of_ecrs"),
                    "ECO": ("#ECOS", "cdbec_number_of_ecos")}

    def getSchema(self):
        schema = powerreports.XSDType(self.CARD)
        schema.add_attr("maturity", sqlapi.SQL_CHAR)
        schema.add_attr("ec_state", sqlapi.SQL_CHAR)
        schema.add_attr("date", sqlapi.SQL_DATE)
        schema.add_attr("value", sqlapi.SQL_FLOAT)
        return schema

    def _get_data_for_state(self, ec_state):
        qccode, state_label = self._STATE_PROPS[ec_state]
        state_name = util.get_label(state_label)

        result = powerreports.ReportDataList(self)

        qcdef = QCDefinition.ByKeys(identifier=qccode)
        if qcdef:
            for qc in qcdef.QualityCharacteristics:
                maturity = ""
                grps = qc.Groupings.KeywordQuery(attribute_name="maturity")
                if grps:
                    matobj = products.Maturity.ByKeys(grps[0].attribute_value)
                    if matobj:
                        maturity = matobj.Name['']

                for hist in qc.Historie.Query("1=1", order_by="cdb_cdate desc"):
                    data = powerreports.ReportData(self)
                    data["maturity"] = maturity
                    data["ec_state"] = state_name
                    data["date"] = hist.cdb_cdate.strftime(get_pydatetime_format())
                    data["value"] = hist.value

                    result.append(data)

        return result

    def getData(self, parent_result, source_args, **kwargs):
        return self._get_data_for_state("ECR") + self._get_data_for_state("ECO")


def _generate_demo_data(startdate, enddate):
    import datetime
    import itertools
    import random
    from cdb import cdbtime
    from cdb import auth

    maturities = products.Maturity.Query()
    qcdefs = QCDefinition.Query(QCDefinition.identifier.one_of("#ECRS", "#ECOS"))

    for qcdef, maturity in itertools.product(qcdefs, maturities):
        qcs = [qc for qc in qcdef.QualityCharacteristics
               if maturity.cdb_object_id in qc.Groupings.attribute_value]

        if qcs:
            qc = qcs[0]

            currentdate = datetime.datetime(day=1,
                                            month=startdate.month,
                                            year=startdate.year)
            while currentdate <= enddate:
                cond = (qualitycharacteristics.History.cdb_cdate >= currentdate) & \
                    (qualitycharacteristics.History.cdb_cdate <= currentdate + datetime.timedelta(days=1))
                hists = qc.Historie.Query(cond)
                if hists:
                    hist = hists[0]
                else:
                    args = {
                        "cdbqc_object_id": qc.cdb_object_id,
                        "value": 0,
                        "cdb_cdate": currentdate.strftime(get_pydate_format()),
                        "cdb_cpersno": auth.persno}
                    hist = qualitycharacteristics.History.Create(**args)
                hist.value = random.randint(0, 500)

                nextdate = datetime.date(day=1, month=(currentdate.month % 12) + 1,
                                         year=currentdate.year if currentdate.month != 12 else currentdate.year + 1)
                currentdate = datetime.datetime(day=nextdate.day,
                                                month=nextdate.month,
                                                year=nextdate.year)
