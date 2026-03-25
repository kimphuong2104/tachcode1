def _get_error_msg(label, *errp):
    from cdb import misc, util

    msg = util.CDBMsg(util.CDBMsg.kFatal, label)
    for repl in errp:
        msg.addReplacement(repl)
    return misc.unescape_string(str(msg))


def show_error_msg(hook, error_msg, *params):
    from cdb import ue

    if hook:
        hook.set_error("", _get_error_msg(error_msg, *params))
    else:
        raise ue.Exception(error_msg, *params)
