import sys

from PySide6.QtCore import QLoggingCategory
from PySide6.QtWidgets import QApplication

from ui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)

    # Suppress Qt's internal image-codec warnings (e.g. "Invalid SOS parameters
    # for sequential JPEG").  These messages come from Qt's C++ libjpeg/libpng
    # layer and cannot be caught as Python exceptions.  The application already
    # handles decode failures gracefully via _decode_failed_paths; the raw Qt
    # codec noise is not actionable for end-users.
    QLoggingCategory.setFilterRules("qt.gui.imageio=false\n")

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()