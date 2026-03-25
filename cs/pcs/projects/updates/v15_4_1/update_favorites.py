# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2017 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/


"""
Module update_favorites

Favorites that are using 'subject_name' are beeing migrated to use
'mapped_subject_name_de' instead.
"""

from cdb.comparch import protocol

from cs.pcs.projects.updates.v15_4_1 import MigrateFavorites

upd_classes = [MigrateFavorites]


def main():
    for cls in upd_classes:
        printable_name = cls().__class__.__name__
        start_message = f"\nUpdate task {printable_name} running..."
        end_message = f"Update {printable_name} has been executed."
        protocol.logMessage(start_message)
        print(start_message)
        cls().run()
        protocol.logMessage(end_message)
        print(end_message)


# Guard importing as main module
if __name__ == "__main__":
    main()
