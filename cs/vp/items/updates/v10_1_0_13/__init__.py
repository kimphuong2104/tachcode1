# !/usr/bin/env powerscript
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 1990 - 2013 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/


from cs.metrics import qualitycharacteristics


class SetQualityCharacteristicsInvalid(object):
    """Set some quality characteristics invalid"""

    QCS = ["96ec6500-2365-11e2-b30c-0026c78a4864",  # Gewicht
           "1bdf1e80-d9a3-11e2-a3e3-082e5f0d3665",  # Fertigungseinzelkosten
           "5146b05e-d9a3-11e2-b553-082e5f0d3665",  # Materialeinzelkosten
           ]

    def run(self):
        qcdefs = qualitycharacteristics.QCDefinition.Query(
            qualitycharacteristics.QCDefinition.cdb_object_id.one_of(*self.QCS))
        for qcdef in qcdefs:
            try:
                qcdef.ChangeState(qualitycharacteristics.QCDefinition.INVALID.status)
            except RuntimeError:
                pass


pre = []
post = [SetQualityCharacteristicsInvalid]


if __name__ == '__main__':
    SetQualityCharacteristicsInvalid().run()
