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

# File:        config.py
# Author:      Michael Gasche
# Created:     2026-08
# Product:     TuFac
# Description: Application metadata constants.


APP_NAME = "TuFac"
APP_VERSION = "1.2.0"
APP_COPYRIGHT = "© 2026 Michael Gasche"
GITHUB_LINK = "github.com/mikegasche"

# Start as a menu bar / system tray app instead of a regular windowed app.
# Closing the window then only hides it; quit via the tray icon menu.
TRAY_MODE = True

# LaunchAgent label used for macOS auto-start.
LAUNCH_AGENT_LABEL = "ch.autumo.tufac"
