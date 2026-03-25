#!/usr/bin/env python
# -*- coding: utf-8 -*-
# vim: set fileencoding=latin1 :
# -*- Python -*-
# $Id$
#
# Copyright (C) 1990 - 2006 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#
# File:     Item.py
# Author:   aki
# Creation: 01.08.06
# Purpose:

# pylint: disable-msg=R0901,R0201,R0904,E0203,W0212,W0201

import os
import datetime

from cdb import ue
from cdb import sqlapi
from cdb import auth
from cdb import kernel
from cdb import rte
from cdb import sig
from cdb import util
from cdb.classbody import classbody
from cdb.rte import require_config

from cdb.objects import ReferenceMethods_1

from cs.vp.items import Item
from cs.vp.items import ItemCategory
from cs.vp.utils import NEVER_VALID_DATE, get_sql_row_limit
from cdb.objects.common import WithStateChangeNotification
from cdb.objects.org import CommonRole

from cs.materials import Material, MaterialStates
from cdbwrapc import StatusInfo
from cdb.platform.olc import StateDefinition


# Sentinel: raise when "std-solution" is not set
require_config("std-solution")

ATTRIBUTES_TO_CLEAR_ON_COPY = ['t_ersatz_fuer', 't_ersatz_durch', 't_pruefer', 't_pruef_datum']


@classbody
class Item(WithStateChangeNotification):

    def _PreviousIndex(self):
        ctx = self.GetContext()
        if ctx and ctx.action == "index" and ctx.mode in ['post_mask', 'pre']:
            prev_idx = ctx.cdbtemplate.t_index
        else:
            prev_idx = kernel.get_prev_index(self.teilenummer, self.t_index, self.GetTableName())
        return Item.ByKeys(self.teilenummer, prev_idx)
    PreviousIndex = ReferenceMethods_1(Item, lambda self: self._PreviousIndex())

    _MAX_COMPONENTS_MSG = 15

    def _clearAttributesOnBatchCopy(self, ctx):
        # We need to clear some attributes (ATTRIBUTES_TO_CLEAR_ON_COPY) in case a part is copied in batch
        # mode. We cannot re-use the clearAttributes() function for the pre step because the user might have
        # specified values for the to-be-cleared attributes explicitly, which would then be cleared by calling
        # clearAttributes().

        if ctx.interactive or ctx.uses_webui:
            return

        attributes_to_clear = ATTRIBUTES_TO_CLEAR_ON_COPY
        for attribute in attributes_to_clear:
            if attribute not in ctx.dialog.get_attribute_names():
                continue

            # Reset if attribute was not explicitly changed.
            # Note: in the edge case that the explicitly passed attribute value is the same as the previous
            # value, the attribute will still be reset since we cannot differentiate between 'no new value
            # specified for attribute' and 'value specified but unchanged'.
            if ctx.dialog[attribute] == ctx.object[attribute]:
                self[attribute] = ""

    def checkComponentsReleased(self):
        if self.isAssembly():
            released_status = ", ".join(["190", "200", "300", "400"])
            select_limit, where_limit = get_sql_row_limit()
            stmt = f"""
                einzelteile.teilenummer FROM einzelteile 
                LEFT JOIN teile_stamm 
                ON teile_stamm.teilenummer=einzelteile.teilenummer AND teile_stamm.t_index=
                CASE WHEN einzelteile.is_imprecise = 0 
                    THEN einzelteile.t_index
                    ELSE (
                        SELECT {select_limit} t_index FROM teile_stamm ts
                        WHERE ts.teilenummer=einzelteile.teilenummer AND ts.status in ({released_status})
                        {where_limit}
                    )
                END
                WHERE 
                    einzelteile.baugruppe='{self.teilenummer}' AND
                    einzelteile.b_index='{self.t_index}' AND 
                    (teile_stamm.status is NULL OR teile_stamm.status not in ({released_status}))
            """
            t = sqlapi.SQLselect(stmt)
            rows = sqlapi.SQLrows(t)
            if rows > 0:
                items = []
                for i in range(min(rows, self._MAX_COMPONENTS_MSG)):
                    items.append(sqlapi.SQLstring(t, 0, i))
                text = ",\n".join(items)

                if rows > self._MAX_COMPONENTS_MSG:
                    text += "\n" + \
                            util.get_label("cdbvp_and_x_more") % (rows - self._MAX_COMPONENTS_MSG)

                raise ue.Exception("cdb_konfstd_009", "\n" + text)

    def checkMaterialReleased(self):
        if self.material_object_id:
            material = Material.ByKeys(cdb_object_id=self.material_object_id)
            if material.status != MaterialStates.RELEASED:
                raise ue.Exception("csvp_material_not_released", material.GetDescription())

    def on_state_change_pre(self, ctx):
        self.Super(Item).on_state_change_pre(ctx)

        # Zur Freigabe von Baugruppen müssen alle Komponenten freigegeben sein
        if self.status == 200:
            self.checkComponentsReleased()
            self.checkMaterialReleased()

    def stateChangeAllowed(self, target_state, batch):
        if batch:
            return True
        exclude = {"*": [180, 190, 300],
                   0: [200],
                   190: [200],
                   }
        return (target_state not in exclude.get("*", []) and
                target_state not in exclude.get(self.status, []))

    # == Email notification ==
    def getNotificationReceiver(self, ctx=None):
        rcvr = {}
        if self.status == 100:
            releaseRole = CommonRole.ByKeys("public")
            for pers in releaseRole.getPersons():
                if pers.e_mail:
                    tolist = rcvr.setdefault("to", [])
                    tolist.append((pers.e_mail, pers.name))
        return [rcvr]
    # == End email notification ==

    def _prevIndexStateChange(self, item, target_state):
        # In der Regel sollte es hier nur einen Artikel geben
        try:
            item.ChangeState(target_state)
        except Exception as e:
            raise ue.Exception("cdb_konfstd_008", "%d" % (item.status), "%s" % (target_state), e)

    def on_state_change_pre_mask(self, ctx):
        self.Super(Item).on_state_change_pre_mask(ctx)

        for state in ctx.statelist:
            if not self.stateChangeAllowed(state, ctx.batch):
                ctx.excl_state(state)

    def on_state_change_post(self, ctx):
        self.Super(Item).on_state_change_post(ctx)

        if ctx.error != 0:
            return
        if ctx.old.status ["100", "120"] and ctx.new.status == '200':
            # Prüfer und Prüfdatum setzen
            self.t_pruefer = auth.get_name()
            self.t_pruef_datum = datetime.datetime.utcnow()
            # Vorgängerindex von 'in Änderung' auf 'ungültig' setzen
            items = Item.KeywordQuery(teilenummer=self.teilenummer, status=190)
            for item in items:
                self._prevIndexStateChange(item, 180)

    def on_modify_pre(self, ctx):
        repl_for_set = 0
        if "t_ersatz_fuer" in ctx.dialog.get_attribute_names():
            if ctx.dialog.t_ersatz_fuer != ctx.object.t_ersatz_fuer:
                repl_for_set = 1
        ctx.set("cdb::argument.repl_for_set", "%d" % (repl_for_set))

    def on_modify_post(self, ctx):
        if ctx.error:
            return
        if ctx.sys_args["repl_for_set"] == "1":
            self.removeReplacementFor()
            self.setReplacementFor(ctx)

    def setWorkflow(self, ctx):
        categ = ItemCategory.ByKeys(self.t_kategorie)
        if categ:
            self.cdb_objektart = categ.teileart
        else:
            raise ue.Exception("cdb_konfstd_018", self.t_kategorie)

    def switchObjectLifecycle(self, ctx):
        if self.status == 0 and ctx.object.t_kategorie != self.t_kategorie \
                and StateDefinition.ByKeys(0, self.cdb_objektart) is not None:
            self.setWorkflow(ctx)
            status_info = StatusInfo(self.cdb_objektart, 0)
            self.cdb_status_txt = status_info.getStatusTxt()

    def on_delete_post(self, ctx):
        if ctx.error:
            return
        # Wenn der Artikel überhaupt nicht mehr existiert, kann er auch keinen Anderen mehr ersetzen.
        # Ein Fall, der in Produktivumgebungen eigentlich nicht vorkommen kann, hier aber
        # der Vollständigkeit halber implementiert.
        if len(Item.KeywordQuery(teilenummer='%s' % self.teilenummer)) == 0:
            self.removeReplacementFor()

        items = Item.KeywordQuery(
            teilenummer=self.teilenummer,
            status=[0, 100, 190]
        )
        in_change_item = None
        for item in items:
            if item.status == 190:
                in_change_item = item
                break

        set_to_prev_status = True
        if in_change_item:
            for item in items:
                if item.status != 190 and item.cdb_copy_of_item_id == in_change_item.cdb_object_id:
                    set_to_prev_status = False
        else:
            set_to_prev_status = False

        if set_to_prev_status:
            # item.status_prev should always be set. In some corner cases
            # (e.g. after an update from a very old system, or if the customer code breaks the data)
            # it can be None though (E049417).
            broken = []
            for item in items:
                if item.status == 190:
                    if item.status_prev is not None:
                        # change predecessor back to prev state
                        self._prevIndexStateChange(item, item.status_prev)
                    else:
                        broken.append(item)

            if broken:
                raise util.ErrorMessage(
                    "prev_index_state_change_failed",
                    ", ".join([item.GetDescription() for item in broken])
                )

    def indexPost(self, template_index):
        pObj = self.getPersistentObject()
        pObj.clearAttributes()
        # Status des Vorgängerindex von 200 (freigeben) nach 190 (in Änderung)
        item = Item.ByKeys(self.teilenummer, template_index)
        if item and item.status == 200:
            old_state = item.status
            self._prevIndexStateChange(item, 190)
            item.status_prev = old_state

    def on_index_post(self, ctx):
        if ctx.error:
            return
        self.indexPost(ctx.cdbtemplate.t_index)
        # Wir haben am teile_stamm Aenderungen vorgenommen - damit der Server
        # das mitkriegt, muessen wir es ihm mitteilen
        ctx.refresh_tables(["teile_stamm"])

    def on_copy_pre_mask(self, ctx):
        self.t_index = ""
        self.clearAttributes()

    def clearAttributes(self):
        # Felder leeren
        attrs = ATTRIBUTES_TO_CLEAR_ON_COPY
        for attr in attrs:
            self[attr] = ""

    def setDefaults(self, ctx):
        self.t_bereich = auth.get_department()

    def setReplacementFor(self, ctx):

        """ Setzt 'Ersetzt durch' Attribut bei allen Indexständen des ersetzten Teils
        und leert ggf. zuvor das 'Ersatz für' Attribut des zuvor eingetragenen Teils."""

        if ctx.error or not self.t_ersatz_fuer:
            return
        t = sqlapi.SQLselect("t_ersatz_durch from teile_stamm where "
                             "teilenummer = '%s' and t_ersatz_durch!='%s' and t_ersatz_durch != '' " %
                             (self.t_ersatz_fuer, self.teilenummer))
        if sqlapi.SQLrows(t) > 0:
            sqlapi.SQLupdate("teile_stamm set t_ersatz_fuer = '' where teilenummer = '%s'" %
                             (sqlapi.SQLstring(t, 0, 0)))
        sqlapi.SQLupdate("teile_stamm SET t_ersatz_durch = '%s' WHERE teilenummer = '%s'" %
                         (self.teilenummer, self.t_ersatz_fuer))
        # Wir haben am teile_stamm Aenderungen vorgenommen - damit der Server
        # das mitkriegt, muessen wir es ihm mitteilen
        ctx.refresh_tables(["teile_stamm"])

    def removeReplacementFor(self):
        sqlapi.SQLupdate("teile_stamm SET t_ersatz_durch = '' WHERE t_ersatz_durch = '%s'" % self.teilenummer)

    def on_preview_now(self, ctx):
        # Wenn es ein zugeordnetes CAD-Dokument gibt, dieses als Vorschau verwenden
        for doc in sorted(self.Documents, key=lambda x: (x.z_nummer, x.z_index), reverse=True):
            if doc.isModel():
                # Wenn es eine geeignete Datei gibt, setzen
                preview_file = doc.GetPreviewFile()
                if preview_file:
                    preview_file.handlePreviewCtx(ctx)
                    return
        # Kein geeignetes Dokument gefunden - auf Standard zurueckfallen
        self.Super(Item).on_preview_now(ctx)

    def reset_effectivity_dates(self, ctx):
        """
        Resets both `ce_valid_from` and `ce_valid_to` to `None`. By default, this method is used by the copy
        pre_mask step to clear the dates when copying an existing item.
        """
        self.ce_valid_from = None
        self.ce_valid_to = None

    def set_never_effective(self, ctx, keep_existing):
        """
        Sets the item as never being valid yet.

        :param keep_existing: If True and `ce_valid_from` is already set, neither `ce_valid_from` nor
            `ce_valid_to` will be changed.
            Otherwise, `ce_valid_from` will be set to the `NEVER_VALID_DATE` and `ce_valid_to` will be set to
            None.
        """
        if keep_existing and self.ce_valid_from:
            return

        self.ce_valid_from = NEVER_VALID_DATE
        self.ce_valid_to = None

    def set_effectivity_dates_on_state_change(self, ctx):
        """
        Handles the effectivity changes when changing the item life cycle status.

        By default, when the item is released, the item is set as valid (`ce_valid_from` is set to the date of
        the state change). When the item is set as obsolete, `ce_valid_to` is set to the date of the state
        change.
        """
        if ctx.new.status == '200':
            import hashlib
            from datetime import datetime, date

            md5 = hashlib.md5((self.cdb_object_id + str(datetime.utcnow())).encode()).hexdigest()

            self.getPersistentObject().Update(ce_valid_from=date.today(), ce_valid_to=None)

            initial_datetime = datetime.strptime(str(self.cdb_mdate), "%Y-%m-%d %H:%M:%S")
            date_update = str(initial_datetime.replace(microsecond=0)) + '.000'
	    
            sqlapi.SQLupdate("cdb_t_statiprot SET md5='{}' WHERE teilenummer='{}' and cdbprot_neustat = 'Released' and cdbprot_zeit = '{}'".format(md5, self.teilenummer, date_update))
            Item.ByKeys(cdb_object_id=self.cdb_object_id).Update(md5=md5)

            subject = "PLM 751 - Part released"
            msg_body = '''
                <div>
                    <div>
                        <p>Part có mã: <b>{}</b> đã được phê duyệt.
                        <p>Mã MD5: {}</p>
                        <p>Email này được tạo ra tự động từ hệ thống PLM 751. Vui lòng không reply.</p>
                        <p>PLM 751 System</p>                      
                    </div>
                </div>'''.format(self.teilenummer, md5)

            send_email_status_change(teilenummer=self.teilenummer, subject=subject, message_body=msg_body)

        elif ctx.new.status in ['170', '180']:
            self.getPersistentObject().Update(ce_valid_to=date.today())
        elif ctx.new.status in ['100']:
            subject = "PLM 751 - Part waiting for VTX review"
            msg_body = '''
                <div>
                    <div>
                        <p>Part có mã: <b>{}</b> đang chờ VTX xem xét.<br>Truy cập hệ thống để thực hiện công việc liên quan.<br></p>
                        <p>Email này được tạo ra tự động từ hệ thống PLM 751. Vui lòng không reply.</p>
                        <p>PLM 751 System</p>
                    </div>
                </div>'''.format(self.teilenummer)

            send_email_status_change(teilenummer=self.teilenummer, subject=subject, message_body=msg_body)

    event_map = {
        (('copy', 'create', 'modify', 'info', 'query', 'requery'), 'pre_mask'): "smlPremaskImages",
        (('copy', 'create'), 'pre'): ("setWorkflow", "setItemNumber", "setItemIndex"),
        (('copy', 'create'), 'post'): ("setReplacementFor"),
        (('copy', 'create'), 'pre_mask'): ("setDefaults"),
        ('copy', 'pre'): "_clearAttributesOnBatchCopy",
        ('modify', 'pre'): "switchObjectLifecycle"
    }

# Email notification attributes
#Item.__notification_template__ = "part_approval.html"
#Item.__notification_title__ = "PLM 751 - Part waiting for VTX review"
# Force looking for the template file in defined folder
#dirname = os.path.dirname(__file__)
#Item.__notification_template_folder__ = os.path.join(dirname, "chrome")


@sig.connect(rte.APPLICATIONS_LOADED_HOOK)
def connect_effectivities():
    sig.connect(Item, "copy", "pre_mask")(reset_effectivity_dates)
    sig.connect(Item, "copy", "pre")(set_never_effective)
    sig.connect(Item, "create", "pre")(set_never_effective_if_unset)
    sig.connect(Item, "index", "pre")(set_never_effective)
    sig.connect(Item, "state_change", "post")(set_effectivity_dates_on_state_change)


def reset_effectivity_dates(self, ctx):
    self.reset_effectivity_dates(ctx)


def set_never_effective_if_unset(self, ctx):
    self.set_never_effective(ctx, keep_existing=True)


def set_never_effective(self, ctx):
    self.set_never_effective(ctx, keep_existing=False)


def set_effectivity_dates_on_state_change(self, ctx):
    self.set_effectivity_dates_on_state_change(ctx)


def send_email_status_change(teilenummer, subject, message_body):
    from cdb.mail import Message

    query_user = sqlapi.SQLselect("e_mail, name FROM angestellter WHERE e_mail != ''")

    msg = Message()
    msg.Subject(subject)

    for i in range(sqlapi.SQLrows(query_user)):
        user_email = sqlapi.SQLstring(query_user, 0, i)
        user_name = sqlapi.SQLstring(query_user, 1, i)
        if not user_email is None:
            # Send email
            msg.To(user_email, user_name)
            msg.From("systemplm@congty751.com.vn", 'PLM 751')
        
        msg.body(message_body, mimetype="text/html")
            
    msg.send()