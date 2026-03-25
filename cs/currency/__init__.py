#!/usr/bin/env powerscript
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 1990 - 2012 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

from __future__ import absolute_import

import six
import datetime

from cdb import sqlapi, ue
from cdb.objects import Object
from cdb.objects import Forward


__all__ = ["Currency", "CurrConversion"]


fCurrency = Forward(__name__ + ".Currency")
fCurrConversion = Forward(__name__ + ".CurrConversion")


class Currency(Object):
    """
    Class of Currency object.
    """

    __maps_to__ = "cdbpco_currency"
    __classname__ = "cdbpco_currency"

    event_map = {
        (('copy', 'create', 'modify'), 'pre_mask'): ('checkRefCurr')
    }

    @classmethod
    def getReferenceCurrency(cls):
        """
        Get the reference currency.
        """
        return (Currency.Query("is_ref_curr=1") + [None])[0]

    def checkRefCurr(self, ctx):
        """
        Check uniqueness of the reference currency: there can be only one.
        """
        if self.is_ref_curr != 1:
            if len(Currency.Query("is_ref_curr=1")) > 0:
                ctx.set_readonly("is_ref_curr")

    @classmethod
    def getDefaultCurrency(cls):
        """
        Get the default currency, which is in standard solution the
        reference currency.
        """
        return cls.getReferenceCurrency()

    def convertTo(self, tocurr, value, cdb_project_id=None):
        """
        Convert given value of current currency into another currency.
        """
        if value:
            exch = fCurrConversion.getExchangeRate(self,
                                                   tocurr,
                                                   cdb_project_id)
            value = value * exch
        return value

    def convertToReference(self, value, cdb_project_id=None):
        """
        Convert given value of current currency into reference currency.
        """
        if value:
            value = fCurrConversion.convertToReference(self,
                                                       value,
                                                       cdb_project_id)
        return value


class CurrConversion(Object):
    """
    Conversion between currencies.
    """
    __maps_to__ = "cdbpco_curr_convert"
    __classname__ = "cdbpco_curr_convert"

    event_map = {
        (('copy', 'create'), 'post'): ('create_matching_conv')
    }

    def create_matching_conv(self, ctx):
        args = {
            "from_curr_object_id": self.to_curr_object_id,
            "to_curr_object_id": self.from_curr_object_id,
            "cdb_project_id": self.cdb_project_id
        }
        if not CurrConversion.KeywordQuery(**args):
            args["convert_factor"] = 1 / self.convert_factor if self.convert_factor else 1
            CurrConversion.CreateNoResult(**args)

    @classmethod
    def getExchangeRate(cls, fromcurr, tocurr, cdb_project_id=None):
        """
        Get the exchange rate between currencies. If given, take the values
        respecting the project.
        @param fromcurr: cdb.objects-Object of the source currency or its
                         cdb_object_id.
        @param tocurr: cdb.objects-Object of the target currency or its
                       cdb_object_id.
        @param cdb_project_id: optional, use project specific exchange factor.
        """

        # Ensure using cdb_object_id to look up the data
        def get_currency_id(currid):
            if not isinstance(currid, six.string_types):
                if hasattr(currid, "cdb_object_id"):
                    currid = currid.cdb_object_id
                else:
                    currid = ""
            return currid

        fromcurr = get_currency_id(fromcurr)
        tocurr = get_currency_id(tocurr)

        if fromcurr == tocurr:
            return 1.0

        def gen_sql_str(fc, tc):
            """
            Generate the query condition. Using power value -1 to recalculate
            the opposite direction.
            """
            str1 = "from_curr_object_id='%s' and to_curr_object_id='%s'" % \
                   (fc, tc)
            str2 = "to_curr_object_id='%s' and from_curr_object_id='%s'" % \
                   (fc, tc)
            sqlstr = ""
            if cdb_project_id:
                morecond = " and cdb_project_id='%s'" % cdb_project_id
                sqlstr = ("select cdbpco_curr_convert.*, 1 as tpower "
                          "from cdbpco_curr_convert where %s" %
                          (str1 + morecond))
                sqlstr += " union "
                sqlstr += ("select cdbpco_curr_convert.*, -1 as tpower "
                           "from cdbpco_curr_convert where %s" %
                           (str2 + morecond))
                sqlstr += " union "
            sqlstr += ("select cdbpco_curr_convert.*, 1 as tpower "
                       "from cdbpco_curr_convert where %s" % (str1))
            sqlstr += " union "
            sqlstr += ("select cdbpco_curr_convert.*, -1 as tpower "
                       "from cdbpco_curr_convert where %s" % (str2))
            return sqlstr

        today = datetime.datetime.now()
        # direct conversion: source currency <-> target currency

        rset = sqlapi.RecordSet2(sql=gen_sql_str(fromcurr, tocurr))
        if len(rset) > 0:
            for rset in rset:
                if (rset.validity_period_from and rset.validity_period_to) and (rset.validity_period_from < today < rset.validity_period_to):
                    tpower = int(rset.tpower)
                    return pow(float(rset.convert_factor), tpower) * 1.0
                elif not (rset.validity_period_from and rset.validity_period_to):
                    tpower = int(rset.tpower)
                    return pow(float(rset.convert_factor), tpower) * 1.0
                else:
                    raise ue.Exception("No conversion rate found between the given dates")

        ref_curr = fCurrency.getReferenceCurrency()
        if ref_curr:
            result = 1.0
            # source currency -> reference currency
            rset = sqlapi.RecordSet2(sql=gen_sql_str(fromcurr,
                                                     ref_curr.cdb_object_id))
            if len(rset) > 0:
                for rset in rset:
                    if (rset.validity_period_from and rset.validity_period_to) and (rset.validity_period_from < today < rset.validity_period_to):
                        tpower = int(rset.tpower)
                        result = pow(float(rset.convert_factor), tpower) * 1.0
                        # reference currency -> target currency
                        rset = sqlapi.RecordSet2(
                            sql=gen_sql_str(ref_curr.cdb_object_id, tocurr))
                        if len(rset) > 0:
                            for rset in rset:
                                tpower = int(rset.tpower)
                                return result * pow(float(rset.convert_factor), tpower)
                    elif not (rset.validity_period_from and rset.validity_period_to):
                        tpower = int(rset.tpower)
                        result = pow(float(rset.convert_factor), tpower) * 1.0
                        # reference currency -> target currency
                        rset = sqlapi.RecordSet2(
                            sql=gen_sql_str(ref_curr.cdb_object_id, tocurr))
                        if len(rset) > 0:
                            for rset in rset:
                                tpower = int(rset.tpower)
                                return result * pow(float(rset.convert_factor), tpower)
                    else:
                        raise ue.Exception("No conversion rate found between the given dates")
        else:
            # no possible conversion: 1.0
            raise ue.Exception("No conversion rate found between the given dates")

    @classmethod
    def convertToReference(cls, fromcurr, fromvalue, cdb_project_id=None):
        """
        Convert a currency into reference currency. If given, take the exchange
        factor respecting the project.
        """
        if fromvalue:
            exch = 1.0
            refcurr = fCurrency.getReferenceCurrency()
            if refcurr:
                exch = cls.getExchangeRate(fromcurr, refcurr, cdb_project_id)
            fromvalue = fromvalue * exch
        return fromvalue

    @classmethod
    def getCurrExchangeFactor(cls, fromcurr, tocurr, cdb_project_id=None):
        """
        Alias to the `getExchangeRate` method to keep backwards compatibility.
        """
        return cls.getExchangeRate(fromcurr, tocurr, cdb_project_id)
