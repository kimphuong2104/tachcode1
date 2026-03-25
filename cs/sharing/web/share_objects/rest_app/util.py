# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/


def check_attachment_recipient_access(attachment, recipients):
    """
    Checks if the given recipients have the required access rights to view the given attachment.
    """
    if not attachment:
        return True
    for persno, _ in recipients:
        if not attachment.CheckAccess("read", persno=persno):
            return False
    return True
