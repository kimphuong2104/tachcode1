# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/


class TestImportContext(object):
    class Dialog(object):
        def __init__(self, export_file, import_file):
            self.export_file = export_file
            self.import_file = import_file
            self.export_function = "cs.materials.material_export.json_export"

    class UeArgs(dict):
        def get_attribute_names(self):
            return list(self)

    def __init__(self, export_file="", import_file="", json_data="", uses_webui=False):
        self.ue_args = TestImportContext.UeArgs()
        self.dialog = TestImportContext.Dialog(export_file, import_file)
        self.json_data = json_data
        self.uses_webui = uses_webui
        self.server_file = ""
        self.dest_url = None

    def download_from_client(
        self, client_path, server_name, delete_file_after_download=0
    ):
        with open(server_name, "w", encoding="utf-8") as text_file:
            text_file.write(self.json_data)

    def keep(self, key, value):
        self.ue_args[key] = value

    def upload_to_client(
        self, server_name, client_filename="", delete_file_after_upload=0
    ):
        self.server_file = server_name

    def url(self, url):
        self.dest_url = url
