import os
import sys

from PySide6.QtCore import QLoggingCategory
from PySide6.QtWidgets import QApplication

from ui.main_window import MainWindow


def main():
    # Suppress Qt's internal image-codec warnings (e.g. "Invalid SOS parameters
    # for sequential JPEG").  These messages come from Qt's C++ libjpeg/libpng
    # layer and cannot be caught as Python exceptions.  The application already
    # handles decode failures gracefully via _decode_failed_paths; the raw Qt
    # codec noise is not actionable for end-users.
    #
    # QT_LOGGING_RULES must be set before QApplication is created so that the
    # filter is in effect during Qt library initialisation.  The wildcard suffix
    # (*) is required: "qt.gui.imageio" only disables the exact category; the
    # actual JPEG messages are emitted under the sub-category
    # "qt.gui.imageio.jpeg", which needs the wildcard to be covered.
    #
    # We always append our rule rather than overwriting any existing user config,
    # so that legitimate debug rules set by the user remain active.
    _existing = os.environ.get("QT_LOGGING_RULES", "")
    _jpeg_rule = "qt.gui.imageio*=false"
    if _jpeg_rule not in _existing:
        os.environ["QT_LOGGING_RULES"] = (_existing.rstrip("\n") + "\n" + _jpeg_rule).lstrip("\n")

    app = QApplication(sys.argv)

    # Belt-and-suspenders: also apply via the runtime API after QApplication is
    # created, in case the env var was already set to something else or the
    # platform ignored the env var during initialisation.
    QLoggingCategory.setFilterRules(_jpeg_rule + "\n")

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()