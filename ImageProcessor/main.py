# main.py

import sys
import os
import platform
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon
from ui.main_window import MainWindow

def main():
    app = QApplication(sys.argv)
    
    # 设置应用程序图标
    icon_path = os.path.join(os.path.dirname(__file__), "icons", "icon.png")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))
    
    # 在Windows上尝试设置标题栏颜色（Windows 10/11）
    if platform.system() == "Windows":
        try:
            # 使用Windows API设置标题栏颜色
            app.setAttribute(Qt.ApplicationAttribute.AA_EnableHighDpiScaling, True)
        except:
            pass
    
    win = MainWindow()
    win.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
