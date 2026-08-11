# ------------------------------------------------------------------------------
# Copyright (c) 2026 Michael Gasche
#
# TuFac is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# TuFac is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with TuFac. If not, see <https://www.gnu.org/licenses/>.
# ------------------------------------------------------------------------------

# File:        autostart.py
# Author:      Michael Gasche
# Created:     2026-08
# Product:     TuFac
# Description: Auto-start at OS login (macOS LaunchAgent / Windows registry).


import os
import plistlib
import subprocess
import sys
from pathlib import Path

from config import APP_NAME, LAUNCH_AGENT_LABEL

LAUNCH_AGENTS_DIR = Path.home() / "Library" / "LaunchAgents"
LAUNCH_AGENT_PATH = LAUNCH_AGENTS_DIR / f"{LAUNCH_AGENT_LABEL}.plist"
WIN_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def _launch_command():
    if getattr(sys, "frozen", False):
        command = [os.path.abspath(sys.executable)]
    else:
        script = Path(__file__).resolve().parent / "tufac.py"
        command = [sys.executable, str(script)]

    command.append("--autostart")
    return command


def is_enabled():
    if sys.platform == "darwin":
        return LAUNCH_AGENT_PATH.exists()
    if sys.platform == "win32":
        import winreg

        try:
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER, WIN_RUN_KEY, 0, winreg.KEY_QUERY_VALUE
            ) as key:
                winreg.QueryValueEx(key, APP_NAME)
            return True
        except FileNotFoundError:
            return False
    return False


def enable():
    if sys.platform == "darwin":
        plist = {
            "Label": LAUNCH_AGENT_LABEL,
            "ProgramArguments": _launch_command(),
            "RunAtLoad": True,
        }
        LAUNCH_AGENTS_DIR.mkdir(parents=True, exist_ok=True)
        with open(LAUNCH_AGENT_PATH, "wb") as f:
            plistlib.dump(plist, f)

        """ Don't start it! It is running right now.
        subprocess.run(
            ["launchctl", "bootstrap", f"gui/{os.getuid()}", str(LAUNCH_AGENT_PATH)],
            check=False,
        )
        """
    elif sys.platform == "win32":
        import winreg

        command = f'"{os.path.abspath(sys.executable)}" --autostart'
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, WIN_RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, command)


def disable():
    if sys.platform == "darwin":
        subprocess.run(
            ["launchctl", "bootout", f"gui/{os.getuid()}/{LAUNCH_AGENT_LABEL}"],
            check=False,
        )
        LAUNCH_AGENT_PATH.unlink(missing_ok=True)
    elif sys.platform == "win32":
        import winreg

        try:
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER, WIN_RUN_KEY, 0, winreg.KEY_SET_VALUE
            ) as key:
                winreg.DeleteValue(key, APP_NAME)
        except FileNotFoundError:
            pass
