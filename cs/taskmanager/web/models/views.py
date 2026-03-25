#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

__revision__ = "$Id: "
__docformat__ = "restructuredtext en"

import json
import logging
from collections import defaultdict

from webob.exc import HTTPForbidden, HTTPInternalServerError, HTTPNotFound

from cdb import ElementsError, auth, constants, transactions, util
from cdb.fls import get_license
from cdb.objects.operations import form_input, operation, system_args
from cs.taskmanager.user_views import CATEG_EDITED, CATEG_USER, SELECTED, UserView
from cs.taskmanager.web.models import ModelWithUserSettings, offer_admin_ui
from cs.taskmanager.web.util import (
    get_classname_from_rest_id,
    get_pkeys_from_rest_id,
    get_uuid_from_rest_id,
)

USER_VIEWS_FEATURE_ID = "TASKMANAGER_050"
MYTASKSAPP = "my-tasks-app"


def run_operation(opname, *args, **kwargs):
    try:
        return operation(opname, *args, **kwargs)
    except ElementsError:
        uuid = "?"
        if args:
            uuid = getattr(args[0], "cdb_object_id", "?")

        logging.exception(
            "view operation '%s' failed; args: >%s< (UUID '%s'); kwargs: >%s<",
            opname,
            args,
            uuid,
            kwargs,
        )
        raise HTTPInternalServerError


def get_backend_condition(frontend_condition):
    """
    Convert given `frontend_condition` to backend format,
    e.g. convert REST IDs to cdb_object_ids or user IDs.
    """
    backend_condition = dict(frontend_condition)

    for key, transform in (
        ("types", get_classname_from_rest_id),
        ("contexts", get_uuid_from_rest_id),
        ("users", get_pkeys_from_rest_id),
    ):
        backend_condition[key] = [
            transform(value) for value in backend_condition.get(key, [])
        ]

    return backend_condition


def get_view_condition_json(frontend_condition):
    """
    Convert given `frontend_condition` to backend format,
    e.g. convert REST IDs to cdb_object_ids or user IDs.
    """
    backend_condition = get_backend_condition(frontend_condition)
    return str(json.dumps(backend_condition))


class ViewBaseModel(ModelWithUserSettings):
    def __init__(self):
        if not get_license(USER_VIEWS_FEATURE_ID):
            raise HTTPForbidden(
                "This operation is not licensed. "
                "Please contact your system administrator."
            )
        super(ViewBaseModel, self).__init__()

    def _getUserView(self, uuid):
        view = UserView.ByKeys(uuid)
        if not (view and view.CheckAccess("read")):
            message = "tried to access non-{} view '%s'".format(
                "readable" if view else "existing",
            )
            logging.error(message, uuid)
            raise HTTPNotFound
        return view

    def _delete_edited(self, view):
        if view.Edited:
            run_operation(constants.kOperationDelete, view.Edited)

    def _get_selected_view_id(self):
        return self._get_setting(SELECTED)

    def get_all_views(self, request):
        default_view = UserView.GetDefaultView()

        if not default_view:
            raise util.ErrorMessage("cs_tasks_no_default_settings")

        default_id = default_view.cdb_object_id

        custom_views = {view.cdb_object_id: view for view in UserView.ForUser()}

        if offer_admin_ui():
            # for admins, serialize _all_ readable views in the system
            query_str = "subject_type != 'Person' OR subject_id = '{}'".format(
                auth.persno
            )
            views_to_serialize = {
                view.cdb_object_id: view
                for view in UserView.Query(query_str, access="read")
            }
        else:
            views_to_serialize = {default_id: default_view}
            views_to_serialize.update(custom_views)

        serialized = {
            view_id: view.toJSON(request)
            for view_id, view in views_to_serialize.items()
        }

        def get_rest_ids(*view_ids):
            rest_ids = [
                serialized.get(view_id, {"@id": None})["@id"] for view_id in view_ids
            ]
            return [rest_id for rest_id in rest_ids if rest_id]

        default_rest_id = get_rest_ids(default_id)[0]
        selected_ids = self._get_selected_view_id()

        selected = {}
        for selected_id in selected_ids:
            widget_id = selected_id.setting_id2.removeprefix("selectedView--")
            if get_rest_ids(selected_id.value):
                selected[widget_id] = get_rest_ids(selected_id.value)[0]

        if MYTASKSAPP not in selected:
            selected[MYTASKSAPP] = default_rest_id

        user_views = {
            "selected": selected,
            "default": default_rest_id,
            "custom": get_rest_ids(
                *[
                    view.cdb_object_id
                    for view in sorted(
                        custom_views.values(),
                        key=lambda x: x.name,
                    )
                ]
            ),
            "byID": serialized,
        }

        return user_views


class NewView(ViewBaseModel):
    def new(self, name, frontend_condition):
        """
        Creates a new user-specific view (category "user")

        :param name: Name of the new view
        :type name: str

        :param frontend_condition: filter conditions in frontend format
        :type frontend_condition: dict

        :returns: UUID of the new view
        :rtype: str

        :raises HTTPInternalServerError: if operation `CDB_Create` fails
        """
        condition = get_view_condition_json(frontend_condition)
        kwargs = UserView.GetCustomAttributes(name, condition)
        new_view = run_operation(constants.kOperationNew, UserView, **kwargs)

        model = View(new_view.cdb_object_id)
        model.select()

        return new_view.cdb_object_id


class View(ViewBaseModel):
    def __init__(self, view_object_id, widget_object_id=MYTASKSAPP):
        super(View, self).__init__()
        self.view_object_id = view_object_id
        self.view = self._getUserView(self.view_object_id)
        self.widget_object_id = widget_object_id

    def _set_others_unedited(self, view):
        for edited in UserView.KeywordQuery(
            category=CATEG_EDITED,
            subject_id=auth.persno,
            subject_type="Person",
        ):
            if edited.customizes != view.cdb_object_id:
                run_operation(constants.kOperationDelete, edited)

    def _is_default(self):
        return self.view.is_default or (
            self.view.Customizes and self.view.Customizes.is_default
        )

    def select(self, new_view=None):
        """
        :param new_view: View to be selected for logged-in user.
            Default is ``None``, which will instead select ``self.view``.
        :type new_view: cs.taskmanager.user_views.UserView

        :raises HTTPInternalServerError: if other edited views exist,
            but cannot be deleted
        """
        if new_view is None:
            new_view = self.view

        if new_view.category != CATEG_EDITED:
            try:
                self._set_others_unedited(new_view)
            except HTTPInternalServerError:
                logging.exception("could not delete edited user views")

        settings_id = "{}--{}".format(SELECTED, self.widget_object_id)
        self._set_setting(settings_id, new_view.cdb_object_id)

    def save(self, frontend_condition):
        """
        Saves `self.view` (updates its filter condition)

        :param frontend_condition: filter conditions in frontend format
        :type frontend_condition: dict

        :raises HTTPInternalServerError: if operation fails
            (`CDB_Modify` if this is a "user" view, else `CDB_Copy`)
        """
        condition = get_view_condition_json(frontend_condition)
        new_view = None

        if self.view.category == CATEG_USER:
            # update custom view
            kwargs = self.view.toDict()
            kwargs[self.view.__condition_attr__] = condition
            run_operation(constants.kOperationModify, self.view, **kwargs)
        else:
            # create a custom copy of default or preconfigured views
            kwargs = self.view.getCustomCopyAttributes(None, condition)
            new_view = run_operation(constants.kOperationCopy, self.view, **kwargs)

        self._delete_edited(self.view)
        self.select(new_view)

    def rename(self, name):
        """
        Rename `self.view`

        :param name: New name
        :type name: str

        :raises HTTPInternalServerError: if operation fails
            (`CDB_Modify` if this is a "user" view, else `CDB_Copy`)
        """
        if self.view.category == CATEG_USER:
            # rename custom view
            kwargs = self.view.toDict()
            kwargs[UserView.getNameField()] = name
            run_operation(constants.kOperationModify, self.view, **kwargs)
        else:
            # create a custom copy of default or preconfigured views
            kwargs = self.view.getCustomCopyAttributes(name)
            newView = run_operation(constants.kOperationCopy, self.view, **kwargs)

            model = View(newView.cdb_object_id)
            model.select()

    def edit(self, frontend_condition):
        """
        Mark `self.view` as "edited" by the logged-in user:

        - Create an "edited" copy of the user view (if not already present)
        - Set the "edited" copy's condition to `frontend_condition`

        :param frontend_condition: filter conditions in frontend format
        :type frontend_condition: dict

        :raises HTTPInternalServerError: if operation fails
            (`CDB_Modify` if "edited" view already exists, else `CDB_Copy`)
        """
        condition = get_view_condition_json(frontend_condition)
        edited = self.view.Edited
        condition_update = {self.view.__condition_attr__: condition}

        if edited:
            # this will not perform an update if the condition is unchanged
            run_operation(
                constants.kOperationModify,
                edited,
                form_input(edited, **condition_update),
            )
            self.select()
        else:
            edited = run_operation(
                constants.kOperationCopy,
                self.view,
                category=CATEG_EDITED,
                customizes=self.view.cdb_object_id,
                subject_id=auth.persno,
                subject_type="Person",
                cdb_object_id=None,  # validation runs in "pre" and compares UUIDs
                **condition_update
            )
            model = View(edited.cdb_object_id)
            model.select()

    def revert(self):
        """
        Revert `self.view` for the logged-in user
        (if an "edited" copy of the user view exists, delete it)

        :raises HTTPInternalServerError: if `CDB_Delete` operation fails
        """
        edited = self.view.Edited

        if edited:
            run_operation(constants.kOperationDelete, edited)


class ChangeViews(ViewBaseModel):
    def get_defaults(self, delete, changesById):
        fields = ["is_default", "subject_id", "subject_type"]

        # index all views that will not be deleted
        # (they might become default views when changes are applied)
        views_by_id = {
            u.cdb_object_id: {field: u[field] for field in fields}
            for u in UserView.Query()
            if u.cdb_object_id not in delete
        }

        # simluate applying the changes
        for uuid in changesById:
            # we do not support creating views via changesById,
            # but it could contain uuids since deleted
            if uuid in views_by_id:
                views_by_id[uuid].update(changesById[uuid])

        defaults = defaultdict(list)

        # index all views that are still defaults
        for uuid in views_by_id:
            if (
                views_by_id[uuid]["is_default"] == 1
                and views_by_id[uuid]["subject_type"] == "Common Role"
            ):
                role_id = views_by_id[uuid]["subject_id"]
                defaults[role_id].append(uuid)

        return defaults

    def run_operation(self, opname, view, defaults, *args, **kwargs):
        try:
            operation(
                opname,
                view,
                system_args(**{UserView.__defaults__: defaults}),
                *args,
                **kwargs
            )
        except ElementsError as error:
            logging.exception("view operation failed: %s", error)
            return error

        return None

    def delete_views(self, uuids_to_delete, defaults):
        """
        :param uuids_to_delete: UUIDs of views to delete
        :type uuids_to_delete: list

        :returns: Error messages of single delete operations (if any).
            Views that do not exist or are not readable for the user
            are ignored silently.
        :rtype: list
        """
        errors = []

        for uuid in uuids_to_delete:
            view = self._getUserView(uuid)

            if view:
                error = self.run_operation(constants.kOperationDelete, view, defaults)
                if error:
                    errors.append(str(error))
                else:
                    self._delete_edited(view)

        return errors

    def change_views(self, changes, defaults):
        """
        :param changes: Changes indexed by UUIDs
        :type changes: dict

        :returns: Error messages of single modify operations (if any).
            Views that do not exist or are not readable for the user
            are ignored silently.
            Empty modification values (non-operations) are also ignored.
        :rtype: list
        """
        errors = []
        name_ml = "name_multilang"

        for uuid in changes:
            try:
                view = self._getUserView(uuid)
            except HTTPNotFound:
                logging.error("view does not exist: '%s', ignoring...", uuid)
                continue

            view_changes = changes.get(uuid, None)

            new_names = view_changes.get(name_ml, None)

            if new_names:
                field_names = UserView.name.getLanguageFields()
                view_changes.update(
                    {field_names[iso].name: new_names[iso] for iso in new_names}
                )
                del view_changes[name_ml]

            if view and view_changes:
                error = self.run_operation(
                    constants.kOperationModify,
                    view,
                    defaults,
                    form_input(view, **view_changes),
                )
                if error:
                    errors.append("{}:\n{}".format(view.GetDescription(), error))

        return errors

    def apply_all_changes(self, delete, changesById):
        errors = []
        defaults = self.get_defaults(delete, changesById)
        defaults_count = len(defaults.get("public", []))
        defaults_for_ctx = json.dumps(defaults)

        if defaults_count != 1:
            errors.append(
                "{}".format(
                    util.ErrorMessage(
                        "cs_tasks_user_view_public_default", defaults_count
                    )
                )
            )

        try:
            with transactions.Transaction():
                errors += self.delete_views(delete, defaults_for_ctx)
                errors += self.change_views(changesById, defaults_for_ctx)
                if errors:
                    raise transactions.Rollback
        except transactions.Rollback:
            pass  # messes up test otherwise :(

        return errors
