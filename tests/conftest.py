import pytest
from unittest.mock import MagicMock
from game.systems import sound

@pytest.fixture(autouse=True)
def mock_sound_manager_for_all_tests(monkeypatch):
    """
    Prevent the actual sound manager from initializing its physical SDL/mixer
    backend during tests to avoid hardware audio popping and frequency reset spam.
    """
    mock_manager = MagicMock()
    # Provide dummy methods for common calls if necessary, but MagicMock
    # handles most arbitrary method calls gracefully.
    mock_manager.enabled = True
    monkeypatch.setattr(sound, "get_sound_manager", lambda: mock_manager)
