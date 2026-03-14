import os
import PyQt6

qt_bin = os.path.join(os.path.dirname(PyQt6.__file__), "Qt6", "bin")
os.add_dll_directory(qt_bin)

from PyQt6.QtWidgets import QApplication, QWidget
print("PyQt6 OK")
