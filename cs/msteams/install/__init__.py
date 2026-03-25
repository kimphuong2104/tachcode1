# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2020 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

"""
Create activitystream_daily_mail.conf
"""
import io
import json
import os

from cdb import CADDOK
from cdb.comparch import protocol


class CreateMSTeamsQueueJSON:
    def run(self):
        conf_path = os.path.join(CADDOK.BASE, "etc", "msteams_queue.json")
        if os.path.exists(conf_path):
            protocol.logMessage(f"{conf_path} already exists")
            return
        sample_json_dict = {}
        connection_para = {"host": "localhost", "virtual_host": "/"}
        sample_json_dict["ConnectionParameters"] = connection_para

        protocol.logMessage(f"Creating default {conf_path}")
        with io.open(conf_path.encode("utf-8"), "w", encoding="utf_8_sig") as f:
            f.write(json.dumps(sample_json_dict))


class AppendMSTeamsQueueToSiteConf:
    def run(self):
        conf_path = os.path.join(CADDOK.BASE, "etc", "site.conf")
        if os.path.exists(conf_path):
            with io.open(conf_path.encode("utf-8"), "r", encoding="utf_8_sig") as f:
                for line in f:
                    if line.find("CADDOK_MSTEAMS_QUEUE_DESC") >= 0:
                        # No need to change the conf-File
                        return
            with io.open(conf_path.encode("utf-8"), "a", encoding="utf_8_sig") as f:
                f.write("\n\n# RabbitMQ configuration for MS Teams\n")
                f.write('# if "CADDOK_MSTEAMS_QUEUE_DESC" not in os.environ:\n')
                f.write(
                    '#     CADDOK_MSTEAMS_QUEUE_DESC="$CADDOK_BASE/etc/msteams_queue.json"\n'
                )


pre = []
post = [CreateMSTeamsQueueJSON, AppendMSTeamsQueueToSiteConf]


if __name__ == "__main__":
    CreateMSTeamsQueueJSON().run()
    AppendMSTeamsQueueToSiteConf().run()
