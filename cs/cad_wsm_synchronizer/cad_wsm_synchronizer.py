#!/usr/bin/env python
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 1990 - 2013 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

"""
Module cad_wsm_synchronizer.py

This user exit is used by CAD integrations.
It is called whenever changes have been committed by the CAD integration.
Its purpose it to create or update Workspace Manager-compatible link structures
and appinfo files such that CAD documents of "classic" integrations can be
loaded with the Workspace Manager.
"""

from __future__ import absolute_import

__docformat__ = "restructuredtext en"

import traceback
import logging

import six

from cdb import ue
from cs.cad_wsm_synchronizer.synchronize_from_classic import synchronizeDocuments


class CadWsmSynchronizerAdapter:
    context_name = "cadtalkstdinout"

    def impl(self, ctx):
        logging.info("-----start CadWsmSynchronizerAdapter.impl(...)")
        returnCode = 0
        try:
            pairs = self._parseZNumberZIndexPairs(ctx.stdin)
            synchronizeDocuments(pairs)
        except Exception as e:
            returnCode = -1
            logging.error("An exception occurred calling UE CadWsmSynchronizerAdapter")
            logging.error(six.text_type(e))
            logging.error(traceback.format_exc())
        finally:
            ctx.writeln(six.text_type(returnCode))

        logging.info("-----end CadWsmSynchronizerAdapter.impl(...)")

    def _parseZNumberZIndexPairs(self, stdin):
        result = []
        for line in stdin:
            parts = line.split(",")
            if len(parts) != 2:
                raise ValueError(
                    "Expecting comma-separated pair "
                    'of z_nummer,z_index, got: "%s"' % line
                )
            z_nummer = parts[0]
            z_index = parts[1]
            result.append((z_nummer, z_index))
        return result


if __name__ == "__main__":
    ue.run(CadWsmSynchronizerAdapter)
