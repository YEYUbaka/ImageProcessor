import os
import sys
from PyQt6.QtWidgets import QApplication, QLabel

# 获取虚拟环境根目录
venv_root = os.path.dirname(os.path.dirname(sys.executable))
print("Virtual environment root:", venv_root)

# 构造插件路径（PyQt6 的结构与 PyQt5 类似）
qt_plugins_path = os.path.join(
    venv_root,
    'Lib', 'site-packages', 'PyQt6', 'Qt6', 'plugins', 'platforms'
)
print("QT_PLUGIN_PATH:", qt_plugins_path)

# 设置环境变量
os.environ['QT_PLUGIN_PATH'] = qt_plugins_path

app = QApplication(sys.argv)
label = QLabel("Hello, Qt!")
label.show()
sys.exit(app.exec())
