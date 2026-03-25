#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

from collections import defaultdict

__revision__ = "$Id: "
__docformat__ = "restructuredtext en"

import json

from cdb import CADDOK, auth, util
from cdb.objects import ByID, Forward, ReferenceMethods_1
from cdb.objects.org import User, WithSubject
from cdb.platform.gui import CDBCatalog
from cs.taskmanager.web.util import (
    get_class_rest_id,
    get_object_rest_id,
    get_rest_id_from_uuid,
)

CATEG_PRECONFIGURED = "preconfigured"
CATEG_USER = "user"
CATEG_EDITED = "edited"
CATEGORIES = [
    CATEG_PRECONFIGURED,
    CATEG_USER,
    CATEG_EDITED,
]

SELECTED = "selectedView"

fUserView = Forward("{}.UserView".format(__name__))


def get_frontend_condition(condition, request):
    """
    Replace object references in filter conditions `condition`
    with their respective REST links:

    +----------+-----------------------------------+--------------------+
    | Key      | Original Value                    | Converted Value    |
    +==========+===================================+====================+
    | types    | Classnames, for ex.               | List of `@type`    |
    |          | `["cdbpcs_issue", "cdbpcs_task"]` | URLs               |
    +----------+-----------------------------------+--------------------+
    | contexts | List of `cdb_object_id` values    | List of `@id` URLs |
    +----------+-----------------------------------+--------------------+
    | users    | List of user IDs and "$(persno)": | List of `@id` URLs |
    |          | `["caddok", "$(persno)"]`         |                    |
    +----------+-----------------------------------+--------------------+

    :param condition: Filter conditions as stored in the backend
        (already deserialized from JSON).
    :type condition: dict

    :param request: The morepath request object. If `None`,
        only relative URLs are generated.

    :returns: Frontend-compatible condition.
    :rtype: dict
    """

    def replace_user(id_or_var, request):
        persno = auth.persno if id_or_var == "$(persno)" else id_or_var
        user = User.ByKeys(persno)
        if user and user.CheckAccess("read"):
            return get_object_rest_id(user, request)
        return None

    result = dict(condition)
    for attr, replace_func in [
        ("contexts", get_rest_id_from_uuid),
        ("types", get_class_rest_id),
        ("users", replace_user),
    ]:
        replaced = [
            replace_func(oid, request) for oid in condition.get(attr, []) if oid
        ]
        result[attr] = [rest_id for rest_id in replaced if rest_id]

    return result


def _dialog_handle_category_change(hook_or_ctx, category, prefix=None):
    def _field(name):
        if prefix:
            return "{}.{}".format(prefix, name)
        return name

    name_fields = UserView.name.getLanguageFields()

    if category == CATEG_PRECONFIGURED:
        for isolang in name_fields:
            hook_or_ctx.set_mandatory(_field(name_fields[isolang].name))
        hook_or_ctx.set_writeable(_field("is_default"))
    else:
        # "name" is still mandatory, so any one language is OK
        for isolang in name_fields:
            hook_or_ctx.set_optional(_field(name_fields[isolang].name))
        hook_or_ctx.set(_field("is_default"), 0)
        hook_or_ctx.set_readonly(_field("is_default"))


class UserView(WithSubject):
    """
    UserView represents a persistent combination of filter values for
    |cs.taskmanager|. Each user view must have one of the following
    `category` values and adhere to its category's rules (see `validate`).

    For a more detailed explanation of each user view category, see the
    :ref:`Administrator Manual<tm_admin:taskmanager-conf-user-views>`.

    .. rubric :: Access Control

    +---------------+-------------------------------+
    | Access Right  | Granted for                   |
    +===============+===============================+
    | read          | - Subjects of user view       |
    +---------------+-------------------------------+
    | FULL ACCESS   | - Owner of personal user view |
    |               | - Owner of edited view        |
    |               | - Common Role "Administrator" |
    +---------------+-------------------------------+
    """

    __maps_to__ = "cs_tasks_user_view"
    __classname__ = "cs_tasks_user_view"
    __condition_attr__ = "cs_tasks_user_view_condition"
    __customizes_whitelist__ = {
        CATEG_USER: {CATEG_PRECONFIGURED},
        CATEG_EDITED: {CATEG_PRECONFIGURED, CATEG_USER},
    }
    __dict_whitelist__ = {
        "category",
        "cdb_cdate",
        "cdb_cpersno",
        "cdb_mdate",
        "cdb_mpersno",
        "cdb_object_id",
        "customizes",
        "name",
        "subject_id",
        "subject_type",
    }

    @classmethod
    def _getDefaultViewQueries(cls):
        roles = util.get_roles("GlobalContext", "", auth.persno)
        return [
            # subject_id, subject_type
            ("= '{}'".format(auth.persno), "Person"),
            (
                "IN ('{}') AND subject_id != 'public'".format("', '".join(roles)),
                "Common Role",
            ),
            ("= 'public'", "Common Role"),
        ]

    def _get_edited(self):
        for edited in UserView.KeywordQuery(
            customizes=self.cdb_object_id,
            category=CATEG_EDITED,
            subject_id=auth.persno,
            subject_type="Person",
        ):
            return edited

        return None

    def _get_customizes(self):
        if self.customizes:
            return ByID(self.customizes)
        return None

    Edited = ReferenceMethods_1(fUserView, _get_edited)
    Customizes = ReferenceMethods_1(fUserView, _get_customizes)

    @classmethod
    def GetCustomAttributes(cls, name=None, condition=None):
        """
        :param name: Name of the new user view.
            Will be used for all internationalized names.
        :type name: basestring

        :param condition: Filter condition as serialized JSON.
        :type condition: basestring

        :returns: Default values for creating
            a new custom user view for logged-in user.
        :rtype: dict
        """
        result = {
            "is_default": 0,
            "category": CATEG_USER,
            "subject_id": auth.persno,
            "subject_type": "Person",
        }

        if name:
            result[UserView.getNameField()] = name

        if condition:
            result[cls.__condition_attr__] = condition

        return result

    def toDict(self):
        """
        :returns: Representation of `self`
            including resolved long text (condition).
        :rtype: dict
        """
        result = {field: self[field] for field in self.GetFieldNames()}
        result[self.__condition_attr__] = self.GetText(self.__condition_attr__)
        return result

    @staticmethod
    def getNameField():
        return UserView.name.getLanguageField(CADDOK.ISOLANG).name

    def getCustomCopyAttributes(self, name=None, condition=None):
        "used when copying a preconfigured user view"
        result = self.GetCustomAttributes(
            name, condition or self.GetText(self.__condition_attr__)
        )
        result["cdb_object_id"] = None
        return result

    @classmethod
    def GetDefaultView(cls):
        """
        Returns the default view for the current user.
        It is the first view the current user has read access to in this list:

        1. The personal default view for the user
        2. First default view for any of the user's common roles but 'public'
        3. The default view for common role 'public'

        If the returned view is customized for the user,
        the customized view is returned instead.

        :returns: The default view for the current user.
        :rtype: cs.taskmanager.user_views.UserView
        """
        for subject_id, subject_type in cls._getDefaultViewQueries():
            query_str = (
                "(customizes IS NULL OR customizes = '') "
                "AND category = '{}' "
                "AND is_default = 1 "
                "AND subject_id {} "
                "AND subject_type = '{}'".format(
                    CATEG_PRECONFIGURED, subject_id, subject_type
                )
            )
            views = cls.Query(query_str, access="read")
            for default_view in views:
                return default_view

    @classmethod
    def ForUser(cls):
        """
        Returns all non-default, non-edited views readable by current user.

        :param cdb_person_id: User ID to get views for.
            Defaults to logged-in user's ID.
        :type cdb_person_id: str

        :returns: All views current user has read access to.
        :rtype: cdb.objects.ObjectCollection of cs.taskmanager.user_views.UserView
        """
        roles = util.get_roles("GlobalContext", "", auth.persno)
        all_views = cls.Query(
            # condition is a performance optimization
            # read access is checked and expected to match subject assignment
            "is_default = 0 AND "
            "category != '{}' AND "
            "customizes = '' AND "
            "((subject_type = 'Person' AND subject_id = '{}') OR "
            "(subject_type = 'Common Role' AND subject_id IN ('{}')))".format(
                CATEG_EDITED,
                auth.persno,
                "', '".join(roles),
            ),
            access="read",
        )

        return all_views

    def getCondition(self, request):
        cond = json.loads(self.GetText(self.__condition_attr__))
        return get_frontend_condition(cond, request)

    def getEditedJSON(self, condition, request):
        edited = {}

        if self.Edited:
            edited_condition = self.Edited.getCondition(request)
            edited = {
                key: value
                for key, value in edited_condition.items()
                if key not in condition or condition[key] != value
            }

        return edited

    def toJSON(self, request=None):
        """
        Return value contains these keys:

        - `@id`: The view's UUID
        - `category` and `is_default`: type-identifying values
        - `edited`: Delta between persisted and edited filter conditions
        - `filters`: Current filter condition (includes edits)
        - `name`: Name of the view in session language
        - `name_multilang`: Internationalized names indexed by iso language code
        - ``view_position``: numerical sorting order
        - `subject_id`, `subject_type`, `subject_name`:
            (Predefined views only) The role this view belongs to

        .. warning ::

            Read access is not checked.

        :returns: JSON-serializable representation of `self`
        :rtype: dict
        """
        condition = self.getCondition(request)
        edited = {}

        if self.category == CATEG_EDITED:
            edited = self.Customizes.getEditedJSON(condition, request)
        elif self.Edited:
            edited = self.getEditedJSON(condition, request)

        condition.update(edited)
        result = {
            # view URLs are unused, so use UUIDs instead to save space
            "@id": self.cdb_object_id,
            "category": self.category,
            "is_default": self.is_default,
            "edited": list(edited.keys()),
            "filters": condition,
            "name": self.name,
            "name_multilang": self.GetLocalizedValues("name"),
            "view_position": self.view_position,
            "subject_id": self.subject_id,
            "subject_type": self.subject_type,
            "subject_name": self.Subject.name if self.Subject else "",
        }

        if self.customizes:
            result["customizes"] = self.customizes

        return result

    @staticmethod
    def dialog_handle_category_change_hook(hook):
        prefix = "cs_tasks_user_view"
        new_values = hook.get_new_values()
        category_field = "{}.category".format(prefix)
        category = new_values[category_field]
        changed = category_field in hook.get_changed_fields()
        if changed:
            _dialog_handle_category_change(hook, category, prefix)

    def dialog_handle_category_change(self, ctx):
        changed = ctx.mode == "dialogitem_change" and ctx.changed_item == "category"
        if changed:
            _dialog_handle_category_change(ctx, ctx.dialog.category)

    event_map = {
        (("create", "copy", "modify", "delete"), "pre"): "validate",
        (
            ("create", "copy", "modify"),
            ("dialogitem_change", "pre_mask"),
        ): "dialog_handle_category_change",
    }

    def _validate_public_default(self, public_defaults, is_delete):
        condition = {
            "is_default": 1,
            "subject_id": "public",
            "subject_type": "Common Role",
        }
        found = len(public_defaults)

        def _self_is_public_default():
            for key, value in condition.items():
                if self[key] != value:
                    return False
            return True

        self_is_public_default = _self_is_public_default()

        if self.cdb_object_id in public_defaults:
            # if persistent version of self is public default,
            # but version to be persisted is not, subtract one count
            if not self_is_public_default:
                found -= 1
        elif self_is_public_default and not is_delete:
            # if persistent version of self is not a public default,
            # but version to be persisted is, add one count
            found += 1

        if found != 1:
            return util.ErrorMessage(
                "cs_tasks_user_view_public_default",
                found,
            )

    def _validate_name(self, categ_is_user):
        if categ_is_user:
            if not self.name:
                return util.ErrorMessage("cs_tasks_user_view_empty_name")
        else:
            all_names = self.GetLocalizedValues("name")
            empty_names = [iso for iso, name in all_names.items() if not name]
            if empty_names:
                return util.ErrorMessage(
                    "cs_tasks_user_view_empty_name_i18n", empty_names
                )

        return None

    def _validate_condition(self, ctx):
        condition = getattr(ctx.dialog, self.__condition_attr__, None)
        if condition:
            try:
                json.loads(condition)
            except (ValueError, TypeError):
                return util.ErrorMessage(
                    "cs_tasks_invalid_json", self.__condition_attr__
                )

        return None

    def _validate_customizes(self):
        if self.category == CATEG_EDITED:
            whitelist = self.__customizes_whitelist__[self.category]

            if not self.Customizes or (self.Customizes.category not in whitelist):
                return util.ErrorMessage("cs_tasks_user_view_no_cust_usr")

        return None

    def _validate_subject(self, categ_is_user):
        if categ_is_user:
            if self.subject_type != "Person" or not self.Subject:
                return util.ErrorMessage("cs_tasks_user_view_no_usr_role")

        elif self.subject_type != "Common Role" or not self.Subject:
            return util.ErrorMessage("cs_tasks_user_view_no_common_role")

        return None

    def _validate_default(self, categ_is_user, defaults, is_delete):
        # pylint: disable=missing-format-attribute
        if not categ_is_user and self.is_default and not is_delete:
            other_defaults = set(defaults).difference([self.cdb_object_id])

            if other_defaults:
                return util.ErrorMessage(
                    "cs_tasks_user_view_default_exists",
                    getattr(
                        self.Subject,
                        "name",
                        "{0.subject_id} ({0.subject_type})".format(self),
                    ),
                )

        return None

    @classmethod
    def get_defaults(cls):
        defaults = defaultdict(set)

        for default_view in cls.KeywordQuery(
            is_default=1,
            subject_type="Common Role",
        ):
            defaults[default_view.subject_id].add(default_view.cdb_object_id)

        return defaults

    __defaults__ = "cs_tasks_default_views"

    def validate(self, ctx):
        """
        Make sure the user view ``self`` adheres to its category's rules:

        +-----------------+-----------------------------------------+
        | Category        | Rules                                   |
        +=================+=========================================+
        | any             | - ``cs_tasks_user_view_condition``      |
        |                 |   contains valid JSON (This rule is not |
        |                 |   checked if the long text field is not |
        |                 |   part of the dialog)                   |
        |                 | - exactly one public default user view  |
        |                 |   exists.                               |
        +-----------------+-----------------------------------------+
        | "preconfigured" | - Name may not be empty in any          |
        |                 |   translation                           |
        |                 | - ``Subject`` must be a Common Role     |
        |                 | - Another default view                  |
        |                 |   for the same role may not exist       |
        +-----------------+-----------------------------------------+
        | "user" and      | - ``Subject`` must be a Person          |
        | "edited"        | - ``name`` may not be empty             |
        +-----------------+-----------------------------------------+
        | "edited"        | - ``customizes`` may not be empty and   |
        |                 |   references a view with a category     |
        |                 |   other than "edited"                   |
        +-----------------+-----------------------------------------+

        Because combining multiple operations can result in a valid state,
        ``ctx.sys_args.cs_tasks_default_views`` can contain serialized
        JSON with UUIDs of default user views of a projected future state
        indexed by subject_id.
        Only if this is missing will defaults be read from database.
        If exactly one public default user view exists is only checked
        in this case.
        The existence of the sys arg flag indicates the check has already been made.

        :raises cdb.util.ErrorMessage: If at least one rule is violated.
        """
        self.Reload()
        categ_is_user = self.category in (CATEG_USER, CATEG_EDITED)
        is_delete = ctx.action == "delete"

        errors = []
        defaults = getattr(ctx.sys_args, self.__defaults__, None)

        if defaults is None:
            defaults = self.get_defaults()
            error_public_default = self._validate_public_default(
                defaults.get("public", []), is_delete
            )
            if error_public_default:
                errors.append(error_public_default)
        else:
            defaults = json.loads(defaults)

        errors.append(
            self._validate_default(
                categ_is_user, defaults.get(self.subject_id, []), is_delete
            )
        )

        if not is_delete:
            errors += [
                self._validate_name(categ_is_user),
                self._validate_condition(ctx),
                self._validate_customizes(),
                self._validate_subject(categ_is_user),
            ]

        errors = [msg for msg in errors if msg]

        if errors:
            raise util.ErrorMessage(
                "just_a_replacement",
                "\n".join(["- {}".format(str(error)) for error in errors]),
            )


class UserViewCategoryBrowser(CDBCatalog):
    def __init__(self):
        CDBCatalog.__init__(self)

    def handlesSimpleCatalog(self):
        return True

    def getCatalogEntries(self):
        return CATEGORIES
