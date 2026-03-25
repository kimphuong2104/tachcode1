from cs.workplan.rest.main import App
from cs.workplan.rest.model import WorkplanVisualization


@App.path(
    path="visualization/{workplan_id}/{workplan_index}", model=WorkplanVisualization
)
def get_visualization_model(app, workplan_id, workplan_index):
    return WorkplanVisualization(workplan_id, workplan_index)
