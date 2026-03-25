# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 2013 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#

import json
from webob.exc import HTTPNotFound

from cdb import sqlapi
from cs.vp.cad.rest import get_available_viewers_for_document
from cs.vp.cad.queries import classified_parts_query, create_part_condition

from cs.documents import Document
from cs.vp.cad import CADVariant
from cdbwrapc import CDBClassDef, RestTabularData
from cs.platform.web.uisupport.resttable import RestTableWrapper
from cs.platform.web.rest.support import get_restlink_by_keys


class AvailableViewers(object):
    def __init__(self, object_id):
        self.object_id = object_id

    def get_available_viewers(self, request):
        doc = Document.ByKeys(cdb_object_id=self.object_id)
        if doc is None:
            raise HTTPNotFound()

        return get_available_viewers_for_document(doc, request)


class CadSearchModel(object):

    @staticmethod
    def _get_cad_variants(baseModel, classificationSearch, searchCriteria, request):
        """
        Returns the CAD variants for a given model, together with an icon which indicates if the CAD variant
        matches the current part search criteria or not.
        No icon is returned if the current search does not contain any part related criteria.

        :param baseModel: The model for which to return the CAD variants.
        :param classificationSearch: The search criteria for the part classification search or None if no
                                     classification search was specified.
        :param searchCriteria: The current search criteria for attributes (includes all search fields, not
                               just those for part)
        :param request: The http request

        :return:
        """

        # Build a where statement for the part attributes
        attrs = {name[name.find(".") + 1:]: value for name, value in searchCriteria.items()}
        _, whereStmt = create_part_condition(attrs)

        # If neither part classification nor part attributes are used in the search, then return all
        # CAD variants without the "matches part search" icon
        if not classificationSearch and not whereStmt:
            stmt = """
            SELECT cv.* 
            FROM cad_variant cv
            WHERE cv.z_nummer='{}' AND cv.z_index='{}'""".format(
                sqlapi.quote(baseModel["z_nummer"]), sqlapi.quote(baseModel["z_index"]))
            allCadVariants = CADVariant.SQL(stmt)

            values = []
            rest_links = []

            for obj in allCadVariants:
                obj_dict = dict(obj)
                values.append(obj_dict)

                rest_link = get_restlink_by_keys("cad_variant", objargs=obj, request=request)
                rest_links.append(rest_link)

            return {"values": values, "rest_links": rest_links}

        if not whereStmt:
            whereStmt = "(1=1)"

        # Create entries in temporary table for all parts which match the classification search attributes
        cond = classified_parts_query("part", "ts", classificationSearch)
        if cond:
            existsStmt = """
            SELECT *
            FROM teile_stamm ts, {}
            WHERE ts.teilenummer=cv.teilenummer AND ts.t_index=cv.t_index AND {} AND {}
            """.format(cond[1], cond[0], whereStmt)
        else:
            # No classification query - only use the master attributes
            existsStmt = """
            SELECT *
            FROM teile_stamm ts
            WHERE ts.teilenummer=cv.teilenummer AND ts.t_index=cv.t_index AND {}
            """.format(whereStmt)

        # Get all CAD variants which match the part search criteria (attributes AND classification properties)
        stmt = """
SELECT cv.* 
FROM cad_variant cv
WHERE cv.z_nummer='{}' AND cv.z_index='{}'
      AND EXISTS ({})
""".format(sqlapi.quote(baseModel["z_nummer"]), sqlapi.quote(baseModel["z_index"]), existsStmt)
        matchingCadVariants = CADVariant.SQL(stmt)

        # Get all CAD variants which do NOT match the part search criteria (attributes AND classification)
        stmt = """
SELECT cv.* 
FROM cad_variant cv
WHERE cv.z_nummer='{}' AND cv.z_index='{}'
      AND NOT EXISTS ({})
""".format(sqlapi.quote(baseModel["z_nummer"]), sqlapi.quote(baseModel["z_index"]), existsStmt)
        nonMatchingCadVariants = CADVariant.SQL(stmt)

        # Generate links to the objects
        # RestTabularData() below requires an array - the ObjectCollection returned by
        # KeywordQuery works if it is not empty, but as soon as it is empty RestTabularData() fails with
        # an access violation

        values = []
        rest_links = []

        for obj in matchingCadVariants:
            obj_dict = dict(obj)
            obj_dict.update({"matches_part_query": "cis_cad_variant_match"})
            values.append(obj_dict)

            rest_link = get_restlink_by_keys("cad_variant", objargs=obj, request=request)
            rest_links.append(rest_link)

        for obj in nonMatchingCadVariants:
            obj_dict = dict(obj)
            obj_dict.update({"matches_part_query": "cis_cad_variant_nomatch"})
            values.append(obj_dict)

            rest_link = get_restlink_by_keys("cad_variant", objargs=obj, request=request)
            rest_links.append(rest_link)

        return {"values": values, "rest_links": rest_links}

    def get_cad_variants_to_show(self, baseModel, searchValues, request):
        """
        :param baseModel: The model to which the CAD variants are assigned
                          ({"z_nummer": "...", "z_index": "..."})

        :param searchValues: The search attributes which have been entered by the user. Contains
                             "attribute name""/"search criteria" pairs for each attribute.

                             If available, the special attribute ".part_classification_web_ctrl" contains the
                             search properties for the classification search:

                             {"addtl_properties": ...,
                              "assigned_classes": ...,
                              "values": ...,
                              ...}

                            The special attribute ".consider_cad_variant_items" specifies whether ...

        :@param request: The HTTP request object

        :return: A list of all CAD variants for the given model with an additional flag whether the
                 CAD variant matches the given part classification search criteria.
        """

        partSearch = {name: expression for name, expression in searchValues.items()
                      if name not in ['.consider_cad_variant_items', '.part_classification_web_ctrl']}

        classification_search = searchValues.get('.part_classification_web_ctrl')

        classification_params = None
        if classification_search:
            classification_params = json.loads(classification_search)
        searchResult = CadSearchModel._get_cad_variants(baseModel,
                                                        classification_params, partSearch,
                                                        request)

        table_def = CDBClassDef("cad_variant").getTabDefinition("cad_search_variant", False)

        # Map values (list of dicts) to column data where each row is a list of values in the column order
        # specified by the given table definition (afterwards, no easy access of attributes by name possible
        # anymore, columns can only be accessed by their position in the table)
        data = RestTabularData(searchResult["values"], table_def)

        # Convert row/column data into JSON data suitable for the frontend
        rest_data = RestTableWrapper(data).get_rest_data(request)

        rest_links = searchResult["rest_links"]
        rest_data_rows = rest_data["rows"]
        for each_index, each_row in enumerate(rest_data_rows):
            rest_link = rest_links[each_index]
            each_row["id"] = rest_link
            each_row["persistent_id"] = rest_link

        return rest_data
