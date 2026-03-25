# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2018 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/


from cdb.wsgi import util as wsgiUtil
from cdb.uberserver import secure


__all__ = ["get_ws_scheme_and_host"]


# Key mapping constant used by `get_ws_scheme_and_host`
HEADER_KEY_MAPPING = {
    "Forwarded": "HTTP_FORWARDED",
    "X-Forwarded-Proto": "HTTP_X_FORWARDED_PROTO",
    "X-Forwarded-Host": "HTTP_X_FORWARDED_HOST",
    "Host": "HTTP_HOST",
}


def __get_default_port_for_scheme(request):
    scheme = _get_client_url_scheme(request)
    return 80 if scheme == "http" else 443


def _get_client_request_port(request):
    """
    Return the port the client used for its initial request. If there is a reverse
    proxy between the application server and the client, use the port supplied
    through the request headers "Forwarded" or "X-Forwarded-Host". Fall back to
    using the port supplied by `twisted.web.http.Request#getHost`.

    :param request: The current request
    :return: the port number of the first request
    """
    host = None
    if request.getHeader("Forwarded") is not None:
        splitted = wsgiUtil.split_http_forward(request.getHeader("Forwarded"))

        # the first element in this list is the host originally used by the client
        host = splitted[0].get("host")
    elif request.getHeader("X-Forwarded-Host") is not None:
        host = request.getHeader("X-Forwarded-Host")

    if host is not None:
        host_parts = host.split(":")
        if len(host_parts) == 1:
            # happens when the broker service runs on a default port
            return __get_default_port_for_scheme(request)
        return int(host_parts[-1])

    host = request.getHost()
    return host.port


def _get_client_url_scheme(request):
    if request.getHeader("Forwarded") is not None:
        splitted = wsgiUtil.split_http_forward(request.getHeader("Forwarded"))

        # the first element in this list is the host originally used by the client
        return splitted[0].get("proto")

    if request.getHeader("X-Forwarded-Proto") is not None:
        return request.getHeader("X-Forwarded-Proto")

    # Assume that, if no header indicating that we are behind a reverse proxy is present,
    # we are a default Elements instance, so just check the ssl mode
    return "https" if secure.get_ssl_mode() == secure.USESSL else "http"


def get_ws_scheme_and_host(request):
    port = _get_client_request_port(request)
    scheme = _get_client_url_scheme(request)
    if port is None:
        # if the port is not present in the host headers, it is the default port for the given scheme.
        # This should not happen with the broker service, but check for it anyway.
        port = 80 if scheme == "https" else 443
    environ = {
        "SERVER_PORT": str(port),
        "wsgi.url_scheme": scheme,
    }

    for header, env_key in HEADER_KEY_MAPPING.items():
        header_value = request.getHeader(header)
        if header_value is not None:
            environ[env_key] = header_value

    http_base = wsgiUtil.proxyserver_base(environ)
    http_proto, base = http_base.split("://")

    ws_proto = "wss" if http_proto == "https" else "ws"

    return "%s://%s" % (ws_proto, base)
