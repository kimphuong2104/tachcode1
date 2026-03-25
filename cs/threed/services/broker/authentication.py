# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2018 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

"""
Module authentication

This module contains the logic for verifying authentication information used by
the Broker Service.
"""

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

import logging

from cs.threed.services import auth
from twisted.web import http

# Exported objects
__all__ = ["validate_request"]

LOG = logging.getLogger(__name__)


def validate_request(request, scope):
    """
    Check a twisted request for containing a valid Bearer token in its header.

    If the token is not present or otherwise not valid, a respective
    error code will be set inside the request.

    This method will add a ``WWW-Authenticate`` header to the `responseHeader` of the request.

    This method will consume and log exceptions.

    :param request: a request object to be validated
    :type request: twisted.web.http.Request
    :param scope: Expected scope of a valid token
    :type scope: string
    :return: ``True``, if the request provided a valid token
    :rtype: bool
    """
    auth_headers = request.requestHeaders.getRawHeaders("authorization")
    if not auth_headers or not len(auth_headers) == 1:
        request.setResponseCode(http.UNAUTHORIZED)
        request.setHeader("WWW-Authenticate", "Bearer")
        return False

    auth_header = auth_headers[0].strip()
    LOG.debug("Authorization Token received: %s", auth_header)
    if not auth_header[:7] == "Bearer ":
        request.setResponseCode(http.UNAUTHORIZED)
        request.setHeader("WWW-Authenticate", "Bearer")
        return False
    try:
        auth.WebKey.validate_token(auth_header[7:], scope)
    except (auth.InvalidRequestError, auth.InvalidTokenError, auth.InsufficientScopeError) as e:
        LOG.warning("Bearer Token could not be verified.", exc_info=1)
        request.setResponseCode(e.HTTP_ERROR_CODE)
        resp_value = "Bearer"
        resp_value += ', error="%s"' % (e.ERROR_NAME,)
        error_description = str(e)
        if error_description:
            resp_value += ', error_description="%s"' % (error_description,)
        request.setHeader("WWW-Authenticate", resp_value)
        return False
    except:
        LOG.exception("Bearer Token validation failed.")
        request.setResponseCode(http.UNAUTHORIZED)
        request.setHeader("WWW-Authenticate", "Bearer")
        return False
    else:
        request.setHeader("WWW-Authenticate", "Bearer")
        return True


def validate_token(token, scope):
    """
    Checks, whether a token is valid.

    This method will consume and log exceptions.

    :param token: A JW Token to be validated
    :type token: string
    :param scope: Expected scope of a valid token
    :type scope: string
    :return: ``True``, if the token is valid
    :rtype: bool
    """
    try:
        auth.WebKey.validate_token(token, scope)
    except (auth.InvalidRequestError, auth.InvalidTokenError, auth.InsufficientScopeError) as e:
        LOG.warning("Bearer Token for WS endpoint could not be verified.", exc_info=1)
        return False
    except:
        LOG.exception("Bearer Token for WS endpoint validation failed.")
        return False
    else:
        return True


# Guard importing as main module
if __name__ == "__main__":
    pass
