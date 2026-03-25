#!/usr/bin/env powerscript
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2020 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

"""
AS Services

"""

from __future__ import absolute_import

import logging
import os
import sched
import sys
import time

from cdb import CADDOK, rte
from cdb.dberrors import DBError
from cdb.dbutil import with_reconnect
from cdb.plattools import killableprocess

__docformat__ = "restructuredtext en"

SVCNAME = "AS Daily Mailer"
_DAY_SECONDS = 86400
_DATABASE_TIMEOUT = 10.0
scheduler = sched.scheduler(time.time, time.sleep)
update_clocks = None

log = logging.getLogger(__name__)


def seconds_to(starting_time):
    """Returns the number of seconds between the current time starting_time."""
    st = time.strptime(starting_time, "%H:%M")
    st_seconds = st.tm_min * 60 + st.tm_hour * 3600

    lt = time.localtime()
    current_seconds = lt.tm_hour * 3600 + lt.tm_min * 60 + lt.tm_sec

    if st_seconds > current_seconds:
        result = st_seconds - current_seconds
    else:
        result = _DAY_SECONDS + st_seconds - current_seconds

    return result


@with_reconnect(timeout=_DATABASE_TIMEOUT)
def sendDailyMails():
    try:
        args = [
            rte.runtime_tool("powerscript"),
            "--program-name=activitystream_daily_mail",
            os.path.join(os.path.dirname(__file__), "daily_mails.py"),
        ]

        sender = CADDOK.get("DAILY_AS_MAIL_SENDER", None)
        if sender:
            args.append("--sender=%s" % sender)

        killableprocess.check_call(args)
    except Exception:  # pylint: disable=W0703
        log.exception("Failed to send daily activities")


def run_loop(starting_time):
    while True:
        try:
            scheduler.enter(seconds_to(starting_time), 1, sendDailyMails, [])
            scheduler.run()
        except DBError:
            log.exception("%s Database error", SVCNAME)
        except Exception:  # pylint: disable=W0703
            log.exception(SVCNAME)
        except KeyboardInterrupt:
            log.info("%s shutting down", SVCNAME)
            return


if __name__ == "__main__":
    logging.basicConfig(
        format="[%(levelname)-8s] [%(name)s] %(message)s",
        stream=sys.stderr,
        level=logging.INFO,
    )
    import argparse

    parser = argparse.ArgumentParser(description="Activity Stream Daily Mailer")
    parser.add_argument(
        "-s",
        "--start",
        dest="starting_time",
        action="store",
        default="00:00",
        help="when to send daily e-mails (format HH:MM)",
    )
    parser.add_argument(
        "-o", "--once", dest="once", action="store_true", help="Trigger mails once"
    )

    args = parser.parse_args()
    if args.once:
        sendDailyMails()
    else:
        log.info("%s: running daily @ %s", SVCNAME, args.starting_time)
        run_loop(args.starting_time)
