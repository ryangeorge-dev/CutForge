"""Review state transitions, independent of HTTP and UI."""
from .models import Cut, CutState, Project, ReviewRequest


def snapshot(project: Project):
    return {cut.id: CutState(decision=cut.decision, start=cut.start, end=cut.end, adjusted=cut.adjusted) for cut in project.cuts}


def review(project: Project, request: ReviewRequest) -> None:
    if request.action in {"undo", "redo"}:
        source, target = (project.history, project.future) if request.action == "undo" else (project.future, project.history)
        if not source:
            return
        target.append(snapshot(project))
        state = source.pop()
        for cut in project.cuts:
            saved = state.get(cut.id, "pending")
            if isinstance(saved, CutState):
                cut.decision, cut.start, cut.end, cut.adjusted = saved.decision, saved.start, saved.end, saved.adjusted
            else:
                cut.decision = saved
        return
    before = snapshot(project)
    if request.action in {"accept", "reject", "adjust"}:
        cut = next((c for c in project.cuts if c.id == request.cut_id), None)
        if cut is None:
            raise ValueError("Unknown cut")
        if request.action == "adjust":
            if request.start is None or request.end is None or not 0 <= request.start < request.end <= project.metadata.duration_ticks:
                raise ValueError("Cut boundaries must satisfy 0 ≤ start < end ≤ source duration.")
            cut.start, cut.end = request.start, request.end
            cut.adjusted = True
        else:
            cut.decision = "accepted" if request.action == "accept" else "rejected"
    else:
        for cut in project.cuts:
            if request.action == "restore":
                cut.decision = "pending"
            elif cut.current or cut.decision != "pending" or cut.adjusted:
                cut.decision = "accepted" if request.action == "accept_all" else "rejected"
    if before != snapshot(project):
        project.history.append(before)
        project.future.clear()


def merge_analysis(project: Project, intervals: list[tuple[int, int]]) -> None:
    """Keep decisions and history even when changed parameters move boundaries."""
    by_id = {c.id: c for c in project.cuts}
    for cut in project.cuts:
        cut.current = False
    for start, end in intervals:
        identifier = f"{start}:{end}"
        if identifier in by_id:
            by_id[identifier].current = True
        else:
            project.cuts.append(Cut(id=identifier, start=start, end=end))
    project.cuts.sort(key=lambda cut: (cut.start, cut.end))
    project.analyzed = True
