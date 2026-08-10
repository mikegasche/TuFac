#!/usr/bin/env python

import json
import os
import sys
from pathlib import Path


APP_NAME = "TuFac"


def get_data_dir():
    if sys.platform == "darwin":
        return (
            Path.home()
            / "Library"
            / "Application Support"
            / APP_NAME
        )

    if sys.platform == "win32":
        app_data = os.environ.get("APPDATA")

        if app_data:
            return Path(app_data) / APP_NAME

        return (
            Path.home()
            / "AppData"
            / "Roaming"
            / APP_NAME
        )

    xdg_config = os.environ.get("XDG_CONFIG_HOME")

    if xdg_config:
        return Path(xdg_config) / APP_NAME

    return Path.home() / ".config" / APP_NAME


class TuFacStorage:

    def __init__(self):
        self.data_dir = get_data_dir()
        self.data_file = self.data_dir / "tufac.json"

    def load(self):
        if not self.data_file.exists():
            return {"groups": []}

        try:
            with self.data_file.open(
                "r",
                encoding="utf-8"
            ) as file:
                data = json.load(file)

        except (OSError, json.JSONDecodeError):
            return {"groups": []}

        if not isinstance(data, dict):
            return {"groups": []}

        if not isinstance(data.get("groups"), list):
            data["groups"] = []

        return data

    def save(self, data):
        self.data_dir.mkdir(
            parents=True,
            exist_ok=True
        )

        temporary_file = self.data_file.with_suffix(
            ".json.tmp"
        )

        with temporary_file.open(
            "w",
            encoding="utf-8"
        ) as file:
            json.dump(
                data,
                file,
                indent=2,
                ensure_ascii=False
            )
            file.write("\n")

        temporary_file.replace(self.data_file)
