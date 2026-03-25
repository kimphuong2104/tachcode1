import os
import traceback

from cdb import misc, ue
from cdb.objects import IconCache
from cdb.util import get_label

from cs.pcs.projects.chart import ChartConfig
from cs.pcs.timeschedule import ColumnDefinition


class BaseHelper:
    @staticmethod
    def get_chart_columns(persno, chart_oid):
        columns_instances = ColumnDefinition.KeywordQuery(
            chart="timeschedule", order_by="position"
        )
        chart_configurations = ChartConfig.KeywordQuery(
            persno=persno, chart_oid=chart_oid
        )
        chart_config = {
            (config.attr, config.attr_type): config for config in chart_configurations
        }
        columns = [
            BaseHelper.get_complete_column_config(col_inst, chart_config)
            for col_inst in columns_instances
        ]
        columns.sort(key=lambda x: x["position"])
        return columns

    @staticmethod
    def get_column_config(col_inst, persno, schedule_id):
        visible = ChartConfig.getValue(persno, schedule_id, col_inst.name, "visible")
        visible = int(visible) if visible else col_inst.visible
        position = ChartConfig.getValue(persno, schedule_id, col_inst.name, "position")
        position = int(position) if position else col_inst.position
        width = ChartConfig.getValue(persno, schedule_id, col_inst.name, "width")
        width = width if width else col_inst.width
        label = get_label(col_inst.label) if col_inst.label else ""
        icon = IconCache.getIcon(col_inst.icon_id) if col_inst.icon_id else ""
        return {
            "name": col_inst.name,
            "position": position,
            "visible": visible != 0,
            "moveable": col_inst.moveable != 0,
            "always_visible": col_inst.always_visible != 0,
            "format": col_inst.Format.name if col_inst.Format else None,
            "title": label,
            "width": int(width),
            "icon": icon,
        }

    @staticmethod
    def get_complete_column_config(col_inst, chart_config):
        visible = BaseHelper.getValueFromChartConfig(
            col_inst.name, "visible", chart_config
        )
        visible = int(visible) if visible else col_inst.visible
        position = BaseHelper.getValueFromChartConfig(
            col_inst.name, "position", chart_config
        )
        position = int(position) if position else col_inst.position
        width = BaseHelper.getValueFromChartConfig(col_inst.name, "width", chart_config)
        width = width if width else col_inst.width
        label = get_label(col_inst.label) if col_inst.label else ""
        icon = IconCache.getIcon(col_inst.icon_id) if col_inst.icon_id else ""
        return {
            "name": col_inst.name,
            "position": position,
            "visible": visible != 0,
            "moveable": col_inst.moveable != 0,
            "always_visible": col_inst.always_visible != 0,
            "format": col_inst.Format.name if col_inst.Format else None,
            "title": label,
            "width": int(width),
            "icon": icon,
        }

    @staticmethod
    def getValueFromChartConfig(attr_type, attr, chart_config):
        if (attr, attr_type) in chart_config:
            config = chart_config.get((attr, attr_type))
            return config.value
        return None

    @staticmethod
    def exception_decorator(func):
        def func_wrapper(**kwargs):
            try:
                return func(**kwargs)
            except Exception as e:
                error = None
                if "exception_id" in kwargs:
                    error = str(ue.Exception(kwargs["exception_id"]))
                error = str(e)
                misc.cdblogv(misc.kLogErr, 0, str(traceback.format_exc()))
                return {"error": error}

        return func_wrapper

    @staticmethod
    def mute_exception_decorator(func):
        def func_wrapper(**kwargs):
            try:
                return func(**kwargs)
            except Exception:
                return None

        return func_wrapper

    @staticmethod
    def get_custom_templates(entry_point_path):
        def parse_hbs(name):
            name_arr = name.split(".")
            return [".".join(name_arr[:-1])] if name_arr[-1] == "hbs" else []

        def parse_dir(path):
            dirname = os.path.basename(path)
            dir_templates = []
            for file in os.listdir(path):
                if os.path.isfile(os.path.join(path, file)):
                    hbs = parse_hbs(file)
                    if hbs:
                        dir_templates.append(dirname + "/" + parse_hbs(file)[0])
            return dir_templates

        if os.path.isfile(entry_point_path):
            entry_point_path = os.path.dirname(entry_point_path)
        here_path = os.path.realpath(entry_point_path)
        if not here_path.endswith(os.sep):
            here_path = os.path.join(here_path, "")
        custom_path = os.path.join(
            os.path.dirname(here_path), "resources", "custom_hbs"
        )
        custom_templates = []
        for name in os.listdir(custom_path):
            full_path = os.path.join(custom_path, name)
            if os.path.isfile(full_path):
                custom_templates.extend(parse_hbs(name))
            elif os.path.isdir(full_path):
                custom_templates.extend(parse_dir(full_path))
        return custom_templates
