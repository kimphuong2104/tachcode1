# !/usr/bin/env powerscript
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 2016 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#
from .broker_service_options import UpdateBrokerServiceOptions
from .broker_service_sec_options import AddBrokerServiceSecurityOptions

pre = []
post = [UpdateBrokerServiceOptions, AddBrokerServiceSecurityOptions]
