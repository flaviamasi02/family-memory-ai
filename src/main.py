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
    os.environ.setdefault("QT_LOGGING_RULES", "qt.gui.imageio*=false")

    app = QApplication(sys.argv)

    # Belt-and-suspenders: also apply via the runtime API after QApplication is
    # created, in case the env var was already set to something else.
    QLoggingCategory.setFilterRules("qt.gui.imageio*=false\n")

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()