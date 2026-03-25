#!/usr/bin/env python
# -*- python -*- coding: UTF-8 -*-
# $Id$
#
# Copyright (C) 1990 - 2003 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#
# File:     cdbxml_set_defaults.ue
# Author:   aki
# Creation: 22.10.08
# Purpose:


from cdb import auth, ue
from cs.tools.powerreports import XMLReport, XMLReportParameter


def save_defaults(ctx):
    dlg_attrs = ctx.dialog.get_attribute_names()

    if "cdbxml_report_id" in dlg_attrs:
        report = XMLReport.ByKeys(cdb_object_id=ctx.dialog.cdbxml_report_id)
        if report:
            provider_arg_prefixes = set()
            for prov in report.XMLSource.DataProviders:
                provider_arg_prefixes.add("%s-" % prov.xsd_name.lower())
            report.ParametersByPersno[auth.persno].Delete()
            for attr in dlg_attrs:
                # Don't save any non-provider-arg dialog attributes
                if any(  # pylint: disable=R1729
                    [attr.startswith(prefix) for prefix in provider_arg_prefixes]
                ):
                    XMLReportParameter.Create(
                        name=report.name,
                        report_title=report.title,
                        persno=auth.persno,
                        arg_name=attr,
                        arg_value=ctx.dialog[attr],
                    )


if __name__ == "__main__":
    ue.run(save_defaults, "cdbmaskaction")
