from cs.workplan import Workplan


class WorkplanVisualization(object):
    def __init__(self, workplan_id, workplan_index):
        if workplan_index == "None":
            workplan_index = ""
        query = Workplan.KeywordQuery(
            workplan_id=workplan_id, workplan_index=workplan_index
        )

        self.workplan = query[0] if query else None
        self.svg = self.workplan.cswp_workplan_visualization_render()

    def get_visualization(self):
        return self.svg
