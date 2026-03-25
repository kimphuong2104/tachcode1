#  -*- mode: python; coding: utf-8 -*-
#
#  Copyright (C) 1990 - 2021 CONTACT Software GmbH
#  All rights reserved.
#  https://www.contact-software.com/
import logging
import sys

LOGGER = None


def init_logging():
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)

    formatter = logging.Formatter(
        "[%(asctime)s.%(msecs)03d] [%(levelname)-8s] %(name)s - %(message)s",
        "%Y-%m-%dT%H:%M:%S",
    )

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setLevel(logging.INFO)
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    file_handler = logging.FileHandler("migrate_old_vm.log", mode="w")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger


if LOGGER is None:
    LOGGER = init_logging()
