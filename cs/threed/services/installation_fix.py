#!/usr/bin/env powerscript
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2019 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/
#

import sys
import argparse
import collections
import os
import re
import stat
import io
import logging

from cdb.comparch.packages import get_package_dir


LOG = logging.getLogger(__name__)


BACKUP_COPY_FILE_EXTENSION = ".backup"


MAX_FILE_SIZE_FOR_LINK_FILES = 1024
BINARY_CHARACTER_THRESHOLD = 0.3


TEXT_CHARACTERS = str("".join(list(map(chr, list(range(32, 127)))) + list("\n\r\t\b")))


CorruptSymlink = collections.namedtuple("CorruptSymlink", "filename file_dir link_target")


SYMLINK_DIRECTORY = "linux64/release/img"

EXECUTABLE_FLAG_DIRECTORY = "linux64/release"

# lists all filenames which need to be executable
# see https://docs.techsoft3d.com/exchange/latest/build/distributing_your_application.html#linux for further information
FILENAMES_WITH_EXECUTABLE_FLAG_MANDATORY = [
    "csconvert",
    "converter",
    "A3DHELF.so",
    "node",
    "ts3d_sc_server",
]


def is_executable(filepath):
    return os.path.isfile(filepath) and os.access(filepath, os.X_OK)


# Borrowed from here: http://code.activestate.com/recipes/173220-test-if-a-file-or-string-is-text-or-binary/
# with the corrections mentioned in the comment and extended to ignore files bigger than a given size
# it also uses the context manager to open the file to check so that that file can be deleted, if necessary
def is_textfile(filename, max_file_size=MAX_FILE_SIZE_FOR_LINK_FILES, blocksize=512):
    try:
        if os.path.getsize(filename) > max_file_size:
            return False
        return is_text(filename, blocksize)
    except OSError as err:
        LOG.error("Cannot stat file: %s - Expeption: %s", filename, err)
        return False

def is_text(filename, blocksize):
    with io.open(filename) as f:
        try:
            s = f.read(blocksize)
            if "\0" in s:
                return False

            if not s:  # Empty files are considered text
                return True

            # Get the non-text characters (maps a character to itself then
            # use the 'remove' option to get rid of the text characters.)
            t = s.translate({ord(c): None for c in TEXT_CHARACTERS})

            # If more than 30% non-text characters, then
            # this is considered a binary file
            if float(len(t)) / len(s) > BINARY_CHARACTER_THRESHOLD:
                return False
            return True
        except UnicodeDecodeError:
            # this can happen when reading a binary file, so just return False in that case
            return False

def get_corrupt_symlink_target(filename):
    with io.open(filename) as f:
        line = f.readline()
        lines = f.readlines()
        if len(lines) <= 1:
            is_eof = f.read(MAX_FILE_SIZE_FOR_LINK_FILES) == ""
            file_directory = os.path.dirname(filename)
            link_target_filename = os.path.join(file_directory, line)
            if os.path.isfile(link_target_filename):
                return line
        else:
            return None

def get_corrupt_symlink(filename):
    if not is_textfile(filename) or filename.endswith(BACKUP_COPY_FILE_EXTENSION):
        # binary files cannot contain corrupt symlinks. If the file extension
        # is the one for the backup copy, ignore this file
        return None
    link_target = get_corrupt_symlink_target(filename)
    if link_target is None:
        return None
    file_dir = os.path.dirname(filename)
    return CorruptSymlink(
        filename=filename,
        file_dir=file_dir,
        link_target=os.path.join(file_dir, link_target),
    )


def get_corrupt_symlinks(egg_path):
    result = []
    symlink_dir = os.path.join(egg_path, SYMLINK_DIRECTORY)

    for root, _, files in os.walk(symlink_dir):
        for f in files:
            file_dir = os.path.join(root, f)
            corrupt_symlink = get_corrupt_symlink(file_dir)
            if corrupt_symlink is not None:
                result.append(corrupt_symlink)

    return result


def fix_corrupt_symlink(corrupt_symlink):
    try:
        backup_filename = "%s%s" % (corrupt_symlink.filename, BACKUP_COPY_FILE_EXTENSION)
        os.rename(corrupt_symlink.filename, backup_filename)
        LOG.debug("renamed '%s' to '%s'. The *.backup file is only intended as a backup and can be safely deleted "
                  "if the threed services are working as expected" % (corrupt_symlink.filename, backup_filename))
    except OSError:
        LOG.exception("Exception while renaming a corrupt symlink. File: %s - Target: %s", corrupt_symlink.filename, backup_filename)
        # the following step wont work with the corrupt symlink not being deleted,
        # so just return at this point
        return
    try:
        os.symlink(corrupt_symlink.link_target, corrupt_symlink.filename)
        LOG.info("Replaced: %s" % get_corrupt_symlink_description(corrupt_symlink))
    except (OSError, AttributeError):
        # catch the attribute error just in case that this function is called on windows, where os.symlink does
        # not exist
        LOG.exception("Exception while creating a new symlink. You need to create it manually using this "
                      "command line: 'ln -s %s %s'. Run this command as the same user that is running "
                      "your cs.threed services" % (corrupt_symlink.link_target, corrupt_symlink.filename))


def get_corrupt_symlink_description(corrupt_symlink):
    return "%s ---> %s" % (corrupt_symlink.filename, corrupt_symlink.link_target)


def get_missing_executable_flags(egg_path):
    result = []

    flag_dir = os.path.join(egg_path, EXECUTABLE_FLAG_DIRECTORY)
    for root, _, files in os.walk(flag_dir):
        for f in files:
            filepath = os.path.join(root, f)
            if f in FILENAMES_WITH_EXECUTABLE_FLAG_MANDATORY and not is_executable(filepath):
                result.append(filepath)

    return result


def fix_executable_flag(filepath):
    try:
        file_stat = os.stat(filepath)
        os.chmod(filepath, file_stat.st_mode | stat.S_IEXEC)
        LOG.info("Fixed: %s" % filepath)
    except OSError:
        LOG.exception("Exception while adding the executable flag for this file: %s" % filepath)


def check_platform(run_flag):
    if not run_flag:
        if "win32" in sys.platform:
            LOG.warning("this script should not be run on Windows, only Linux is supported!\n"
                        "Running this program with the '--run' flag is not allowed.")
    else:
        if "win32" in sys.platform:
            LOG.error("this script is not allowed to be run on windows!")
            exit(-1)


def fix_installation(dry_run=False):
    if "win32" in sys.platform and not dry_run:
        # this is not needed on windows platforms
        return

    egg_path = get_package_dir("cs.threed")
    corrupt_symlinks = get_corrupt_symlinks(egg_path)
    missing_executable_flags = get_missing_executable_flags(egg_path)

    if dry_run:
        LOG.info("These symlinks are broken (pass --run to this program to actually fix the links):")
        if len(corrupt_symlinks) > 0:
            for c in corrupt_symlinks:
                LOG.info(get_corrupt_symlink_description(c))
        else:
            LOG.info("No broken symlinks found")
        LOG.info("These executable flags are missing (pass --run to this program to actually fix the flags):")
        if len(missing_executable_flags) > 0:
            for f in missing_executable_flags:
                LOG.info(f)
        else:
            LOG.info("No missing executable flags found")
    else:
        LOG.info("Replacing the symlinks")
        if len(corrupt_symlinks) > 0:
            for c in corrupt_symlinks:
                fix_corrupt_symlink(c)
        else:
            LOG.info("No broken symlinks found")

        LOG.info("Adding the executable flags")
        if len(missing_executable_flags) > 0:
            for f in missing_executable_flags:
                fix_executable_flag(f)
        else:
            LOG.info("No missing executable flags found")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Installation Fixer for installed cs.threed eggs on linux")
    parser.add_argument("--run",
                        help="Set this parameter to actually fix the symlinks and executable flags. Otherwise "
                             "this program will just print the files it would fix",
                        action="store_true",
                        default=False,
                        dest="run")

    ch = logging.StreamHandler()
    formatter = logging.Formatter('%(levelname)s: %(message)s')
    ch.setFormatter(formatter)

    LOG.setLevel(logging.INFO)
    LOG.addHandler(ch)

    args = parser.parse_args()

    check_platform(args.run)

    fix_installation(dry_run=not args.run)
