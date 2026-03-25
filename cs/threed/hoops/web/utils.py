# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2016 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#
# Version:  $$


def add_csp_header(response):
    from cs.threed import services
    endpoints = set()
    for svc in services.get_services():
        endpoints.update(services.ThreeDBrokerService.get_endpoints(svc))

    response.headers.add(
        "Content-Security-Policy",
        "default-src 'self' 'unsafe-inline' "
        "'unsafe-eval'; img-src 'self' data: blob: ;"
        "connect-src 'self' data: " + " ".join(endpoints) + "; "
        "child-src blob: ; worker-src 'self' blob: data: ; media-src 'self' blob: ; frame-src 'self' ; "
        "font-src 'self' data: blob: ;"
    )
