# !/usr/bin/env powerscript
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 2020 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

from cdb import sqlapi

class MigrateToNewBrokerServiceParams(object):
    """
    With cs.threed 15.5.3, the following parameters are being migrated:
      - csr_count / ssr_count : migrated to new parameter max_spawn_count/csr_enabled/ssr_enabled
      - csr_start_port : migrated to new parameter spawn_start_port

    In addition to the ports listed above, the following parameters are being deleted,
    they are not used any more:
      - ssr_start_port
      - tls_cert
      - tls_private_key
    """

    @staticmethod
    def __get_broker_services():
        cdb_service_base_name = "cs.threed.services.ThreeDBrokerService"

        return sqlapi.RecordSet2(
            sql="SELECT * FROM cdbus_svcs WHERE svcname LIKE '{}%'".format(cdb_service_base_name)
        )

    @staticmethod
    def __get_service_option(service, option_name):
        result = sqlapi.RecordSet2(
            "cdbus_svcopts",
            "svcid='%s' AND name='%s'" % (
                sqlapi.quote(service.svcid),
                option_name
            )
        )

        if len(result) == 1:
            return result[0]
        return None

    def __get_service_option_value(self, service, option_name):
        option = self.__get_service_option(service, option_name)
        if option:
            return option.value
        return None

    def __set_service_option(self, service, option_name, option_value):
        option = self.__get_service_option(service, option_name)

        if option is not None:
            option.update(value=option_value)
        else:
            sqlapi.Record(
                "cdbus_svcopts",
                svcid=service.svcid,
                name=option_name,
                value=option_value
            ).insert()

    @staticmethod
    def __delete_service_option(service, option_name):
        sqlapi.SQLdelete("FROM cdbus_svcopts WHERE svcid='{id}' AND name='{name}'".format(
            id=sqlapi.quote(service.svcid),
            name=sqlapi.quote(option_name)
        ))

    def run(self):
        self.migrate_parameters()
        self.delete_old_parameters()

    def migrate_parameters(self):
        for service in self.__get_broker_services():
            csr_start_port = self.__get_service_option_value(service, "--csr_start_port")
            if csr_start_port is not None:
                # update the spawn start port
                start_port = int(csr_start_port)
                self.__set_service_option(service, "--spawn_start_port", start_port)

            csr_count = self.__get_service_option_value(service, "--csr_count")
            ssr_count = self.__get_service_option_value(service, "--ssr_count")
            if csr_count is not None and ssr_count is not None:
                # update the spawn counts
                csr_count = int(csr_count)
                ssr_count = int(ssr_count)
                self.__set_service_option(service, "--max_spawn_count", "%d" % (csr_count + ssr_count))

                csr_enabled = csr_count != 0
                ssr_enabled = ssr_count > 10  # disable ssr if the default has not been changed or reduced
                self.__set_service_option(service, "--csr_enabled", 1 if csr_enabled else 0)
                self.__set_service_option(service, "--ssr_enabled", 1 if ssr_enabled else 0)

    def delete_old_parameters(self):
        for service in self.__get_broker_services():
            for option in ["--csr_start_port", "--ssr_start_port",
                           "--csr_count", "--ssr_count", "--tls_cert",
                           "--tls_private_key"]:
                self.__delete_service_option(service, option)


pre = []
post = [MigrateToNewBrokerServiceParams]

if __name__ == "__main__":
    MigrateToNewBrokerServiceParams().run()
