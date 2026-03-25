from webob.exc import HTTPNotFound
from cdb.platform.mom.entities import CDBClassDef
from cdb import ElementsError
from cs.platform.web import uisupport
from cs.web.components.outlet_config import _replace_outlet, _add_lib
from cs.web.components.configurable_ui import ConfigurableUIModel, handle_configuration
from cs.web.components.base.main import SettingDict
from cs.platform.web import root, JsonAPI


# We need this App because setup functions might call "request.app.include()"
# to register libraries that must be loaded.
class OutletApp(JsonAPI):
    def __init__(self):
        self._libraries = []

    def include(self, libname, libver):
        self._libraries.append((libname, libver))


@uisupport.App.mount(path="outlet", app=OutletApp)
def mount_app():
    return OutletApp()


class OutletConfig(ConfigurableUIModel):
    """
    Class that can be used to retrieve the outlet configuration based on an outlet name, a class
    name and, if given, the keys of an object.
    """
    def __init__(self, outlet_name, class_name, keys):
        super(OutletConfig, self).__init__()
        self.outlet_name = outlet_name
        self.keys = keys
        try:
            self.classdef = CDBClassDef(class_name)
        except ElementsError:
            raise HTTPNotFound("The outlet configuration cannot be retrieved. The passed class name does not exist.")

    def to_json(self, request):
        result = SettingDict()
        _replace_outlet(self, result, self.outlet_name, self.keys)
        if result.get("needs_object") and self.keys is None:
            raise HTTPNotFound("The outlet configuration cannot be retrieved. No object keys were passed.")
        libs = handle_configuration(self, request, result)
        for library_name, library_version in request.app._libraries + libs:
            _add_lib(result["libraries"], library_name, library_version)
        return result


@OutletApp.path(path="{outlet_name}/{class_name}", model=OutletConfig, absorb=True)
def _path_outlets(outlet_name, class_name, absorb):
    return OutletConfig(outlet_name, class_name, absorb if absorb else None)


@OutletApp.json(model=OutletConfig)
def _view_outlets(self, request):
    return self.to_json(request)
