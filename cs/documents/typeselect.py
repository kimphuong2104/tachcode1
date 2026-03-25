# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2018 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

"""
This module contains the standard document type selector
"""


__docformat__ = "restructuredtext en"


# Exported objects
__all__ = ["DocumentTypeSelector"]

from cdb.objects.typeselector import TypeSelector


class DocumentTypeSelector(TypeSelector):
    """
    Implementiert das Standardverhalten zur Typauswahl bei der Dokumentenneuanlage:
    - bei Drag&Drop aus dem Dateisystem
    - bei Neuanlage aus Kopplungen
    - bei Neuanlage aus dem WorkspaceManager
    - bei Neuanlage via Toolbar
    """

    def on_file_dragdrop_pre_mask(self):
        # Modelle und deren Spezialisierungen
        # aus der interaktiven Auswahl ausschließen.
        # Modelle werden über CAD-Kopplungen und den WSM
        # engestellt, nicht via Drag&Drop aus dem Dateisystem.
        self.exclude_class("model", True)

        # Workspaces werden auch nicht via Drag&Drop erzeugt,
        # sondern durch den WSM.
        self.exclude_class("cdb_wsp")

        # In Standardinstallationen ohne weitere Dokumentenklassen
        # ist jetzt nur noch document übrig. Wenn unter Berücksichtigung
        # der ausgeschlossenen Klassen nur eine Klasse übrig bleibt, wird
        # diese Klasse automatisch genommen. Der Dialog wird dann also
        # nicht mehr angezeigt.
        # Falls weitere Dokumentenspezialisierungen existieren,
        # werden diese gemäß folgender Bedingungen zur Auswahl angeboten.

        # Bei Drag&Drop von Dateien immer interaktive Typauswahl anbieten,
        # wenn die aus dem Anwendungskontext vorgegebene Klasse
        # zur Neuanlage nicht geeignet ist: Neuanlageoperation ist für den
        # Anwender deaktiviert oder Klasse ist abstrakt.
        if not self.can_create():
            return True

        # Bei Drag&Drop in den Menübaum keine Typauswahl anzeigen, wenn
        # die Klasse des Drop Targets verwendbar ist.
        # Es wird angenommen, dass die Dokumententypen im Menübaum
        # sichtbar sind und der Anwender das Drop Target bewusst
        # ausgewählt hat. Bei allen anderen Drop Targets den Anwender
        # Fragen, weil er hier sonst keine Auswahl treffen kann:
        # StructureView, CDBDesktop, HitList
        ask_user = not self.get_dragdrop_target_area() == "MenuTree"
        return ask_user

    def on_embedded_creation_pre_mask(self):
        if self.get_active_cad().startswith("MS-"):
            # Bei Neuanlage aus Office Kopplung Modelle und
            # deren Spezialisierungen aus der interaktiven Typauswahl
            # ausschließen.
            self.exclude_class("model", True)

            # Workspaces werden auch nicht via Office Kopplung
            # angelegt, sondern durch den WSM.
            self.exclude_class("cdb_wsp")

            # In Standardinstallationen ohne weitere Dokumentenklassen
            # ist jetzt nur noch document übrig. Wenn unter Berücksichtigung
            # der ausgeschlossenen Klassen nur eine Klasse übrig bleibt, wird
            # diese Klasse automatisch genommen. Der Dialog wird dann also
            # nicht mehr angezeigt.
            # Falls weitere Dokumentenspezialisierungen existieren,
            # werden diese zur interaktiven Auswahl angeboten.
            return True
        elif self.get_active_cad().startswith("wspmanager"):
            # Wenn im WSM document ausgewählt wurde, war dies bereits in Bezug auf
            # die Alternativen model und cdb_wsp explizit, der der WSM bereits
            # diese drei Typen zur Auswahl anbietet. Daher model und
            # cdb_wsp aus der interaktiven Auswahl ausschließen, wenn im WSM
            # document ausgewählt wurde.
            if self.ctx.classname == "document":
                self.exclude_class("model", True)
                self.exclude_class("cdb_wsp", True)
            # In Standardinstallationen ohne weitere Dokumentenklassen
            # ist der Typ wegen obiger Excludes für document immer
            # eindeutig definiert und es wird in keinem Fall eine
            # zusätzliche interaktive Typauswahl angezeigt.
            # Wenn im Customizing weitere Ableitungen für document, model oder
            # cdb_wsp eingeführt werden, werden diese autom. zur
            # interaktiven Auswahl angeboten.
            return True
        else:
            # Bei CAD-Kopplungen sollte niemals eine interaktive Typauswahl
            # angezeigt werden. Die vorgegebene Klasse (model) wird direkt verwendet.
            # Falls Spezialisierungen für model existieren,
            # kann die zu verwendende Spezialisierung anhand des erzeugenden Systems
            # oder Dateinames automatisch in der Methode
            # on_embedded_creation_pre(...) ermittelt und mit der Methode
            # set_new_class(...) gesetzt werden.
            # Wenn Spezialisierungen für Modelle eingeführt werden, ist
            # diese Vorgehensweise zwingend, da CAD-Kopplungen auch Neuanlagen
            # im Batch durchführen.
            return False

    def on_pre_mask(self):
        if self.is_toolbar_action():
            # Bei Neuanlage via Toolbar, die Klasse nehmen, wenn
            # verwendbar. Sonst User fragen.
            return not self.can_create()
        else:
            # Direkter Aufruf der Typauswahloperation aus dem Kontextmenü.
            if self.ctx.classname == "document":
                self.exclude_class("model", True)
                self.exclude_class("cdb_wsp", True)
            return True
