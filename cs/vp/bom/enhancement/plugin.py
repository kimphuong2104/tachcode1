# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

# Exported objects
__all__ = [
    "AbstractPlugin",
    "Dependencies",
    "AbstractRestPlugin",
]

from typing import Optional, Any, Type, Iterable, Self

from cdb.sqlapi import Record


class AbstractPlugin:
    """
    Base class to implement different enhancement plugins for usage
    with :class:`cs.vp.bom.enhancement.FlatBomEnhancement` class.

    :return: a constructed :class:`cs.vp.bom.enhancement.plugin.AbstractPlugin` object
    """

    """
    Aliasname for table einzelteile.
    """
    BOM_ITEM_TABLE_ALIAS: str = "bom_item"

    """
    Aliasname used for the component join from einzelteile to teile_stamm.
    """
    COMPONENT_TABLE_ALIAS: str = "component"

    def get_sql_join_stmt_extension(self) -> Optional[str]:
        """
        SQL extension to add "JOIN" statement of the bom_item (einzelteile) query.
        Each statement of the different plugins gets added together as these are.
        So each plugin is responsible for providing correct syntax.

        If the plugin should not use this `None` should be returned.
        This is the default behavior if you inherited from this class
        :class:`cs.vp.bom.enhancement.plugin.AbstractPlugin`.

        See :ref:`Enhance the SQL`

        :return: string which get added to "JOIN" statement or None if not used
        """
        return None

    def get_part_where_stmt_extension(self) -> Optional[str]:
        """
        SQL extension for the "WHERE" condition of the part (teile_stamm) query

        If the plugin should not use this `None` should be returned.
        This is the default behavior if you inherited from this class
        :class:`cs.vp.bom.enhancement.plugin.AbstractPlugin`.

        See :ref:`Enhance the SQL`

        :return: string which get added to "WHERE" condition or None if not used
        """
        return None

    def get_bom_item_select_stmt_extension(self) -> Optional[str]:
        """
        SQL extension for the "SELECT" condition of the bom_item (einzelteile) query.
        Each statement of the different plugins gets added together as these are.
        So each plugin is responsible for providing correct syntax.

        If the plugin should not use this `None` should be returned.
        This is the default behavior if you inherited from this class
        :class:`cs.vp.bom.enhancement.plugin.AbstractPlugin`.

        See :ref:`Enhance the SQL`

        :return: string which get added to "SELECT" condition or None if not used
        """
        return None

    def get_bom_item_where_stmt_extension(self) -> Optional[str]:
        """
        SQL extension for the "WHERE" condition of the bom_item (einzelteile) query

        If the plugin should not use this `None` should be returned.
        This is the default behavior if you inherited from this class
        :class:`cs.vp.bom.enhancement.plugin.AbstractPlugin`.

        See :ref:`Enhance the SQL`

        :return: string which get added to "WHERE" condition or None if not used
        """
        return None

    def get_additional_bom_item_attributes(
        self, bom_item_record: Record
    ) -> Optional[dict[Any, Any]]:
        """
        Used to retrieve additional attributes for the bom_item (einzelteile).

        If the plugin should not use this `None` should be returned.
        This is the default behavior if you inherited from this class
        :class:`cs.vp.bom.enhancement.plugin.AbstractPlugin`.

        :param bom_item_record: database record of the bom_item

        :return: dictionary with additional attributes for the bom_item
        """
        return None

    def filter_bom_item_records(self, bom_item_records: list[Record]) -> list[Record]:
        """
        Used to filter bom_item (einzelteile) records.

        If the plugin should not use this just return the original `bom_item_records`.
        This is the default behavior if you inherited from this class

        :param bom_item_records: list with :class:`cdb.sqlapi.Record`

        :return: filtered list with :class:`cdb.sqlapi.Record`
        """
        return bom_item_records

    def resolve_bom_item_children(self, bom_item_record: Record) -> bool:
        """
        Used to further deeply resolve the children of the `bom_item`.

        Example:
        Abort in case of an imprecise position

        .. code-block:: python

            def resolve_bom_item_children(self, bom_item_record: Record) -> bool:
                return bom_item_record.is_imprecise == 0


        :param bom_item_record: `cdb.sqlapi.Record`
        :return: True (default) if children should be resolved or False if not
        """
        return True


Dependencies = dict[Type["AbstractRestPlugin"], Optional["AbstractRestPlugin"]]


class AbstractRestPlugin(AbstractPlugin):
    """
    Base class to implement different enhancement plugins for REST usage
    with :class:`cs.vp.bom.enhancement.FlatBomRestEnhancement` class.

    :return: a constructed :class:`cs.vp.bom.enhancement.plugin.AbstractRestPlugin` object
    """

    DISCRIMINATOR: str = "unknown"
    """
    This discriminator is a arbitrary string and is used to store the data in the frontend. Also the
    frontend components send the data to the REST calls with these discriminators.

    .. note::
        It is important that this is globally unique. Therefore currently plugins use
        the python module as prefix. e.g. "cs.vp.pluginA"
    """

    DEPENDENCIES: Iterable[Type["AbstractRestPlugin"]] = tuple()
    """
    Iterable with all needed plugin dependencies. These dependencies are given as class references.
    """

    @classmethod
    def create_from_rest_data(
        cls, rest_data: Optional[Any], dependencies: Dependencies
    ) -> Optional[Self]:
        """
        Create a plugin instance with data from a REST request

        :param rest_data: REST data for this specific plugin
                          (:attr:`cs.vp.bom.enhancement.plugin.AbstractRestPlugin.DISCRIMINATOR`
                          is used to get this specific data)
        :param dependencies: dict with dependencies which where requested by this plugin.
                             key is the class type.
                             value is the instanced plugin.

                             .. note::
                                 It is guaranteed that this dict contains keys for all given dependencies
                                 :attr:`cs.vp.bom.enhancement.plugin.AbstractRestPlugin.DEPENDENCIES`.
                                 If a dependency does not exist the value is `None`.

        :return: a constructed :class:`cs.vp.bom.enhancement.plugin.AbstractRestPlugin` object or None
        """
        raise RuntimeError()

    @classmethod
    def create_for_default_data(
        cls, dependencies: Dependencies, **kwargs: Any
    ) -> Optional[Self]:
        """
        Create a plugin instance for generating default data with
        :meth:`cs.vp.bom.enhancement.plugin.AbstractRestPlugin.get_default_data`

        :param dependencies: dict with dependencies which where requested by this plugin.
                             key is the class type reference.
                             value is the instanced plugin.

                             .. note::
                                 It is guaranteed that this dict contains keys for all given dependencies
                                 :attr:`cs.vp.bom.enhancement.plugin.AbstractRestPlugin.DEPENDENCIES`.
                                 If a dependency does not exist the value is `None`.
        :param kwargs: dependent on the REST endpoint additional information can be provided

        :return: a constructed :class:`cs.vp.bom.enhancement.plugin.AbstractRestPlugin` object or None
        """
        return None

    def get_default_data(self) -> tuple[Any, Any]:
        """
        Generate default data for this plugin

        Returns a tuple:
            * The first value are the bomEnhancementData which are applied per default (initial).
              This can be used e.g. for URL parameters or similar.
            * The second value are the reset Data (used by resetting the enhancement data)
              This value is used in the 'resetBomEnhancementData' js action to set the bomEnhancementData
              to this value

        :return: the default data for this plugin
        """
        return None, None
