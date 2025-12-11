# image_processor_refactor.py
"""
简易图片处理工具 - 重构单文件实现

依赖:
    pip install PyQt6 Pillow

功能:
    - 打开图片 (JPEG/PNG/BMP 等)
    - 保存图片 / 格式转换
    - 缩放（滑块与放大/缩小按钮）
    - 旋转（任意角度或 90°）
    - 裁剪（输入坐标/宽高的简易裁剪）
    - 添加文字水印（可选位置、大小、透明度）
    - 重置、撤销
    - 现代化 QSS 风格（Win11 类）
"""

import sys
import os
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSize
from PyQt6.QtGui import QPixmap, QImage, QAction, QIcon
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QPushButton, QLabel, QFileDialog, QSlider, QGroupBox,
    QSpinBox, QLineEdit, QComboBox, QMessageBox, QScrollArea,
    QToolButton, QSizePolicy, QStyle
)

# ---------------------------
# 图像处理工具类（Pillow 封装）
# ---------------------------
class ImageTools:
    @staticmethod
    def ensure_rgb(img: Image.Image):
        if img.mode != "RGB":
            return img.convert("RGB")
        return img

    @staticmethod
    def scale(img: Image.Image, factor: float) -> Image.Image:
        img = ImageTools.ensure_rgb(img)
        new_w = max(1, int(img.width * factor))
        new_h = max(1, int(img.height * factor))
        return img.resize((new_w, new_h), Image.Resampling.LANCZOS)

    @staticmethod
    def rotate(img: Image.Image, angle: float) -> Image.Image:
        img = ImageTools.ensure_rgb(img)
        return img.rotate(angle, expand=True, resample=Image.Resampling.BICUBIC)

    @staticmethod
    def crop(img: Image.Image, left: int, top: int, width: int, height: int) -> Image.Image:
        img = ImageTools.ensure_rgb(img)
        right = left + width
        bottom = top + height
        # 限制到图像范围
        left = max(0, min(left, img.width - 1))
        top = max(0, min(top, img.height - 1))
        right = max(left + 1, min(right, img.width))
        bottom = max(top + 1, min(bottom, img.height))
        return img.crop((left, top, right, bottom))

    @staticmethod
    def add_text_watermark(img: Image.Image, text: str, position: str = "bottom-right",
                           font_path: str = None, font_size: int = 36, opacity: float = 0.6) -> Image.Image:
        img = ImageTools.ensure_rgb(img).copy()
        drawable = Image.new("RGBA", img.size)
        draw = ImageDraw.Draw(drawable)

        # 字体尝试加载优先级
        font = None
        if font_path:
            try:
                font = ImageFont.truetype(font_path, font_size)
            except Exception:
                font = None
        if not font:
            try:
                font = ImageFont.truetype("arial.ttf", font_size)
            except Exception:
                try:
                    font = ImageFont.truetype("DejaVuSans.ttf", font_size)
                except Exception:
                    font = ImageFont.load_default()

        # 计算文本大小
        bbox = draw.textbbox((0, 0), text, font=font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]

        margin = int(0.03 * min(img.size))  # 边距随图像尺寸缩放
        if position == "bottom-right":
            x = img.width - text_w - margin
            y = img.height - text_h - margin
        elif position == "bottom-left":
            x = margin
            y = img.height - text_h - margin
        elif position == "top-left":
            x = margin
            y = margin
        elif position == "top-right":
            x = img.width - text_w - margin
            y = margin
        elif position == "center":
            x = (img.width - text_w) // 2
            y = (img.height - text_h) // 2
        else:
            x, y = margin, img.height - text_h - margin

        # 绘制含描边的文本到透明层
        stroke_width = max(1, font_size // 18)
        draw.text((x, y), text, font=font, fill=(255, 255, 255, int(255 * opacity)),
                  stroke_width=stroke_width, stroke_fill=(0, 0, 0, int(255 * opacity)))
        combined = Image.alpha_composite(img.convert("RGBA"), drawable)
        return combined.convert("RGB")

    @staticmethod
    def save_image(img: Image.Image, path: str, fmt: str = None, quality: int = 95):
        img = ImageTools.ensure_rgb(img)
        if not fmt:
            ext = os.path.splitext(path)[1].lower()
            if ext in [".jpg", ".jpeg"]:
                fmt = "JPEG"
            elif ext == ".png":
                fmt = "PNG"
            elif ext == ".bmp":
                fmt = "BMP"
            else:
                fmt = "PNG"
        img.save(path, format=fmt, quality=quality)


# ---------------------------
# 后台处理线程（用于耗时操作）
# ---------------------------
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


# ---------------------------
# 主窗口
# ---------------------------
class ImageProcessorApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("简易图片处理工具")
        self.setMinimumSize(1000, 640)

        # 应用图像状态
        self.original_image = None   # 始终保存原始（打开时）
        self.current_image = None    # 当前显示编辑后的图像
        self.history = []            # 撤销栈（保存 PIL 图像）
        self.max_history = 10

        # 当前后台线程（用于等待或取消）
        self.worker = None

        # UI 结构
        self._build_ui()
        self._apply_qss()

    # ---------------------------
    # UI 构建
    # ---------------------------
    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QHBoxLayout()
        central.setLayout(layout)

        # 左侧功能栏（竖向）
        left_bar = QVBoxLayout()
        left_widget = QWidget()
        left_widget.setLayout(left_bar)
        left_widget.setFixedWidth(140)
        layout.addWidget(left_widget)

        # 按钮样式：图标可替换为 svg 文件
        self.btn_open = QToolButton()
        self.btn_open.setText("打开")
        self.btn_open.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        self.btn_open.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogOpenButton))
        self.btn_open.clicked.connect(self.open_image)
        left_bar.addWidget(self.btn_open)

        self.btn_save = QToolButton()
        self.btn_save.setText("保存")
        self.btn_save.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogSaveButton))
        self.btn_save.clicked.connect(self.save_image)
        left_bar.addWidget(self.btn_save)

        left_bar.addSpacing(8)

        self.btn_zoom_in = QPushButton("放大")
        self.btn_zoom_in.clicked.connect(lambda: self.apply_scale(1.2))
        left_bar.addWidget(self.btn_zoom_in)

        self.btn_zoom_out = QPushButton("缩小")
        self.btn_zoom_out.clicked.connect(lambda: self.apply_scale(0.8))
        left_bar.addWidget(self.btn_zoom_out)

        self.btn_rotate90 = QPushButton("旋转90°")
        self.btn_rotate90.clicked.connect(lambda: self.apply_rotate(90))
        left_bar.addWidget(self.btn_rotate90)

        self.btn_undo = QPushButton("撤销")
        self.btn_undo.clicked.connect(self.undo)
        left_bar.addWidget(self.btn_undo)

        left_bar.addStretch(1)

        # 中间预览区（QScrollArea + QLabel）
        preview_area = QVBoxLayout()
        preview_widget = QWidget()
        preview_widget.setLayout(preview_area)
        layout.addWidget(preview_widget, stretch=1)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.preview_label = QLabel()
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
        self.preview_label.setStyleSheet("background-color: #1e1e1e; color: white;")
        self.scroll.setWidget(self.preview_label)
        preview_area.addWidget(self.scroll)

        self.status_label = QLabel("就绪")
        preview_area.addWidget(self.status_label)

        # 右侧参数区
        right_bar = QVBoxLayout()
        right_widget = QWidget()
        right_widget.setLayout(right_bar)
        right_widget.setFixedWidth(320)
        layout.addWidget(right_widget)

        # 缩放组
        scale_group = QGroupBox("缩放")
        s_layout = QVBoxLayout()
        scale_group.setLayout(s_layout)
        self.scale_slider = QSlider(Qt.Orientation.Horizontal)
        self.scale_slider.setMinimum(10)
        self.scale_slider.setMaximum(300)
        self.scale_slider.setValue(100)
        self.scale_slider.valueChanged.connect(self.on_scale_slider)
        s_layout.addWidget(self.scale_slider)
        self.scale_label = QLabel("100%")
        s_layout.addWidget(self.scale_label)
        s_btns = QHBoxLayout()
        btn_apply_scale = QPushButton("应用缩放")
        btn_apply_scale.clicked.connect(self.on_scale_slider_apply)
        s_btns.addWidget(btn_apply_scale)
        btn_reset_view = QPushButton("重置视图")
        btn_reset_view.clicked.connect(self.reset_view)
        s_btns.addWidget(btn_reset_view)
        s_layout.addLayout(s_btns)
        right_bar.addWidget(scale_group)

        # 旋转组
        rotate_group = QGroupBox("旋转")
        r_layout = QVBoxLayout()
        rotate_group.setLayout(r_layout)
        self.rotate_spin = QSpinBox()
        self.rotate_spin.setRange(-360, 360)
        self.rotate_spin.setValue(0)
        r_layout.addWidget(self.rotate_spin)
        r_btns = QHBoxLayout()
        btn_apply_rotate = QPushButton("应用旋转")
        btn_apply_rotate.clicked.connect(lambda: self.apply_rotate(self.rotate_spin.value()))
        r_btns.addWidget(btn_apply_rotate)
        btn_rotate_ccw = QPushButton("逆时针90°")
        btn_rotate_ccw.clicked.connect(lambda: self.apply_rotate(-90))
        r_btns.addWidget(btn_rotate_ccw)
        r_layout.addLayout(r_btns)
        right_bar.addWidget(rotate_group)

        # 裁剪组
        crop_group = QGroupBox("裁剪（输入像素）")
        crop_layout = QVBoxLayout()
        crop_group.setLayout(crop_layout)
        self.crop_left = QLineEdit("0")
        self.crop_top = QLineEdit("0")
        self.crop_w = QLineEdit("100")
        self.crop_h = QLineEdit("100")
        crop_layout.addWidget(QLabel("左:"))
        crop_layout.addWidget(self.crop_left)
        crop_layout.addWidget(QLabel("上:"))
        crop_layout.addWidget(self.crop_top)
        crop_layout.addWidget(QLabel("宽:"))
        crop_layout.addWidget(self.crop_w)
        crop_layout.addWidget(QLabel("高:"))
        crop_layout.addWidget(self.crop_h)
        crop_apply = QPushButton("应用裁剪")
        crop_apply.clicked.connect(self.apply_crop)
        crop_layout.addWidget(crop_apply)
        right_bar.addWidget(crop_group)

        # 水印组
        watermark_group = QGroupBox("文字水印")
        wm_layout = QVBoxLayout()
        watermark_group.setLayout(wm_layout)
        self.wm_text = QLineEdit("Hello World")
        wm_layout.addWidget(QLabel("文本:"))
        wm_layout.addWidget(self.wm_text)
        self.wm_pos = QComboBox()
        self.wm_pos.addItems(["bottom-right", "bottom-left", "top-left", "top-right", "center"])
        wm_layout.addWidget(QLabel("位置:"))
        wm_layout.addWidget(self.wm_pos)
        self.wm_size = QSpinBox()
        self.wm_size.setRange(8, 200)
        self.wm_size.setValue(36)
        wm_layout.addWidget(QLabel("字号:"))
        wm_layout.addWidget(self.wm_size)
        self.wm_opacity = QSlider(Qt.Orientation.Horizontal)
        self.wm_opacity.setRange(0, 100)
        self.wm_opacity.setValue(70)
        wm_layout.addWidget(QLabel("透明度:"))
        wm_layout.addWidget(self.wm_opacity)
        wm_apply = QPushButton("添加水印")
        wm_apply.clicked.connect(self.apply_watermark)
        wm_layout.addWidget(wm_apply)
        right_bar.addWidget(watermark_group)

        # 转换/保存组
        fmt_group = QGroupBox("格式与保存")
        fmt_layout = QVBoxLayout()
        fmt_group.setLayout(fmt_layout)
        self.fmt_combo = QComboBox()
        self.fmt_combo.addItems(["PNG", "JPEG", "BMP"])
        fmt_layout.addWidget(QLabel("选择输出格式:"))
        fmt_layout.addWidget(self.fmt_combo)
        fmt_save_btn = QPushButton("保存为...")
        fmt_save_btn.clicked.connect(self.save_image)
        fmt_layout.addWidget(fmt_save_btn)
        right_bar.addWidget(fmt_group)

        # 控制底部间距
        right_bar.addStretch(1)

        # 菜单栏操作（文件/编辑）
        self._create_menu()

    def _create_menu(self):
        menubar = self.menuBar()
        file_menu = menubar.addMenu("文件")
        open_act = QAction("打开", self)
        open_act.triggered.connect(self.open_image)
        file_menu.addAction(open_act)

        save_act = QAction("保存", self)
        save_act.triggered.connect(self.save_image)
        file_menu.addAction(save_act)

        file_menu.addSeparator()
        exit_act = QAction("退出", self)
        exit_act.triggered.connect(self.close)
        file_menu.addAction(exit_act)

        edit_menu = menubar.addMenu("编辑")
        reset_act = QAction("重置", self)
        reset_act.triggered.connect(self.reset_image)
        edit_menu.addAction(reset_act)

    # ---------------------------
    # QSS（简洁 Win11 风格）
    # ---------------------------
    def _apply_qss(self):
        qss = """
        QMainWindow { background-color: #f3f4f6; }
        QWidget { font-family: "Segoe UI", "Microsoft Yahei", Arial; font-size: 10pt; }
        QPushButton, QToolButton {
            background: #ffffff;
            border: 1px solid #d6d6d6;
            padding: 8px 10px;
            border-radius: 8px;
        }
        QPushButton:hover, QToolButton:hover { background: #f0f0f0; }
        QGroupBox {
            background: #ffffff;
            border: 1px solid #e3e3e3;
            border-radius: 8px;
            margin-top: 8px;
            padding: 8px;
        }
        QLabel { color: #000000; }
        QLabel#PreviewLabel { background-color: #1e1e1e; }
        QSlider::groove:horizontal { height: 8px; background: #e0e0e0; border-radius: 4px; }
        QSlider::handle:horizontal { background: #ffffff; border: 1px solid #bdbdbd; width: 16px; height: 16px; margin: -4px 0; border-radius: 8px; }
        QPushButton, QToolButton { color: #000000; }
        """
        self.setStyleSheet(qss)

    # ---------------------------
    # 工具函数：PIL -> QPixmap 显示
    # ---------------------------
    def pil_to_qpixmap(self, img: Image.Image) -> QPixmap:
        if img is None:
            return QPixmap()
        img = ImageTools.ensure_rgb(img)
        # 使用 BytesIO 避免直接从内存缓冲区读取产生问题
        buf = BytesIO()
        img.save(buf, format="PNG")
        data = buf.getvalue()
        qimg = QImage.fromData(data)
        pix = QPixmap.fromImage(qimg)
        return pix

    def update_preview(self):
        if self.current_image is None:
            self.preview_label.setPixmap(QPixmap())
            self.preview_label.setText("<h2>无图片</h2>")
            return
        pix = self.pil_to_qpixmap(self.current_image)
        self.preview_label.setPixmap(pix)
        # 让 label 自动调整大小以便 scrollarea 支持大图滚动
        self.preview_label.resize(pix.size())
        self.status_label.setText(f"W: {self.current_image.width} H: {self.current_image.height}")

    # ---------------------------
    # 撤销栈
    # ---------------------------
    def push_history(self):
        if self.current_image is not None:
            # 保存副本
            self.history.append(self.current_image.copy())
            if len(self.history) > self.max_history:
                self.history.pop(0)

    def undo(self):
        if not self.history:
            QMessageBox.information(self, "提示", "没有可撤销的操作。")
            return
        self.current_image = self.history.pop()
        self.update_preview()

    # ---------------------------
    # 文件操作
    # ---------------------------
    def open_image(self):
        if self.worker and self.worker.isRunning():
            self.worker.wait()
        path, _ = QFileDialog.getOpenFileName(self, "打开图片", "", "图片文件 (*.jpg *.jpeg *.png *.bmp);;所有文件 (*)")
        if not path:
            return
        try:
            img = Image.open(path)
            img = ImageTools.ensure_rgb(img)
            self.original_image = img.copy()
            self.current_image = img.copy()
            self.history.clear()
            self.update_preview()
            self.statusBar().showMessage(f"已打开: {os.path.basename(path)}")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"无法打开图片: {e}")

    def save_image(self):
        if self.current_image is None:
            QMessageBox.warning(self, "警告", "当前没有图片可保存。")
            return
        # 弹出保存对话框
        selected_fmt = self.fmt_combo.currentText()
        default_ext = selected_fmt.lower()
        filename, _ = QFileDialog.getSaveFileName(self, "保存图片", f"output.{default_ext}", "图片 (*.png *.jpg *.bmp)")
        if not filename:
            return
        try:
            fmt = None
            ext = os.path.splitext(filename)[1].lower()
            if ext in [".jpg", ".jpeg"]:
                fmt = "JPEG"
            elif ext == ".png":
                fmt = "PNG"
            elif ext == ".bmp":
                fmt = "BMP"
            else:
                fmt = selected_fmt
            ImageTools.save_image(self.current_image, filename, fmt=fmt)
            self.statusBar().showMessage(f"已保存: {os.path.basename(filename)}")
            QMessageBox.information(self, "保存成功", f"已保存为: {filename}")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"保存失败: {e}")

    # ---------------------------
    # 缩放操作（在后台线程执行）
    # ---------------------------
    def on_scale_slider(self, value):
        # 实时更新 slider 文本
        self.scale_label.setText(f"{value}%")
        # 不再实时应用缩放，避免过于频繁的操作

    def apply_scale(self, factor: float):
        if self.current_image is None:
            return
        # record history
        self.push_history()
        self.statusBar().showMessage("正在缩放...")
        self.worker = WorkerThread(ImageTools.scale, self.current_image.copy(), factor)
        self.worker.finished_image.connect(self._on_worker_finished)
        self.worker.error.connect(self._on_worker_error)
        self.worker.start()

    def on_scale_slider_apply(self):
        # 应用缩放
        factor = self.scale_slider.value() / 100.0
        self.apply_scale(factor)

    # ---------------------------
    # 旋转
    # ---------------------------
    def apply_rotate(self, angle: float):
        if self.current_image is None:
            return
        self.push_history()
        self.statusBar().showMessage("正在旋转...")
        self.worker = WorkerThread(ImageTools.rotate, self.current_image.copy(), angle)
        self.worker.finished_image.connect(self._on_worker_finished)
        self.worker.error.connect(self._on_worker_error)
        self.worker.start()

    # ---------------------------
    # 裁剪
    # ---------------------------
    def apply_crop(self):
        if self.current_image is None:
            return
        try:
            left = int(self.crop_left.text())
            top = int(self.crop_top.text())
            w = int(self.crop_w.text())
            h = int(self.crop_h.text())
            if w <= 0 or h <= 0:
                raise ValueError("宽高必须>0")
        except Exception as e:
            QMessageBox.warning(self, "参数错误", f"裁剪参数无效: {e}")
            return
        self.push_history()
        try:
            result = ImageTools.crop(self.current_image.copy(), left, top, w, h)
            self.current_image = result
            self.update_preview()
        except Exception as e:
            QMessageBox.critical(self, "错误", f"裁剪失败: {e}")

    # ---------------------------
    # 水印
    # ---------------------------
    def apply_watermark(self):
        if self.current_image is None:
            return
        text = self.wm_text.text().strip()
        if not text:
            QMessageBox.warning(self, "警告", "请输入水印文本。")
            return
        pos = self.wm_pos.currentText()
        size = self.wm_size.value()
        opacity = self.wm_opacity.value() / 100.0
        self.push_history()
        self.statusBar().showMessage("正在添加水印...")
        self.worker = WorkerThread(ImageTools.add_text_watermark, self.current_image.copy(),
                                   text, pos, None, size, opacity)
        self.worker.finished_image.connect(self._on_worker_finished)
        self.worker.error.connect(self._on_worker_error)
        self.worker.start()

    # ---------------------------
    # 重置 / 重置视图
    # ---------------------------
    def reset_image(self):
        if self.original_image is None:
            return
        self.current_image = self.original_image.copy()
        self.history.clear()
        self.scale_slider.setValue(100)
        self.rotate_spin.setValue(0)
        self.update_preview()
        self.statusBar().showMessage("已重置为原始图像")

    def reset_view(self):
        # 把视图滑块和 spinbox 同步回默认
        self.scale_slider.setValue(100)
        self.rotate_spin.setValue(0)
        self.statusBar().showMessage("视图参数已重置（未改变图像）")

    # ---------------------------
    # 后台线程回调
    # ---------------------------
    def _on_worker_finished(self, pil_img):
        self.current_image = pil_img
        self.update_preview()
        self.statusBar().showMessage("操作完成")
        # 清理 worker
        if self.worker:
            self.worker.wait(10)
            self.worker = None

    def _on_worker_error(self, msg):
        QMessageBox.critical(self, "处理错误", msg)
        self.statusBar().showMessage("处理失败")
        if self.worker:
            self.worker.wait(10)
            self.worker = None


# ---------------------------
# 启动
# ---------------------------
def main():
    app = QApplication(sys.argv)
    window = ImageProcessorApp()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
