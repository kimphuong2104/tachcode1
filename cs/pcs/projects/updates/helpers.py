# pylint: disable=consider-using-f-string

from cdb import ddl, sqlapi, util
from cdb.comparch import protocol
from cdb.objects import NULL


def get_sortable_id(table_name, target_col, source_col):
    """
    Returns SQL expression to initialize `target_col` from column
    `source_col` in table `table_name`.

    The old values are prepended with ``0`` chars so they stay sortable.
    """
    dbms = sqlapi.SQLdbms()
    target_length = util.tables[table_name].column(target_col).length()

    if dbms == sqlapi.DBMS_MSSQL:
        return "RIGHT(REPLICATE('0', %d) + LTRIM(%s), %d) " % (
            target_length,
            source_col,
            target_length,
        )
    elif dbms == sqlapi.DBMS_POSTGRES:
        return "LPAD(CAST(%s AS text), %d, '0')" % (source_col, target_length)
    else:
        pre = "0" * target_length
        return "substr('%s' || %s, %d, %d)" % (
            pre,
            source_col,
            -target_length,
            target_length,
        )


def initialize_sortable_id(table_name, blocksize=5000):
    empty_cond = "(%s is NULL or %s = '')" % (
        "cdbprot_sortable_id",
        "cdbprot_sortable_id",
    )
    sql = """SELECT MAX(cdbprot_zaehler) AS maxi,
             MIN(cdbprot_zaehler) AS mini
             FROM %s where %s
          """ % (
        table_name,
        empty_cond,
    )
    entries = sqlapi.RecordSet2(sql=sql)[0]
    max_val = entries.maxi
    min_val = entries.mini
    if max_val == NULL:
        protocol.logMessage("Done! Did not find any uninitialized row")
        return

    if max_val > 9999999999:
        protocol.logWarning(
            "Cannot initialize %s.cdbprot_sortable_id. "
            "Entry IDs with more than 10 digits exist, so we cannot "
            "guarantee sortability. "
            "Please migrate manually (takes some time)." % table_name
        )
        return

    # First we initialize the new key
    new_value = get_sortable_id(table_name, "cdbprot_sortable_id", "cdbprot_zaehler")

    statement = """%s SET cdbprot_sortable_id=%s
                    WHERE cdbprot_zaehler BETWEEN %%d AND %%d
                    AND %s
                """ % (
        table_name,
        new_value,
        empty_cond,
    )

    while max_val >= min_val:
        block_min = max(max_val - (blocksize - 1), min_val)
        sqlapi.SQLupdate(statement % (block_min, max_val))
        max_val -= blocksize

    # Try to change the PK
    t = ddl.Table(table_name)
    t.setPrimaryKey(ddl.PrimaryKey("cdbprot_sortable_id"))
    t.dropAttributes("cdbprot_zaehler")
