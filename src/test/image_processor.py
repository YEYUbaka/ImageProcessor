# image_processor.py
import sys
import os
from PIL import Image, ImageDraw, ImageFont
from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal
from PyQt6.QtGui import QAction, QPixmap, QImage
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QLabel, QVBoxLayout, QHBoxLayout,
    QPushButton, QFileDialog, QWidget, QGroupBox, QSlider,
    QLineEdit, QComboBox, QSpinBox, QMessageBox, QMenuBar
)


# 图像处理工作线程类
class ImageProcessorThread(QThread):
    processed = pyqtSignal(object)  # 发送处理后的图像数据
    error = pyqtSignal(str)         # 发送错误信息
    
    def __init__(self, operation, *args):
        super().__init__()
        self.operation = operation
        self.args = args
        
    def run(self):
        try:
            if self.operation == "scale":
                original_image, factor = self.args
                # 基于原始图像进行缩放
                new_width = max(10, int(original_image.width * factor))
                new_height = max(10, int(original_image.height * factor))
                result = original_image.resize((new_width, new_height), Image.Resampling.LANCZOS)
                self.processed.emit(result)
                
            elif self.operation == "rotate":
                image, angle = self.args
                result = image.copy().rotate(angle, expand=True)
                self.processed.emit(result)
                
            elif self.operation == "watermark":
                image, text = self.args
                result = image.copy()
                draw = ImageDraw.Draw(result)
                
                # 加载字体
                try:
                    font = ImageFont.truetype("arial.ttf", 36)
                except:
                    try:
                        font = ImageFont.truetype("simhei.ttf", 36)
                    except:
                        font = ImageFont.load_default()
                        
                # 计算水印位置
                width, height = result.size
                bbox = draw.textbbox((0, 0), text, font=font)
                text_width = bbox[2] - bbox[0]
                text_height = bbox[3] - bbox[1]
                x = width - text_width - 10
                y = height - text_height - 10
                
                # 绘制水印
                draw.text((x, y), text, fill="white", font=font, stroke_width=1, stroke_fill="black")
                self.processed.emit(result)
                
        except Exception as e:
            self.error.emit(str(e))


class ImageProcessorApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("简易图片处理工具")
        self.setGeometry(100, 100, 800, 600)

        # 初始化变量
        self.image = None
        self.original_image = None  # 保留原始图像用于重置
        self.current_operation_thread = None
        
        # 创建中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # 主布局
        main_layout = QHBoxLayout()
        central_widget.setLayout(main_layout)

        # 左侧功能区
        self.create_left_panel(main_layout)

        # 中间预览区
        self.create_preview_area(main_layout)

        # 右侧参数调节区
        self.create_right_panel(main_layout)

        # 菜单栏
        self.create_menu_bar()

        # 状态栏
        self.statusBar().showMessage("就绪")

    def create_menu_bar(self):
        menubar = self.menuBar()

        # 文件菜单
        file_menu = menubar.addMenu("文件")
        open_action = QAction("打开", self)
        open_action.triggered.connect(self.open_image)
        file_menu.addAction(open_action)

        save_action = QAction("保存", self)
        save_action.triggered.connect(self.save_image)
        file_menu.addAction(save_action)

        exit_action = QAction("退出", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # 编辑菜单
        edit_menu = menubar.addMenu("编辑")
        reset_action = QAction("重置", self)
        reset_action.triggered.connect(self.reset_image)
        edit_menu.addAction(reset_action)

    def create_left_panel(self, layout):
        left_widget = QWidget()
        left_layout = QVBoxLayout()
        left_widget.setLayout(left_layout)

        # 功能按钮
        btn_open = QPushButton("打开图片")
        btn_open.clicked.connect(self.open_image)
        left_layout.addWidget(btn_open)

        btn_save = QPushButton("保存图片")
        btn_save.clicked.connect(self.save_image)
        left_layout.addWidget(btn_save)

        btn_zoom_in = QPushButton("放大")
        btn_zoom_in.clicked.connect(lambda: self.scale_image(1.2))
        left_layout.addWidget(btn_zoom_in)

        btn_zoom_out = QPushButton("缩小")
        btn_zoom_out.clicked.connect(lambda: self.scale_image(0.8))
        left_layout.addWidget(btn_zoom_out)

        btn_rotate = QPushButton("旋转90°")
        btn_rotate.clicked.connect(self.rotate_image)
        left_layout.addWidget(btn_rotate)

        btn_crop = QPushButton("裁剪")
        btn_crop.clicked.connect(self.start_crop)
        left_layout.addWidget(btn_crop)

        btn_watermark = QPushButton("添加水印")
        btn_watermark.clicked.connect(self.add_watermark)
        left_layout.addWidget(btn_watermark)

        btn_convert = QPushButton("格式转换")
        btn_convert.clicked.connect(self.convert_format)
        left_layout.addWidget(btn_convert)

        layout.addWidget(left_widget)

    def create_preview_area(self, layout):
        preview_widget = QWidget()
        preview_layout = QVBoxLayout()
        preview_widget.setLayout(preview_layout)

        self.preview_label = QLabel()
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setStyleSheet("border: 1px solid gray; background-color: white;")
        self.preview_label.setMinimumSize(400, 400)
        preview_layout.addWidget(self.preview_label)

        layout.addWidget(preview_widget)

    def create_right_panel(self, layout):
        right_widget = QWidget()
        right_layout = QVBoxLayout()
        right_widget.setLayout(right_layout)

        # 缩放滑块
        scale_group = QGroupBox("缩放比例")
        scale_layout = QHBoxLayout()
        self.scale_slider = QSlider(Qt.Orientation.Horizontal)
        self.scale_slider.setMinimum(50)
        self.scale_slider.setMaximum(200)
        self.scale_slider.setValue(100)
        self.scale_slider.valueChanged.connect(self.on_scale_changed)
        self.scale_timer = QTimer()
        self.scale_timer.setSingleShot(True)
        self.scale_timer.timeout.connect(self.apply_scale)
        scale_layout.addWidget(self.scale_slider)
        scale_group.setLayout(scale_layout)
        right_layout.addWidget(scale_group)

        # 旋转角度
        rotate_group = QGroupBox("旋转角度")
        rotate_layout = QHBoxLayout()
        self.rotate_spinbox = QSpinBox()
        self.rotate_spinbox.setMinimum(0)
        self.rotate_spinbox.setMaximum(360)
        self.rotate_spinbox.setValue(0)
        self.rotate_spinbox.valueChanged.connect(self.rotate_image_by_angle)
        rotate_layout.addWidget(self.rotate_spinbox)
        rotate_group.setLayout(rotate_layout)
        right_layout.addWidget(rotate_group)

        # 水印文本
        watermark_group = QGroupBox("水印文本")
        wm_layout = QHBoxLayout()
        self.watermark_edit = QLineEdit("Hello World")
        wm_layout.addWidget(self.watermark_edit)
        watermark_group.setLayout(wm_layout)
        right_layout.addWidget(watermark_group)

        # 格式选择
        format_group = QGroupBox("输出格式")
        fmt_layout = QHBoxLayout()
        self.format_combo = QComboBox()
        self.format_combo.addItems(["JPG", "PNG", "BMP"])
        fmt_layout.addWidget(self.format_combo)
        format_group.setLayout(fmt_layout)
        right_layout.addWidget(format_group)

        layout.addWidget(right_widget)

    def on_scale_changed(self, value):
        # 使用定时器延迟处理缩放，避免频繁触发
        self.scale_timer.start(200)  # 200毫秒延迟

    def apply_scale(self):
        value = self.scale_slider.value()
        self.scale_image(value / 100.0)

    def open_image(self):
        # 如果有正在进行的操作，等待其完成
        if self.current_operation_thread and self.current_operation_thread.isRunning():
            self.current_operation_thread.wait()
            
        file_dialog = QFileDialog()
        file_path, _ = file_dialog.getOpenFileName(
            self, "打开图片", "", "图片文件 (*.jpg *.jpeg *.png *.bmp);;所有文件 (*)"
        )
        if not file_path:
            return

        try:
            # 打开图像并确保是RGB模式以避免潜在问题
            self.original_image = Image.open(file_path).convert("RGB")
            self.image = self.original_image.copy()
            self.update_preview()
            self.statusBar().showMessage(f"已加载: {os.path.basename(file_path)}")
            # 重置缩放滑块值
            self.scale_slider.setValue(100)
        except Exception as e:
            QMessageBox.critical(self, "错误", f"无法打开图片: {str(e)}")

    def update_preview(self):
        if self.image is None:
            self.preview_label.setText("无图片")
            return

        try:
            # 转换为 QPixmap 显示
            img_rgb = self.image.convert("RGB")
            
            # 使用更安全的方式创建QImage
            data = img_rgb.tobytes()
            qimage = QImage(data, img_rgb.width, img_rgb.height, QImage.Format.Format_RGB888)
            
            # 创建pixmap并缩放
            pixmap = QPixmap.fromImage(qimage)
            scaled_pixmap = pixmap.scaled(
                self.preview_label.width(), 
                self.preview_label.height(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            
            # 清除并设置新图像
            self.preview_label.clear()
            self.preview_label.setPixmap(scaled_pixmap)
        except Exception as e:
            print(f"预览更新错误: {e}")

    def scale_image(self, factor):
        if self.image is None or self.original_image is None:
            return
            
        # 如果有正在进行的操作，等待其完成
        if self.current_operation_thread and self.current_operation_thread.isRunning():
            self.current_operation_thread.wait()
            
        # 启动图像处理线程
        self.current_operation_thread = ImageProcessorThread("scale", self.original_image, factor)
        self.current_operation_thread.processed.connect(self.on_image_processed)
        self.current_operation_thread.error.connect(self.on_processing_error)
        self.current_operation_thread.start()

    def rotate_image_by_angle(self):
        angle = self.rotate_spinbox.value()
        self.rotate_image_internal(angle)

    def rotate_image(self):
        self.rotate_image_internal(90)

    def rotate_image_internal(self, angle):
        if self.image is None:
            return
            
        # 如果有正在进行的操作，等待其完成
        if self.current_operation_thread and self.current_operation_thread.isRunning():
            self.current_operation_thread.wait()
            
        # 启动图像处理线程
        self.current_operation_thread = ImageProcessorThread("rotate", self.image, angle)
        self.current_operation_thread.processed.connect(self.on_image_processed)
        self.current_operation_thread.error.connect(self.on_processing_error)
        self.current_operation_thread.start()

    def add_watermark(self):
        if self.image is None:
            return
            
        text = self.watermark_edit.text()
        if not text.strip():
            return
            
        # 如果有正在进行的操作，等待其完成
        if self.current_operation_thread and self.current_operation_thread.isRunning():
            self.current_operation_thread.wait()
            
        # 启动图像处理线程
        self.current_operation_thread = ImageProcessorThread("watermark", self.image, text)
        self.current_operation_thread.processed.connect(self.on_image_processed)
        self.current_operation_thread.error.connect(self.on_processing_error)
        self.current_operation_thread.start()

    def on_image_processed(self, processed_image):
        """处理完成后的回调"""
        self.image = processed_image
        self.update_preview()
        
    def on_processing_error(self, error_msg):
        """处理出错的回调"""
        QMessageBox.critical(self, "错误", f"图像处理失败: {error_msg}")

    def start_crop(self):
        if self.image is None:
            return
        # 这里可以扩展为拖拽选区，暂用弹窗提示
        QMessageBox.information(self, "提示", "裁剪功能尚未实现，可使用外部工具或扩展此功能。")

    def convert_format(self):
        if self.image is None:
            return
            
        try:
            fmt = self.format_combo.currentText().lower()
            if fmt == "jpg":
                fmt = "JPEG"
            elif fmt == "png":
                fmt = "PNG"
            elif fmt == "bmp":
                fmt = "BMP"

            # 临时保存为新格式
            temp_path = "temp_output." + fmt.lower()
            self.image.save(temp_path, format=fmt)
            QMessageBox.information(self, "成功", f"已保存为 {temp_path}")
            self.statusBar().showMessage(f"已转换为 {fmt} 格式")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"保存失败: {str(e)}")

    def save_image(self):
        if self.image is None:
            QMessageBox.warning(self, "警告", "没有图片可保存！")
            return

        file_dialog = QFileDialog()
        file_path, _ = file_dialog.getSaveFileName(
            self, "保存图片", "", "图片文件 (*.jpg *.jpeg *.png *.bmp);;所有文件 (*)"
        )
        if not file_path:
            return

        try:
            ext = os.path.splitext(file_path)[1].lower()
            if ext in [".jpg", ".jpeg"]:
                fmt = "JPEG"
            elif ext == ".png":
                fmt = "PNG"
            elif ext == ".bmp":
                fmt = "BMP"
            else:
                fmt = "PNG"

            self.image.save(file_path, format=fmt)
            self.statusBar().showMessage(f"已保存: {os.path.basename(file_path)}")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"保存失败: {str(e)}")

    def reset_image(self):
        if self.original_image is None:
            return
            
        # 如果有正在进行的操作，等待其完成
        if self.current_operation_thread and self.current_operation_thread.isRunning():
            self.current_operation_thread.wait()
            
        try:
            self.image = self.original_image.copy()
            self.update_preview()
            self.scale_slider.setValue(100)
            self.rotate_spinbox.setValue(0)
        except Exception as e:
            print(f"重置图像出错: {e}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ImageProcessorApp()
    window.show()
    sys.exit(app.exec())