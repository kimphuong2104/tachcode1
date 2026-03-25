# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2019 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#


__revision__ = "$Id: "
__docformat__ = "restructuredtext en"

from cdb import sqlapi, typeconversion, ue, util
from cdb.lru_cache import lru_cache
from cdb.objects.org import CommonRole, Person
from cdb.platform.olc import StatusInfo
from cs.activitystream.posting_text_content_type import PostingTextConverter
from cs.platform.web.rest.support import get_restlink

from cs.pcs.projects import Role


def _getContentLabel(obj, content):
    """
    :param obj: Object handle to get attribute label from
    :type obj: ``cdb.platform.mom.CDBObjectHandle``

    :param content: Name of the label attribute of ``obj``
    :type content: basestring

    :returns: Label in current session's language of the ``content`` attribute
        of the given ``obj``

    :raises AttributeError: if ``obj`` does not have an attribute with the
        specified name.
    """
    return obj.getClassDef().getAttributeDefinition(content).getLabel()


def generateLabelProperties(content):
    """
    :param content: Name of the label attribute
    :type content: basestring

    :returns: Functions to retrieve property values from an object handle,
        indexed by "content" and "title".
    :rtype: dict

    .. rubric :: Example return value

    .. code-block :: python

        {
            "content": get_content_value,
            "title": get_label_value,
        }

    This method can be used for every class.
    """
    return {
        "content": lambda obj: getattr(obj, content),
        "title": lambda obj: _getContentLabel(obj, content),
    }


def _getAndParsePostingText(obj, content):
    """
    :param obj: Object handle of an activity post to get posting text from
    :type obj: ``cdb.platform.mom.CDBObjectHandle``

    :param content: Name of the activity posting attribute
    :type content: basestring

    :returns: Posting Text in plain text

    :raises AttributeError: if ``obj`` does not have an attribute with the
        specified name.
    """
    converter = PostingTextConverter()
    return converter.convert(getattr(obj, content))


def generatePostingProperties(content):
    """
    :param content: Name of the activity posting attribute
    :type content: basestring

    :returns: Functions to retrieve property values from an object handle,
        indexed by "content" and "title".
    :rtype: dict

    This method is a special case of `generateLabelProperties` only usable for
    activity posts, since it converts the richtext json value into plain text.
    """

    return {
        "content": lambda obj: _getAndParsePostingText(obj, content),
        "title": lambda obj: _getContentLabel(obj, content),
    }


def generateStaticLabelProperties(content):
    """
    :param content: Id of the static label.
    :type content: basestring

    :returns: Function to return the label defined by label id.
        The label id is defined by the "content" field.
    :rtype: dict
    """
    label = util.get_label(content)
    return {
        "content": lambda obj: label,
        "title": lambda obj: label,
    }


def generateDynamicErrorMessageProperties(content):
    """
    :param content: retrieve content of the Error messages
    :type content: basestring

    :returns: Functions to retrieve error message contents,
        indexed by "content" and "title".
    :rtype: dict
    This method can be used for every class.
    """

    def _getMessage(obj):
        old_string_list = str(ue.Exception(content)).split("+")
        new_string_list = []

        for part_text in old_string_list:
            part_text = part_text.strip()
            if (
                part_text[0] == '"'
                or part_text[0] == "'"
                and part_text[0] == part_text[-1]
            ):
                new_string_list.append(part_text[1:-1])
            else:
                value = getattr(obj, part_text)
                new_string_list.append(value)

        label = "".join(new_string_list)
        return label

    return {"content": _getMessage, "title": lambda obj: content}


@lru_cache(clear_after_ue=True)
def _getSubjectThumbnail(subject_id, subject_type):
    if subject_type == "PCS Role":
        objects = Role.KeywordQuery(role_id=subject_id)
    elif subject_type == "Common Role":
        objects = CommonRole.KeywordQuery(role_id=subject_id)
    elif subject_type == "Person":
        objects = Person.KeywordQuery(personalnummer=subject_id)
    else:
        objects = []

    if len(objects) == 1:
        return get_restlink(objects[0].GetThumbnailFile())

    # unknown or empty name or multiple objects found
    return ""


def generateThumbnailProperties(content):
    """
    :param content: Attribute name used to retrieve the thumbnail
    :type content: basestring

    :returns: Function to retrieve property values from an object handle,
        indexed by "name" and "thumbnail".
    :rtype: dict

    .. rubric :: Example return value

    .. code-block :: python

        {
            "name": get_icon_label,
            "thumbnail": get_icon_url,
        }

    This method can be used for every class.
    """

    def _getThumbnail(obj):
        """
        :returns: Name of the responsible entity (person, common or project
            role)
        :rtype: basestring
        """
        return _getSubjectThumbnail(
            getattr(obj, content),
            getattr(obj, "subject_type"),
        )

    return {
        "name": lambda obj: getattr(obj, content),
        "thumbnail": _getThumbnail,
    }


def generateClassIconProperties(content):
    """
    :param content: IGNORED parameter; present because it is handed down to
        each python help function
    :type content: basestring

    :returns: Function to retrieve property values from an object handle,
        indexed by "title" and "name".
    :rtype: dict

    .. rubric :: Example return value

    .. code-block :: python

        {
            "title": get_classname,
            "name": get_icon_id,
        }

    This method can be used for every class.
    """
    return {
        "title": lambda obj: obj.getClassDef().getClassname(),
        "name": lambda obj: obj.getClassDef().getIconId(),
    }


def generateIconProperties(content):
    """
    :param content: Parameter containing IconId.
    :type content: basestring

    :returns: F
    :rtype: dict
    """
    return {
        "title": lambda obj: "",
        "name": lambda obj: content,
    }


def generateStatusIconProperties(content):
    """
    :param content: IGNORED parameter; present because it is handed down to
        each python help function
    :type content: basestring

    :returns: Function to retrieve property values from an object handle,
        indexed by "status", "color" and "label".
    :rtype: dict

    .. rubric :: Example return value

    .. code-block :: python

        {
            "status": get_status_number,
            "color": get_color,
            "label": get_status_label,
        }

    .. note ::

        The value of "color" is a valid css color value.

    This method can be used for every class.

    .. warning ::

        If the "status" function is called with an object handle missing the
        attribute ``status`` or the "label" function when
        ``joined_status_name`` is missing, an ``AttributeError`` will be
        raised.
    """

    def _getStatusInfo(obj):
        try:
            status = int(getattr(obj, "status"))
        except (ValueError, TypeError):
            return None
        try:
            info = StatusInfo(obj.getOLC(), status)
            return info
        except AttributeError:
            return None

    def _getStatusColor(obj):
        info = _getStatusInfo(obj)
        if info:
            return info.getCSSColor()
        # OLC cannot be found; return default color (white)
        return "rgb(247, 247, 247)"

    def _getStatusLabel(obj):
        info = _getStatusInfo(obj)
        if info:
            return info.getLabel()
        # OLC cannot be found; return empty label
        return ""

    return {
        "status": lambda obj: getattr(obj, "status"),
        "color": _getStatusColor,
        "label": _getStatusLabel,
    }


def generateDateProperties(content):
    """
    :param content: Attribute name to be displayed as date.
    :type content: basestring

    :returns: Function to retrieve property values from an object handle,
        indexed by "date" and "title".
    :rtype: dict

    .. rubric :: Example return value

    .. code-block :: python

        {
            "date": get_isodate,
            "title": get_date_label,
        }

    This method can be used for every class.
    """

    def _getIsoFormattedDate(obj):
        # if the task has no value for the attribute defined by content,
        # return an empty string
        # else return an isoformatted date
        try:
            date = getattr(obj, content)
        except AttributeError:
            # obj has no attribute like specified in content
            date = None
        if date:
            # NOTE: since obj is an object handle we need to use the legacy
            # conversion
            # To display only date we set the hours/mins/seconds all to zeroes
            # As truncating date will display time when rendered
            return (
                typeconversion.from_legacy_date_format(date)
                .replace(hour=0, minute=0, second=0, microsecond=0)
                .isoformat()
            )
        return ""

    return {
        "date": _getIsoFormattedDate,
        "title": lambda obj: _getContentLabel(obj, content),
    }


def generateDocumentAuthorThumbnailProperties(content):
    """
    :param content: Attribute name used to retrieve the thumbnail
    :type content: basestring

    :returns: Function to retrieve property values from an object handle,
        indexed by "name" and "thumbnail".
    :rtype: dict

    .. rubric :: Example return value

    .. code-block :: python

        {
            "name": get_icon_label,
            "thumbnail": get_icon_url,
        }

    This method can be used for document classes.
    """

    def _getThumbnail(obj):
        """
        :returns: Name of the responsible entity (person, common or project
            role)
        :rtype: basestring
        """
        responsibleName = getattr(obj, content).split("/")[0]

        objects = Person.KeywordQuery(name=responsibleName)

        if len(objects) == 1:
            return get_restlink(objects[0].GetThumbnailFile())

        # unknown or empty name or multiple objects found
        return ""

    return {
        "name": lambda obj: getattr(obj, content),
        "thumbnail": _getThumbnail,
    }


def generateDocumentStatusIconProperties(content):
    """
    :param content: IGNORED parameter; present because it is handed down to
        each python help function
    :type content: basestring

    :returns: Function to retrieve property values from an object handle,
        indexed by "status", "color" and "label".
    :rtype: dict

    .. rubric :: Example return value

    .. code-block :: python

        {
            "status": get_status_number,
            "color": get_color,
            "label": get_status_label,
        }

    .. note ::

        The value of "color" is a valid css color value.

    This method can be used for every class.

    .. warning ::

        If the "status" function is called with an object handle missing the
        attribute ``status`` or the "label" function when
        ``joined_status_name`` is missing, an ``AttributeError`` will be
        raised.
    """

    def _getStateColor(obj):
        # use recordset; SQL-Statement always costs the same and RecordSet is
        # lazily evaluated
        objektart = obj.getOLC()
        records = sqlapi.RecordSet2(
            sql="SELECT rot_anteil, gruen_anteil, blau_anteil "
            "FROM objektstati o INNER JOIN farben f "
            "ON o.statusfarbe=f.bezeichnung "
            f"WHERE o.objektart='{objektart}' AND o.statusnummer = '{getattr(obj, 'z_status')}'"
        )
        try:
            # Test if there was an record found
            record = records[0]
            return (
                f"rgb({record.rot_anteil},{record.gruen_anteil},{record.blau_anteil})"
            )
        except IndexError:
            # record set is empty; return default color (white)
            return "rgb(247, 247, 247)"

    return {
        "status": lambda obj: getattr(obj, "z_status"),
        "color": _getStateColor,
        "label": lambda obj: getattr(obj, "joined_status_name"),
    }


def generatePersnoThumbnailProperties(content):
    """
    :param content: Attribute name used to retrieve the thumbnail
    :type content: basestring

    :returns: Function to retrieve property values from an object handle,
        indexed by "name" and "thumbnail".
    :rtype: dict

    .. rubric :: Example return value

    .. code-block :: python

        {
            "name": get_icon_label,
            "thumbnail": get_icon_url,
        }

    This method can be used for all classes.
    """

    def _getThumbnail(obj):
        """
        :returns: Name of the responsible entity (person, common or project
            role)
        :rtype: basestring
        """
        responsiblePersno = getattr(obj, content)

        pers = Person.ByKeys(personalnummer=responsiblePersno)

        if pers:
            return get_restlink(pers.GetThumbnailFile())

        # unknown or empty name or multiple objects found
        return ""

    return {
        "name": lambda obj: getattr(obj, content),
        "thumbnail": _getThumbnail,
    }


def generateObjectIconProperties(content):
    """
    :param content: Parameter containing IconId.
    :type content: basestring

    :returns: F
    :rtype: dict
    """

    def _getObjectIcon(obj):
        from cdb.objects.iconcache import IconCache, _LabelValueAccessor

        icon_id = obj.getClassDef().getObjectIconId() if not content else content
        return IconCache.getIcon(icon_id, accessor=_LabelValueAccessor(obj))

    return {
        "title": lambda obj: "",
        "src": _getObjectIcon,
    }
