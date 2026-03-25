import logging
import json

from urllib.parse import urlencode
from cdb import util, ue
from cdb.objects import ByID
from cdb.lru_cache import lru_cache
from cdb.platform.mom import relships, entities
from cs.platform.web.rest import support

from cdbwrapc import CDBClassDef

from cs.workflow.misc import is_csweb, urljoin
from cs.workflow.web.create_from_template_app import MOUNT_FROM_TEMPLATE
from cs.workflow.web.main import MOUNT


def _cdbwf_ahwf_new_from_template(cls, ctx):
    """
    Performs the mandatory checks e.g. if the template is provided or not.
    Starts the process for the workflow.
    """
    # use event handler instead of event map to handle multiselect only once

    # cs.web: Select template using dedicated app and open info page
    if is_csweb():
        ctx.url(_get_create_workflow_from_template_url(cls, ctx))

    # cdbpc: Legacy template selection mechanism
    else:
        template_id = None
        ahwf_content = cls.PersistentObjectsFromContext(ctx)
        from cs.workflow.processes import Process
        for content in ahwf_content:
            if isinstance(content, Process):
                template_id = content.cdb_process_id
                ahwf_content.remove(content)

        if template_id is None:
            if not ctx.catalog_selection:
                ctx.start_selection(catalog_name="cdbwf_process_templ")
            else:
                template_id = ctx.catalog_selection[0]["cdb_process_id"]
                cdbwf_ahwf_new_from_template(
                    template_id,
                    [content.cdb_object_id for content in ahwf_content],
                    ctx
                )
        else:
            cdbwf_ahwf_new_from_template(
                template_id,
                [content.cdb_object_id for content in ahwf_content],
                ctx
            )


def cdbwf_ahwf_new_from_template(template_id, ahwf_content, ctx=None):
    if not template_id:
        raise util.ErrorMessage("cdbwf_no_template_selected")

    from cs.workflow.processes import Process
    Process.CreateFromTemplate(
        template_id,
        None,
        ahwf_content,
        ctx
    )


def _get_create_workflow_from_template_url(cls, ctx):
    if ctx.relationship_name:
        rs = relships.Relship.ByKeys(ctx.relationship_name)
        classname = rs.referer
        cdef = entities.CDBClassDef(classname)
        o = support._RestKeyObj(cdef, ctx.parent)
        rest_key = support.rest_key(o)
    else:
        classname = cls._getClassname()
        rest_key = ""
    params = {
    "classname": json.dumps(classname),
    "rest_key": json.dumps(rest_key),
    "ahwf_content": _get_ahwf_content_json(cls, ctx),
    }
    query_string = urlencode(sorted(params.items()))
    return urljoin(
        MOUNT,
        "{}?{}".format(
            MOUNT_FROM_TEMPLATE,query_string
        )
    )


def _get_ahwf_content_json(cls, ctx):
    ahwf_content = [
        x.cdb_object_id
        for x in cls.PersistentObjectsFromContext(ctx)
    ]
    return json.dumps(ahwf_content)


@lru_cache()
def content_in_whitelist(object_id, fail_on_false=True):
    """lru_cache is used as this function is called in multiple places with same arguments"""
    from cs.workflow.briefcases import BriefcaseContentWhitelist
    content = ByID(object_id)
    whitelisted = BriefcaseContentWhitelist.Classnames()
    if whitelisted and (content.GetClassname() not in whitelisted):
        whitelist_classes = ', '.join([
            CDBClassDef(classname).getTitle()
            for classname in whitelisted
        ])
        logging.exception(
            util.CDBMsg(util.CDBMsg.kInfo, "cdbwf_briefcase_not_whitelisted"),
            content.GetClassDef().getTitle(),
            whitelist_classes
        )
        if fail_on_false:
            raise ue.Exception(
                "cdbwf_briefcase_not_whitelisted",
                content.GetClassDef().getTitle(),
                whitelist_classes
            )
        else:
            return False
    return True
