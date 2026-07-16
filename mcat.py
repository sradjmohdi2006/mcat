import os
import sys
from PyQt5.QtWidgets import QApplication
from cat_tool.ui import MainWindow


def main():
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()

    if len(sys.argv) > 1:
        file_path = sys.argv[1]
        if os.path.exists(file_path):
            win.open_file_path(file_path)

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
