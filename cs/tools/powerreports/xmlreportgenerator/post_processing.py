import logging
import os
import shutil

import lxml.etree as et  # nosec

from cs.tools.powerreports.xmlreportgenerator import DEBUG, tools

LOG = logging.getLogger(__name__)


def vba_signature(template_dir, generated_excel_path):
    _, extension = os.path.splitext(generated_excel_path)
    if extension == ".xlsm":
        excel_dir = tools.temporary_unzip_file(generated_excel_path)

        excel_xl_dir = os.path.join(excel_dir, "xl")
        excel_rel_dir = os.path.join(excel_xl_dir, "_rels")
        excel_vba_rel = os.path.join(excel_rel_dir, "vbaProject.bin.rels")
        excel_content_file = os.path.join(excel_dir, "[Content_Types].xml")

        template_xl_dir = os.path.join(template_dir, "xl")
        template_vba_rel = os.path.join(template_xl_dir, "_rels", "vbaProject.bin.rels")

        # check if excel vbaProject.bin.rels not exists, but in template (otherwise template has no signature)
        if not os.path.exists(excel_vba_rel) and os.path.exists(template_vba_rel):
            shutil.copy2(template_vba_rel, excel_rel_dir)
            content_file_changes(excel_content_file, template_xl_dir, excel_xl_dir)
            tools.save_excel(generated_excel_path, excel_dir)

        if DEBUG:
            LOG.info("Post processing Excel directory: %s", excel_dir)
        else:
            try:
                shutil.rmtree(excel_dir)
            except Exception as e:  # pylint: disable=W0703
                LOG.warning(
                    "Could not remove post processing Excel directory: %s (%s)",
                    excel_dir,
                    e,
                )


def content_file_changes(content_file, template_xl_dir, excel_xl_dir):

    content_file_tree = et.parse(content_file)  # pylint: disable=I1101 #nosec

    map_tag = None
    index = 0
    part_names = []

    content_file_root = content_file_tree.getroot()
    for child in content_file_root:
        if "Override" in child.tag:
            map_tag = child.tag
            part_names.append(child.attrib["PartName"])
        index += 1

    # add vba project to content types, if not
    if "/xl/vbaProject.bin" not in part_names:
        vba_root = et.Element(  # pylint: disable=I1101
            map_tag,
            attrib={
                "PartName": "/xl/vbaProject.bin",
                "ContentType": "application/vnd.ms-office.vbaProject",
            },
        )
        content_file_root.insert(index, vba_root)
        index += 1

    # add all vba project signature(s) to content types (and to excel), if not
    for sig in os.listdir(template_xl_dir):
        if sig.startswith("vbaProjectSignature"):
            if sig not in os.listdir(excel_xl_dir):
                shutil.copy2(os.path.join(template_xl_dir, sig), excel_xl_dir)
            if sig not in part_names:
                sig_root = et.Element(  # pylint: disable=I1101
                    map_tag,
                    attrib={
                        "PartName": "/xl/" + sig,
                        "ContentType": "application/vnd.ms-office." + sig[:-4],
                    },
                )
                content_file_root.insert(index, sig_root)
                index += 1

    # update content types xml file
    map_tree = et.ElementTree(content_file_root)  # pylint: disable=I1101
    with open(content_file, "wb") as f:
        map_tree.write(f)
