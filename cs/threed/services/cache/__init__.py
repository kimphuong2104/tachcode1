#!/usr/bin/env powerscript
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2016 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#
"""
This module allows to communicate with the HOOPS Steaming Cache.
"""

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

import contextlib
import io
import json
import logging
import os
import sys
import time

from cdb import misc
from cdb import rte
from cdb import util as cdb_util

from cs.documents import Document

from cs.threed.services.cache import utils
from cs.threed.services.broker import util as brokerUtil

# Exported objects
__all__ = [
    'StreamCache', 'get_tmp_dir', 'get_cache_dir', 'get_log_dir',
    'get_config_dir', 'get_instance_config', 'StreamCacheException',
    'LockedCacheException'
]

LOG = logging.getLogger(__name__)
log_handler = misc.CDBLogHandler()
log_handler.setFormatter(logging.Formatter("%(message)s", " "))
LOG.addHandler(log_handler)

ACCESS_FILE_EXTENSION = "access"
LOCK_FILE_EXTENSION = "lock"
CACHE_FILE_EXTENSION = "scz"

MAX_CACHED_MODELS = 1000

# flag to indicate, if the model should clear its temporary files after
# registration
CLEAN_TMP_FILES = True

LOCK_TIMEOUT = 60 * 30  # after 30 minutes a lock file will be ignored


class StreamCacheException(Exception):
    """Exception class for failed Stream Cache operations."""

    pass


class LockedCacheException(StreamCacheException):
    """Exception class for indicating a locked stream model."""

    def __init__(self, *args):
        super(LockedCacheException, self).__init__(*args[1:])
        self.cache_name = args[0]


def _get_global_tmp_dir():
    custom_temp_dir = brokerUtil.read_env_param("THREED_STREAMCACHE_TEMP_DIR")
    if custom_temp_dir:
        return os.path.abspath(custom_temp_dir)

    if sys.platform == 'win32':
        import win32file
        return win32file.GetLongPathName(rte.environ["CADDOK_TMPDIR"])
    else:
        return rte.environ["CADDOK_TMPDIR"]


def get_cache_dir():
    """
    Return a path to the default broker service cache.

    :return: path of the default broker service cache
    """
    return os.path.join(_get_global_tmp_dir(), "hoops", "cache")


def get_log_dir():
    """
    Return the default log path.

    :return: path of the default log folder of the broker service
    """
    return os.path.join(_get_global_tmp_dir(), "hoops", "logs")


def get_tmp_dir():
    """
    Return the default path for the temporary directory.

    :return: path of the default temp folder of the broker service
    """
    return os.path.join(_get_global_tmp_dir(), "hoops", "tmp")


def get_config_dir():
    """
    Return the default path for the config directory.

    :return: path of the default config folder of the broker service
    """
    return os.path.join(_get_global_tmp_dir(), "hoops", "config")


def get_instance_config(attr="stream_cache"):
    conffile = os.path.normpath(
        os.path.join(rte.environ['CADDOK_BASE'], 'etc', 'threed_broker_service.json'))
    if os.path.exists(conffile):
        try:
            with io.open(conffile) as jsonfile:
                result = json.load(jsonfile)
            return result.get(attr, {})
        except ValueError as e:
            LOG.exception(str(e))
    return {}


class StreamCache(object):
    """
    This class allows to register a model to the streaming cache.

    Only then it can be streamed to the 3D Viewer.
    """

    def __init__(self, cache_dir=None, tmp_dir=None):
        self.cache_dir = cache_dir if cache_dir is not None else get_cache_dir()
        self.tmp_dir = tmp_dir if tmp_dir is not None else get_tmp_dir()

    def get_path_to_cache_file(self, cache_name, file_ext=None):
        """Return absolute path to cache model file.

        :param cache_name: versioned hash of the model
        :type cache_name: basestring
        :param file_ext: file extension for the path, defaults to None
        :type file_ext: basestring, optional
        :return: path to cache file
        :rtype: basestring
        """
        file_name = cache_name
        if file_ext:
            file_name += ".%s" % (file_ext,)
        return os.path.join(self.cache_dir, file_name)

    @staticmethod
    def _get_cache_name(model, scz_file):
        return utils.hash(
            (f"{model.cdb_object_id}_{scz_file.cdbf_hash.replace(':', '_')}").encode("utf-8")
        )

    @staticmethod
    def _get_model(document_id):
        model = Document.ByKeys(cdb_object_id=document_id)
        if model is None:
            raise ValueError("CAD document with id '%s' does not exist" % document_id)
        return model

    def cache_state(self, document_id):
        """
        Return the state of a cached object.

        It returns a tuple of two elements: a flag if the model is up-to-date
        and its versioned hash.

        :param document_id: cdb_object_id of CAD document
        :return: True, when the Stream Cache models have changed or are not
                 present and versioned hash of the model as second return value
        """
        model = self._get_model(document_id)
        scz_file = model.get_scz_file()

        if scz_file is None:
            return True, None

        cache_name = self._get_cache_name(model, scz_file)
        cache_path = self.get_path_to_cache_file(cache_name, CACHE_FILE_EXTENSION)

        if os.path.isfile(cache_path):
            return False, cache_name

        return True, None

    def register_model(self, document_id):
        """
        Register a model to the streaming cache.

        The model will be rewritten
        to the filesystem, if it is already there. You can check with
        :func:`~cs.threed.hoops.server.StreamCache.cache_state` if the model
        should be re-registered or is up-to-date.

        :param document_id: cdb_object_id of CAD document

        :return: The stream cache name of the model to be provided to the viewer
        :raises: ValueError when CAD-models couldn't be determined by given
                 arguments
        """
        model = self._get_model(document_id)

        scz_file = model.get_scz_file()
        if scz_file is None:
            raise ValueError("CAD document '%s' has not been converted" % model.GetDescription())

        cache_name = self._get_cache_name(model, scz_file)
        cache_path = self.get_path_to_cache_file(cache_name, CACHE_FILE_EXTENSION)

        scz_file.checkout_file(cache_path)

        return cache_name

    def cache_update_access(self, versioned_hash):
        """
        Update the access date of the model represented by its versioned hash.

        :param versioned_hash: complete name of the stream cache model in the
                               stream cache directory
        """
        path = self.get_path_to_cache_file(versioned_hash, ACCESS_FILE_EXTENSION)
        try:
            os.remove(path)
        except OSError:
            pass
        try:
            io.open(path, "a+").close()
        except:
            # This may happen, if there were concurrent updates
            LOG.exception("Failed to update access time on model %s",
                          versioned_hash)

    def fail_if_locked_hash(self, cache_name):
        """
        Throw an exception if a cache is locked.

        A locked cache indicates, that there is another process working
        on the model cache and the model cache must not be accessed
        until it is unlocked.

        :param cache_name: unversioned name of the stream cache model in the
                           stream cache directory
        """
        path = self.get_path_to_cache_file(cache_name, LOCK_FILE_EXTENSION)
        try:
            stat = os.stat(path)
        except OSError:
            return
        else:
            if stat.st_mtime > time.time() - LOCK_TIMEOUT:
                raise LockedCacheException(cache_name, "Model is locked")

    def lock_hash(self, cache_name):
        """
        Create a lock file for a stream cache identified by a cache name.

        A locked cache indicates, that this process is
        working on the model cache and the model cache must not be accessed by
        another process until it is unlocked.

        :param cache_name: unversioned name of the stream cache model in the
                           stream cache directory
        """
        path = self.get_path_to_cache_file(cache_name, LOCK_FILE_EXTENSION)
        try:
            with io.open(path, "w") as f:
                f.write(str(time.time()))
        except:
            # This may happen, if there were concurrent updates, so check
            # if another process created a lock first
            self.fail_if_locked_hash(cache_name)

    def unlock_hash(self, cache_name):
        """
        Remove a lock file for a stream cache identified by a cache name.

        Removing a locked cache indicates, that this process has stopped
        working on the model cache and the model cache can be accessed by
        another process.

        This function can be used to unlock an unlocked stream cache. In
        this case it will return silently.

        :param cache_name: unversioned name of the stream cache model in the
                           stream cache directory
        """
        path = self.get_path_to_cache_file(cache_name, LOCK_FILE_EXTENSION)
        try:
            os.remove(path)
        except OSError:
            pass

    @contextlib.contextmanager
    def locked_hash(self, cache_name):
        """Execute a block with a locked cache model.

        This will make sure the block is executed if current process is the only
        one to write to the given cache model. Otherwise an StreamCacheException
        will be thrown.

        :param cache_name: Cache name to lock
        :type cache_name: basestring
        :raises StreamCacheException: If stream cache is locked by another process.
        """
        self.fail_if_locked_hash(cache_name)
        self.lock_hash(cache_name)
        try:
            yield
        finally:
            self.unlock_hash(cache_name)

    def clear_obsolete_models(self):
        """
        Clear all obsolete models from the stream cache directory.

        Obsolete models are models, which have an access date
        before the `n`-th top recently accessed models,
        whereby `n` is configured by the system property
        `threed_broker_model_limit`.
        """
        try:
            max_models = int(cdb_util.getSysKey("threed_broker_model_limit"))
        except KeyError:
            max_models = MAX_CACHED_MODELS

        def get_model_access_time(path):
            try:
                access_file_path = ".".join((path, ACCESS_FILE_EXTENSION))
                stat_result = os.stat(access_file_path)
            except OSError:
                # no access file, probably old model
                access_time = 0
            else:
                access_time = stat_result.st_mtime
            return access_time

        def remove_sc_item(path):
            for ext in [CACHE_FILE_EXTENSION, ACCESS_FILE_EXTENSION]:
                filepath = ".".join((path, ext))
                if os.path.exists(filepath):
                    try:
                        os.remove(filepath)
                    except OSError:
                        # file probably missing
                        LOG.exception("Cannot remove obsolete stream cache file %s", filepath)

        model_paths = list(set([os.path.splitext(os.path.join(self.cache_dir, fname))[0]
                                for fname in os.listdir(self.cache_dir)]))
        sorted_paths = sorted(model_paths, key=lambda x: get_model_access_time(x), reverse=True)

        models_over_limit = sorted_paths[max_models:]
        for path in models_over_limit:
            remove_sc_item(path)
