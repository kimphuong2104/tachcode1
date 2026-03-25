#!/usr/bin/env powerscript
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2016 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#
"""
This module defines a worker process for the broker services.
"""

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

import logging
import sys
import traceback

from cdb import fls
from cdb.timeouts import run_with_timeout, WaitResult

from cs.threed.services.cache import StreamCache
from cs.threed.services.cache import LockedCacheException


# Exported objects
__all__ = []


LOG = logging.getLogger()


class CommandHandler(object):

    def __init__(self):
        self.sc = StreamCache()

    # FUTURE THINKABOUT:  @cdb.dbutil.with_reconnect
    def run(self, command, params):
        if command == "check":
            return self.cmd_check(params)
        elif command == "register":
            return self.cmd_register(params)
        elif command == "cleanup":
            return self.cmd_cleanup(params)
        elif command == "exit" or command == "":
            return False
        else:
            sys.stderr.write("Unknown command\n")
            return True

    def cmd_check(self, document_id):
        try:
            def check_cb():
                try:
                    return WaitResult(self.sc.cache_state(document_id), False)
                except LockedCacheException as e:
                    return WaitResult((True, e.cache_name), True)

            # If lock file does not disappear after a while, assume the cache
            # is broken (has_changed will be True).
            has_changed, cache_name = run_with_timeout(
                check_cb, timeout=600, backoff=1.5)

            if cache_name:
                self.sc.cache_update_access(cache_name)
            if has_changed:
                self.cmd_write(sys.stdout, f"RESULT:Changed\t{cache_name}\n")
            else:
                self.cmd_write(sys.stdout, f"RESULT:Unchanged\t{cache_name}\n")
        except Exception as e:
            LOG.exception(f"Model check failed: {str(e)}")
            traceback.print_exc(file=sys.stderr)
            self.cmd_write(sys.stderr, f"RESULT:{str(e)})\n")
        return True

    def cmd_register(self, document_id):
        try:
            cache_name = self.sc.register_model(document_id)
            if cache_name:
                self.sc.cache_update_access(cache_name)
            self.cmd_write(sys.stdout, f"RESULT:Registered\t{cache_name}\n")
        except LockedCacheException as e:
            # Another process is already building the stream cache.
            # Wait until other process has finished building the cache.
            def wait_for_unlock_cb():
                try:
                    self.sc.fail_if_locked_hash(e.cache_name)
                    return WaitResult(None, False)
                except LockedCacheException as e:
                    return WaitResult(None, True)
            run_with_timeout(wait_for_unlock_cb, timeout=1800, backoff=1.5)
            self.cmd_write(sys.stdout, f"RESULT:Registered\t{e.cache_name}\n")
        except Exception as e:
            LOG.exception(f"Model registration failed: {str(e)}")
            traceback.print_exc(file=sys.stderr)
            self.cmd_write(sys.stderr, f"RESULT:{str(e)}\n")
        return True

    def cmd_cleanup(self, arguments=None):
        try:
            self.sc.clear_obsolete_models()
            self.cmd_write(sys.stderr, "RESULT:Done\n")
        except Exception as e:
            LOG.exception(f"Model cleanup failed: {str(e)}")
            traceback.print_exc(file=sys.stderr)
            self.cmd_write(sys.stderr, f"RESULT:{str(e)}\n")
        return True

    def cmd_write(self, std, message_prefix, message=None):
        if message is None:
            std.write(message_prefix)
        else:
            std.write(message_prefix % (message,))
        std.flush()

    @classmethod
    def parse_command(cls, message):
        command = "exit"
        arguments = []
        message = message.rstrip()
        fragments = message.split("\t")
        if fragments:
            command = fragments[0]
            arguments = fragments[1:]

        return command, arguments


def disable_os_error_reporting():
    if sys.platform.startswith("win"):
        # Don't display the Windows GPF dialog if the invoked program dies.
        # See comp.os.ms-windows.programmer.win32
        #  How to suppress crash notification dialog?, Jan 14,2004 -
        #     Raymond Chen's response [1]

        import ctypes
        SEM_NOGPFAULTERRORBOX = 0x0002  # From MSDN
        ctypes.windll.kernel32.SetErrorMode(SEM_NOGPFAULTERRORBOX)


if __name__ == "__main__":
    if fls.get_server_license("3DSC_001"):
        disable_os_error_reporting()
        msg = "ok"
        running = True
        chandler = CommandHandler()
        sys.stdout.write("READY\n")
        sys.stdout.flush()
        while running:
            try:
                msg = sys.stdin.readline()
            except KeyboardInterrupt as e:
                sys.exit(0)
            except BaseException as e:
                sys.stderr.write(f"ERROR:{repr(e)}\n")
                traceback.print_exc(file=sys.stderr)
                sys.stderr.flush()
                sys.exit(1)
            else:
                cmd, args = CommandHandler.parse_command(msg)
                running = chandler.run(cmd, args)
    else:
        LOG.critical("License not available. Aborting.")
