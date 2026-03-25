# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2016 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

from __future__ import absolute_import
__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

from . import App
from cdb import sqlapi
from cdb.platform.olc import StateDefinition, StatusInfo, Workflow


class StateColors(object):

    olc_statecolor_cache = {}

    @classmethod
    def _get_states(cls, olc_class):
        """
        Returns a list of all object life cycles for the given `olc_class`.
        """
        try:
            result = cls.olc_statecolor_cache[olc_class]
        except KeyError:
            olc_names = Workflow.KeywordQuery(objclass=olc_class).objektart
            result = {olc: {} for olc in olc_names}
            for state in StateDefinition.KeywordQuery(objektart=olc_names):
                cssc = StatusInfo(state.objektart,
                                  state.statusnummer).getCSSColor()
                result[state.objektart][state.statusnummer] = cssc
            cls.olc_statecolor_cache[olc_class] = result
        return result

    def __init__(self, obj_class):
        self.obj_class = obj_class

    def get_state_colors(self):
        return self._get_states(self.obj_class)


@App.path(path='state_colors/{obj_class}', model=StateColors)
def _init_state_color_model(obj_class):
    return StateColors(obj_class)


@App.json(model=StateColors)
def _document_state_colors(model, request):
    return model.get_state_colors()
