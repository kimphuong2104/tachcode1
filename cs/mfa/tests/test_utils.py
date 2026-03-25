#!/usr/bin/env powerscript
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 2017 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
from __future__ import unicode_literals, print_function
from cdb.objects.org import User
import cdbwrapc


def with_faked_caddok_pw(obj):
    obj.username = 'caddok'
    u = User.ByKeys(login=obj.username)
    obj.user_pw = 'secret'
    u.Update(password=cdbwrapc.get_crypted_password(obj.username,
                                                    obj.user_pw))
    obj.user = u
