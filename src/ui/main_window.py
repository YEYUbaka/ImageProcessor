# ui/main_window.py

import os
from io import BytesIO
from PIL import Image
from PyQt6.QtWidgets import (
    QMainWindow, QToolButton, QPushButton, QLabel, QFileDialog,
    QScrollArea, QVBoxLayout, QWidget, QHBoxLayout, QSizePolicy,
    QGroupBox, QSlider, QSpinBox, QLineEdit, QComboBox, QMessageBox, QStyle
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QPixmap, QImage, QAction

from image_tools import ImageTools


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


# ------------------ 主窗口 ------------------
class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        self.setWindowTitle("简易图片处理工具")
        self.setMinimumSize(1000, 640)

        self.original_image = None
        self.current_image = None
        self.history = []
        self.max_history = 10
        self.worker = None

        self.build_ui()
        self.load_qss()

    # 读取 qss 样式
    def load_qss(self):
        qss_path = os.path.join(os.path.dirname(__file__), "qss.qss")
        if os.path.exists(qss_path):
            with open(qss_path, "r", encoding="utf-8") as f:
                self.setStyleSheet(f.read())

    # ------------------ UI 核心 ------------------
    def build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)

        # ========== 左侧工具栏 ==========
        left = QVBoxLayout()
        left_widget = QWidget()
        left_widget.setLayout(left)
        left_widget.setFixedWidth(140)
        layout.addWidget(left_widget)

        self.btn_open = QToolButton()
        self.btn_open.setText("打开")
        self.btn_open.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogOpenButton))
        self.btn_open.clicked.connect(self.open_image)
        left.addWidget(self.btn_open)

        self.btn_save = QToolButton()
        self.btn_save.setText("保存")
        self.btn_save.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogSaveButton))
        self.btn_save.clicked.connect(self.save_image)
        left.addWidget(self.btn_save)

        left.addWidget(QPushButton("放大", clicked=lambda: self.apply_scale(1.2)))
        left.addWidget(QPushButton("缩小", clicked=lambda: self.apply_scale(0.8)))
        left.addWidget(QPushButton("旋转90°", clicked=lambda: self.apply_rotate(90)))

        undo_btn = QPushButton("撤销")
        undo_btn.clicked.connect(self.undo)
        left.addWidget(undo_btn)

        left.addStretch()

        # ========== 中间预览 ==========
        preview_layout = QVBoxLayout()
        preview_widget = QWidget()
        preview_widget.setLayout(preview_layout)
        layout.addWidget(preview_widget, stretch=1)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.preview_label = QLabel("无图片")
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setStyleSheet("background:#1e1e1e;color:white;")
        self.preview_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
        self.scroll.setWidget(self.preview_label)

        preview_layout.addWidget(self.scroll)
        self.status_label = QLabel("就绪")
        preview_layout.addWidget(self.status_label)

        # ========== 右侧参数区 ==========
        right = QVBoxLayout()
        right_widget = QWidget()
        right_widget.setLayout(right)
        right_widget.setFixedWidth(300)
        layout.addWidget(right_widget)

        # 缩放组
        s_group = QGroupBox("缩放")
        s_layout = QVBoxLayout()
        s_group.setLayout(s_layout)
        right.addWidget(s_group)

        self.s_slider = QSlider(Qt.Orientation.Horizontal)
        self.s_slider.setRange(10, 300)
        self.s_slider.setValue(100)
        self.s_slider.valueChanged.connect(lambda v: self.scale_label.setText(f"{v}%"))
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

        self.rotate_spin = QSpinBox()
        self.rotate_spin.setRange(-360, 360)
        r_layout.addWidget(self.rotate_spin)

        r_layout.addWidget(QPushButton("应用旋转",
                                       clicked=lambda: self.apply_rotate(self.rotate_spin.value())))

        # 裁剪组
        c_group = QGroupBox("裁剪")
        c_layout = QVBoxLayout()
        c_group.setLayout(c_layout)
        right.addWidget(c_group)

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
        w_layout.addWidget(QLabel("文本:"))
        w_layout.addWidget(self.wm_text)

        self.wm_pos = QComboBox()
        self.wm_pos.addItems(["bottom-right", "bottom-left", "top-left", "top-right", "center"])
        w_layout.addWidget(self.wm_pos)

        self.wm_size = QSpinBox()
        self.wm_size.setRange(8, 200)
        self.wm_size.setValue(36)
        w_layout.addWidget(self.wm_size)

        self.wm_op = QSlider(Qt.Orientation.Horizontal)
        self.wm_op.setRange(0, 100)
        self.wm_op.setValue(70)
        w_layout.addWidget(self.wm_op)

        w_layout.addWidget(QPushButton("添加水印", clicked=self.apply_watermark))

        right.addStretch()

    # ------------------ 工具函数 ------------------
    def push_history(self):
        if self.current_image:
            self.history.append(self.current_image.copy())
            if len(self.history) > self.max_history:
                self.history.pop(0)

    def pil_to_qpixmap(self, img: Image.Image):
        buf = BytesIO()
        img.save(buf, format="PNG")
        qimg = QImage.fromData(buf.getvalue())
        return QPixmap.fromImage(qimg)

    def update_preview(self):
        if self.current_image is None:
            self.preview_label.setText("无图片")
            self.preview_label.setPixmap(QPixmap())
            return

        pix = self.pil_to_qpixmap(self.current_image)
        self.preview_label.setPixmap(pix)
        self.preview_label.resize(pix.size())
        self.status_label.setText(f"{self.current_image.width} x {self.current_image.height}")

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
        self.history.clear()
        self.update_preview()

    def save_image(self):
        if self.current_image is None:
            QMessageBox.warning(self, "提示", "无图片可保存")
            return
        save_path, _ = QFileDialog.getSaveFileName(
            self, "保存图片", "output.png", "PNG (*.png);;JPEG (*.jpg)"
        )
        if save_path:
            ImageTools.save_image(self.current_image, save_path)
            QMessageBox.information(self, "成功", "保存成功")

    # ------------------ 操作逻辑 ------------------
    def on_slider_scale(self):
        factor = self.s_slider.value() / 100
        self.apply_scale(factor)

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

        self.push_history()
        img = ImageTools.crop(self.current_image, left, top, w, h)
        self.current_image = img
        self.update_preview()

    def apply_watermark(self):
        if self.current_image is None:
            return

        text = self.wm_text.text()
        pos = self.wm_pos.currentText()
        size = self.wm_size.value()
        op = self.wm_op.value() / 100

        self.push_history()
        self.worker = WorkerThread(
            ImageTools.add_text_watermark,
            self.current_image, text, pos, None, size, op
        )
        self.worker.finished_image.connect(self.on_worker_finished)
        self.worker.start()

    # ------------------ 撤销 ------------------
    def undo(self):
        if not self.history:
            QMessageBox.information(self, "提示", "无可撤销操作")
            return
        self.current_image = self.history.pop()
        self.update_preview()

    # ------------------ 线程回调 ------------------
    def on_worker_finished(self, img):
        self.current_image = img
        self.update_preview()
        self.worker = None

