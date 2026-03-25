# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2017 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

"""
Module outlet_generators

The module provide some callables that generates generic outlet configurations
"""

from __future__ import absolute_import
__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

# Exported objects
__all__ = []


from copy import deepcopy
from cdb import fls
from cs.web.components import outlet_config
from cs.web.components.ui_support.utils import class_available_in_ui


class OutletPositionRelationshipsCallback(outlet_config.OutletPositionCallbackBase):
    """
    A callback that generates outlet positions for all relationships that are
    prepared to be used with the Web UI.
    The generator adapts the standard configuration so be sure to set the
    correct child name in your configuration.

    You can exclude relationships if you add their role name to a list named
    ``excludeRelships`` that you can configure in the JSON properties. A
    configuration might look like this:

    .. code-block:: none

        {"excludeRelships": ["Cdb_organization_to_cdb_person"]}

    You can also explicitely set the relationships you want to offer by
    providing a list named ``includeRelships``.

    A relationship is included in the generated outlet positions, if it is
    either mentioned explicitly in ``includeRelships``, or the target class has
    one of the operations "Info" or "Search" enabled for the Web UI.
    """
    @classmethod
    def adapt_initial_config(cls, pos_config, cldef, obj):
        """
        This callback allows you to manipulate the configuration of the
        position. You may change `pos_config` or return a list of dictionaries
        that should be used instead of this configuration.
        """
        def _adapt_cfg_from_rs(rs):
            cfg = deepcopy(pos_config)
            cfg["title"] = rs.get_label()
            cfg["icon_url"] = rs.get_icon_url()
            cfg["cfg_id"] = rs.get_rolename()
            cfg["properties"].update({"relshipName": rs.get_rolename()})
            return cfg

        def _is_rsdef_suitable(rs, explicitly_configured, obj):
            """
            Returns ``True`` if a relationship should be displayed as
            a register. The function checks the relationship access if an
            access right is configured for the relationship and if the
            target class has a REST name.
            If the ``checkRoles`` property is set the function also checks
            if the user is an owner of the relationship roles.
            If a relationship is not explicitly configured, which means
            it is not part of the ``includeRelships`` property, the system
            looks if the relationship should be displayed in a mask and
            not initially hidden. If you want to show also hidden
            relationships you have to set the showHidden property to ``True``.
            """
            try:
                if obj and not obj.CheckAccess(rs.get_acl()):
                    return False
            except AttributeError:
                pass

            if not rs or not rs.is_valid() or rs.is_one_on_one():
                return False

            for licfeature in rs.get_lic_features():
                if not fls.is_available(licfeature):
                    return False

            if not cldef.getRESTName():
                return False

            props = pos_config["properties"]
            if not explicitly_configured or props.get("checkRoles", False):
                if not rs.is_visible():
                    return False

            if explicitly_configured:
                # The relship is explicitly included, therefore we only check
                # the minimum technical requirements
                return True

            return (rs.show_in_mask() and
                    (not rs.hide_initially() or props.get("showHidden", False)) and
                    class_available_in_ui(rs.get_reference_cldef()))

        result = []
        if cldef:
            rs_name = pos_config["properties"].get("relshipName")
            if rs_name:
                # Explicitely configured relationship
                rsdef = cldef.getRelationshipByRolename(rs_name)
                if _is_rsdef_suitable(rsdef, True, obj):
                    result.append(pos_config)
            else:
                rs_roles = pos_config["properties"].get("includeRelships")
                if rs_roles:
                    for rs_role in rs_roles:
                        rs = cldef.getRelationshipByRolename(rs_role)
                        if _is_rsdef_suitable(rs, True, obj):
                            result.append(_adapt_cfg_from_rs(rs))
                        elif not rs:
                            # Python role?
                            cfg = deepcopy(pos_config)
                            cfg["properties"].update({"relshipName": rs_role})
                            result.append(cfg)
                else:
                    exclude = pos_config["properties"].get("excludeRelships", [])
                    for rs_name in cldef.getRelationshipNames():
                        rs = cldef.getRelationship(rs_name)
                        if _is_rsdef_suitable(rs, False, obj) and rs.get_rolename() not in exclude:
                            result.append(_adapt_cfg_from_rs(rs))
        return result
