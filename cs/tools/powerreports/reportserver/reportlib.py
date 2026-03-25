#!/usr/bin/env python
# $Id$
#
# Copyright (C) 1990 - 2011 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#
"""general functions for the powerreport server processes"""

import inspect
import os
import traceback

from cdb import conffile_reader, misc

log_initialized = False


def log(txt, level=5, channel=misc.kLogMsg, trace=False):
    global log_initialized  # pylint: disable=W0603
    if not log_initialized:
        caller = inspect.stack()[1][1]
        caller = os.path.basename(caller).split(".")[0]
        misc.cdblog_init(caller, "", "")
        log_initialized = True
    if trace:
        txt = "%s\n%s" % (txt, traceback.format_exc())
    misc.cdblogv(channel, level, txt)


def getConfValue(key, default=None, configfile=None):
    """
    Return value for a key in the configuration file. If 'default' is
    not defined, then exceptions due to missing conf values won't get caught.
    """
    if configfile:
        conf_file = conffile_reader.conffile_reader(configfile)
    else:
        conf_file = conffile_reader.conffile_reader("power_reports.conf")
    ret = default
    if default is not None:
        try:
            ret = conf_file.get_conf_param(key)
        except Exception:  # pylint: disable=W0718,W0703 #nosec
            pass
    else:
        ret = conf_file.get_conf_param(key)
    return ret
