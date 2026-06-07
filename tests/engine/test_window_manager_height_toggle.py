from __future__ import annotations

from types import SimpleNamespace

from engine.window_manager import WindowManager


def test_height_visualization_toggle_updates_main_loop_and_redraw_state() -> None:
    redraws: list[str] = []

    def invalidate_render_cache() -> None:
        redraws.append("invalidated")

    def update_frame() -> None:
        redraws.append("redrawn")

    fake_window = SimpleNamespace(
        main_loop=SimpleNamespace(
            show_height_visualization=False,
            invalidate_render_cache=invalidate_render_cache,
        ),
        _cached_frame=object(),
        _frame_dirty=False,
        update_frame=update_frame,
    )

    WindowManager.ui_toggle_height_visualization(fake_window)

    assert fake_window.main_loop.show_height_visualization is True
    assert fake_window._cached_frame is None
    assert fake_window._frame_dirty is True
    assert redraws == ["invalidated", "redrawn"]
