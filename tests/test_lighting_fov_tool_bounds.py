import numpy as np

from tools.lighting_fov_tool.tool_window import _light_marker_is_visible_or_allowed

def test_light_marker_is_visible_or_allowed():
    visible = np.zeros((10, 10), dtype=bool)
    visible[5, 5] = True
    
    # In-bounds visible emitter draws
    assert _light_marker_is_visible_or_allowed(5, 5, visible, False, False) == True
    
    # In-bounds hidden emitter is hidden when both toggles are false
    assert _light_marker_is_visible_or_allowed(2, 2, visible, False, False) == False
    
    # Out-of-bounds emitter does not raise and is hidden (or handled safely)
    assert _light_marker_is_visible_or_allowed(-1, -1, visible, False, False) == False
    assert _light_marker_is_visible_or_allowed(10, 10, visible, False, False) == False
    
    # Full-light-field mode allows the marker even when not visible
    assert _light_marker_is_visible_or_allowed(2, 2, visible, True, False) == True
    
    # Show hidden allows the marker even when not visible
    assert _light_marker_is_visible_or_allowed(2, 2, visible, False, True) == True
    
    # Out of bounds but show_full_field is true
    assert _light_marker_is_visible_or_allowed(-1, -1, visible, True, False) == True
