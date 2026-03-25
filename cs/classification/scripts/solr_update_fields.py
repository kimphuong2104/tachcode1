# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2017 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

import sys
import traceback

from cs.classification.solr_schema_sync import process_single_field

if __name__ == "__main__":
    try:
        print ("Updating Solr fields ...")
        process_single_field("___currency_unit___", "Currency Unit", "strings")
        process_single_field("___currency_value___", "Currency Unit", "tdoubles")
        process_single_field("___float_range_min_value___", "Currency Unit", "tdoubles")
        process_single_field("___float_range_max_value___", "Currency Unit", "tdoubles")
        print ("Updating Solr fields done.")
    except Exception as e: # pylint: disable=W0703
        print ("Error updating Solr fields: {}").format(str(e))
        traceback.print_exc(file=sys.stdout)
