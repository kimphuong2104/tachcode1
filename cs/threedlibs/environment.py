#!/usr/bin/env powerscript
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#
import os
import sys

SERVER_LICENSE = (
    "4Fi10gQ60Em25Uaz0FmO0eM10TUz0jmzvSZvvANt0TM01Svuj7DFjE6_2UQIBy737TR3rCRy9iV67UNorCfw8ghFjCML5"
    "Fb3Cxjw9EeT9SZ22CYKDgAUCBZ94RJ11Cq44RZ74i63BDV39BI7AUV$2hNrwCZ32DiIvAQH0RY3BTZ92Tm5wvb08Bj31w"
    "6I3QJ4CU2G3Cr21DYZCDq22wQXBUINAjbk3BZ3xUrxCUB09SQ7j7DFDieY3bDFj7EWEinlj7DFjEBpCy$Fj7DF1CU56h9"
    "Oj7EI5VmT7slFjHmPIqQYCAFmvCjqChQREie_8hM82Ebt4vRuxEfk9wbq2wQT0vnc2DV1wuIZCzj6BiYR5yn53wqX2QIK"
    "1g2T9SqMDSZ05sQYzyYgj7DF5NHFjCa85DU60uRdwSMKDeR20Fj90yUG1gUGxUbkvFny0S2Y3gUW8iE6DAR72TMUxE6OC"
    "BY4wvILwvJpCgIUxCzo4Fb46feGwRQWAyV85iE11CyV4wi10RnnDgE5wyIWxUIK5Ufx0wUR9uN0DSMHEgZsACiGxhfd1g"
    "6RDymV9UYH9iYJ8yQM2i2OBiu6DxiRDxZw2vNuxuFxBi6N9CAS5uR8BU2J8TfcEiR8wBnxBUEz9FjdzQEzwUrq6gn2xvf"
    "uvCeVDyQ42yuH4AZ3xhV58FiU5SU5Cxrn6gbm9CqRxSNu4QJ6AeRn7TUL6eIG1EA85AEQ7SE_ww3vvTJavCfowgN1BQE1"
    "3xQ0CSN0wiA13wpFj7DF7slFj7DFj7Ehj7DF8uJoxAM5vTNp7TNlxDQ28uQ58hQ28Rnn8Bnm9bE0vAU48AI88TJnvRm57"
    "TVp9fblwuY8wQE3vDVlwDY68TVk8hY28fezxDRn8xM4xBa48ybn8fjmweJoxUa1vTU3xDM3vTY7weE1vQFmwuQ3xxY88A"
    "U5vDY68uI5vAI78eIz9eJk8Re4xhY57TQ3wDU7wRmz8hQ38eVmwTI0wuJmwBi4xQVk8uNpwTM7weVlxhU7xxNmxQU2vDR"
    "lvARoxEbpxuVnweY77Ua38vm78Rbk8hVmvTQz8fm48eJp7UbkvTJkxhVlvAJl8Ra57QI59fbkxRjmwTU18Bm87QNpxuI1"
    "9ia7whI79hQ8xEblxve2vBfkwTRp7Ubpxfi3weE3xhNnvTVl7TM2xRe2xuUzwhNo8fnn7RfoxeE58va3xia38ia3vRi89"
    "eRpxuY2weU39fbo8QZm8ibpxeJowDVoweM5xeY67TIzxQU78hQzwTRowAJovQI48xI27NF84gZr"
)

PLATFORM_IS_WIN32 = (sys.platform == "win32")

# general paths
THREEDLIBS_DIR = os.path.dirname(os.path.realpath(__file__))

COMMUNICATOR_DIR = os.path.join(
    THREEDLIBS_DIR,
    "win64" if PLATFORM_IS_WIN32 else "linux64",
    "release", "img"
)

RUNTIME_PATH = os.path.join(COMMUNICATOR_DIR, "runtime")


# converter paths
CSCOVNERT_DEBUG_PATH = os.path.join(THREEDLIBS_DIR,
                                    "win64" if PLATFORM_IS_WIN32 else "linux64",
                                    "debug", "src", "csconvert",
                                    "csconvert.exe" if PLATFORM_IS_WIN32 else "csconvert")

CSCONVERT_RELEASE_PATH = os.path.join(THREEDLIBS_DIR,
                                      "win64" if PLATFORM_IS_WIN32 else "linux64",
                                      "release", "src", "csconvert",
                                      "csconvert.exe" if PLATFORM_IS_WIN32 else "csconvert")

CSCONVERT_PATH = CSCOVNERT_DEBUG_PATH if os.path.exists(
    CSCOVNERT_DEBUG_PATH) else CSCONVERT_RELEASE_PATH

HOOPS_CONVERTER_PATH = os.path.normpath(os.path.join(COMMUNICATOR_DIR, "converter",
                                                     "converter.exe" if PLATFORM_IS_WIN32 else "converter"))

HOOPS_DEBUG_LIB_PATH = os.path.join(THREEDLIBS_DIR,
                                    "win64" if PLATFORM_IS_WIN32 else "linux64",
                                    "debug", "img", "lib")

HOOPS_LIB_PATH = os.path.join(THREEDLIBS_DIR,
                              "win64" if PLATFORM_IS_WIN32 else "linux64",
                              "release", "img", "exchange")

# Node and BrokerService paths
NODE_EXECUTABLE_NAME = "node.exe" if PLATFORM_IS_WIN32 else "node"
NODE_EXECUTABLE_PATH = os.path.join(COMMUNICATOR_DIR,
                                    "node" if PLATFORM_IS_WIN32 else os.path.join(
                                        "node", "bin"),
                                    NODE_EXECUTABLE_NAME)

SERVICE_STARTUP_SCRIPT_PATH = os.path.join(
    THREEDLIBS_DIR,
    "hoops", "server", "node",
    "lib", "Startup.js"
)

CONFIG_SPAWNER_TYPES_PATH = os.path.join(
    THREEDLIBS_DIR, "hoops", "server", "node",
    "lib", "SpawnerTypes"
)

STREAM_CACHE_EXECUTABLE_LOCATION = os.path.join(
    COMMUNICATOR_DIR,
    "server", "bin",
    "ts3d_sc_server.exe" if PLATFORM_IS_WIN32 else "ts3d_sc_server"
)
