from __future__ import annotations

import subprocess
import sys
from pathlib import Path


import io
from unittest.mock import patch

from tools.play_game import main


def test_first_playable_launcher_output() -> None:
    test_args = ["play_game.py", "--first-playable", "--mode", "cli"]
    
    # We must mock `input` so the CLI loop doesn't hang, or we can mock `run_cli_mode` to just return.
    # It's cleaner to mock run_cli_mode and run_gui_mode since we just want to verify the launcher sets up args.
    with patch("sys.argv", test_args):
        with patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
            with patch("tools.play_game.run_cli_mode") as mock_run_cli:
                main()
                mock_run_cli.assert_called_once()
                # seed defaults to 20260604 when --first-playable is given without --seed
                mock_run_cli.assert_called_with(None, 20260604)
                
    output = mock_stdout.getvalue()
    assert "First playable expedition mode: starting at ruined harbor." in output


def test_first_playable_gui_default() -> None:
    test_args = ["play_game.py", "--first-playable"]
    with patch("sys.argv", test_args):
        with patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
            with patch("tools.play_game.run_gui_mode") as mock_run_gui:
                main()
                mock_run_gui.assert_called_once()
                mock_run_gui.assert_called_with(None, 20260604)

