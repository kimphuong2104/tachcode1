#!/usr/bin/env python
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 1990 - 2012 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#

"""
CDB eLink plug-in "Filters".
====================================

Class Filter
------------
This plug-in uses the css class name as criterion to filter the entries of a
container.

Usage:

    1. import the javascript in page template:

        <script src="${options.plugins}filters/class_filter.js" type="text/javascript"></script>

    2. set a container "filterable":

        <div class="filterable" data-elink-filter-target="div.detail-object">

       The container must have a css class `fitlerable` and attribute
       `data-elink-filter-target`, which should be set to a css selector,
       which can be used to find out the entries to be filtered.

    3. add entries with filterable class indicator:

        <div class="filterable" data-elink-filter-target="div.detail-object">
            <div class="detail-object filter-mine filter-task">My task</div>
            <div class="detail-object filter-task">Task for someone else</div>
            ...
            <div class="detail-object filter-mine filter-checklist">...</div>
            ...
        </div>

       To be able to be recognized by the plug-in, the filterable entries must
       be represented by the selector defined by the `data-elink-filter-target`
       attribute on the container, in this example a `div`-tag with class
       `detail-object`. To be filtered by special terms, the entries must also
       have at least one class name with a term begins with `filter-`. In this
       example, the entries can be filtered by terms `mine`, `task` and
       `checklist`.

    4. add filter buttons/triggers to the container:

        <div class="filterable" data-elink-filter-target="div.detail-object">
            <div class="btn-group" data-toggle="buttons-radio">
                <button class="btn active elink-filter-on" data-elink-filter="filter-all">All</button>
                <button class="btn" data-elink-filter="filter-mine">Mine</button>
            </div>
            <div class="btn-group" data-toggle="buttons-checkbox">
                <button class="btn active elink-filter-on" data-elink-filter="filter-task">Tasks</button>
                <button class="btn active elink-filter-on" data-elink-filter="filter-checklist">Checklists</button>
            </div>
            <div class="detail-object filter-mine filter-task">My task</div>
            <div class="detail-object filter-task">Task for someone else</div>
            ...
            <div class="detail-object filter-mine filter-checklist">...</div>
            ...
        </div>

       The filter buttons or filter menu items must be grouped. There are 2
       kinds of filter group: radio button like(only one term can be chosen) or
       checkbox like(multiple terms can be combined). They can be displayed
       using button group just like the example above within a container, which
       has the `data-toggle` attribute set to `buttons-radio` or
       `buttons-checkbox`. Alternatively they can also be grouped like
       following example by container having `data-elink-filter-group`
       attribute set to `radio` or `checkbox`, if no buttons are expected:

        <div class="filterable" data-elink-filter-target="div.detail-object">
            <div data-elink-filter-group="radio">
                <p class="elink-filter-on" data-elink-filter="filter-all">All</p>
                <p data-elink-filter="filter-mine">Mine</p>
            </div>
            <div data-elink-filter-group="checkbox">
                <p class="elink-filter-on" data-elink-filter="filter-task">Tasks</p>
                <p class="elink-filter-on" data-elink-filter="filter-checklist">Checklists</p>
            </div>
            <div class="detail-object filter-mine filter-task">My task</div>
            <div class="detail-object filter-task">Task for someone else</div>
            ...
            <div class="detail-object filter-mine filter-checklist">...</div>
            ...
        </div>

       No matter how many filter groups there are, the plug-in generate a
       combined filter condition automatically.

       Notice that the filter buttons or items that have `elink-filter-on`
       class would be treated as active filter and used to filter entries.
       This class can be assigned to the html elements by default, will be
       also toggled automatically when the element get clicked.

       The filterable containers can be nested. However, the nested containers
       should have different filter targets(`data-elink-filter-target`
       attribute). And the filter buttons/items response only to the closest
       parent filterable container.

    5. active the plug-in in application javascript, e.g.:

        //=== Activates Class Filter plug-in ===
        var classFilter = new cdbElinkClassFilter();
        //Tells cdb.elink to run that plug-in.
        cdb.elink.addApplication('cdb.elink.classfilter', classFilter);

       If not all of the entries should be displayed by default, in other
       words, if the `all` filter is not active at the beginning, the
       entries should be filtered manually while initializing, or the
       `filter` event should be triggered once after initialization in
       javascript e.g.:

            $(".filterable").trigger("filter");

    This plug-in provides no css styling rules. The elements should be styled
    by the application itself.

"""

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"
