#!/usr/bin/env python

import sys

from PySide6.QtWidgets import QApplication

from config import APP_NAME, APP_VERSION
from tufac_gui import TuFacWindow


def main():
    app = QApplication(sys.argv)

    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)

    window = TuFacWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
