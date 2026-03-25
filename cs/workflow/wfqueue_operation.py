from cdb import ue
from cdb import sqlapi
from cdb import util


class SystemTaskJobOperation(object):
    def impl(self, ctx):
        if not hasattr(ctx, "object") or not ctx.object:
            return
        if ctx.object.cdbmq_state == "F":
            target_status = 'W'
            update_query = """mq_wfqueue set
                cdbmq_state='{}'
                where cdbmq_id='{}'""".format(
                    target_status, ctx.object.cdbmq_id
                    )
            sqlapi.SQLupdate(update_query)
            ctx.refresh_tables(['mq_wfqueue'])
        else:
            raise util.ErrorMessage("mq_wfqueue_cannot_restart")


if __name__ == "__main__":
    ue.run(SystemTaskJobOperation)
