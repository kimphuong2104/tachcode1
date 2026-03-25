# -*- coding: utf-8 -*-
#
# This file is execfile()d with the current directory set to its containing dir.
#
# See http://sphinx.pocoo.org/config.html for details to all options.
from cs.userassistance.sphinxconf import (
    configure,
    kDocCategoryAdmin,
    kDocCategoryProgramming,
    kDocCategoryReleaseNotes,
    kDocCategoryUser,
)

configure(
    globals(),
    title='%PKGNAME%',
    language='%LANG%',
    # You might change the category
    # Choose one of the categories from above
    category=kDocCategoryUser,
    # You might change the default author on the pdf output start page
    # latex_author='document author'
    # You might change the default logo on the html output
    # html_icon='myicon36x36.png'
)
