import numpy as np
from tools.lighting_fov_tool.tool_window import _light_marker_is_visible_or_allowed


def test_light_marker_is_visible_or_allowed():
    visible = np.zeros((10, 10), dtype=bool)
    visible[5, 5] = True

    assert _light_marker_is_visible_or_allowed(5, 5, visible, False, False)
    assert not _light_marker_is_visible_or_allowed(2, 2, visible, False, False)
    assert not _light_marker_is_visible_or_allowed(-1, -1, visible, False, False)
    assert not _light_marker_is_visible_or_allowed(10, 10, visible, False, False)
    assert _light_marker_is_visible_or_allowed(2, 2, visible, True, False)
    assert _light_marker_is_visible_or_allowed(2, 2, visible, False, True)
    assert _light_marker_is_visible_or_allowed(-1, -1, visible, True, False)
