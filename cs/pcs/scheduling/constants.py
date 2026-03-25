#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

from cs.pcs.projects import tasks

RELSHIP_FS = tasks.kTaskDependencyEA
RELSHIP_SS = tasks.kTaskDependencyAA
RELSHIP_FF = tasks.kTaskDependencyEE
RELSHIP_SF = tasks.kTaskDependencyAE

# constants for network indexes
# duration, early start, early finish, late start, late finish,
# scheduled start date, scheduled end date, free float, total float
DR, ES, EF, LS, LF, AA, ZZ, FF, TF = range(9)
# constants for constraint type values
ASAP, ALAP, MSO, MFO, SNET, SNLT, FNET, FNLT = [str(x) for x in range(8)]
FIXED_CONSTRAINT_TYPES_EARLY = {MSO, SNET, SNLT}
FIXED_CONSTRAINT_TYPES_LATE = {MFO, FNET, FNLT}
# how to "fix" non-workday constraint dates (True = next workday, False = prev workday)
FIXED_CONSTRAINT_FIX_FORWARD = {
    MSO: True,
    MFO: False,
    SNET: True,
    SNLT: False,
    FNET: True,
    FNLT: False,
}
VALID_CONSTRAINTS_FOR_TASK_GROUPS = {ASAP, SNET, FNLT}
VALID_CONSTRAINTS_WITHOUT_DATES = {ASAP, ALAP}
