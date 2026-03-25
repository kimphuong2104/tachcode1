#!/usr/bin/env python
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/
#
from cdb import elink
from cdb import util
from cdb.lru_cache import lru_cache

from cs.metrics import actions as Actions
from cs.metrics.cockpit import qc_cockpits
from cs.metrics.cockpit import qc_object
from cs.metrics.cockpit import qc_process


__docformat__ = "restructuredtext en"
__revision__ = "$Id$"


# Exported objects
__all__ = ["prc_cockpit", "obj_cockpit"]


@elink.using_template_engine("chameleon")
class QCProcessCockpit(elink.Application):
    def __init__(self, *args, **kwargs):
        title = util.get_label('cdbqc_elink_cockpit_process') + " KPI Cockpit"
        super(QCProcessCockpit, self).__init__(title)

    '''
    Application class to start and run the eLINK application
    '''
    def setup(self):
        '''
        Add the page(s) to the application,
        add the JavaScript methods
        '''

        self.add("", qc_process.Mainpage())
        self.addJSON(qc_cockpits.save_target_value)
        self.addJSON(qc_process.set_user_settings)
        self.addJSON(qc_cockpits.gethistorydata)
        self.addJSON(Actions.getActionData)
        self.addJSON(Actions.getTooltipData)
        self.addJSON(qc_cockpits.compute)

    @classmethod
    def on_cdbqc_prc_cockpit_now(cls, ctx):
        return cls.OpenModule("prc_cockpit")


prc_cockpit = elink.AppMaker(QCProcessCockpit, "cdbqc_elink_cockpit_process")


@elink.using_template_engine("chameleon")
class QCObjectCockpit(elink.Application):
    '''
    Application class to start and run the eLINK application
    '''
    def setup(self):
        '''
        Add the page(s) to the application,
        add the JavaScript methods
        '''

        self.add("", qc_object.Mainpage())
        self.addJSON(qc_object.save_actual_value)
        self.addJSON(qc_cockpits.save_target_value)
        self.addJSON(qc_object.set_user_settings)
        self.addJSON(qc_cockpits.gethistorydata)
        self.addJSON(Actions.getActionData)
        self.addJSON(Actions.getTooltipData)
        self.addJSON(qc_cockpits.compute)

    @classmethod
    def on_cdbqc_obj_cockpit_now(cls, ctx):
        from cdb.platform.mom import CDBObjectHandle
        obj_id = ctx.object_id
        handle_obj = CDBObjectHandle(obj_id)
        cdb_object_id = handle_obj.getUUID()
        url = cls.getModuleURL("obj_cockpit")
        ctx.url(url + "?cdb_object_id=%s" % cdb_object_id)


obj_cockpit = elink.AppMaker(QCObjectCockpit, "cdbqc_elink_cockpit_object")


class QCCockpitTools(object):
    def __init__(self):
        self.prc_cockpit = QCProcessCockpit()

    @staticmethod
    def get_qc_tools():
        return {"qccockpittools": QCCockpitTools()}

    def templates(self):
        return self.prc_cockpit.getTemplates()

    @lru_cache(maxsize=100, typed=True)
    def get_user_settings(self):
        return {'qc_process': qc_process.get_user_settings(),
                'qc_object': qc_object.get_user_settings()}

    @lru_cache(maxsize=100, typed=True)
    def get_render_data(self, qc_app, cdb_object_id=None):
        render_data = {}
        valid_qc_apps = {'qc_process': qc_process, 'qc_object': qc_object}
        if qc_app in valid_qc_apps:
            if cdb_object_id:
                render_data = valid_qc_apps[qc_app].get_render_data(cdb_object_id)
            else:
                render_data = valid_qc_apps[qc_app].get_render_data()
        return render_data
