#!/usr/bin/env powerscript
# -*- python -*- coding: UTF-8 -*-
#
# Copyright (C) 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

import os
from xml.etree import ElementTree

from cdb.objects.cdb_filetype import CDB_FileSuffix

PROE_ASEMBLY_FILETYPE = "ProE:Asmbly"
PROE_PART_FILETYPE = "ProE:Part"
accelerator_suffix_by_file_suffix = None

def setup():
    global accelerator_suffix_by_file_suffix
    accelerator_suffix_by_file_suffix = {}
    all_suffixes = CDB_FileSuffix.KeywordQuery(ft_name=[PROE_ASEMBLY_FILETYPE, PROE_PART_FILETYPE])
    for sfx in all_suffixes:
        accelerator_suffix_by_file_suffix[sfx.ft_suffix.strip('.')] = 'xas' if sfx.ft_name == PROE_ASEMBLY_FILETYPE else 'xpr'


def generate_xas_and_xpr_files(wsp, src, fnames, log):
    try:
        log("Generating Creo Parametric XPR and XAS files for family tables\n")
        from cs.cadbase import cadcommands
        from cs.proe.jobexec.proejobexec import ProeJobExec

        if not accelerator_suffix_by_file_suffix:
            setup()

        variants_by_filename = get_family_table_info_from_appinfo(fnames, src)

        current_accelerator_ftype = ""
        cad_job = cadcommands.JobRunner(cad_system="ProE", job_exec=ProeJobExec(), job_dir=wsp).create_job()

        for name in fnames:
            #check if file type is valid
            suffix = name.split('.')[-1]
            if suffix in accelerator_suffix_by_file_suffix:
                current_accelerator_ftype = accelerator_suffix_by_file_suffix[suffix]
            else:
                continue

            # get variants for which xpr/xas files are needed
            basename = os.path.basename(name)
            if basename in variants_by_filename:
                variants = list(variants_by_filename[basename])
            else:
                continue

            cmd_close = cadcommands.CmdCloseAll()
            cmd_save_secondary = cadcommands.CmdSaveSecondary(
                name,
                current_accelerator_ftype,
                wsp,
                parameter = {"variants": variants }
                )

            cad_job.append(cmd_close,
                    cmd_save_secondary
                    )

        if len(variants_by_filename) > 0:
            result = cad_job.execute()
            return result.isOk()
        else:
            log("No occurences that use family tables have been found. No files were generated.\n")
            return True

    except Exception as ex:
        import traceback
        log("The generation of XPR and XAS files failed with the following exception:\n %s" % traceback.format_exc())
        log("This might cause problems with the conversion result.\n")
    return False


def get_family_table_info_from_appinfo(fnames, src):
    result = get_family_table_variants_for_root(src)
    for f in fnames:
        f, tree = open_appinfo(f)
        occs = tree.findall("occurrences/occurrence")
        for occ in occs:
            cad_ref = occ.find("cadreference")
            variant_id = cad_ref.get("variantid")
            if variant_id:
                filename = os.path.basename(cad_ref.get("path"))
                if filename not in result:
                    result[filename] = set()
                result[filename].add(variant_id)
    return result

def get_family_table_variants_for_root(src):
    result = {}
    f, tree = open_appinfo(src)
    variants = tree.findall("variants/variant")
    for variant in variants:
        variant_id = variant.get("id")
        if variant_id:
            filename = os.path.basename(src)
            if filename not in result:
                result[filename] = set()
            result[filename].add(variant_id)
    return result

def open_appinfo(model):
    f = None
    tree = ElementTree.Element("appinfo")
    base_name = os.path.basename(model)
    base_dir = os.path.dirname(model)
    appinfo = os.path.join(base_dir, "%s.appinfo" % base_name)
    if os.path.isfile(appinfo):
        f = open(appinfo, "r")
        try:
            tree = ElementTree.parse(f).getroot()
        except IOError:
            pass
        if f:
            f.close()
    return f, tree


def is_proe(src_file):
    return src_file.cdbf_type in [PROE_ASEMBLY_FILETYPE, PROE_PART_FILETYPE]