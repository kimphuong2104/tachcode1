# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2018 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

"""
This module provides the logic for generating new Json Web Tokens, which will
be used as Bearer Tokens for Broker Service Authentication.
The tokens will only be generated, when the user is authorized to
access the requested object.
"""

from Cryptodome.PublicKey import RSA
import datetime
import json
from jwkest import jwk
from jwkest import jws
from jwkest import BadSyntax, BadSignature
from jwkest.jwt import b2s_conv
import logging
import pytz
import time
from twisted.web import http

from cdb import auth
from cdb.objects import core

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

# Exported objects
__all__ = ["WebKey", "WebKeySet", "InvalidRequestError", "InvalidTokenError",
           "InsufficientScopeError"]

LOG = logging.getLogger()

# The length of the RSA key used for signing
WEB_KEY_LENGTH = 2048
# The algorithm used for signing (RS256 = RSA with SHA-256)
WEB_KEY_ALG = "RS256"

# The duration a webkey is valid to be used for signing.
WEB_KEY_VALID_SECONDS = 60 * 60 * 24

# The duration a bearer token is valid
WEB_TOKEN_EXPIRE_SECONDS = 600


class InvalidRequestError(Exception):
    """Exception for indicating problems with the request itself."""

    HTTP_ERROR_CODE = http.BAD_REQUEST
    ERROR_NAME = "invalid_request"


class InvalidTokenError(Exception):
    """Exception for indicating problems with the token itself."""

    HTTP_ERROR_CODE = http.UNAUTHORIZED
    ERROR_NAME = "invalid_token"


class InsufficientScopeError(Exception):
    """Exception for indicating scope errors."""

    HTTP_ERROR_CODE = http.FORBIDDEN
    ERROR_NAME = "insufficient_scope"


class WebKeySet(object):
    """Manages RSA keys and offers functionality to sign and verify JWT with these keys."""

    def __init__(self, keys=None):
        """
        Construct a RSA key set for JWT signing and verifying.

        :param keys: list of WebKey objects, defaults to None
        :param keys: [WebKey], optional
        """
        self._keys = jwk.KEYS()
        if keys:
            for wk in keys:
                wk_txt = wk.GetText("threed_jwks_txt")
                if wk_txt:
                    self._keys.load_jwks(wk_txt)

    def __len__(self):
        """Return the amount of keys in the set."""
        return len(self._keys)

    def sign(self, issuer_url, scope):
        """
        Create a signed JWT.

        :param issuer_url: The URL of the service that issued this token
        :type issuer_url: string
        :param scope: The scope of the JWT it was issued for
        :type scope: string
        :return: signed JWT
        :rtype: string
        """
        iat = int(time.time())
        payload = {
            "iss": issuer_url,
            "iat": iat,
            "exp": iat + WEB_TOKEN_EXPIRE_SECONDS,
            "scope": scope,
            "user_login": auth.persno
        }
        jws_token = jws.JWS(payload, alg=WEB_KEY_ALG)
        return jws_token.sign_compact(keys=self._keys)

    def verify(self, token):
        """
        Verify that a token is signed with a known valid key and that it has not expired yet.

        :param token: compact jwt as utf-8 string to verify
        :type token: string
        :raises InvalidTokenError: given token is not valid
        :return: token content
        :rtype: dict
        """
        try:
            token_info = jws.JWS().verify_compact(token, self._keys, sigalg=WEB_KEY_ALG)
        except (jws.WrongNumberOfParts, jws.SignerAlgError, BadSyntax, BadSignature) as e:
            raise InvalidTokenError(str(e))
        except jws.NoSuitableSigningKeys:
            # Keys with token kid not found, probably it got deleted or was never there
            raise InvalidTokenError("The access token expired")
        else:
            _now = int(time.time())
            try:
                token_expire = int(token_info.get("exp"))
            except (ValueError, TypeError):
                raise InvalidTokenError("Expiration date missing")
            if _now > token_expire:
                raise InvalidTokenError("The access token expired")
            return token_info

    def make_rsakey(self, kid):
        """
        Create a new RSA key with specified key id.

        :param kid: Key ID for identifying the key a token was signed with
        :type kid: string
        :return: a new RSA key
        :rtype: jwk.RSAKey
        """
        rsa_key = RSA.generate(WEB_KEY_LENGTH)
        return jwk.RSAKey(kid=kid, key=rsa_key)

    def append(self, jwk):
        """Append a RSAKey to the set.

        :param jwk: Key to add
        :type jwk: jwk.RSAKey
        """
        self._keys.append(jwk)


class WebKey(core.Object):
    """
    A persistent object for JWK storage.

    Ther purpose of this object is to share the keys among all resources and token issuer.
    """

    __maps_to__ = "threed_jwks"
    __classname__ = "threed_jwks"

    @classmethod
    def gen_bearer_token(cls, issuer_url, scope):
        """
        Generate a bearer token signed with an active key.

        This function will create and store a key, if none can be found.
        It also will clean the persistent storage from expired keys.

        Example:

            result = WebKey.gen_bearer_token("https://example.org/token", "/gadget/coffeemaker/42")
            print result["access_token"]

        :param issuer_url: URL of the issuer
        :type issuer_url: string
        :param scope: The scope of the bearer token
        :type scope: string
        :return: a dict with the bearer token and token information.
        :rtype: dict
        """
        keys = cls.get_active_keyset(for_validation=False)
        if not keys:
            args = cls.MakeChangeControlAttributes()
            stored_key = cls.Create(**args)
            jwk = keys.make_rsakey(kid=stored_key.cdb_object_id)
            stored_key.save_key(jwk)
            keys.append(jwk)
            cls.delete_expired_keys()
        token = keys.sign(issuer_url, scope)
        return {
            "access_token": token,
            "token_type": "Bearer",
            "expires_in": WEB_TOKEN_EXPIRE_SECONDS,
            "scope": scope,
        }

    @classmethod
    def validate_token(cls, web_token, scope):
        """
        Validate a bearer token.

        Example:

            token = "<JWT string>"
            try:
                token_info = WebKey.validate_token(token, "/gadget/coffeemaker/42")
            except (InvalidTokenError, InsufficientScopeError):
                print "Token could not be verified. Access blocked!"
            else:
                print "Token verified!"
                print "Issuer:", token_info["iss"]
                print "Issued for user:", token_info["user_login"]

        :param web_token: Bearer token in the format of a compact JWT.
        :type web_token: string
        :param scope: The expected scope of the token
        :type scope: string
        :raises InvalidTokenError: When token is not valid
        :raises InvalidTokenError: When there is no active keyset available
        :raises InvalidTokenError: When the token has expired
        :raises InvalidTokenError: When the token does not contain expiration timestamp
        :raises InsufficientScopeError: When the token was issued with a different
                                        scope than expected
        :return: Information embedded in the token
        :rtype: dict
        """
        if not web_token:
            raise InvalidTokenError()
        keys = cls.get_active_keyset(for_validation=True)
        if not keys:
            raise InvalidTokenError("The access token expired")
        token_info = keys.verify(web_token)
        if not scope == token_info.get("scope", ""):
            raise InsufficientScopeError()

        LOG.info("Accepted Bearer token issued by '%s' "
                 "for '%s' "
                 "on '%s' to expire on '%s'.",
                 token_info.get("iss", "[unknown]"),
                 token_info.get("user_login", "[unknown]"),
                 cls._timestamp_to_iso8601(token_info.get("iat")),
                 cls._timestamp_to_iso8601(token_info.get("exp")))
        return token_info

    @classmethod
    def get_active_keyset(cls, for_validation=False):
        """
        Return a set of all currently active keys.

        Inactive keys will be ignored. When `for_validation` is set to ``True``,
        the returned set will contain inactive keys, which could have signed
        tokens that are still valid at the current time.

        :param for_validation: A flag to indicate, whether all keys relevant for
                               token validation should be returned, defaults to False
        :param for_validation: bool, optional
        :return: a key set containing all requested keys
        :rtype: cs.threed.services.auth.WebKeySet
        """
        since_date = datetime.datetime.now()
        since_date -= datetime.timedelta(seconds=WEB_KEY_VALID_SECONDS)
        if for_validation:
            # take also expired keys, which could have signed tokens in their
            # last seconds, allowing these tokens to be accepted for
            # WEB_TOKEN_EXPIRE_SECONDS amount of time
            since_date -= datetime.timedelta(seconds=WEB_TOKEN_EXPIRE_SECONDS)
        active_keys = cls.Query(cls.cdb_cdate >= since_date,
                                order_by="cdb_cdate DESC")
        return WebKeySet(active_keys)

    @classmethod
    def delete_expired_keys(cls):
        """
        Remove expired keys from persistent storage.

        This method will keep expired keys which could have signed currently valid tokens.
        """
        since_date = datetime.datetime.now()
        since_date -= datetime.timedelta(seconds=WEB_KEY_VALID_SECONDS)
        since_date -= datetime.timedelta(seconds=WEB_TOKEN_EXPIRE_SECONDS)
        cls.Query(cls.cdb_cdate < since_date).Delete()

    @staticmethod
    def _timestamp_to_iso8601(ts):
        try:
            return datetime.datetime.fromtimestamp(ts, pytz.UTC).isoformat()
        except (TypeError, ValueError):
            return "[invalid timestamp]"

    def save_key(self, rsa_jwk):
        """
        Store a RSA key object inside a WebKey object.

        :param rsa_jwk: A jwk.RSAKey object to be stored persistently inside this WebKey object.
        :type rsa_jwk: jwk.RSAKey
        """
        self.SetText("threed_jwks_txt", json.dumps({
            "keys": [
                b2s_conv(rsa_jwk.serialize(private=True))
            ]
        }))
