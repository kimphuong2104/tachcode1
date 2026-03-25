from cs.workplan.rest.main import App
from cs.workplan.rest.model import WorkplanVisualization


@App.json(model=WorkplanVisualization, request_method="GET")
def default_view(model, request):
    return {
        # "root_object_id": model.wor
        # "root_desc": model.root.GetDescription(),
        # "radius": model.radius,
        "svg": model.get_visualization()
    }
