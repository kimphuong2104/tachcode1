#!/usr/bin/env python
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/
#

"""
*********************************
Computation of quality characteristics
*********************************
"""

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

from cdb.objects import Object
from cdb.objects import Forward
from cdb.objects import NULL
from cdb.objects import LocalizedField
from cdb.platform import gui
from cdb.platform.mom.entities import Entity

from cdb import sqlapi
from cdb import ue
from cdb import tools

import datetime
import ast
import re

__SQL_STATISTICS__ = ["AVG",
                       "COUNT",
                       "MAX",
                       "MIN",
                       "SUM"
                    ]

# Tools:

date_exp = re.compile("([\d]{2}).([\d]{2}).([\d]{4})")


def isnumber(n):
    try:
        float(n)
        return True
    except (ValueError, TypeError):
        return False


fCustomComputation = Forward(__name__ + ".CustomComputation")
fSQLStatistics = Forward(__name__ + ".SQLStatistics")
fExpressionEvaluation = Forward(__name__ + ".ExpressionEvaluation")


class ComputationRule(Object):
    """ Base class for computation rules """
    __classname__ = "cdbqc_computation_rule"
    __maps_to__ = "cdbqc_computation_rule"

    def getPeriod(self):
        return None

    def compute(self, qc):
        """
        Abstract method to compute quality chacters.

        Should be implemented in the subclasses.
        It should update the value of the quality characteristic using
        the provided interface, as in:

        qc.set_actual_value(<new value>)

        :param qc: The quality characteristic, whose value needs to be computed
        :type qc: cs.metrics.qualitycharacteristics.QualityCharacteristic

        :raise: NotImplementedError
        """
        raise NotImplementedError("To be implemented in the subclasses")


class CustomComputation(ComputationRule):
    """    Class to manage custom computations of quality characteristics. """

    __classname__ = "cdbqc_custom_computation_rule"
    __match__ = fCustomComputation.cdb_classname == "cdbqc_custom_computation_rule"

    def compute(self, qc):
        """
        Method to compute quality characteristics.

        It updates the value of qc.act_value using the CDB kernel operation (i.e. event handlers are triggered).
        It reads the python address of a callable object from ``self.fqpyname`` and calls it giving the
        quality characteristic object ``qc`` as parameter.

        The call to the custom function in ``self.fqpyname`` should return the computed value, without updating
        qc.act_value, and raise an ``Exception`` if the value can not be computed. The exception will be caught
        and logged.

        :param qc: The quality characteristic, whose value needs to be computed
        :type qc: cs.metrics.qualitycharacteristics.QualityCharacteristic

        :return: The computed value
        """
        if qc:
            try:
                mod = tools.getObjectByName(self.fqpyname)
                result = mod(qc)

                qc.set_actual_value(value=result, guetegrad="berechnet")
            except Exception as ex:
                Protocol.Log(qc,
                             "QC Custom Computation. "
                             "Cannot compute quality characteristic:\n"
                             "%s" % repr(ex))
                result = NULL

            return result


class SQLStatistics(ComputationRule):
    """Class to compute the value of a quality characteristic as an SQL statistics"""
    __classname__ = "cdbqc_sql_statistics"
    __match__ = fSQLStatistics.cdb_classname == "cdbqc_sql_statistics"

    def getPeriod(self):
        if self.period == NULL or self.period == '':
            return None
        else:
            return self.period

    def compute(self, qc):
        """
        Method to compute quality characteristics.

        It updates the value of ``qc.act_value`` using the CDB kernel operation (i.e. event handlers are triggered).
        The new value is obtained from the SQL query ``select STATISTICS(ATTRIBUTE) from RELATION``
        where ``STATISTICS`` is the value of ``self.statistics_name``, ``ATTRIBUTE`` is the value of
        ``self.evalued_attribute`` and ``RELATION`` is the database relation corresponding to
        the class in ``self.classname``. ``ATTRIBUTE`` can also be ``*``.

        :param qc: The quality characteristic, whose value needs to be computed
        :type qc: cs.metrics.qualitycharacteristics.QualityCharacteristic

        :return: The computed value
        """
        entity = Entity.ByKeys(classname=qc.classname)
        if entity:
            relation = entity.getRelation()
        else:
            raise ue.Exception()

        root_alias = 'SQLStatistics_Root'
        where_condition = qc.getWhereCondition(relation, root_alias)
        where_stmt = "WHERE ( %s )" % where_condition if where_condition else ""

        # stat_name(alias.eval_attr) won't work in mssql/oracle at least
        stmt = "SELECT {stat_name}({eval_attr}) AS result FROM {relation} {alias} {where_cond}".format(stat_name=self.statistics_name,
                                                                                                       eval_attr=self.evalued_attribute,
                                                                                                       relation=relation,
                                                                                                       alias=root_alias,
                                                                                                       where_cond=where_stmt)
        rs = sqlapi.RecordSet2(sql=stmt)
        result = rs[0]["result"]

        qc.set_actual_value(value=result, guetegrad="berechnet")

        return result


class ExpressionEvaluation(ComputationRule):
    """
    Class for the computation of a quality characteristic, basing on an expression involving
    the attributes of the class
    """
    __classname__ = "cdbqc_expression_evaluation"
    __match__ = fExpressionEvaluation.cdb_classname == "cdbqc_expression_evaluation"

    def compute(self, qc):
        """
        Method to compute quality characteristics.

        It updates the value of ``qc.act_value`` using the CDB kernel operation (i.e. event handlers are triggered).
        The new value is obtained from the evaluation of the expression contained
        in ``self.expression``. Names are evaluated as ``qc.<name>``. If the attribute ``name`` contains
        a date, the date is converted to an integer (this allows for computation of time windows, i.e.
        differences of dates).

        :param qc: The quality characteristic, whose value needs to be computed
        :type qc: cs.metrics.qualitycharacteristics.QualityCharacteristic

        :return: The computed value
        """
        transformer = EvaluateAttributes(qc)
        try:
            node = ast.parse(self.expression, mode="eval")
            new_node = transformer.visit(node)
            code = compile(new_node, "<string>", "eval")
            result = eval(code)
        except Exception as ex:
            Protocol.Log(qc,
                         "QC Expression. "
                         "Cannot compute quality characteristic.\n"
                         "%s" % repr(ex))
        else:
            qc.set_actual_value(value=result, guetegrad="berechnet")
            return result
        return None


class UpdateClock(Object):
    __maps_to__ = "cdbqc_update_clocks"
    __classname__ = "cdbqc_update_clocks"

    Name = LocalizedField("name")
    Period = LocalizedField("period")


class SQLStatisticsCatalog(gui.CDBCatalog):
    def __init__(self):
        gui.CDBCatalog.__init__(self)

    def handlesSimpleCatalog(self):
        return True

    def getCatalogEntries(self):
        return __SQL_STATISTICS__


class EvaluateAttributes(ast.NodeTransformer):
    reserved = ["int", "float"]

    def __init__(self, qc):
        self.qc = qc

    def _get_qc_value(self, name):
        from cs.metrics import qualitycharacteristics as QualityCharacteristics

        if isinstance(self.qc, QualityCharacteristics.ObjectQualityCharacteristic):
            qcdef = QualityCharacteristics.QCDefinition.ByKeys(identifier=name)
            if qcdef:
                qc = QualityCharacteristics.ObjectQualityCharacteristic.\
                        ByKeys(cdbqc_def_object_id=qcdef.cdb_object_id,
                               cdbf_object_id=self.qc.cdbf_object_id)
                if qc:
                    if qcdef.computed and qc.Association and\
                        ((qc.Association.UpdateClock and qc.Association.UpdateClock.Name['de'] == "manuell") or
                         qc.Association.next_computation <= datetime.datetime.now()):
                        qc.compute(qc)

                    if qc.act_value != NULL:
                        return qc.act_value
        return None

    def visit_Name(self, node):
        if not node.id in self.reserved and not isnumber(node.id):
            value = self._get_qc_value(node.id)
            if value is None:
                value = self.qc.evaluate_attribute(node.id)
                if value is None:
                    Protocol.Log(self.qc,
                                 "QC Expression: attribute " + node.id + " is NULL")
                    raise ue.Exception("just_a_replacement", "NULL attribute")

            if isnumber(value):
                new_node = ast.Num(n=float(value))
            elif isinstance(value, str) and date_exp.match(value):
                date = datetime.datetime.strptime(value, "%d.%m.%Y")
                new_node = ast.Num(n=float(date.toordinal()))
            elif isinstance(value, datetime.datetime) or isinstance(value, datetime.date):
                new_node = ast.Num(n=float(value.toordinal()))
            else:
                Protocol.Log(self.qc,
                             "QC Expression: attribute " + node.id + " is invalid")
                raise ue.Exception("just_a_replacement", "invalid attribute")

            new_node = ast.copy_location(new_node, node)
            return ast.fix_missing_locations(new_node)
        return node


class Protocol(Object):
    __maps_to__ = "cdbqc_computation_protocol"
    __classname__ = "cdbqc_computation_protocol"

    @classmethod
    def Log(cls, qc, message):
        args = {"qc_object_id": qc.cdb_object_id}
        args.update(cls.MakeChangeControlAttributes())
        protocol = cls.Create(**args)
        protocol.SetText("cdbqc_computation_prot_txt", message)
