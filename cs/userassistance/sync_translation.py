# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/


# Module sync_translation
# This is the documentation for the sync_translation module.

import hashlib
import logging
import os
import shutil

from cdb.plattools import killableprocess

from cs.userassistance import doc, subcommand

_logger = logging.getLogger(__name__)


def _file_eq(a, b):
    """Checks whether two files identified by path are identical"""
    if not os.stat(a).st_size == os.stat(b).st_size:
        return False
    with open(a, 'rb') as af:
        hash_a = hashlib.sha1(af.read())
    with open(b, 'rb') as af:
        return hashlib.sha1(af.read()).digest() == hash_a.digest()


def _copytree(source, destination):
    """
    Copy all rst files recursive from src to dst.
    The basic implementation is taken from ``shutil.copytree``.
    """
    if not os.path.exists(destination):
        os.makedirs(destination)

    errors = []
    for name in os.listdir(source):
        source_name = os.path.join(source, name)
        dist_name = os.path.join(destination, name)
        if os.path.isfile(source_name) and not name.endswith('.rst'):
            continue
        try:
            if os.path.isdir(source_name):
                _copytree(source_name, dist_name)
            else:
                _copyfile(source_name, dist_name)
        # Catch the Error from the recursive _copytree so that we can continue
        # with other files
        except shutil.Error as err:
            errors.extend(err.args[0])
        except EnvironmentError as why:
            errors.append((source_name, dist_name, str(why)))

    if errors:
        raise shutil.Error(errors)


def _copyfile(src_name, dst_name):
    """
    Create a copy of given file `src_name` as file `dst_name`.
    Take care of Git/SVN files if we are in a Git/SVN repo.
    """
    from cdb import svncmd

    if os.path.exists(dst_name):
        if not _file_eq(src_name, dst_name):
            _logger.debug('cp %s %s', src_name, dst_name)
            shutil.copy2(src_name, dst_name)
    else:
        # Simply always try adding the new file to both SCM repos, since using both
        # Git and SVN simultaneously on the same local source is a justified use case.
        _logger.debug('svn cp %s %s', src_name, dst_name)
        try:
            svn = svncmd.Client()
            svn.copy(src_name, dst_name)
        except svncmd.ClientError:
            shutil.copy2(src_name, dst_name)
        # There's no "file history" in Git like in SVN, thus simply git-add-ing
        # a copied file is enough for later researching purposes.
        _logger.debug('git add %s', dst_name)
        try:
            # Suppress Git's "fatal: not a git repository" output
            devnull = open(os.devnull, 'w')
            killableprocess.check_call(['git', 'add', dst_name], stderr=devnull)
        except (OSError, killableprocess.CalledProcessError) as ex:
            _logger.debug('Error calling git: %s', ex)


def _remove_outdated_rst(src, dst):
    """
    Remove rst files from dst that do no longer exist in src tree.
    The basic implementation is taken from ``shutil.copytree``.
    """
    errors = []
    for name in os.listdir(dst):
        src_name = os.path.join(src, name)
        dst_name = os.path.join(dst, name)
        if os.path.isfile(dst_name) and not name.endswith('.rst'):
            continue
        try:
            if os.path.isdir(src_name):
                _remove_outdated_rst(src_name, dst_name)
            elif not os.path.exists(src_name):
                _remove_path_item(dst_name)
        # catch the Error from the recursive _remove_outdated_rst so that we can
        # continue with other files
        except shutil.Error as err:
            errors.extend(err.args[0])
        except EnvironmentError as why:
            errors.append((src_name, dst_name, str(why)))
    if errors:
        raise shutil.Error(errors)


def _remove_path_item(file_name):
    """
    Remove given rst file `file_name` (or folder) from target folder.
    Take care of Git/SVN files if we are in a Git/SVN repo.
    """
    # Simply always try removing the new file from both SCM repos, since using both
    # Git and SVN simultaneously on the same local source is a justified use case.
    from cdb import svncmd

    svn = svncmd.Client()
    _logger.debug('svn rm %s', file_name)
    try:
        svn.remove(file_name)
    except svncmd.ClientError:
        pass
    # It is OK removing a file from the Git index when it's
    # already gone from the file system by the "svn rm" above
    _logger.debug('git rm -f %s', file_name)
    try:
        # Suppress Git's "fatal: not a git repository" output
        devnull = open(os.devnull, 'w')
        killableprocess.check_call(['git', 'rm', '-f', file_name], stderr=devnull)
    except (OSError, killableprocess.CalledProcessError) as ex:
        _logger.debug('Error calling git: %s', ex)
    if os.path.exists(file_name):
        if os.path.isfile(file_name):
            os.unlink(file_name)
        elif os.path.isdir(file_name):
            shutil.rmtree(file_name)


def _sync_rst(source, target):
    """
    Prepares the translation workflow by synchronizing the :file:`*.rst` files
    from the source language (see :file:`doclink.txt`) with the target language.
    Any changes are copied into the existing translations.

    After running :program:`userassistance sync_translation`,
    you have to run :program:`userassistance doctranslate`
    and translate the changes in the :file:`*.po` files of the target language.
    """
    source = os.path.join(source, 'src')
    target = os.path.join(target, 'src')
    _copytree(source, target)
    # remove no longer existing rst files in target folder
    _remove_outdated_rst(source, target)


@subcommand()
def sync_translation(args, extra, setup):
    """Synchronize changes from the source for all translated docsets identified by
    doclink.txt."""
    for docset, src in doc.translated_docsets(args, extra, setup):
        if extra and not docset.startswith(tuple(extra)):
            continue
        _logger.info('Syncing docset "%s" which originates from "%s"', docset, src)
        _sync_rst(os.path.join(args.prefix, src), os.path.join(args.prefix, docset))
