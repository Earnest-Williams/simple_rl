import numpy as np
from tools.lighting_fov_tool.tool_window import _light_marker_is_visible_or_allowed

def test_light_marker_is_visible_or_allowed():
    visible = np.zeros((3, 3), dtype=bool)
    visible[1, 1] = True

    # Assert an emitter at (1, 1) returns True when show_full_field=False and show_hidden=False
    assert _light_marker_is_visible_or_allowed(1, 1, visible, False, False) == True

    # Assert an in-bounds non-visible emitter, for example (2, 2), returns False when both toggles are false
    assert _light_marker_is_visible_or_allowed(2, 2, visible, False, False) == False

    # Assert the same hidden emitter returns True when show_hidden=True
    assert _light_marker_is_visible_or_allowed(2, 2, visible, False, True) == True

    # Assert an out-of-bounds emitter, for example (99, 99) or (-1, 0), returns False when show_full_field=False and show_hidden=False
    assert _light_marker_is_visible_or_allowed(99, 99, visible, False, False) == False
    assert _light_marker_is_visible_or_allowed(-1, 0, visible, False, False) == False

    # Assert an out-of-bounds emitter returns True when show_full_field=True
    assert _light_marker_is_visible_or_allowed(99, 99, visible, True, False) == True
    assert _light_marker_is_visible_or_allowed(-1, 0, visible, True, False) == True
