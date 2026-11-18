from config import RunnerData
from dual_main import LaneAssigner


def runner(tid, x, confidence=.9):
    return RunnerData(tid, x, 90, (x-5,0,x+5,100), confidence)


def test_confident_runner_does_not_steal_neighbours_lane():
    lanes = LaneAssigner(3, 101, False, 0, 100)
    lanes.assign([runner(1,20),runner(2,50),runner(3,80)])
    assigned = lanes.assign([runner(1,45,.99),runner(2,51,.8),runner(3,75,.7)])
    assert [r.ankle_mid_x for r in assigned] == [45,51,75]
    assert [r.track_id for r in assigned] == [1,2,3]


def test_partial_detections_keep_spatial_lane_identity():
    lanes = LaneAssigner(3, 101, False, 0, 100)
    lanes.assign([runner(1,20),runner(2,50),runner(3,80)])
    assigned = lanes.assign([runner(7,21),runner(8,79)])
    assert [r.track_id for r in assigned] == [1,3]
    assert lanes.assign([]) == []


def test_opposite_camera_reverses_lane_order():
    lanes = LaneAssigner(3, 101, True, 0, 100)
    assigned = lanes.assign([runner(9,20),runner(8,50),runner(7,80)])
    assert [r.ankle_mid_x for r in assigned] == [80,50,20]


def test_background_pose_cannot_steal_lane_identity():
    from dual_main import filter_line_candidates
    from line_geometry import PerspectiveLine
    line = PerspectiveLine.from_points([(0,600),(480,620)])
    nearby = RunnerData(1,200,590,(180,400,220,610),.85)
    background = RunnerData(9,60,330,(30,200,90,350),.99)
    assert filter_line_candidates([background,nearby],line,854) == [nearby]


def test_line_roi_moves_with_calibrated_geometry():
    from dual_main import filter_line_candidates
    from line_geometry import PerspectiveLine
    line = PerspectiveLine.from_points([(100,600),(400,620)])
    r = RunnerData(1,200,590,(180,400,220,610),.85)
    assert filter_line_candidates([r],line,854) == [r]
    assert filter_line_candidates([r],line.shifted(-250),854) == []
