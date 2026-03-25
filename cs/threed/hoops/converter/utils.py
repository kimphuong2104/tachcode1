#!/usr/bin/env powerscript
# -*- python -*- coding: UTF-8 -*-
#
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/


import collections
import io
import itertools
import json
import logging
import os
import re

from lxml import etree

from cdb import util

LOG = logging.getLogger(__name__)

DEFAULT_CONFIG_NAME = "DEFAULT"
SRC_BASENAME_PLACEHOLDER = "$(SRC_BASENAME)"

CONTROL_CHARS = ''.join(map(chr, itertools.chain(range(0x00,0x20), range(0x7f,0xa0))))
CONTROL_CHARS_RE = re.compile('[%s]' % re.escape(CONTROL_CHARS))

def __get_path_to_root(i, parent, id_to_eid):
    result = []

    if i in parent and i in id_to_eid:
        # there are parents for this position
        p = parent[i]
        result.append(id_to_eid[i])
        result.extend(__get_path_to_root(p["id"], parent, id_to_eid))

    return result


def __get_file_path_to_root(i, parent, id_to_eid):
    result = []

    if i in parent and i in id_to_eid:
        # there are parents for this position
        p = parent[i]
        result.append(p["filename"])

        result.extend(__get_file_path_to_root(p["id"], parent, id_to_eid))

    return result


def nested_set(dic, keys, value):
    for key in keys[:-1]:
        dic = dic.setdefault(key, {})
    dic[keys[-1]] = value


def remove_control_characters(s):
    return CONTROL_CHARS_RE.sub('', s)


def convert_xml_to_json(xml_path):
    id_result = {}
    parent = {}
    id_to_eid = {}
    configs = [DEFAULT_CONFIG_NAME]

    def parse_xml(xml_file):
        for _, elem in etree.iterparse(xml_file, tag="ProductOccurence"):

            eid = elem.attrib["ExchangeId"] if "ExchangeId" in elem.attrib else None
            path = elem.attrib["FilePath"] if "FilePath" in elem.attrib else None
            name = elem.attrib["Name"] if "Name" in elem.attrib else None
            config = elem.attrib["Configuration"] if "Configuration" in elem.attrib else False
            if config:
                default = elem.attrib["Default"] if "Default" in elem.attrib else False
                if default:
                    configs[0] = name # The default config should be the first element of the list

            trafo_elem = elem.find("Transformation")
            rel_trafo = trafo_elem.attrib["RelativeTransfo"] if trafo_elem is not None else None

            if eid and path:
                i = elem.attrib["Id"]
                id_to_eid[i] = eid
                children = elem.attrib["Children"].split() if "Children" in elem.attrib else []
                path = os.path.basename(path)

                for child in children:
                    parent[child] = {
                        "filename": path,
                        "transform": rel_trafo,

                        # the following entries are solely for construction of the final json
                        "id": i,
                        "name": name,
                        "config": config,
                        "self": child
                    }
                id_result[eid] = {
                    "filename": path,
                    "transform": rel_trafo,

                    # the following entries are solely for construction of the final json
                    "id": i,
                    "name": name,
                    "config": config,
                    "self": eid
                }
                if config and name not in configs:
                    configs.append(name)

    try:
        with open(xml_path, "rb") as xml_file:
            read_xml = xml_file.read()
            try:
                parse_xml(io.BytesIO(read_xml))
            except etree.XMLSyntaxError:
                stripped_xml = remove_control_characters(read_xml)
                parse_xml(io.BytesIO(stripped_xml))

            file_result = collections.defaultdict(list)
            temp_paths = collections.defaultdict(list)

            # create the information for the json file
            for eid, id_info in id_result.items():
                id_info["path"] = __get_path_to_root(id_info["id"], parent, id_to_eid)

                filename_path = [id_info["filename"]]
                filename_path.extend(__get_file_path_to_root(id_info["id"], parent, id_to_eid))
                id_info["filename_path"] = filename_path
                file_result[id_info["filename"]].append(eid)

                # construct a mapping from paths to exchange ids
                if id_info["filename_path"]:
                    p = id_info["filename_path"]
                    if len(id_info["path"]) > 0: #check if root
                        root = id_result[id_info["path"][-1]]
                        if root['config']:
                            p.append(root['name'])
                        else:
                            p.append(DEFAULT_CONFIG_NAME)
                    elif id_info['config']:
                            p.append(root['name'])
                    else:
                        p.append(DEFAULT_CONFIG_NAME)

                    # add valid exchange id to their corresponding path
                    if p[-1] in configs:
                        rev = list(reversed(p))
                        temp_paths[tuple(rev)].append(id_info)

            # use the previously saved paths to construct the final tree
            final_tree = collections.defaultdict(dict)
            for path, entries in temp_paths.items():
                dict_path = []

                exchange_ids = []
                for i in entries:
                    if len(i["path"]) > 0:
                        exchange_ids.append(i["path"][0])
                    else:
                        # in some cases the path is empty, use the own id instead
                        exchange_ids.append( i["self"])

                path_list = list(path)
                for p in path_list:
                    if p not in dict_path:
                        dict_path.append(p)
                        if p != path[-1]:
                            dict_path.append("children")

                if len(dict_path) > 0:
                    dict_path.append("exchange_ids")
                    nested_set(final_tree, dict_path, exchange_ids)


            # remove all values that were only used for the construction of the final json
            for eid in id_result.keys():
                cur = id_result[eid]
                del cur["id"]
                del cur["name"]
                del cur["config"]
                del cur["self"]
                del cur["filename_path"]

            result = {
                "default_config": configs[0],
                "by_exchange_id": id_result,
                "by_filename": file_result,
                "by_filename_path": final_tree
            }

            json_path = "%s.json" % os.path.splitext(os.path.abspath(xml_path))[0]

            with open(json_path, "w") as j:
                json.dump(result, j)

            return json_path

    except OSError as err:
        LOG.error(err)


def get_substituted_src_basename(value, full_src_path):
    fpath, fname = os.path.split(full_src_path)
    return os.path.join(fpath, value.replace(SRC_BASENAME_PLACEHOLDER, fname))

def get_job_params(job_id):
    params_str = util.text_read("threed_hoops_job_params", ['job_id'], [job_id])
    return json.loads(params_str) if params_str else {}
