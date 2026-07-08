import sys
from PyQt5.QtWidgets import QApplication
from cat_tool.ui import MainWindow

def main():
    app = QApplication(sys.argv)
    
    # We can add custom app styling details here if needed
    win = MainWindow()
    win.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
