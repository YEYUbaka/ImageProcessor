# ui/main_window.py

import os
import glob
from io import BytesIO
from PIL import Image
from PyQt6.QtWidgets import (
    QMainWindow, QToolButton, QPushButton, QLabel, QFileDialog,
    QScrollArea, QVBoxLayout, QWidget, QHBoxLayout, QSizePolicy,
    QGroupBox, QSlider, QSpinBox, QLineEdit, QComboBox, QMessageBox, QStyle, QRadioButton, QFontDialog,
    QDialog, QDialogButtonBox, QCheckBox, QProgressDialog
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSize, QRect, QPoint, QSettings, QPointF, QTimer, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QPixmap, QImage, QAction, QIcon, QPainter, QPen, QColor, QBrush, QPalette, QCursor, QKeySequence, QShortcut, QWheelEvent, QTransform
from PyQt6.QtWidgets import QApplication
from typing import Optional
import platform

from image_tools import ImageTools


# ------------------ 工具函数 ------------------
def get_icon_url(icon_filename: str, debug: bool = False) -> str:
    """获取图标的 URL，用于 QSS
    
    根据文件名生成适用于 QSS 的 file:// URL
    路径基于项目根目录下的 icons/ 文件夹
    
    Args:
        icon_filename: 图标文件名（如 "up.png"）
        debug: 是否输出调试信息，默认 False
    
    Returns:
        图标的 file:// URL，如果文件不存在则返回空字符串
    """
    import urllib.parse
    
    # 获取 icons 目录绝对路径（与 load_qss 逻辑完全一致）
    ui_dir = os.path.dirname(os.path.abspath(__file__))
    icons_dir = os.path.join(os.path.dirname(ui_dir), "icons")
    icon_path = os.path.join(icons_dir, icon_filename)
    
    if debug:
        print(f"[调试 get_icon_url] 查找图标: {icon_filename}")
        print(f"[调试 get_icon_url] 图标目录: {icons_dir}")
        print(f"[调试 get_icon_url] 图标完整路径: {icon_path}")
        print(f"[调试 get_icon_url] 文件是否存在: {os.path.exists(icon_path)}")
    
    if not os.path.exists(icon_path):
        if debug:
            print(f"[调试 get_icon_url] 文件不存在，返回空字符串")
        return ""  # 文件不存在，返回空
    
    # 使用绝对路径（Windows 使用正斜杠）
    abs_path = os.path.abspath(icon_path)
    abs_path_normalized = abs_path.replace("\\", "/")
    
    # Windows 路径处理：file:///F:/path/to/file
    if platform.system() == "Windows":
        # Windows 路径格式：F:/path/to/file
        # 需要转换为：file:///F:/path/to/file
        # 注意：Windows 路径中，驱动器字母后面有冒号，需要保留
        if ":" in abs_path_normalized:
            # 分离驱动器字母和路径部分
            drive_part = abs_path_normalized[:2]  # 例如 "F:"
            path_part = abs_path_normalized[2:]    # 例如 "/path/to/file"
            # 只对路径部分进行 URL 编码（保留驱动器字母和冒号）
            encoded_path_part = urllib.parse.quote(path_part, safe="/")
            url_encoded = f"file:///{drive_part}{encoded_path_part}"
        else:
            # 没有驱动器字母的情况（Unix 风格路径）
            encoded_path = urllib.parse.quote(abs_path_normalized, safe="/")
            url_encoded = f"file:///{encoded_path}"
    else:
        # Unix/Linux/Mac 路径处理
        encoded_path = urllib.parse.quote(abs_path_normalized, safe="/")
        url_encoded = f"file://{encoded_path}"
    
    if debug:
        print(f"[调试 get_icon_url] 标准化路径: {abs_path_normalized}")
        print(f"[调试 get_icon_url] URL 编码路径: {url_encoded}")
    
    return url_encoded


def get_icons_dir_url() -> str:
    """获取 icons 目录的 URL，用于 QSS 中的路径替换
    
    Returns:
        icons 目录的 file:// URL（不带文件名）
    """
    ui_dir = os.path.dirname(os.path.abspath(__file__))
    icons_dir = os.path.join(os.path.dirname(ui_dir), "icons")
    icons_dir_abs = os.path.abspath(icons_dir)
    
    # Windows路径需要转换为正斜杠（Qt QSS支持正斜杠路径）
    if platform.system() == "Windows":
        icons_dir_qss = icons_dir_abs.replace("\\", "/")
        # Windows上使用file:///协议（三个斜杠）
        icons_url = f"file:///{icons_dir_qss}"
    else:
        icons_url = f"file://{icons_dir_abs}"
    
    return icons_url


# ------------------ worker 线程 ------------------
class WorkerThread(QThread):
    finished_image = pyqtSignal(object)
    error = pyqtSignal(str)

    def __init__(self, func, *args, **kwargs):
        super().__init__()
        self.func = func
        self.args = args
        self.kwargs = kwargs

    def run(self):
        try:
            result = self.func(*self.args, **self.kwargs)
            self.finished_image.emit(result)
        except Exception as e:
            self.error.emit(str(e))


# ------------------ 自定义数字输入控件（替代 QSpinBox）------------------
class NumberInput(QWidget):
    """自定义数字输入控件，使用 + 和 - 按钮替代 QSpinBox 的箭头按钮"""
    
    valueChanged = pyqtSignal(int)  # 值改变信号
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._min_value = 0
        self._max_value = 100
        self._value = 0
        self._step = 1
        self._suffix = ""
        
        # 创建布局
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        
        # 创建 - 按钮
        self.dec_button = QPushButton("-")
        self.dec_button.setFixedWidth(30)
        self.dec_button.setFixedHeight(30)
        self.dec_button.clicked.connect(self._decrease)
        layout.addWidget(self.dec_button)
        
        # 创建输入框
        self.line_edit = QLineEdit()
        self.line_edit.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.line_edit.textChanged.connect(self._on_text_changed)
        self.line_edit.editingFinished.connect(self._on_editing_finished)
        layout.addWidget(self.line_edit, 1)  # 1 表示可伸缩
        
        # 创建 + 按钮
        self.inc_button = QPushButton("+")
        self.inc_button.setFixedWidth(30)
        self.inc_button.setFixedHeight(30)
        self.inc_button.clicked.connect(self._increase)
        layout.addWidget(self.inc_button)
        
        self.setLayout(layout)
        self._apply_theme_style()
        self._update_display()
    
    def _apply_theme_style(self):
        """应用主题样式"""
        # 检测当前主题（与 load_qss 逻辑保持一致）
        try:
            settings = QSettings("ImageTool", "Settings")
            theme = settings.value("theme", "auto", type=str)
            
            if theme == "auto":
                # 检测系统主题（与 load_qss 中的逻辑一致）
                app = QApplication.instance()
                if app:
                    palette = app.palette()
                    bg_color = palette.color(QPalette.ColorRole.Window)
                    is_dark = bg_color.lightness() < 128
                else:
                    # 如果没有应用程序实例，尝试从父窗口获取
                    parent = self.parent()
                    while parent and not hasattr(parent, 'palette'):
                        parent = parent.parent()
                    if parent:
                        palette = parent.palette()
                        bg_color = palette.color(QPalette.ColorRole.Window)
                        is_dark = bg_color.lightness() < 128
                    else:
                        is_dark = False
            elif theme == "dark":
                is_dark = True
            else:  # theme == "light"
                is_dark = False
        except:
            is_dark = False
        
        # 设置按钮样式
        if is_dark:
            button_bg = "#4a4a4a"
            button_border = "#555555"
            button_hover = "#5a5a5a"
            button_text = "#e0e0e0"
        else:
            button_bg = "#f0f0f0"
            button_border = "#cccccc"
            button_hover = "#e0e0e0"
            button_text = "#000000"
        
        button_style = f"""
        QPushButton {{
            background-color: {button_bg};
            border: 1px solid {button_border};
            border-radius: 4px;
            color: {button_text};
            font-weight: bold;
            font-size: 14px;
        }}
        QPushButton:hover {{
            background-color: {button_hover};
        }}
        QPushButton:pressed {{
            background-color: {button_border};
        }}
        QPushButton:disabled {{
            background-color: {button_bg};
            color: #888888;
        }}
        """
        
        self.dec_button.setStyleSheet(button_style)
        self.inc_button.setStyleSheet(button_style)
    
    def setRange(self, min_value: int, max_value: int):
        """设置数值范围"""
        self._min_value = min_value
        self._max_value = max_value
        self._clamp_value()
    
    def setValue(self, value: int):
        """设置当前值"""
        self._value = value
        self._clamp_value()
        self._update_display()
    
    def value(self) -> int:
        """获取当前值"""
        return self._value
    
    def setSuffix(self, suffix: str):
        """设置后缀（如 "°" 或 " px"）"""
        self._suffix = suffix
        self._update_display()
    
    def setStep(self, step: int):
        """设置步长"""
        self._step = step
    
    def setEnabled(self, enabled: bool):
        """启用/禁用控件"""
        super().setEnabled(enabled)
        self.dec_button.setEnabled(enabled)
        self.inc_button.setEnabled(enabled)
        self.line_edit.setEnabled(enabled)
    
    def _clamp_value(self):
        """将值限制在范围内"""
        self._value = max(self._min_value, min(self._max_value, self._value))
    
    def _update_display(self):
        """更新显示"""
        self.line_edit.setText(f"{self._value}{self._suffix}")
    
    def _decrease(self):
        """减少值"""
        self._value -= self._step
        self._clamp_value()
        self._update_display()
        self.valueChanged.emit(self._value)
    
    def _increase(self):
        """增加值"""
        self._value += self._step
        self._clamp_value()
        self._update_display()
        self.valueChanged.emit(self._value)
    
    def _on_text_changed(self, text: str):
        """文本改变时的处理（实时更新）"""
        # 移除后缀，提取数字
        text_clean = text.replace(self._suffix, "").strip()
        try:
            new_value = int(text_clean)
            if new_value != self._value:
                old_value = self._value
                self._value = new_value
                self._clamp_value()
                # 如果值被限制，更新显示（避免循环）
                if self._value != new_value:
                    # 使用 blockSignals 避免触发 textChanged 信号
                    self.line_edit.blockSignals(True)
                    self._update_display()
                    self.line_edit.blockSignals(False)
                # 只有值真正改变时才发出信号
                if self._value != old_value:
                    self.valueChanged.emit(self._value)
        except ValueError:
            # 如果输入不是数字，恢复显示
            self.line_edit.blockSignals(True)
            self._update_display()
            self.line_edit.blockSignals(False)
    
    def _on_editing_finished(self):
        """编辑完成时的处理"""
        # 确保显示正确的值
        self.line_edit.blockSignals(True)
        self._update_display()
        self.line_edit.blockSignals(False)


# ------------------ 预览标签（支持框选裁剪区域、缩放、拖动） ------------------
class CropLabel(QLabel):
    selection_finished = pyqtSignal(QRect)
    zoom_changed = pyqtSignal(float)  # 缩放比例改变信号
    watermark_position_selected = pyqtSignal(int, int)  # 水印位置选择完成信号 (x, y)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._selecting = False
        self._start_pos: Optional[QPoint] = None
        self._end_pos: Optional[QPoint] = None
        # 需要键盘焦点，用于 ESC 取消框选
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        
        # 预览缩放和偏移
        self._zoom_factor = 1.0  # 缩放比例（1.0 = 100%）
        self._offset_x = 0  # X偏移
        self._offset_y = 0  # Y偏移
        self._dragging = False  # 是否正在拖动
        self._drag_start_pos: Optional[QPoint] = None
        self._original_pixmap: Optional[QPixmap] = None  # 原始图片
        self._aspect_ratio: Optional[float] = None  # 预设比例（宽/高），None表示自由
        self._preview_rotate_angle: float = 0.0  # 预览旋转角度（度）
        
        # 水印位置选择模式
        self._watermark_mode = False  # 是否为水印位置选择模式
        self._watermark_pos: Optional[QPoint] = None  # 水印位置（图片坐标）
        self._watermark_size: Optional[QSize] = None  # 水印大小（用于预览框）
        # 水印预览信息
        self._watermark_text: str = ""  # 水印文本
        self._watermark_font_family: str = ""  # 水印字体
        self._watermark_font_size: int = 36  # 水印字体大小
        self._watermark_opacity: float = 0.7  # 水印透明度
        self._watermark_position: str = "bottom-right"  # 水印位置类型

    def mousePressEvent(self, event):
        if self.pixmap() is None:
            super().mousePressEvent(event)
            return
            
        if event.button() == Qt.MouseButton.LeftButton:
            if self._watermark_mode:
                # 水印位置选择模式：点击设置位置
                screen_pos = event.position().toPoint()
                img_pos = self.screen_to_image_coords(screen_pos)
                if img_pos is not None:
                    self._watermark_pos = img_pos
                    self.update()
            else:
                # 左键：裁剪选择
                self._selecting = True
                self._start_pos = event.position().toPoint()
                self._end_pos = self._start_pos
                self.update()
        elif event.button() == Qt.MouseButton.RightButton:
            # 右键：拖动预览区域
            self._dragging = True
            self._drag_start_pos = event.position().toPoint()
            self.setCursor(QCursor(Qt.CursorShape.ClosedHandCursor))
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._selecting:
            # 裁剪选择模式
            if self._aspect_ratio is not None and self._start_pos is not None:
                # 有预设比例，需要保持比例
                current_pos = event.position().toPoint()
                delta_x = current_pos.x() - self._start_pos.x()
                delta_y = current_pos.y() - self._start_pos.y()
                
                # 计算保持比例的尺寸
                # 根据鼠标移动的主要方向决定是调整宽度还是高度
                if abs(delta_x) > abs(delta_y):
                    # 主要水平移动，以宽度为准
                    new_width = abs(delta_x)
                    new_height = int(new_width / self._aspect_ratio)
                else:
                    # 主要垂直移动，以高度为准
                    new_height = abs(delta_y)
                    new_width = int(new_height * self._aspect_ratio)
                
                # 根据方向确定结束位置
                if delta_x >= 0:
                    end_x = self._start_pos.x() + new_width
                else:
                    end_x = self._start_pos.x() - new_width
                
                if delta_y >= 0:
                    end_y = self._start_pos.y() + new_height
                else:
                    end_y = self._start_pos.y() - new_height
                
                # 确保裁剪框在图片范围内
                label_rect = self.contentsRect()
                if self._original_pixmap:
                    # 使用实际的scaled_pixmap尺寸（与paintEvent和screen_to_image_coords保持一致）
                    scaled_width = int(self._original_pixmap.width() * self._zoom_factor)
                    scaled_height = int(self._original_pixmap.height() * self._zoom_factor)
                    scaled_pixmap = self._original_pixmap.scaled(
                        scaled_width, scaled_height,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation
                    )
                    img_x = (label_rect.width() - scaled_pixmap.width()) // 2 + self._offset_x
                    img_y = (label_rect.height() - scaled_pixmap.height()) // 2 + self._offset_y
                    img_right = img_x + scaled_pixmap.width()
                    img_bottom = img_y + scaled_pixmap.height()
                    
                    # 根据限制后的位置重新计算，保持比例
                    # 先计算符合比例的尺寸
                    actual_delta_x = end_x - self._start_pos.x()
                    actual_delta_y = end_y - self._start_pos.y()
                    
                    # 根据实际移动距离重新计算尺寸（保持比例）
                    if abs(actual_delta_x) > abs(actual_delta_y) * self._aspect_ratio:
                        # 以宽度为准
                        final_width = abs(actual_delta_x)
                        final_height = int(final_width / self._aspect_ratio)
                    else:
                        # 以高度为准
                        final_height = abs(actual_delta_y)
                        final_width = int(final_height * self._aspect_ratio)
                    
                    # 根据方向确定最终位置
                    if actual_delta_x >= 0:
                        end_x = self._start_pos.x() + final_width
                    else:
                        end_x = self._start_pos.x() - final_width
                    
                    if actual_delta_y >= 0:
                        end_y = self._start_pos.y() + final_height
                    else:
                        end_y = self._start_pos.y() - final_height
                    
                    # 限制在图片范围内（如果超出，调整位置而不是破坏比例）
                    if end_x < img_x:
                        end_x = img_x
                        # 重新计算以保持比例
                        if actual_delta_x >= 0:
                            final_width = end_x - self._start_pos.x()
                        else:
                            final_width = self._start_pos.x() - end_x
                        final_height = int(final_width / self._aspect_ratio)
                        if actual_delta_y >= 0:
                            end_y = self._start_pos.y() + final_height
                        else:
                            end_y = self._start_pos.y() - final_height
                    
                    if end_x > img_right:
                        end_x = img_right
                        # 重新计算以保持比例
                        if actual_delta_x >= 0:
                            final_width = end_x - self._start_pos.x()
                        else:
                            final_width = self._start_pos.x() - end_x
                        final_height = int(final_width / self._aspect_ratio)
                        if actual_delta_y >= 0:
                            end_y = self._start_pos.y() + final_height
                        else:
                            end_y = self._start_pos.y() - final_height
                    
                    if end_y < img_y:
                        end_y = img_y
                        # 重新计算以保持比例
                        if actual_delta_y >= 0:
                            final_height = end_y - self._start_pos.y()
                        else:
                            final_height = self._start_pos.y() - end_y
                        final_width = int(final_height * self._aspect_ratio)
                        if actual_delta_x >= 0:
                            end_x = self._start_pos.x() + final_width
                        else:
                            end_x = self._start_pos.x() - final_width
                    
                    if end_y > img_bottom:
                        end_y = img_bottom
                        # 重新计算以保持比例
                        if actual_delta_y >= 0:
                            final_height = end_y - self._start_pos.y()
                        else:
                            final_height = self._start_pos.y() - end_y
                        final_width = int(final_height * self._aspect_ratio)
                        if actual_delta_x >= 0:
                            end_x = self._start_pos.x() + final_width
                        else:
                            end_x = self._start_pos.x() - final_width
                    
                    # 最终限制（确保在图片范围内）
                    end_x = max(img_x, min(end_x, img_right))
                    end_y = max(img_y, min(end_y, img_bottom))
                
                self._end_pos = QPoint(end_x, end_y)
            else:
                # 自由模式
                self._end_pos = event.position().toPoint()
            self.update()
        elif self._dragging:
            # 拖动预览区域
            if self._drag_start_pos is not None:
                delta = event.position().toPoint() - self._drag_start_pos
                self._offset_x += delta.x()
                self._offset_y += delta.y()
                self._drag_start_pos = event.position().toPoint()
            self.update()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if self._watermark_mode and self._watermark_pos is not None:
                # 水印位置选择完成，发送信号
                self.watermark_position_selected.emit(self._watermark_pos.x(), self._watermark_pos.y())
            elif self._selecting:
                self._selecting = False
                # 如果有预设比例，需要重新计算_end_pos以保持比例
                if self._aspect_ratio is not None and self._start_pos is not None:
                    # 在mouseMoveEvent中已经计算好了符合比例的_end_pos，这里不需要再更新
                    # 但如果鼠标释放时位置有变化，需要重新计算
                    current_pos = event.position().toPoint()
                    if self._end_pos != current_pos:
                        # 重新计算以保持比例（复用mouseMoveEvent的逻辑）
                        delta_x = current_pos.x() - self._start_pos.x()
                        delta_y = current_pos.y() - self._start_pos.y()
                    
                        # 根据鼠标移动的主要方向决定是调整宽度还是高度
                        if abs(delta_x) > abs(delta_y):
                            # 主要水平移动，以宽度为准
                            new_width = abs(delta_x)
                            new_height = int(new_width / self._aspect_ratio)
                        else:
                            # 主要垂直移动，以高度为准
                            new_height = abs(delta_y)
                            new_width = int(new_height * self._aspect_ratio)
                    
                    # 根据方向确定结束位置
                    if delta_x >= 0:
                        end_x = self._start_pos.x() + new_width
                    else:
                        end_x = self._start_pos.x() - new_width
                    
                    if delta_y >= 0:
                        end_y = self._start_pos.y() + new_height
                    else:
                        end_y = self._start_pos.y() - new_height
                    
                    # 确保裁剪框在图片范围内
                    label_rect = self.contentsRect()
                    if self._original_pixmap:
                        # 使用实际的scaled_pixmap尺寸（与paintEvent和screen_to_image_coords保持一致）
                        scaled_width = int(self._original_pixmap.width() * self._zoom_factor)
                        scaled_height = int(self._original_pixmap.height() * self._zoom_factor)
                        scaled_pixmap = self._original_pixmap.scaled(
                            scaled_width, scaled_height,
                            Qt.AspectRatioMode.KeepAspectRatio,
                            Qt.TransformationMode.SmoothTransformation
                        )
                        img_x = (label_rect.width() - scaled_pixmap.width()) // 2 + self._offset_x
                        img_y = (label_rect.height() - scaled_pixmap.height()) // 2 + self._offset_y
                        img_right = img_x + scaled_pixmap.width()
                        img_bottom = img_y + scaled_pixmap.height()
                        
                        # 限制结束位置在图片范围内
                        end_x = max(img_x, min(end_x, img_right))
                        end_y = max(img_y, min(end_y, img_bottom))
                        
                        # 根据限制后的位置重新计算，保持比例
                        actual_delta_x = end_x - self._start_pos.x()
                        actual_delta_y = end_y - self._start_pos.y()
                        
                        # 根据实际移动距离重新计算尺寸
                        if abs(actual_delta_x) > abs(actual_delta_y) * self._aspect_ratio:
                            # 以宽度为准
                            final_width = abs(actual_delta_x)
                            final_height = int(final_width / self._aspect_ratio)
                        else:
                            # 以高度为准
                            final_height = abs(actual_delta_y)
                            final_width = int(final_height * self._aspect_ratio)
                        
                        # 根据方向确定最终位置
                        if actual_delta_x >= 0:
                            end_x = self._start_pos.x() + final_width
                        else:
                            end_x = self._start_pos.x() - final_width
                        
                        if actual_delta_y >= 0:
                            end_y = self._start_pos.y() + final_height
                        else:
                            end_y = self._start_pos.y() - final_height
                        
                        # 再次限制在图片范围内
                        end_x = max(img_x, min(end_x, img_right))
                        end_y = max(img_y, min(end_y, img_bottom))
                        
                        self._end_pos = QPoint(end_x, end_y)
            else:
                # 自由模式，直接使用鼠标位置
                self._end_pos = event.position().toPoint()
            
            rect = self._current_rect()
            if rect is not None and rect.width() > 0 and rect.height() > 0:
                self.selection_finished.emit(rect)
            self.update()
        elif event.button() == Qt.MouseButton.RightButton and self._dragging:
            # 停止拖动
            self._dragging = False
            self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event):
        # 按 ESC 取消当前框选
        if event.key() == Qt.Key.Key_Escape:
            self.clear_selection()
            return
        super().keyPressEvent(event)

    def _current_rect(self) -> Optional[QRect]:
        """获取当前选择框（考虑缩放和偏移）"""
        if self._start_pos is None or self._end_pos is None:
            return None
        return QRect(self._start_pos, self._end_pos).normalized()
    
    def screen_to_image_coords(self, screen_pos: QPoint) -> Optional[QPoint]:
        """将屏幕坐标转换为图片坐标（考虑缩放和偏移）
        
        Args:
            screen_pos: 屏幕坐标（相对于label）
            
        Returns:
            图片坐标（相对于原始图片），如果转换失败返回None
        """
        if self._original_pixmap is None:
            return None
        
        label_rect = self.contentsRect()
        
        # 计算缩放后的图片尺寸
        scaled_width = int(self._original_pixmap.width() * self._zoom_factor)
        scaled_height = int(self._original_pixmap.height() * self._zoom_factor)
        
        # 创建缩放后的pixmap（与paintEvent保持一致，使用KeepAspectRatio）
        scaled_pixmap = self._original_pixmap.scaled(
            scaled_width, scaled_height,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
        
        # 计算图片在label中的实际绘制位置（与paintEvent中的计算保持一致）
        img_x = (label_rect.width() - scaled_pixmap.width()) // 2 + self._offset_x
        img_y = (label_rect.height() - scaled_pixmap.height()) // 2 + self._offset_y
        
        # 转换为相对于图片的坐标
        rel_x = screen_pos.x() - img_x
        rel_y = screen_pos.y() - img_y
        
        # 转换为原始图片坐标（即使超出范围也转换，然后进行边界限制）
        if scaled_pixmap.width() > 0 and scaled_pixmap.height() > 0:
            orig_x = (rel_x / scaled_pixmap.width()) * self._original_pixmap.width()
            orig_y = (rel_y / scaled_pixmap.height()) * self._original_pixmap.height()
            # 使用round()而不是int()以提高精度
            orig_x = round(orig_x)
            orig_y = round(orig_y)
            # 边界检查（限制在图片范围内）
            orig_x = max(0, min(orig_x, self._original_pixmap.width() - 1))
            orig_y = max(0, min(orig_y, self._original_pixmap.height() - 1))
            return QPoint(orig_x, orig_y)
        return None
    
    def screen_rect_to_image_rect(self, screen_rect: QRect) -> Optional[QRect]:
        """将屏幕矩形转换为图片矩形（考虑缩放和偏移）
        
        使用基于中心点和尺寸的转换方法，确保精度和比例
        
        Args:
            screen_rect: 屏幕矩形（相对于label）
            
        Returns:
            图片矩形（相对于原始图片），如果转换失败返回None
        """
        if self._original_pixmap is None:
            return None
        
        label_rect = self.contentsRect()
        
        # 计算缩放后的图片尺寸
        scaled_width = int(self._original_pixmap.width() * self._zoom_factor)
        scaled_height = int(self._original_pixmap.height() * self._zoom_factor)
        
        # 创建缩放后的pixmap（与paintEvent保持一致）
        scaled_pixmap = self._original_pixmap.scaled(
            scaled_width, scaled_height,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
        
        # 计算图片在label中的实际绘制位置（与paintEvent中的计算保持一致）
        img_x = (label_rect.width() - scaled_pixmap.width()) // 2 + self._offset_x
        img_y = (label_rect.height() - scaled_pixmap.height()) // 2 + self._offset_y
        
        # 计算屏幕矩形的中心点（相对于图片）
        screen_center_x = screen_rect.center().x() - img_x
        screen_center_y = screen_rect.center().y() - img_y
        screen_width = screen_rect.width()
        screen_height = screen_rect.height()
        
        # 检查中心点是否在图片范围内
        if (screen_center_x < 0 or screen_center_x > scaled_pixmap.width() or
            screen_center_y < 0 or screen_center_y > scaled_pixmap.height()):
            return None
        
        # 将屏幕尺寸转换为图片尺寸（考虑缩放）
        if scaled_pixmap.width() > 0 and scaled_pixmap.height() > 0:
            # 计算图片尺寸（使用浮点数提高精度）
            img_w = (screen_width / scaled_pixmap.width()) * self._original_pixmap.width()
            img_h = (screen_height / scaled_pixmap.height()) * self._original_pixmap.height()
            
            # 计算图片中心点
            img_center_x = (screen_center_x / scaled_pixmap.width()) * self._original_pixmap.width()
            img_center_y = (screen_center_y / scaled_pixmap.height()) * self._original_pixmap.height()
            
            # 如果有预设比例，调整尺寸以符合比例（保持中心点不变）
            if self._aspect_ratio is not None:
                current_ratio = img_w / img_h if img_h > 0 else 0
                if abs(current_ratio - self._aspect_ratio) > 0.001:  # 允许0.1%的误差
                    # 以较小的尺寸为准，保持比例
                    if img_w / img_h > self._aspect_ratio:
                        # 当前更宽，以高度为准
                        img_w = img_h * self._aspect_ratio
                    else:
                        # 当前更高，以宽度为准
                        img_h = img_w / self._aspect_ratio
            
            # 四舍五入尺寸
            img_w = round(img_w)
            img_h = round(img_h)
            
            # 确保尺寸有效
            if img_w <= 0 or img_h <= 0:
                return None
            
            # 基于中心点计算左上角
            img_left = round(img_center_x - img_w / 2)
            img_top = round(img_center_y - img_h / 2)
            
            # 边界检查和调整
            img_width = self._original_pixmap.width()
            img_height = self._original_pixmap.height()
            
            # 如果超出边界，调整位置（保持尺寸和比例）
            if img_left < 0:
                img_left = 0
            elif img_left + img_w > img_width:
                img_left = img_width - img_w
            
            if img_top < 0:
                img_top = 0
            elif img_top + img_h > img_height:
                img_top = img_height - img_h
            
            # 如果调整后仍然超出，缩小尺寸（保持比例）
            # 先检查并调整宽度
            if img_left < 0:
                img_left = 0
            if img_left + img_w > img_width:
                img_w = img_width - img_left
                if self._aspect_ratio is not None:
                    img_h = round(img_w / self._aspect_ratio)
            
            # 再检查并调整高度
            if img_top < 0:
                img_top = 0
            if img_top + img_h > img_height:
                img_h = img_height - img_top
                if self._aspect_ratio is not None:
                    img_w = round(img_h * self._aspect_ratio)
                    # 如果宽度调整后超出，再次调整
                    if img_left + img_w > img_width:
                        img_w = img_width - img_left
                        img_h = round(img_w / self._aspect_ratio)
            
            # 最终边界检查
            img_left = max(0, min(img_left, img_width - 1))
            img_top = max(0, min(img_top, img_height - 1))
            img_w = max(1, min(img_w, img_width - img_left))
            img_h = max(1, min(img_h, img_height - img_top))
            
            # 最终比例检查（如果有预设比例）
            if self._aspect_ratio is not None and img_h > 0:
                current_ratio = img_w / img_h
                if abs(current_ratio - self._aspect_ratio) > 0.01:  # 允许1%的误差
                    # 以较小的尺寸为准，重新计算
                    if current_ratio > self._aspect_ratio:
                        img_w = round(img_h * self._aspect_ratio)
                        if img_left + img_w > img_width:
                            img_w = img_width - img_left
                            img_h = round(img_w / self._aspect_ratio)
                    else:
                        img_h = round(img_w / self._aspect_ratio)
                        if img_top + img_h > img_height:
                            img_h = img_height - img_top
                            img_w = round(img_h * self._aspect_ratio)
            
            return QRect(img_left, img_top, img_w, img_h)
        
        return None

    def clear_selection(self):
        """清除当前选择状态"""
        self._selecting = False
        self._start_pos = None
        self._end_pos = None
        self.update()
    
    def set_aspect_ratio(self, ratio: Optional[float]):
        """设置预设比例（宽/高），None表示自由"""
        self._aspect_ratio = ratio
        # 如果当前有选择框，调整它以符合新比例
        if self._start_pos is not None and self._end_pos is not None and ratio is not None:
            current_rect = self._current_rect()
            if current_rect and not current_rect.isNull():
                # 以中心点为准，调整大小以符合比例
                center = current_rect.center()
                current_width = current_rect.width()
                current_height = current_rect.height()
                
                # 计算符合比例的新尺寸
                if current_width / current_height > ratio:
                    # 当前更宽，以宽度为准
                    new_width = current_width
                    new_height = int(new_width / ratio)
                else:
                    # 当前更高，以高度为准
                    new_height = current_height
                    new_width = int(new_height * ratio)
                
                # 以中心点重新计算位置
                half_w = new_width // 2
                half_h = new_height // 2
                self._start_pos = QPoint(center.x() - half_w, center.y() - half_h)
                self._end_pos = QPoint(center.x() + half_w, center.y() + half_h)
                self.update()

    def wheelEvent(self, event):
        """鼠标滚轮事件：缩放图片（以鼠标位置为中心，每次缩放10%）"""
        if self._original_pixmap is None:
            super().wheelEvent(event)
            return
        
        # 获取鼠标位置（相对于label）
        mouse_pos = event.position().toPoint()
        
        # 计算缩放因子（每次10%）
        old_zoom = self._zoom_factor
        zoom_step = 0.1  # 10%
        
        if event.angleDelta().y() > 0:
            # 向上滚动：放大10%
            new_zoom = old_zoom * (1.0 + zoom_step)
        else:
            # 向下滚动：缩小10%
            new_zoom = old_zoom * (1.0 - zoom_step)
        
        # 限制缩放范围（10% - 1000%）
        new_zoom = max(0.1, min(10.0, new_zoom))
        
        if abs(new_zoom - old_zoom) < 0.001:
            super().wheelEvent(event)
            return
        
        # 计算当前图片在label中的位置
        label_rect = self.contentsRect()
        scaled_width = int(self._original_pixmap.width() * old_zoom)
        scaled_height = int(self._original_pixmap.height() * old_zoom)
        
        # 图片左上角在label中的位置
        img_x = (label_rect.width() - scaled_width) // 2 + self._offset_x
        img_y = (label_rect.height() - scaled_height) // 2 + self._offset_y
        
        # 鼠标位置相对于图片的坐标（在缩放前的图片坐标系中）
        rel_x = mouse_pos.x() - img_x
        rel_y = mouse_pos.y() - img_y
        
        # 转换为原始图片坐标（0-1范围）
        if scaled_width > 0 and scaled_height > 0:
            img_ratio_x = rel_x / scaled_width
            img_ratio_y = rel_y / scaled_height
        else:
            img_ratio_x = 0.5
            img_ratio_y = 0.5
        
        # 应用新缩放
        self._zoom_factor = new_zoom
        
        # 计算新缩放后的图片尺寸
        new_scaled_width = int(self._original_pixmap.width() * new_zoom)
        new_scaled_height = int(self._original_pixmap.height() * new_zoom)
        
        # 计算新的图片位置，使鼠标位置对应的图片点保持不变
        new_img_x = mouse_pos.x() - (img_ratio_x * new_scaled_width)
        new_img_y = mouse_pos.y() - (img_ratio_y * new_scaled_height)
        
        # 计算新的偏移量
        center_x = label_rect.width() / 2
        center_y = label_rect.height() / 2
        self._offset_x = new_img_x - (label_rect.width() - new_scaled_width) // 2
        self._offset_y = new_img_y - (label_rect.height() - new_scaled_height) // 2
        
        self.update()
        self.zoom_changed.emit(self._zoom_factor)
        event.accept()

    def zoom_at_point(self, point: QPoint, zoom_in: bool):
        """在指定点进行缩放（用于快捷键）
        
        Args:
            point: 缩放中心点（相对于label的坐标）
            zoom_in: True为放大，False为缩小
        """
        if self._original_pixmap is None:
            return
        
        # 计算缩放因子（每次10%）
        old_zoom = self._zoom_factor
        zoom_step = 0.1  # 10%
        
        if zoom_in:
            # 放大10%
            new_zoom = old_zoom * (1.0 + zoom_step)
        else:
            # 缩小10%
            new_zoom = old_zoom * (1.0 - zoom_step)
        
        # 限制缩放范围（10% - 1000%）
        new_zoom = max(0.1, min(10.0, new_zoom))
        
        if abs(new_zoom - old_zoom) < 0.001:
            return
        
        # 计算当前图片在label中的位置
        label_rect = self.contentsRect()
        scaled_width = int(self._original_pixmap.width() * old_zoom)
        scaled_height = int(self._original_pixmap.height() * old_zoom)
        
        # 图片左上角在label中的位置
        img_x = (label_rect.width() - scaled_width) // 2 + self._offset_x
        img_y = (label_rect.height() - scaled_height) // 2 + self._offset_y
        
        # 鼠标位置相对于图片的坐标（在缩放前的图片坐标系中）
        rel_x = point.x() - img_x
        rel_y = point.y() - img_y
        
        # 转换为原始图片坐标（0-1范围）
        if scaled_width > 0 and scaled_height > 0:
            img_ratio_x = rel_x / scaled_width
            img_ratio_y = rel_y / scaled_height
        else:
            img_ratio_x = 0.5
            img_ratio_y = 0.5
        
        # 应用新缩放
        self._zoom_factor = new_zoom
        
        # 计算新缩放后的图片尺寸
        new_scaled_width = int(self._original_pixmap.width() * new_zoom)
        new_scaled_height = int(self._original_pixmap.height() * new_zoom)
        
        # 计算新的图片位置，使鼠标位置对应的图片点保持不变
        new_img_x = point.x() - (img_ratio_x * new_scaled_width)
        new_img_y = point.y() - (img_ratio_y * new_scaled_height)
        
        # 计算新的偏移量
        center_x = label_rect.width() / 2
        center_y = label_rect.height() / 2
        self._offset_x = new_img_x - (label_rect.width() - new_scaled_width) // 2
        self._offset_y = new_img_y - (label_rect.height() - new_scaled_height) // 2
        
        self.update()
        self.zoom_changed.emit(self._zoom_factor)

    def set_original_pixmap(self, pixmap: QPixmap):
        """设置原始图片"""
        self._original_pixmap = pixmap
        self._zoom_factor = 1.0
        self._offset_x = 0
        self._offset_y = 0
        self._preview_rotate_angle = 0.0
        self.update()
    
    def set_preview_rotate_angle(self, angle: float):
        """设置预览旋转角度（度）"""
        self._preview_rotate_angle = angle
        self.update()

    def set_zoom_factor(self, zoom_factor: float):
        """设置缩放比例（以预览区域中心为缩放中心）
        
        Args:
            zoom_factor: 缩放比例（1.0 = 100%）
        """
        if self._original_pixmap is None:
            return
        
        # 限制缩放范围（10% - 1000%）
        zoom_factor = max(0.1, min(10.0, zoom_factor))
        
        if abs(zoom_factor - self._zoom_factor) < 0.001:
            return
        
        # 计算当前图片在label中的位置
        label_rect = self.contentsRect()
        old_zoom = self._zoom_factor
        scaled_width = int(self._original_pixmap.width() * old_zoom)
        scaled_height = int(self._original_pixmap.height() * old_zoom)
        
        # 图片左上角在label中的位置
        img_x = (label_rect.width() - scaled_width) // 2 + self._offset_x
        img_y = (label_rect.height() - scaled_height) // 2 + self._offset_y
        
        # 以预览区域中心为缩放中心
        center_x = label_rect.width() / 2
        center_y = label_rect.height() / 2
        
        # 计算中心点相对于图片的坐标（在缩放前的图片坐标系中）
        rel_x = center_x - img_x
        rel_y = center_y - img_y
        
        # 转换为原始图片坐标（0-1范围）
        if scaled_width > 0 and scaled_height > 0:
            img_ratio_x = rel_x / scaled_width
            img_ratio_y = rel_y / scaled_height
        else:
            img_ratio_x = 0.5
            img_ratio_y = 0.5
        
        # 应用新缩放
        self._zoom_factor = zoom_factor
        
        # 计算新缩放后的图片尺寸
        new_scaled_width = int(self._original_pixmap.width() * zoom_factor)
        new_scaled_height = int(self._original_pixmap.height() * zoom_factor)
        
        # 计算新的图片位置，使中心点对应的图片点保持不变
        new_img_x = center_x - (img_ratio_x * new_scaled_width)
        new_img_y = center_y - (img_ratio_y * new_scaled_height)
        
        # 计算新的偏移量
        self._offset_x = new_img_x - (label_rect.width() - new_scaled_width) // 2
        self._offset_y = new_img_y - (label_rect.height() - new_scaled_height) // 2
        
        self.update()
        self.zoom_changed.emit(self._zoom_factor)

    def set_watermark_mode(self, enabled: bool):
        """设置水印位置选择模式"""
        self._watermark_mode = enabled
        if enabled:
            self.setCursor(QCursor(Qt.CursorShape.CrossCursor))
        else:
            self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))
            self._watermark_pos = None
        self.update()
    
    def set_watermark_size(self, width: int, height: int):
        """设置水印大小（用于预览框）"""
        self._watermark_size = QSize(width, height)
        self.update()
    
    def set_watermark_preview(self, text: str, font_family: str, font_size: int, 
                              opacity: float, position: str, x: int = None, y: int = None):
        """设置水印预览信息"""
        self._watermark_text = text
        self._watermark_font_family = font_family
        self._watermark_font_size = font_size
        self._watermark_opacity = opacity
        self._watermark_position = position
        if x is not None and y is not None:
            self._watermark_pos = QPoint(x, y)
        self.update()
    
    def clear_watermark_preview(self):
        """清除水印预览"""
        self._watermark_pos = None
        self._watermark_text = ""
        self.update()
    
    def _draw_watermark_preview(self, painter: QPainter, label_rect: QRect, 
                                scaled_pixmap: QPixmap, img_x: int, img_y: int):
        """绘制水印预览文本"""
        from PyQt6.QtGui import QFont
        
        # 设置字体
        font = QFont(self._watermark_font_family if self._watermark_font_family else "Arial")
        font.setPixelSize(int(self._watermark_font_size * scaled_pixmap.width() / self._original_pixmap.width()))
        painter.setFont(font)
        
        # 计算文本尺寸
        metrics = painter.fontMetrics()
        text_width = metrics.horizontalAdvance(self._watermark_text)
        text_height = metrics.height()
        
        # 计算水印位置（屏幕坐标）
        margin = int(20 * scaled_pixmap.width() / self._original_pixmap.width())
        img_width = scaled_pixmap.width()
        img_height = scaled_pixmap.height()
        
        if self._watermark_position == "custom" and self._watermark_pos is not None:
            # 自定义位置
            wm_x = img_x + int(self._watermark_pos.x() * img_width / self._original_pixmap.width())
            wm_y = img_y + int(self._watermark_pos.y() * img_height / self._original_pixmap.height())
        elif self._watermark_position == "bottom-right":
            wm_x = img_x + img_width - text_width - margin
            wm_y = img_y + img_height - text_height - margin
        elif self._watermark_position == "bottom-left":
            wm_x = img_x + margin
            wm_y = img_y + img_height - text_height - margin
        elif self._watermark_position == "top-left":
            wm_x = img_x + margin
            wm_y = img_y + margin
        elif self._watermark_position == "top-right":
            wm_x = img_x + img_width - text_width - margin
            wm_y = img_y + margin
        else:  # center
            wm_x = img_x + (img_width - text_width) // 2
            wm_y = img_y + (img_height - text_height) // 2
        
        # 设置文本颜色和透明度
        text_color = QColor(255, 255, 255, int(255 * self._watermark_opacity))
        painter.setPen(text_color)
        
        # 绘制文本
        painter.drawText(wm_x, wm_y + text_height - metrics.descent(), self._watermark_text)
    
    def reset_view(self):
        """重置视图（缩放和偏移）"""
        self._zoom_factor = 1.0
        self._offset_x = 0
        self._offset_y = 0
        self.update()
        self.zoom_changed.emit(self._zoom_factor)

    def paintEvent(self, event):
        """绘制图片和选择框"""
        # 先调用父类绘制（绘制背景等）
        super().paintEvent(event)
        
        if self._original_pixmap is None:
            return
        
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        
        # 计算缩放后的尺寸
        scaled_width = int(self._original_pixmap.width() * self._zoom_factor)
        scaled_height = int(self._original_pixmap.height() * self._zoom_factor)
        
        # 创建缩放后的图片
        scaled_pixmap = self._original_pixmap.scaled(
            scaled_width, scaled_height,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
        
        # 如果有预览旋转角度，应用旋转
        if abs(self._preview_rotate_angle) > 0.01:
            # 将QPixmap转换为QImage进行旋转
            qimage = scaled_pixmap.toImage()
            # 创建变换矩阵
            transform = QTransform()
            transform.rotate(self._preview_rotate_angle)
            # 应用旋转
            rotated_qimage = qimage.transformed(transform, Qt.TransformationMode.SmoothTransformation)
            scaled_pixmap = QPixmap.fromImage(rotated_qimage)
        
        # 计算绘制位置（居中 + 偏移）
        label_rect = self.contentsRect()
        x = (label_rect.width() - scaled_pixmap.width()) // 2 + self._offset_x
        y = (label_rect.height() - scaled_pixmap.height()) // 2 + self._offset_y
        
        # 绘制图片
        painter.drawPixmap(int(x), int(y), scaled_pixmap)
        
        # 保存图片位置和尺寸，供后续绘制使用
        img_x = int(x)
        img_y = int(y)
        
        # 绘制裁剪选择框
        rect = self._current_rect()
        if rect is not None and not rect.isNull():
            # 半透明填充区域
            brush = QBrush(QColor(0, 120, 215, 40))
            painter.fillRect(rect, brush)

            # 边框
            pen = QPen(QColor(0, 120, 215))
            pen.setWidth(1)
            painter.setPen(pen)
            painter.drawRect(rect)
        
        # 绘制水印文本（实时预览）
        if self._watermark_mode and self._watermark_text and self._original_pixmap:
            self._draw_watermark_preview(painter, label_rect, scaled_pixmap, img_x, img_y)


# ------------------ 主窗口 ------------------
class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        self.setWindowTitle("简易图片处理工具")
        self.setMinimumSize(1000, 640)
        
        # 设置窗口图标
        icon_path = os.path.join(os.path.dirname(__file__), "..", "icons", "icon.png")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        
        self.original_image = None
        self.current_image = None
        self.original_file_path = None  # 原始文件路径
        self.history = []  # 撤销历史栈
        self.redo_history = []  # 重做历史栈
        self.max_history = 10
        self.worker = None
        self.current_filter = "none"  # 当前选择的滤镜：none, grayscale, blur, vintage
        self.blur_radius = 2.0  # 模糊半径
        self.watermark_font_path = None  # 水印字体路径

        self.build_ui()
        self.load_qss()
        self.create_menu_bar()
        self.setup_shortcuts()  # 设置快捷键
        
        # 窗口显示后设置标题栏主题（Windows）
        if platform.system() == "Windows":
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(200, self._apply_title_bar_theme)

    def create_menu_bar(self):
        menubar = self.menuBar()

        # 文件菜单
        file_menu = menubar.addMenu("文件")

        # 编辑菜单
        edit_menu = menubar.addMenu("编辑")

        # 工具菜单
        tools_menu = menubar.addMenu("工具")
        batch_action = QAction("批量处理", self)
        batch_action.triggered.connect(self.show_batch_process_dialog)
        tools_menu.addAction(batch_action)

        # 设置菜单
        settings_menu = menubar.addMenu("设置")
        appearance_action = QAction("外观", self)
        appearance_action.triggered.connect(self.show_appearance_dialog)
        settings_menu.addAction(appearance_action)

        # 放映菜单
        play_menu = menubar.addMenu("放映")
        slideshow_action = QAction("开始放映", self)
        slideshow_action.setShortcut(QKeySequence("F5"))  # 快捷键：F5
        slideshow_action.triggered.connect(self.start_slideshow)
        play_menu.addAction(slideshow_action)

        # 打开文件
        open_action = QAction("打开", self)
        open_action.setShortcut(QKeySequence("Ctrl+O"))  # 快捷键：Ctrl+O
        open_action.triggered.connect(self.open_image)
        file_menu.addAction(open_action)

        # 保存文件
        save_action = QAction("保存", self)
        save_action.setShortcut(QKeySequence("Ctrl+S"))  # 快捷键：Ctrl+S
        save_action.triggered.connect(self.save_image)
        file_menu.addAction(save_action)

        # 退出
        exit_action = QAction("退出", self)
        exit_action.setShortcut(QKeySequence("Ctrl+Q"))  # 快捷键：Ctrl+Q
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # ===== 编辑菜单子项（对应左侧功能按钮，无图标） =====
        act_open = QAction("打开（导入图片）", self)
        act_open.triggered.connect(self.open_image)
        edit_menu.addAction(act_open)

        act_save = QAction("保存图片", self)
        act_save.triggered.connect(self.save_image)
        edit_menu.addAction(act_save)

        edit_menu.addSeparator()

        act_zoom_in = QAction("放大图片", self)
        act_zoom_in.triggered.connect(lambda: self.apply_scale(1.2))
        edit_menu.addAction(act_zoom_in)

        act_zoom_out = QAction("缩小图片", self)
        act_zoom_out.triggered.connect(lambda: self.apply_scale(0.8))
        edit_menu.addAction(act_zoom_out)
        
        # 预览区域缩放（与图片缩放不同）
        edit_menu.addSeparator()
        act_preview_zoom_in = QAction("放大预览", self)
        act_preview_zoom_in.setShortcut(QKeySequence("Ctrl++"))  # 快捷键：Ctrl+Plus
        act_preview_zoom_in.triggered.connect(self.zoom_in_preview)
        edit_menu.addAction(act_preview_zoom_in)
        
        act_preview_zoom_out = QAction("缩小预览", self)
        act_preview_zoom_out.setShortcut(QKeySequence("Ctrl+-"))  # 快捷键：Ctrl+Minus
        act_preview_zoom_out.triggered.connect(self.zoom_out_preview)
        edit_menu.addAction(act_preview_zoom_out)
        
        act_reset_view = QAction("重置预览视图", self)
        act_reset_view.setShortcut(QKeySequence("Ctrl+0"))  # 快捷键：Ctrl+0
        act_reset_view.triggered.connect(self.reset_preview_view)
        edit_menu.addAction(act_reset_view)

        act_rotate = QAction("顺时针旋转90°", self)
        act_rotate.triggered.connect(lambda: self.apply_rotate(-90))
        edit_menu.addAction(act_rotate)

        edit_menu.addSeparator()

        act_redo = QAction("重做上一步", self)
        act_redo.setShortcut(QKeySequence("Ctrl+Y"))  # 快捷键：Ctrl+Y
        act_redo.triggered.connect(self.redo)
        edit_menu.addAction(act_redo)

        act_undo = QAction("撤销上一步", self)
        act_undo.setShortcut(QKeySequence("Ctrl+Z"))  # 快捷键：Ctrl+Z
        act_undo.triggered.connect(self.undo)
        edit_menu.addAction(act_undo)

    def setup_shortcuts(self):
        """设置全局快捷键（不依赖菜单项）"""
        # Ctrl+= 也支持（与Ctrl++等效，因为+和=在键盘上是同一个键）
        zoom_in_preview_alt = QShortcut(QKeySequence("Ctrl+="), self)
        zoom_in_preview_alt.activated.connect(self.zoom_in_preview)

    def zoom_in_preview(self):
        """预览区域放大（快捷键）"""
        if self.preview_label and self.preview_label._original_pixmap:
            # 获取鼠标位置（相对于label）
            global_pos = QCursor.pos()
            local_pos = self.preview_label.mapFromGlobal(global_pos)
            # 如果鼠标不在label内，使用label中心点
            if not self.preview_label.rect().contains(local_pos):
                local_pos = QPoint(
                    self.preview_label.width() // 2,
                    self.preview_label.height() // 2
                )
            self.preview_label.zoom_at_point(local_pos, zoom_in=True)

    def zoom_out_preview(self):
        """预览区域缩小（快捷键）"""
        if self.preview_label and self.preview_label._original_pixmap:
            # 获取鼠标位置（相对于label）
            global_pos = QCursor.pos()
            local_pos = self.preview_label.mapFromGlobal(global_pos)
            # 如果鼠标不在label内，使用label中心点
            if not self.preview_label.rect().contains(local_pos):
                local_pos = QPoint(
                    self.preview_label.width() // 2,
                    self.preview_label.height() // 2
                )
            self.preview_label.zoom_at_point(local_pos, zoom_in=False)

    def reset_preview_view(self):
        """重置预览视图（缩放和偏移）"""
        if self.preview_label:
            self.preview_label.reset_view()

    def show_appearance_dialog(self):
        """显示外观设置对话框"""
        dialog = AppearanceDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            # 重新加载样式（应用到整个应用程序）
            self.load_qss()
            # 更新标题栏主题（Windows）
            if platform.system() == "Windows":
                from PyQt6.QtCore import QTimer
                QTimer.singleShot(100, self._apply_title_bar_theme)
            # 提示信息（现在也会使用正确的主题）
            QMessageBox.information(self, "提示", "主题已更改！")

    # 读取 qss 样式
    def load_qss(self, theme=None):
        """加载QSS样式表并应用到整个应用程序
        
        Args:
            theme: 主题名称 ('light', 'dark', 'auto')，None时从设置读取
        """
        if theme is None:
            settings = QSettings("ImageTool", "Settings")
            theme = settings.value("theme", "auto", type=str)

        if theme == "auto":
            # 检测系统主题
            palette = self.palette()
            bg_color = palette.color(QPalette.ColorRole.Window)
            # 如果背景色较暗，使用深色主题
            if bg_color.lightness() < 128:
                theme = "dark"
            else:
                theme = "light"

        if theme == "dark":
            qss_file = "qss_dark.qss"
        else:
            qss_file = "qss.qss"

        qss_path = os.path.join(os.path.dirname(__file__), qss_file)
        if os.path.exists(qss_path):
            with open(qss_path, "r", encoding="utf-8") as f:
                qss_content = f.read()
                
                # 将QSS中的相对路径转换为绝对路径
                # QSS的url路径是相对于应用程序工作目录的，需要转换为绝对路径
                # 使用统一的函数获取 icons 目录 URL
                icons_url = get_icons_dir_url()
                
                # 替换QSS中的相对路径为绝对路径
                # 格式：url(file:///C:/path/to/icons/up.png) 或 url(file:///path/to/icons/up.png)
                qss_content = qss_content.replace("url(../icons/", f"url({icons_url}/")
                
                # 应用到整个应用程序，这样所有窗口（包括对话框）都会使用相同主题
                app = QApplication.instance()
                if app:
                    app.setStyleSheet(qss_content)
                # 同时也应用到主窗口（确保主窗口样式正确）
                self.setStyleSheet(qss_content)
                
                # 不再需要设置 QSpinBox 图标，已改用 NumberInput 控件
                
                # 在Windows上尝试设置标题栏颜色
                # 注意：需要在窗口显示后调用，所以延迟执行
                if platform.system() == "Windows":
                    from PyQt6.QtCore import QTimer
                    QTimer.singleShot(100, lambda: self._apply_title_bar_theme())
                
                # 更新所有 NumberInput 控件的主题样式
                self._update_all_number_inputs_theme()

    def _apply_title_bar_theme(self):
        """应用标题栏主题（在窗口显示后调用）"""
        settings = QSettings("ImageTool", "Settings")
        theme = settings.value("theme", "auto", type=str)
        
        if theme == "auto":
            # 检测系统主题
            palette = self.palette()
            bg_color = palette.color(QPalette.ColorRole.Window)
            if bg_color.lightness() < 128:
                theme = "dark"
            else:
                theme = "light"
        
        self._set_windows_title_bar_theme(theme)
    
    def _set_windows_title_bar_theme(self, theme: str):
        """在Windows上设置标题栏主题颜色
        
        使用Windows API (DwmSetWindowAttribute) 来设置标题栏颜色
        注意：这需要Windows 10/11 (Build 17763+)
        """
        if platform.system() != "Windows":
            return
            
        try:
            import ctypes
            from ctypes import wintypes
            
            # Windows API 常量
            DWMWA_USE_IMMERSIVE_DARK_MODE = 20  # Windows 11
            DWMWA_MICA_EFFECT = 1029  # Windows 11 Mica效果
            
            # 获取窗口句柄
            hwnd = int(self.winId())
            
            # 设置深色/浅色模式
            if theme == "dark":
                # 深色模式：标题栏文字为浅色，背景为深色
                value = ctypes.c_int(1)  # 启用深色模式
            else:
                # 浅色模式：标题栏文字为深色，背景为浅色
                value = ctypes.c_int(0)  # 禁用深色模式（使用浅色）
            
            # 调用Windows API
            try:
                # 尝试使用Windows 11的API
                ctypes.windll.dwmapi.DwmSetWindowAttribute(
                    wintypes.HWND(hwnd),
                    DWMWA_USE_IMMERSIVE_DARK_MODE,
                    ctypes.byref(value),
                    ctypes.sizeof(value)
                )
            except:
                # 如果失败，可能是Windows 10或更早版本
                # 在Windows 10上，标题栏颜色主要由系统设置控制
                pass
                
        except Exception as e:
            # 如果设置失败，不影响程序运行
            # print(f"设置标题栏主题失败: {e}")  # 注释掉，避免控制台输出
            pass
    
    def _update_all_number_inputs_theme(self):
        """更新所有 NumberInput 控件的主题样式"""
        def find_number_inputs(widget):
            """递归查找所有 NumberInput 控件"""
            number_inputs = []
            if isinstance(widget, NumberInput):
                number_inputs.append(widget)
            for child in widget.findChildren(QWidget):
                if isinstance(child, NumberInput):
                    number_inputs.append(child)
            return number_inputs
        
        # 查找所有 NumberInput 控件并更新样式
        number_inputs = find_number_inputs(self)
        for number_input in number_inputs:
            number_input._apply_theme_style()

    # ------------------ UI 核心 ------------------
    def build_ui(self):
        # 设置窗口标志，移除系统标题栏（可选，如果需要完全自定义）
        # 注意：在Windows上，我们可以尝试设置标题栏颜色
        if platform.system() == "Windows":
            try:
                # Windows 10/11 支持设置标题栏颜色
                # 但这需要额外的Windows API调用，这里我们通过QSS尝试
                pass
            except:
                pass
        
        central = QWidget()
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)
        # 去掉中央布局的外边距，让左右分隔线从上到下贴合中央区域
        layout.setContentsMargins(0, 0, 0, 0)

        # ========== 左侧工具栏 ==========
        icons_dir = os.path.join(os.path.dirname(__file__), "..", "icons")

        left = QVBoxLayout()
        left.setContentsMargins(4, 8, 4, 8)
        left.setSpacing(6)
        left_widget = QWidget()
        left_widget.setObjectName("leftToolBar")
        left_widget.setLayout(left)
        # 更窄的工具栏，类似 PS 左侧工具条
        left_widget.setFixedWidth(60)
        layout.addWidget(left_widget)

        # 统一使用工具按钮样式（带图标的纵向工具栏）
        self.btn_open = QToolButton()
        self.btn_open.setText("打开")
        self.btn_open.setIcon(QIcon(os.path.join(icons_dir, "open.png")))
        self.btn_open.clicked.connect(self.open_image)
        self.btn_open.setToolTip("打开并导入图片文件")
        left.addWidget(self.btn_open)

        self.btn_save = QToolButton()
        self.btn_save.setText("保存")
        self.btn_save.setIcon(QIcon(os.path.join(icons_dir, "save.png")))
        self.btn_save.clicked.connect(self.save_image)
        self.btn_save.setToolTip("保存当前图片到本地")
        left.addWidget(self.btn_save)

        self.btn_zoom_in = QToolButton()
        self.btn_zoom_in.setText("放大")
        self.btn_zoom_in.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_ArrowUp))
        self.btn_zoom_in.clicked.connect(lambda: self.apply_scale(1.2))
        self.btn_zoom_in.setToolTip("放大当前图片")
        left.addWidget(self.btn_zoom_in)

        self.btn_zoom_out = QToolButton()
        self.btn_zoom_out.setText("缩小")
        self.btn_zoom_out.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_ArrowDown))
        self.btn_zoom_out.clicked.connect(lambda: self.apply_scale(0.8))
        self.btn_zoom_out.setToolTip("缩小当前图片")
        left.addWidget(self.btn_zoom_out)

        self.btn_rotate = QToolButton()
        self.btn_rotate.setText("旋转90°")
        # 使用与当前旋转方向一致的自定义图标
        self.btn_rotate.setIcon(QIcon(os.path.join(icons_dir, "turn90deg.png")))
        self.btn_rotate.clicked.connect(lambda: self.apply_rotate(-90))
        self.btn_rotate.setToolTip("顺时针旋转 90 度")
        left.addWidget(self.btn_rotate)

        # 重做按钮
        self.btn_redo = QToolButton()
        self.btn_redo.setText("重做")
        self.btn_redo.setIcon(QIcon(os.path.join(icons_dir, "redo_new.png")))
        self.btn_redo.clicked.connect(self.redo)
        self.btn_redo.setToolTip("重做上一步操作")
        left.addWidget(self.btn_redo)

        self.btn_undo = QToolButton()
        self.btn_undo.setText("撤销")
        # 使用自定义撤销图标
        self.btn_undo.setIcon(QIcon(os.path.join(icons_dir, "undo_new.png")))
        self.btn_undo.clicked.connect(self.undo)
        self.btn_undo.setToolTip("撤销上一步操作")
        left.addWidget(self.btn_undo)

        # 统一左侧所有工具按钮的尺寸和风格，参考 PS 图标工具条
        for btn in [
            self.btn_open,
            self.btn_save,
            self.btn_zoom_in,
            self.btn_zoom_out,
            self.btn_rotate,
            self.btn_redo,
            self.btn_undo,
        ]:
            # 只显示图标，文字使用悬停提示
            btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
            btn.setIconSize(QSize(24, 24))
            # 窄而统一的按钮尺寸
            btn.setFixedSize(40, 40)

        left.addStretch()

        # 重置按钮（放在最底部）
        self.btn_reset = QToolButton()
        self.btn_reset.setText("重置")
        self.btn_reset.setIcon(QIcon(os.path.join(icons_dir, "reset.png")))
        self.btn_reset.clicked.connect(self.reset_all_effects)
        self.btn_reset.setToolTip("重置所有效果，恢复到图片刚打开时的样子")
        self.btn_reset.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        self.btn_reset.setIconSize(QSize(24, 24))
        self.btn_reset.setFixedSize(40, 40)
        left.addWidget(self.btn_reset)

        # ========== 中间预览 ==========
        preview_layout = QVBoxLayout()
        preview_widget = QWidget()
        preview_widget.setLayout(preview_layout)
        layout.addWidget(preview_widget, stretch=1)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        # 使用自定义的 CropLabel 支持鼠标拖拽选择裁剪区域
        self.preview_label = CropLabel("无图片")
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setStyleSheet("background:#1e1e1e;color:white;")
        self.preview_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.scroll.setWidget(self.preview_label)
        # 选择完成后回调
        self.preview_label.selection_finished.connect(self.on_selection_finished)
        # 水印位置选择完成回调
        self.preview_label.watermark_position_selected.connect(self.on_watermark_position_selected)

        preview_layout.addWidget(self.scroll)
        
        # 状态栏：显示图片信息和缩放比例
        status_layout = QHBoxLayout()
        self.status_label = QLabel("就绪")
        self.status_label.setWordWrap(True)
        status_layout.addWidget(self.status_label)
        
        self.zoom_label = QLabel("100%")
        self.zoom_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.zoom_label.setMinimumWidth(80)
        status_layout.addWidget(self.zoom_label)
        
        status_widget = QWidget()
        status_widget.setLayout(status_layout)
        preview_layout.addWidget(status_widget)
        
        # 连接缩放改变信号
        self.preview_label.zoom_changed.connect(self._on_zoom_changed)

        # ========== 右侧参数区（带滚动） ==========
        right_scroll = QScrollArea()
        right_scroll.setWidgetResizable(True)
        right_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        right_scroll.setFixedWidth(300)
        layout.addWidget(right_scroll)

        right_widget = QWidget()
        right_widget.setObjectName("rightPanel")  # <<< 新增：右侧整体面板的名字
        right = QVBoxLayout(right_widget)
        right_widget.setLayout(right)

        right_scroll.setWidget(right_widget)

        # 缩放组
        s_group = QGroupBox("缩放")
        s_layout = QVBoxLayout()
        s_group.setLayout(s_layout)
        right.addWidget(s_group)

        self.s_slider = QSlider(Qt.Orientation.Horizontal)
        self.s_slider.setRange(10, 300)
        self.s_slider.setValue(100)
        # 滑块值改变时，实时更新预览区域的缩放
        self.s_slider.valueChanged.connect(self.on_slider_value_changed)
        s_layout.addWidget(self.s_slider)

        self.scale_label = QLabel("100%")
        s_layout.addWidget(self.scale_label)

        btn_apply_scale = QPushButton("应用缩放", clicked=self.on_slider_scale)
        s_layout.addWidget(btn_apply_scale)

        # 旋转组
        r_group = QGroupBox("旋转")
        r_layout = QVBoxLayout()
        r_group.setLayout(r_layout)
        right.addWidget(r_group)

        self.rotate_spin = NumberInput()
        self.rotate_spin.setRange(-360, 360)
        self.rotate_spin.setSuffix("°")  # 添加度数字符
        self.rotate_spin.setValue(0)
        # 实时预览：值改变时更新预览
        self.rotate_spin.valueChanged.connect(self.on_rotate_spin_changed)
        
        r_layout.addWidget(self.rotate_spin)

        r_layout.addWidget(QPushButton("应用旋转",
                                       clicked=lambda: self.apply_rotate(self.rotate_spin.value())))

        # 裁剪组
        c_group = QGroupBox("裁剪")
        c_layout = QVBoxLayout()
        c_group.setLayout(c_layout)
        right.addWidget(c_group)

        # 预设比例下拉框
        c_layout.addWidget(QLabel("预设比例:"))
        self.crop_ratio_combo = QComboBox()
        self.crop_ratio_combo.addItems([
            "自由",
            "1:1 (正方形)",
            "4:3 (标准)",
            "16:9 (宽屏)",
            "3:2 (照片)",
            "21:9 (超宽屏)",
            "9:16 (竖屏)",
            "2:3 (竖照片)"
        ])
        self.crop_ratio_combo.currentIndexChanged.connect(self.on_crop_ratio_changed)
        c_layout.addWidget(self.crop_ratio_combo)

        self.crop_left = QLineEdit("0")
        self.crop_top = QLineEdit("0")
        self.crop_w = QLineEdit("200")
        self.crop_h = QLineEdit("200")

        for label, widget in [
            ("左:", self.crop_left),
            ("上:", self.crop_top),
            ("宽:", self.crop_w),
            ("高:", self.crop_h),
        ]:
            c_layout.addWidget(QLabel(label))
            c_layout.addWidget(widget)

        c_layout.addWidget(QPushButton("应用裁剪", clicked=self.apply_crop))

        # 水印组
        w_group = QGroupBox("水印")
        w_layout = QVBoxLayout()
        w_group.setLayout(w_layout)
        right.addWidget(w_group)

        self.wm_text = QLineEdit("Hello")
        self.wm_text.textChanged.connect(self._on_watermark_text_changed)
        w_layout.addWidget(QLabel("文本:"))
        w_layout.addWidget(self.wm_text)

        # 字体选择
        font_btn_layout = QHBoxLayout()
        font_btn_layout.addWidget(QLabel("字体:"))
        self.wm_font_btn = QPushButton("选择字体...")
        self.wm_font_btn.clicked.connect(self.select_watermark_font)
        font_btn_layout.addWidget(self.wm_font_btn)
        font_btn_layout.addStretch()
        font_widget = QWidget()
        font_widget.setLayout(font_btn_layout)
        w_layout.addWidget(font_widget)

        # 位置选择（包含自定义）
        w_layout.addWidget(QLabel("位置:"))
        self.wm_pos = QComboBox()
        self.wm_pos.addItems(["bottom-right", "bottom-left", "top-left", "top-right", "center", "自定义"])
        self.wm_pos.currentTextChanged.connect(self._on_watermark_position_changed)
        w_layout.addWidget(self.wm_pos)

        # 自定义位置输入（默认隐藏）
        custom_pos_layout = QHBoxLayout()
        custom_pos_layout.addWidget(QLabel("X:"))
        self.wm_custom_x = NumberInput()
        self.wm_custom_x.setRange(0, 10000)
        self.wm_custom_x.setValue(0)
        custom_pos_layout.addWidget(self.wm_custom_x)
        custom_pos_layout.addWidget(QLabel("Y:"))
        self.wm_custom_y = NumberInput()
        self.wm_custom_y.setRange(0, 10000)
        self.wm_custom_y.setValue(0)
        custom_pos_layout.addWidget(self.wm_custom_y)
        self.wm_custom_pos_container = QWidget()
        self.wm_custom_pos_container.setLayout(custom_pos_layout)
        self.wm_custom_pos_container.setVisible(False)
        w_layout.addWidget(self.wm_custom_pos_container)
        
        # 连接自定义位置输入框的变化，实时更新预览
        self.wm_custom_x.valueChanged.connect(self._on_watermark_custom_pos_changed)
        self.wm_custom_y.valueChanged.connect(self._on_watermark_custom_pos_changed)

        # 字体大小
        w_layout.addWidget(QLabel("大小:"))
        self.wm_size = NumberInput()
        self.wm_size.setRange(8, 200)
        self.wm_size.setValue(36)
        self.wm_size.setSuffix(" px")
        self.wm_size.valueChanged.connect(self._on_watermark_size_changed)
        w_layout.addWidget(self.wm_size)

        # 透明度（带标签显示）
        opacity_layout = QVBoxLayout()
        opacity_label_layout = QHBoxLayout()
        opacity_label_layout.addWidget(QLabel("透明度:"))
        self.wm_opacity_label = QLabel("70%")
        opacity_label_layout.addWidget(self.wm_opacity_label)
        opacity_label_layout.addStretch()
        opacity_label_widget = QWidget()
        opacity_label_widget.setLayout(opacity_label_layout)
        opacity_layout.addWidget(opacity_label_widget)

        self.wm_op = QSlider(Qt.Orientation.Horizontal)
        self.wm_op.setRange(0, 100)
        self.wm_op.setValue(70)
        self.wm_op.valueChanged.connect(
            lambda v: (self.wm_opacity_label.setText(f"{v}%"), 
                      self._update_watermark_preview() if self.preview_label._watermark_mode else None)
        )
        opacity_layout.addWidget(self.wm_op)
        opacity_widget = QWidget()
        opacity_widget.setLayout(opacity_layout)
        w_layout.addWidget(opacity_widget)

        w_layout.addWidget(QPushButton("添加水印", clicked=self.apply_watermark))

        # 滤镜组
        f_group = QGroupBox("滤镜")
        f_layout = QVBoxLayout()
        f_group.setLayout(f_layout)
        right.addWidget(f_group)

        self.radio_none = QRadioButton("无滤镜")
        self.radio_none.setChecked(True)
        f_layout.addWidget(self.radio_none)

        self.radio_grayscale = QRadioButton("黑白")
        f_layout.addWidget(self.radio_grayscale)

        self.radio_blur = QRadioButton("模糊")
        f_layout.addWidget(self.radio_blur)

        self.radio_vintage = QRadioButton("复古")
        f_layout.addWidget(self.radio_vintage)

        # 模糊半径滑块（默认隐藏）
        blur_slider_layout = QHBoxLayout()
        blur_slider_layout.addWidget(QLabel("半径:"))
        self.blur_slider = QSlider(Qt.Orientation.Horizontal)
        self.blur_slider.setRange(5, 100)  # 0.5 ~ 10.0
        self.blur_slider.setValue(20)  # 默认2.0
        self.blur_slider.valueChanged.connect(
            lambda v: self.blur_radius_label.setText(f"{v/10.0:.1f}")
        )
        blur_slider_layout.addWidget(self.blur_slider)
        self.blur_radius_label = QLabel("2.0")
        self.blur_radius_label.setMinimumWidth(40)
        blur_slider_layout.addWidget(self.blur_radius_label)
        self.blur_slider_container = QWidget()
        self.blur_slider_container.setLayout(blur_slider_layout)
        self.blur_slider_container.setVisible(False)
        f_layout.addWidget(self.blur_slider_container)

        # 连接单选按钮信号
        self.radio_none.toggled.connect(lambda checked: self._on_filter_changed("none", checked))
        self.radio_grayscale.toggled.connect(lambda checked: self._on_filter_changed("grayscale", checked))
        self.radio_blur.toggled.connect(lambda checked: self._on_filter_changed("blur", checked))
        self.radio_vintage.toggled.connect(lambda checked: self._on_filter_changed("vintage", checked))

        f_layout.addWidget(QPushButton("应用滤镜", clicked=self.apply_filter))

        right.addStretch()

    # ------------------ 工具函数 ------------------
    def push_history(self):
        """将当前图片状态推入撤销历史，并清空重做历史"""
        if self.current_image:
            self.history.append(self.current_image.copy())
            if len(self.history) > self.max_history:
                self.history.pop(0)
            # 执行新操作时，清空重做历史
            self.redo_history.clear()

    def pil_to_qpixmap(self, img: Image.Image):
        buf = BytesIO()
        img.save(buf, format="PNG")
        qimg = QImage.fromData(buf.getvalue())
        return QPixmap.fromImage(qimg)

    def update_preview(self):
        if self.current_image is None:
            self.preview_label.setText("无图片")
            self.preview_label.setPixmap(QPixmap())
            self.preview_label.set_original_pixmap(QPixmap())
            self.preview_label.clear_selection()
            self.status_label.setText("就绪")
            self.zoom_label.setText("")
            return

        pix = self.pil_to_qpixmap(self.current_image)
        # 设置原始图片（用于缩放和旋转）
        self.preview_label.set_original_pixmap(pix)
        # 同步滑块值到预览区域（如果滑块不是100%，则应用滑块的缩放）
        slider_value = self.s_slider.value()
        if slider_value != 100:
            zoom_factor = slider_value / 100.0
            self.preview_label.set_zoom_factor(zoom_factor)
        # 同步旋转角度到预览区域（如果旋转角度不是0，则应用旋转）
        rotate_angle = self.rotate_spin.value()
        if rotate_angle != 0:
            self.preview_label.set_preview_rotate_angle(float(rotate_angle))
        # 更新状态信息
        self.status_label.setText(f"{self.current_image.width} x {self.current_image.height}")
        self._on_zoom_changed(self.preview_label._zoom_factor)
        # 图片更新后清除选择框
        self.preview_label.clear_selection()
        # 如果处于水印位置选择模式，更新水印预览
        if self.preview_label._watermark_mode:
            self._update_watermark_preview()

    def _on_zoom_changed(self, zoom_factor: float):
        """缩放比例改变时的回调"""
        zoom_percent = int(zoom_factor * 100)
        self.zoom_label.setText(f"{zoom_percent}%")

    # ------------------ 文件操作 ------------------
    def open_image(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "打开图片", "", "图片 (*.png *.jpg *.jpeg *.bmp)"
        )
        if not path:
            return

        img = Image.open(path)
        self.original_image = img.copy()
        self.current_image = img.copy()
        self.original_file_path = path  # 保存原始文件路径
        self.history.clear()
        self.redo_history.clear()
        # 更新水印自定义位置的取值范围
        self._on_watermark_position_changed(self.wm_pos.currentText())
        self.update_preview()

    def save_image(self):
        if self.current_image is None:
            QMessageBox.warning(self, "提示", "无图片可保存")
            return
        
        # 生成默认文件名
        if self.original_file_path:
            # 如果有原始文件路径，使用原文件名 + "export"
            base_path = os.path.splitext(self.original_file_path)[0]  # 去掉扩展名
            base_name = os.path.basename(base_path)  # 获取文件名（不含路径）
            default_name = f"{base_name}_export.png"
            default_dir = os.path.dirname(self.original_file_path)  # 获取原文件所在目录
            default_path = os.path.join(default_dir, default_name)
        else:
            # 如果没有原始文件路径，使用默认名称
            default_path = "output.png"
        
        # 支持多种格式
        file_filter = (
            "PNG 图片 (*.png);;"
            "JPEG 图片 (*.jpg *.jpeg);;"
            "TIFF 图片 (*.tiff *.tif);;"
            "WebP 图片 (*.webp);;"
            "所有文件 (*)"
        )
        
        save_path, selected_filter = QFileDialog.getSaveFileName(
            self, "保存图片", default_path, file_filter
        )
        if save_path:
            # 如果用户没有输入扩展名，根据选择的过滤器添加
            if not os.path.splitext(save_path)[1]:
                # 根据选择的过滤器确定扩展名
                if "PNG" in selected_filter:
                    save_path += ".png"
                elif "JPEG" in selected_filter:
                    save_path += ".jpg"
                elif "TIFF" in selected_filter:
                    save_path += ".tiff"
                elif "WebP" in selected_filter:
                    save_path += ".webp"
                else:
                    save_path += ".png"  # 默认PNG
            
            try:
                ImageTools.save_image(self.current_image, save_path)
                QMessageBox.information(self, "成功", f"保存成功：{os.path.basename(save_path)}")
            except Exception as e:
                QMessageBox.critical(self, "错误", f"保存失败：{str(e)}")

    def reset_all_effects(self):
        """重置所有效果，恢复到图片刚打开时的样子"""
        if self.original_image is None:
            QMessageBox.information(self, "提示", "没有打开的图片")
            return
        
        # 确认对话框
        reply = QMessageBox.question(
            self, 
            "确认重置", 
            "确定要重置所有效果吗？这将清除所有已应用的操作（旋转、缩放、滤镜、水印、裁剪等）。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply != QMessageBox.StandardButton.Yes:
            return
        
        # 重置图片为原始图片
        self.current_image = self.original_image.copy()
        
        # 重置所有状态变量
        self.current_filter = "none"
        self.blur_radius = 2.0
        self.watermark_font_path = None
        
        # 清空历史记录
        self.history.clear()
        self.redo_history.clear()
        
        # 重置UI控件
        # 缩放滑块
        self.s_slider.setValue(100)
        self.scale_label.setText("100%")
        
        # 旋转输入
        self.rotate_spin.setValue(0)
        
        # 滤镜单选按钮
        self.radio_none.setChecked(True)
        self.blur_slider_container.setVisible(False)
        self.blur_slider.setValue(20)  # 默认2.0
        
        # 水印相关控件
        self.wm_text.setText("Hello")
        self.wm_size.setValue(36)
        self.wm_op.setValue(70)
        self.wm_opacity_label.setText("70%")
        self.wm_pos.setCurrentIndex(0)  # bottom-right
        self.wm_custom_x.setValue(0)
        self.wm_custom_y.setValue(0)
        self.wm_custom_pos_container.setVisible(False)
        # 更新自定义位置的取值范围
        if self.current_image:
            self.wm_custom_x.setRange(0, self.current_image.width)
            self.wm_custom_y.setRange(0, self.current_image.height)
        
        # 重置预览标签状态
        if self.preview_label:
            # 重置缩放
            self.preview_label.set_zoom_factor(1.0)
            # 重置旋转预览角度
            self.preview_label.set_preview_rotate_angle(0.0)
            # 清除裁剪选择
            self.preview_label.clear_selection()
            # 关闭水印模式
            self.preview_label.set_watermark_mode(False)
            self.preview_label.clear_watermark_preview()
            # 重置宽高比限制
            self.preview_label.set_aspect_ratio(None)
        
        # 重置裁剪比例选择
        self.crop_ratio_combo.setCurrentIndex(0)  # 自由
        
        # 更新预览显示
        self.update_preview()
        
        QMessageBox.information(self, "成功", "已重置所有效果")

    # ------------------ 操作逻辑 ------------------
    def on_slider_value_changed(self, value: int):
        """滑块值改变时的回调（实时预览）"""
        # 更新标签文本
        self.scale_label.setText(f"{value}%")
        # 实时更新预览区域的缩放（以预览区域中心为缩放中心）
        if self.preview_label._original_pixmap is not None:
            zoom_factor = value / 100.0
            self.preview_label.set_zoom_factor(zoom_factor)
    
    def on_slider_scale(self):
        """应用缩放按钮点击时的回调（实际修改图片）"""
        factor = self.s_slider.value() / 100
        self.apply_scale(factor)
    
    def on_rotate_spin_changed(self, angle: int):
        """旋转角度值改变时的回调（实时预览）"""
        # 实时更新预览区域的旋转角度
        if self.preview_label._original_pixmap is not None:
            self.preview_label.set_preview_rotate_angle(float(angle))

    def apply_scale(self, factor):
        if self.current_image is None:
            return
        self.push_history()
        self.worker = WorkerThread(ImageTools.scale, self.current_image, factor)
        self.worker.finished_image.connect(self.on_worker_finished)
        self.worker.start()

    def apply_rotate(self, angle):
        if self.current_image is None:
            return
        self.push_history()
        self.worker = WorkerThread(ImageTools.rotate, self.current_image, angle)
        self.worker.finished_image.connect(self.on_worker_finished)
        self.worker.start()
        # 应用旋转后，清除预览旋转角度
        self.preview_label.set_preview_rotate_angle(0.0)
        # 重置旋转输入框
        self.rotate_spin.setValue(0)

    def apply_crop(self):
        if self.current_image is None:
            return

        try:
            left = int(self.crop_left.text())
            top = int(self.crop_top.text())
            w = int(self.crop_w.text())
            h = int(self.crop_h.text())
        except:
            QMessageBox.warning(self, "错误", "裁剪参数无效")
            return

        self.apply_crop_rect(left, top, w, h)

    def apply_crop_rect(self, left: int, top: int, w: int, h: int):
        """根据给定矩形区域执行裁剪。"""
        if self.current_image is None:
            return
        # 边界保护
        left = max(0, min(left, self.current_image.width - 1))
        top = max(0, min(top, self.current_image.height - 1))
        w = max(1, min(w, self.current_image.width - left))
        h = max(1, min(h, self.current_image.height - top))

        self.push_history()
        img = ImageTools.crop(self.current_image, left, top, w, h)
        self.current_image = img
        self.update_preview()
        # 裁剪后清除选框
        self.preview_label.clear_selection()

    def _on_watermark_position_changed(self, position: str):
        """当水印位置选择改变时的回调"""
        if position == "自定义":
            self.wm_custom_pos_container.setVisible(True)
            # 更新自定义位置的取值范围
            if self.current_image:
                self.wm_custom_x.setRange(0, self.current_image.width)
                self.wm_custom_y.setRange(0, self.current_image.height)
            # 启用水印位置选择模式
            if self.preview_label._original_pixmap is not None:
                self.preview_label.set_watermark_mode(True)
                # 更新水印预览
                self._update_watermark_preview()
        else:
            self.wm_custom_pos_container.setVisible(False)
            # 禁用水印位置选择模式
            self.preview_label.set_watermark_mode(False)
            self.preview_label.clear_watermark_preview()
            # 更新水印预览（使用预设位置）
            self._update_watermark_preview()
    
    def on_watermark_position_selected(self, x: int, y: int):
        """水印位置选择完成时的回调"""
        # 更新自定义位置输入框
        self.wm_custom_x.setValue(x)
        self.wm_custom_y.setValue(y)
        # 更新预览
        self._update_watermark_preview()
    
    def _update_watermark_preview(self):
        """更新水印预览（文本、字体、大小、位置、透明度）"""
        if not self.current_image or not self.preview_label._watermark_mode:
            return
        
        # 获取水印参数
        text = self.wm_text.text() if hasattr(self, 'wm_text') else ""
        font_family = self.watermark_font_path if self.watermark_font_path else "Arial"
        font_size = self.wm_size.value() if hasattr(self, 'wm_size') else 36
        opacity = self.wm_op.value() / 100.0 if hasattr(self, 'wm_op') else 0.7
        position = self.wm_pos.currentText() if hasattr(self, 'wm_pos') else "bottom-right"
        
        # 转换位置名称
        pos_map = {
            "bottom-right": "bottom-right",
            "bottom-left": "bottom-left",
            "top-left": "top-left",
            "top-right": "top-right",
            "center": "center",
            "自定义": "custom"
        }
        position = pos_map.get(position, "bottom-right")
        
        # 获取自定义位置坐标
        x = None
        y = None
        if position == "custom" and hasattr(self, 'wm_custom_x') and hasattr(self, 'wm_custom_y'):
            x = self.wm_custom_x.value()
            y = self.wm_custom_y.value()
        
        # 更新预览
        self.preview_label.set_watermark_preview(text, font_family, font_size, opacity, position, x, y)
    
    def _on_watermark_text_changed(self, text: str):
        """水印文本改变时的回调"""
        if self.preview_label._watermark_mode:
            self._update_watermark_preview()
    
    def _on_watermark_size_changed(self, size: int):
        """水印大小改变时的回调"""
        if self.preview_label._watermark_mode:
            self._update_watermark_preview()
    
    def _on_watermark_custom_pos_changed(self, value: int):
        """水印自定义位置改变时的回调（实时更新预览）"""
        if self.preview_label._watermark_mode:
            self._update_watermark_preview()

    def select_watermark_font(self):
        """选择水印字体"""
        # 创建字体对话框实例，禁用原生对话框以使用Qt样式
        dialog = QFontDialog(self)
        # 禁用原生对话框，强制使用Qt自己的对话框（这样QSS样式才能生效）
        dialog.setOption(QFontDialog.FontDialogOption.DontUseNativeDialog, True)
        
        # 如果之前选择过字体，设置当前字体
        if self.watermark_font_path:
            from PyQt6.QtGui import QFont
            current_font = QFont(self.watermark_font_path)
            dialog.setCurrentFont(current_font)
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            font = dialog.currentFont()
            # 保存字体信息（PyQt6的QFont需要转换为PIL可用的路径）
            # 这里简化处理，实际使用时需要根据系统获取字体文件路径
            self.watermark_font_path = font.family()
            # 更新水印预览
            if self.preview_label._watermark_mode:
                self._update_watermark_preview()
            QMessageBox.information(self, "提示", f"已选择字体: {font.family()}")

    def apply_watermark(self):
        if self.current_image is None:
            return

        text = self.wm_text.text()
        if not text.strip():
            QMessageBox.warning(self, "提示", "请输入水印文本")
            return

        pos = self.wm_pos.currentText()
        size = self.wm_size.value()
        opacity = self.wm_op.value() / 100.0

        # 处理自定义位置
        x = None
        y = None
        if pos == "自定义":
            x = self.wm_custom_x.value()
            y = self.wm_custom_y.value()
            pos = "custom"

        self.push_history()
        self.worker = WorkerThread(
            ImageTools.add_text_watermark,
            self.current_image, text, pos, x, y, self.watermark_font_path, size, opacity
        )
        self.worker.finished_image.connect(self.on_worker_finished)
        self.worker.start()

    def on_crop_ratio_changed(self, index: int):
        """预设比例改变时的回调"""
        # 比例映射：宽/高
        ratio_map = {
            0: None,  # 自由
            1: 1.0,   # 1:1
            2: 4.0 / 3.0,  # 4:3
            3: 16.0 / 9.0,  # 16:9
            4: 3.0 / 2.0,   # 3:2
            5: 21.0 / 9.0,  # 21:9
            6: 9.0 / 16.0,  # 9:16
            7: 2.0 / 3.0,   # 2:3
        }
        ratio = ratio_map.get(index, None)
        self.preview_label.set_aspect_ratio(ratio)

    # ------------------ 鼠标框选裁剪回调 ------------------
    def on_selection_finished(self, rect: QRect):
        """当用户在预览区域拖拽选择完成后，将屏幕坐标转换为图片坐标。"""
        if self.current_image is None:
            self.preview_label.clear_selection()
            return

        # 使用CropLabel的坐标转换方法（考虑缩放和偏移）
        img_rect = self.preview_label.screen_rect_to_image_rect(rect)
        
        if img_rect is None or img_rect.width() < 5 or img_rect.height() < 5:
            # 转换失败或区域过小，忽略
            self.preview_label.clear_selection()
            return
        
        # 获取图片坐标
        img_left = img_rect.left()
        img_top = img_rect.top()
        img_w = img_rect.width()
        img_h = img_rect.height()

        # 同步更新右侧输入框，方便用户看到具体数值
        self.crop_left.setText(str(img_left))
        self.crop_top.setText(str(img_top))
        self.crop_w.setText(str(img_w))
        self.crop_h.setText(str(img_h))

    # ------------------ 撤销 ------------------
    def undo(self):
        if not self.history:
            QMessageBox.information(self, "提示", "无可撤销操作")
            return
        # 将当前状态保存到重做历史
        if self.current_image:
            self.redo_history.append(self.current_image.copy())
            if len(self.redo_history) > self.max_history:
                self.redo_history.pop(0)
        # 恢复到上一个历史状态
        self.current_image = self.history.pop()
        self.update_preview()

    # ------------------ 重做 ------------------
    def redo(self):
        if not self.redo_history:
            QMessageBox.information(self, "提示", "无可重做操作")
            return
        # 将当前状态保存到撤销历史
        if self.current_image:
            self.history.append(self.current_image.copy())
            if len(self.history) > self.max_history:
                self.history.pop(0)
        # 恢复到重做历史中的状态
        self.current_image = self.redo_history.pop()
        self.update_preview()

    # ------------------ 滤镜功能 ------------------
    def _on_filter_changed(self, filter_type: str, checked: bool):
        """当滤镜选择改变时的回调"""
        if not checked:
            return
        self.current_filter = filter_type
        # 显示/隐藏模糊滑块
        if filter_type == "blur":
            self.blur_slider_container.setVisible(True)
        else:
            self.blur_slider_container.setVisible(False)

    def apply_filter(self):
        """应用选中的滤镜"""
        if self.current_image is None:
            return

        self.push_history()

        if self.current_filter == "none":
            # 无滤镜，不做处理
            self.update_preview()
            return
        elif self.current_filter == "grayscale":
            self.worker = WorkerThread(ImageTools.grayscale, self.current_image)
        elif self.current_filter == "blur":
            radius = self.blur_slider.value() / 10.0  # 转换为实际半径值
            self.worker = WorkerThread(ImageTools.blur, self.current_image, radius)
        elif self.current_filter == "vintage":
            self.worker = WorkerThread(ImageTools.vintage, self.current_image)
        else:
            return

        self.worker.finished_image.connect(self.on_worker_finished)
        self.worker.start()

    # ------------------ 批量处理 ------------------
    def show_batch_process_dialog(self):
        """显示批量处理对话框"""
        dialog = BatchProcessDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.process_batch_files(
                dialog.input_folder,
                dialog.output_folder,
                dialog.target_format,
                dialog.resize_enabled,
                dialog.target_width,
                dialog.rename_enabled,
                dialog.rename_prefix
            )

    def process_batch_files(self, input_folder, output_folder, target_format,
                           resize_enabled, target_width, rename_enabled, rename_prefix):
        """批量处理文件"""
        # 支持的图片格式
        extensions = ['*.png', '*.jpg', '*.jpeg', '*.bmp', '*.PNG', '*.JPG', '*.JPEG', '*.BMP']
        image_files = []
        for ext in extensions:
            image_files.extend(glob.glob(os.path.join(input_folder, ext)))

        if not image_files:
            QMessageBox.warning(self, "提示", "未找到图片文件")
            return

        # 创建输出目录
        if not os.path.exists(output_folder):
            os.makedirs(output_folder)

        # 进度对话框
        progress = QProgressDialog("正在处理...", "取消", 0, len(image_files), self)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.show()

        success_count = 0
        error_count = 0

        for i, file_path in enumerate(image_files):
            if progress.wasCanceled():
                break

            try:
                # 打开图片
                img = Image.open(file_path)
                img = ImageTools.ensure_rgb(img)

                # 调整尺寸
                if resize_enabled and target_width > 0:
                    ratio = target_width / img.width
                    new_height = int(img.height * ratio)
                    img = img.resize((target_width, new_height), Image.Resampling.LANCZOS)

                # 生成输出文件名
                if rename_enabled:
                    base_name = f"{rename_prefix}_{i+1:03d}"
                else:
                    base_name = os.path.splitext(os.path.basename(file_path))[0]

                # 确定格式
                if target_format == "JPG":
                    fmt = "JPEG"
                    ext = ".jpg"
                elif target_format == "PNG":
                    fmt = "PNG"
                    ext = ".png"
                elif target_format == "BMP":
                    fmt = "BMP"
                    ext = ".bmp"
                else:
                    fmt = "PNG"
                    ext = ".png"

                output_path = os.path.join(output_folder, f"{base_name}{ext}")
                img.save(output_path, format=fmt)
                success_count += 1

            except Exception as e:
                print(f"处理文件失败 {file_path}: {e}")
                error_count += 1

            progress.setValue(i + 1)

        progress.close()

        # 显示结果
        msg = f"处理完成！\n成功: {success_count} 个\n失败: {error_count} 个"
        QMessageBox.information(self, "批量处理完成", msg)

    # ------------------ 线程回调 ------------------
    def on_worker_finished(self, img):
        self.current_image = img
        self.update_preview()
        self.worker = None

    # ------------------ 放映功能 ------------------
    def start_slideshow(self):
        """开始放映"""
        # 创建放映窗口（会自动显示选择对话框）
        try:
            from .slideshow_window import SlideshowWindow
            slideshow = SlideshowWindow(self)
            # 确保窗口正确显示
            slideshow.show()
            slideshow.raise_()
            slideshow.activateWindow()
        except ImportError:
            # 如果相对导入失败，尝试绝对导入
            try:
                from ui.slideshow_window import SlideshowWindow
                slideshow = SlideshowWindow(self)
                # 确保窗口正确显示
                slideshow.show()
                slideshow.raise_()
                slideshow.activateWindow()
            except ImportError as e:
                QMessageBox.warning(self, "错误", f"导入放映窗口失败：{str(e)}")


# ------------------ 批量处理对话框 ------------------
class BatchProcessDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("批量处理")
        self.setMinimumWidth(500)

        layout = QVBoxLayout(self)

        # 输入文件夹
        input_layout = QHBoxLayout()
        input_layout.addWidget(QLabel("输入文件夹:"))
        self.input_folder_edit = QLineEdit()
        self.input_folder_edit.setReadOnly(True)
        input_layout.addWidget(self.input_folder_edit)
        input_btn = QPushButton("浏览...")
        input_btn.clicked.connect(self.select_input_folder)
        input_layout.addWidget(input_btn)
        input_widget = QWidget()
        input_widget.setLayout(input_layout)
        layout.addWidget(input_widget)

        # 输出文件夹
        output_layout = QHBoxLayout()
        output_layout.addWidget(QLabel("输出文件夹:"))
        self.output_folder_edit = QLineEdit()
        self.output_folder_edit.setReadOnly(True)
        output_layout.addWidget(self.output_folder_edit)
        output_btn = QPushButton("浏览...")
        output_btn.clicked.connect(self.select_output_folder)
        output_layout.addWidget(output_btn)
        output_widget = QWidget()
        output_widget.setLayout(output_layout)
        layout.addWidget(output_widget)

        # 格式选择
        format_layout = QHBoxLayout()
        format_layout.addWidget(QLabel("输出格式:"))
        self.format_combo = QComboBox()
        self.format_combo.addItems(["PNG", "JPG", "BMP"])
        format_layout.addWidget(self.format_combo)
        format_layout.addStretch()
        format_widget = QWidget()
        format_widget.setLayout(format_layout)
        layout.addWidget(format_widget)

        # 统一尺寸
        self.resize_check = QCheckBox("统一尺寸")
        self.resize_check.toggled.connect(self._on_resize_toggled)
        layout.addWidget(self.resize_check)

        resize_layout = QHBoxLayout()
        resize_layout.addWidget(QLabel("宽度:"))
        self.width_spin = NumberInput()
        self.width_spin.setRange(100, 10000)
        self.width_spin.setValue(1920)
        self.width_spin.setEnabled(False)
        resize_layout.addWidget(self.width_spin)
        resize_layout.addWidget(QLabel("px (高度自动计算，保持比例)"))
        resize_layout.addStretch()
        resize_widget = QWidget()
        resize_widget.setLayout(resize_layout)
        layout.addWidget(resize_widget)

        # 重命名
        self.rename_check = QCheckBox("重命名")
        self.rename_check.toggled.connect(self._on_rename_toggled)
        layout.addWidget(self.rename_check)

        rename_layout = QHBoxLayout()
        rename_layout.addWidget(QLabel("前缀:"))
        self.rename_prefix_edit = QLineEdit("image")
        self.rename_prefix_edit.setEnabled(False)
        rename_layout.addWidget(self.rename_prefix_edit)
        rename_layout.addWidget(QLabel("(格式: 前缀_001.jpg)"))
        rename_layout.addStretch()
        rename_widget = QWidget()
        rename_widget.setLayout(rename_layout)
        layout.addWidget(rename_widget)

        # 按钮
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def select_input_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "选择输入文件夹")
        if folder:
            self.input_folder_edit.setText(folder)

    def select_output_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "选择输出文件夹")
        if folder:
            self.output_folder_edit.setText(folder)

    def _on_resize_toggled(self, checked):
        self.width_spin.setEnabled(checked)

    def _on_rename_toggled(self, checked):
        self.rename_prefix_edit.setEnabled(checked)

    def accept(self):
        self.input_folder = self.input_folder_edit.text()
        self.output_folder = self.output_folder_edit.text()
        self.target_format = self.format_combo.currentText()
        self.resize_enabled = self.resize_check.isChecked()
        self.target_width = self.width_spin.value() if self.resize_enabled else 0
        self.rename_enabled = self.rename_check.isChecked()
        self.rename_prefix = self.rename_prefix_edit.text() if self.rename_enabled else ""

        if not self.input_folder or not os.path.exists(self.input_folder):
            QMessageBox.warning(self, "错误", "请选择有效的输入文件夹")
            return

        if not self.output_folder:
            QMessageBox.warning(self, "错误", "请选择输出文件夹")
            return

        super().accept()


# ------------------ 外观设置对话框 ------------------
class AppearanceDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("外观设置")
        self.setMinimumWidth(300)

        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("主题:"))
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["跟随系统", "浅色", "深色"])
        
        # 读取当前设置
        settings = QSettings("ImageTool", "Settings")
        current_theme = settings.value("theme", "auto", type=str)
        if current_theme == "auto":
            self.theme_combo.setCurrentIndex(0)
        elif current_theme == "light":
            self.theme_combo.setCurrentIndex(1)
        else:
            self.theme_combo.setCurrentIndex(2)
        
        layout.addWidget(self.theme_combo)

        # 按钮
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def accept(self):
        # 保存设置
        settings = QSettings("ImageTool", "Settings")
        index = self.theme_combo.currentIndex()
        if index == 0:
            theme = "auto"
        elif index == 1:
            theme = "light"
        else:
            theme = "dark"
        
        settings.setValue("theme", theme)
        super().accept()

