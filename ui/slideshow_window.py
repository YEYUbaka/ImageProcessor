# ui/slideshow_window.py

import os
import glob
from io import BytesIO
from typing import List, Optional
from PIL import Image
from PyQt6.QtWidgets import (
    QWidget, QLabel, QVBoxLayout, QHBoxLayout, QPushButton, QSpinBox,
    QComboBox, QDialog, QDialogButtonBox, QCheckBox, QFileDialog, QMessageBox, QListWidget, QListWidgetItem, QSizePolicy
)
from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, pyqtProperty, QPoint, QEvent
from PyQt6.QtGui import QPixmap, QImage, QPainter, QColor, QKeySequence, QShortcut


class SlideshowWindow(QWidget):
    """放映窗口"""
    
    def __init__(self, parent=None, image_paths: List[str] = None):
        super().__init__(parent, Qt.WindowType.Window)  # 明确指定窗口类型
        self.parent_window = parent
        self.images: List[Image.Image] = []
        self.image_paths: List[str] = []  # 保存图片路径
        self.current_index = 0
        self.is_playing = False
        self.interval = 3000  # 默认3秒
        self.transition_type = "fade"  # 默认淡入淡出
        self.is_fullscreen = False
        self.normal_geometry = None  # 保存正常窗口的几何信息
        
        # 动画相关
        self.fade_animation = None
        self.current_pixmap = None
        self.next_pixmap = None
        self.original_pixmap = None  # 保存原始pixmap（未缩放）
        
        # 定时器（必须在初始化时创建，即使后续可能不会使用）
        self.timer = QTimer()
        self.timer.timeout.connect(self.next_image)
        
        # 如果提供了图片路径，直接使用；否则显示选择对话框
        if image_paths:
            self.load_images_from_paths(image_paths)
        else:
            if not self.show_selection_dialog():
                return  # 用户取消了选择
        
        self.init_ui()
        self.setup_shortcuts()
        
        # 显示第一张图片
        if self.images:
            self.show_image(0)
        
    def init_ui(self):
        """初始化UI"""
        self.setWindowTitle("图片放映")
        self.setMinimumSize(1000, 600)
        
        # 主布局（水平布局：左侧图片，右侧控制面板）
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # 图片显示区域（左侧，占据大部分空间）
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setStyleSheet("background-color: black;")
        self.image_label.setScaledContents(False)  # 不自动缩放，手动控制
        self.image_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        # 设置最小大小，确保label有足够的空间
        self.image_label.setMinimumSize(400, 300)
        main_layout.addWidget(self.image_label, stretch=3)  # 占据3/4的空间
        
        # 控制面板（右侧）
        self.control_panel = QWidget()
        self.control_panel.setFixedWidth(250)  # 固定宽度
        self.control_panel.setStyleSheet("background-color: #f5f5f5;")
        control_layout = QVBoxLayout(self.control_panel)
        control_layout.setContentsMargins(15, 15, 15, 15)
        control_layout.setSpacing(10)
        
        # 标题
        title_label = QLabel("放映控制")
        title_label.setStyleSheet("font-size: 14pt; font-weight: bold;")
        control_layout.addWidget(title_label)
        
        control_layout.addWidget(QLabel(""))  # 间距
        
        # 播放/暂停按钮
        self.play_btn = QPushButton("播放 (Space/F5)")
        self.play_btn.setMinimumHeight(40)
        self.play_btn.clicked.connect(self.toggle_play)
        control_layout.addWidget(self.play_btn)
        
        control_layout.addWidget(QLabel(""))  # 间距
        
        # 间隔时间
        control_layout.addWidget(QLabel("间隔时间:"))
        self.interval_spin = QSpinBox()
        self.interval_spin.setRange(1, 60)
        self.interval_spin.setValue(3)
        self.interval_spin.setSuffix(" 秒")
        self.interval_spin.valueChanged.connect(self.on_interval_changed)
        control_layout.addWidget(self.interval_spin)
        
        control_layout.addWidget(QLabel(""))  # 间距
        
        # 切换动画
        control_layout.addWidget(QLabel("切换动画:"))
        self.transition_combo = QComboBox()
        self.transition_combo.addItems(["淡入淡出", "从左滑入", "从右滑入", "从上滑入", "从下滑入", "无动画"])
        self.transition_combo.currentTextChanged.connect(self.on_transition_changed)
        control_layout.addWidget(self.transition_combo)
        
        control_layout.addStretch()  # 弹性空间
        
        # 全屏按钮
        self.fullscreen_btn = QPushButton("全屏 (F11)")
        self.fullscreen_btn.setMinimumHeight(35)
        self.fullscreen_btn.clicked.connect(self.toggle_fullscreen)
        control_layout.addWidget(self.fullscreen_btn)
        
        # 导出视频按钮
        self.export_btn = QPushButton("导出视频")
        self.export_btn.setMinimumHeight(35)
        self.export_btn.clicked.connect(self.export_video)
        control_layout.addWidget(self.export_btn)
        
        # 关闭按钮
        self.close_btn = QPushButton("关闭")
        self.close_btn.setMinimumHeight(35)
        self.close_btn.clicked.connect(self.close)
        control_layout.addWidget(self.close_btn)
        
        main_layout.addWidget(self.control_panel, stretch=1)  # 占据1/4的空间
        
        # 定时器
        self.timer = QTimer()
        self.timer.timeout.connect(self.next_image)
    
    def show_selection_dialog(self) -> bool:
        """显示选择图片/文件夹对话框"""
        dialog = SlideshowSelectionDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            image_paths = dialog.get_selected_paths()
            if image_paths:
                self.load_images_from_paths(image_paths)
                return True
            else:
                QMessageBox.warning(self, "提示", "请至少选择一张图片")
                return False
        return False
    
    def load_images_from_paths(self, paths: List[str]):
        """从路径列表加载图片"""
        self.images = []
        self.image_paths = []
        seen_paths = set()  # 用于去重
        
        for path in paths:
            if os.path.isfile(path):
                # 单个文件
                # 转换为绝对路径并标准化，避免重复
                abs_path = os.path.abspath(path)
                if abs_path not in seen_paths:
                    try:
                        img = Image.open(path)
                        img = img.convert("RGB")
                        self.images.append(img)
                        self.image_paths.append(abs_path)
                        seen_paths.add(abs_path)
                    except Exception as e:
                        print(f"加载图片失败 {path}: {e}")
            elif os.path.isdir(path):
                # 文件夹
                extensions = ['*.png', '*.jpg', '*.jpeg', '*.bmp', '*.PNG', '*.JPG', '*.JPEG', '*.BMP']
                image_files = []
                for ext in extensions:
                    image_files.extend(glob.glob(os.path.join(path, ext)))
                
                image_files.sort()
                for img_file in image_files:
                    # 转换为绝对路径并标准化，避免重复
                    abs_path = os.path.abspath(img_file)
                    if abs_path not in seen_paths:
                        try:
                            img = Image.open(img_file)
                            img = img.convert("RGB")
                            self.images.append(img)
                            self.image_paths.append(abs_path)
                            seen_paths.add(abs_path)
                        except Exception as e:
                            print(f"加载图片失败 {img_file}: {e}")
        
        if not self.images:
            QMessageBox.warning(self, "提示", "未找到可用的图片")
    
    def show_image(self, index: int):
        """显示指定索引的图片"""
        if not self.images or index < 0 or index >= len(self.images):
            return
        
        self.current_index = index
        img = self.images[index]
        
        # 转换为QPixmap
        qimg = self.pil_to_qimage(img)
        pixmap = QPixmap.fromImage(qimg)
        
        # 保存原始pixmap（用于缩放）
        self.original_pixmap = pixmap
        
        # 调整大小以适应窗口
        scaled_pixmap = self.scale_pixmap_to_fit(pixmap)
        self.current_pixmap = scaled_pixmap
        self.image_label.setPixmap(scaled_pixmap)
        
        # 更新窗口标题（非全屏时）
        if not self.is_fullscreen:
            self.setWindowTitle(f"图片放映 ({self.current_index + 1}/{len(self.images)})")
    
    def pil_to_qimage(self, img: Image.Image) -> QImage:
        """将PIL Image转换为QImage（使用BytesIO方法，更可靠）"""
        buf = BytesIO()
        img.save(buf, format="PNG")
        qimg = QImage.fromData(buf.getvalue())
        return qimg
    
    def scale_pixmap_to_fit(self, pixmap: QPixmap) -> QPixmap:
        """缩放pixmap以适应窗口，保持宽高比，确保图片所有部分都显示并居中"""
        # 获取label的实际可用大小
        label_size = self.image_label.size()
        if label_size.width() <= 0 or label_size.height() <= 0:
            # 如果label还没有大小，使用窗口大小
            window_size = self.size()
            if self.control_panel.isVisible():
                # 减去控制面板的宽度
                label_width = window_size.width() - self.control_panel.width()
            else:
                label_width = window_size.width()
            label_height = window_size.height()
        else:
            label_width = label_size.width()
            label_height = label_size.height()
        
        if label_width <= 0 or label_height <= 0:
            return pixmap
        
        # 计算缩放比例，确保图片所有部分都显示（保持宽高比）
        pixmap_size = pixmap.size()
        if pixmap_size.width() <= 0 or pixmap_size.height() <= 0:
            return pixmap
        
        # 计算缩放比例（使用较小的比例，确保图片完全可见）
        scale_w = label_width / pixmap_size.width()
        scale_h = label_height / pixmap_size.height()
        scale = min(scale_w, scale_h)  # 使用较小的比例，确保图片所有部分都显示
        
        # 缩放
        new_width = int(pixmap_size.width() * scale)
        new_height = int(pixmap_size.height() * scale)
        
        # 确保尺寸有效
        if new_width <= 0 or new_height <= 0:
            return pixmap
        
        # 缩放pixmap（保持原始宽高比）
        scaled = pixmap.scaled(new_width, new_height, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        
        # 创建一个与label大小相同的pixmap，将缩放后的图片居中放置
        result = QPixmap(label_width, label_height)
        result.fill(QColor(0, 0, 0))  # 黑色背景
        
        painter = QPainter(result)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        
        # 计算居中位置
        x = (label_width - scaled.width()) // 2
        y = (label_height - scaled.height()) // 2
        
        # 绘制居中图片
        painter.drawPixmap(x, y, scaled)
        painter.end()
        
        return result
    
    def next_image(self):
        """切换到下一张图片（定时器回调）"""
        if not self.images:
            if self.timer.isActive():
                self.timer.stop()
            self.is_playing = False
            self.play_btn.setText("播放")
            return
        
        # 如果只有一张图片，停止播放
        if len(self.images) <= 1:
            if self.timer.isActive():
                self.timer.stop()
            self.is_playing = False
            self.play_btn.setText("播放")
            return
        
        # 计算下一张图片的索引
        next_index = (self.current_index + 1) % len(self.images)
        # 切换到下一张图片
        self.transition_to_image(next_index)
    
    def prev_image(self):
        """切换到上一张图片"""
        if not self.images:
            return
        
        prev_index = (self.current_index - 1) % len(self.images)
        self.transition_to_image(prev_index)
    
    def transition_to_image(self, target_index: int):
        """使用动画切换到目标图片"""
        if target_index < 0 or target_index >= len(self.images):
            return
        
        # 如果目标索引和当前索引相同，跳过
        if target_index == self.current_index:
            return
        
        # 更新当前索引
        self.current_index = target_index
        
        target_img = self.images[target_index]
        qimg = self.pil_to_qimage(target_img)
        next_pixmap = QPixmap.fromImage(qimg)
        self.original_pixmap = next_pixmap  # 保存原始pixmap
        next_pixmap = self.scale_pixmap_to_fit(next_pixmap)
        self.next_pixmap = next_pixmap
        
        transition = self.transition_type
        
        if transition == "none" or transition == "无动画":
            # 无动画，直接切换
            self.current_pixmap = next_pixmap
            self.image_label.setPixmap(next_pixmap)
            if not self.is_fullscreen:
                self.setWindowTitle(f"图片放映 ({self.current_index + 1}/{len(self.images)})")
        elif transition == "fade" or transition == "淡入淡出":
            self.fade_transition(next_pixmap)
        elif transition == "slide_left" or transition == "从左滑入":
            self.slide_transition(next_pixmap, "left")
        elif transition == "slide_right" or transition == "从右滑入":
            self.slide_transition(next_pixmap, "right")
        elif transition == "slide_top" or transition == "从上滑入":
            self.slide_transition(next_pixmap, "top")
        elif transition == "slide_bottom" or transition == "从下滑入":
            self.slide_transition(next_pixmap, "bottom")
        else:
            # 默认无动画
            self.current_pixmap = next_pixmap
            self.image_label.setPixmap(next_pixmap)
            if not self.is_fullscreen:
                self.setWindowTitle(f"图片放映 ({self.current_index + 1}/{len(self.images)})")
    
    def fade_transition(self, next_pixmap: QPixmap):
        """淡入淡出动画"""
        # 停止之前的动画（如果有）
        if self.fade_animation:
            self.fade_animation.stop()
        
        # 创建合成图片
        current = self.current_pixmap
        if current is None:
            self.current_pixmap = next_pixmap
            self.image_label.setPixmap(next_pixmap)
            # 更新索引
            if self.next_pixmap == next_pixmap:
                # 从next_image调用，索引已经在transition_to_image中更新
                pass
            else:
                self.current_index = (self.current_index + 1) % len(self.images)
            if not self.is_fullscreen:
                self.setWindowTitle(f"图片放映 ({self.current_index + 1}/{len(self.images)})")
            return
        
        # 确保两张图片大小一致
        size = current.size()
        if next_pixmap.size() != size:
            next_pixmap = next_pixmap.scaled(size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        
        # 创建动画
        self._fade_opacity = 0.0
        self.fade_animation = QPropertyAnimation(self, b"fadeOpacity")
        self.fade_animation.setDuration(500)  # 500ms动画
        self.fade_animation.setStartValue(0.0)
        self.fade_animation.setEndValue(1.0)
        self.fade_animation.setEasingCurve(QEasingCurve.Type.InOutQuad)
        self.fade_animation.finished.connect(self.on_fade_finished)
        
        self.fade_current = current
        self.fade_next = next_pixmap
        self.fade_animation.start()
    
    def get_fadeOpacity(self):
        """获取淡入淡出透明度"""
        return getattr(self, '_fade_opacity', 0.0)
    
    def set_fadeOpacity(self, value):
        """设置淡入淡出透明度"""
        self._fade_opacity = value
        if hasattr(self, 'fade_current') and hasattr(self, 'fade_next') and self.fade_current and self.fade_next:
            # 创建混合图片
            blended = QPixmap(self.fade_current.size())
            blended.fill(QColor(0, 0, 0))
            painter = QPainter(blended)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setOpacity(1.0 - value)
            painter.drawPixmap(0, 0, self.fade_current)
            painter.setOpacity(value)
            painter.drawPixmap(0, 0, self.fade_next)
            painter.end()
            self.image_label.setPixmap(blended)
    
    fadeOpacity = pyqtProperty(float, get_fadeOpacity, set_fadeOpacity)
    
    def on_fade_finished(self):
        """淡入淡出动画完成"""
        if hasattr(self, 'fade_next') and self.fade_next:
            self.current_pixmap = self.fade_next
            # 索引已经在transition_to_image中更新，这里不需要再更新
            if not self.is_fullscreen:
                self.setWindowTitle(f"图片放映 ({self.current_index + 1}/{len(self.images)})")
        self.fade_animation = None
    
    def slide_transition(self, next_pixmap: QPixmap, direction: str):
        """滑动动画"""
        # 简化实现：直接切换，滑动动画较复杂
        # 可以后续优化
        # 更新索引和pixmap
        self.current_pixmap = next_pixmap
        self.image_label.setPixmap(next_pixmap)
        # 索引已经在transition_to_image中更新，这里不需要再更新
        if not self.is_fullscreen:
            self.setWindowTitle(f"图片放映 ({self.current_index + 1}/{len(self.images)})")
    
    def toggle_play(self):
        """切换播放/暂停"""
        if not self.images:
            QMessageBox.warning(self, "提示", "没有图片可播放")
            return
        
        # 如果只有一张图片，提示用户
        if len(self.images) <= 1:
            QMessageBox.information(self, "提示", "只有一张图片，无需播放")
            return
        
        self.is_playing = not self.is_playing
        if self.is_playing:
            self.play_btn.setText("暂停")
            # 确保定时器已连接
            if not self.timer.isActive():
                self.timer.start(self.interval)
        else:
            self.play_btn.setText("播放")
            if self.timer.isActive():
                self.timer.stop()
    
    def on_interval_changed(self, value: int):
        """间隔时间改变"""
        self.interval = value * 1000  # 转换为毫秒
        if self.is_playing:
            self.timer.setInterval(self.interval)
    
    def on_transition_changed(self, text: str):
        """切换动画改变"""
        transition_map = {
            "淡入淡出": "fade",
            "从左滑入": "slide_left",
            "从右滑入": "slide_right",
            "从上滑入": "slide_top",
            "从下滑入": "slide_bottom",
            "无动画": "none"
        }
        self.transition_type = transition_map.get(text, "fade")
    
    def toggle_fullscreen(self):
        """切换全屏"""
        if not self.is_fullscreen:
            # 进入全屏
            # 保存当前窗口几何信息
            if not self.normal_geometry:
                self.normal_geometry = self.geometry()
            # 隐藏控制面板
            self.control_panel.hide()
            # 确保窗口可见
            if not self.isVisible():
                self.show()
            # 直接调用showFullScreen()，这是最可靠的方法
            self.setWindowState(Qt.WindowState.WindowFullScreen)
            self.is_fullscreen = True
            # 延迟重新缩放图片，确保窗口已经全屏
            QTimer.singleShot(300, self.update_image_display)
        else:
            # 退出全屏
            # 清除全屏状态
            self.setWindowState(Qt.WindowState.WindowNoState)
            # 恢复窗口几何信息
            if self.normal_geometry:
                self.setGeometry(self.normal_geometry)
            # 显示控制面板
            self.control_panel.show()
            self.is_fullscreen = False
            # 延迟重新缩放图片，确保窗口已经恢复正常
            QTimer.singleShot(300, self.update_image_display)
    
    def update_image_display(self):
        """更新图片显示（用于全屏切换后）"""
        if self.images and self.current_index < len(self.images):
            # 重新显示当前图片
            self.show_image(self.current_index)
    
    def setup_shortcuts(self):
        """设置快捷键"""
        # Space: 播放/暂停（最常用的快捷键）
        space_shortcut = QShortcut(QKeySequence("Space"), self)
        space_shortcut.activated.connect(self.toggle_play)
        
        # F5: 开始/暂停（备用）
        play_shortcut = QShortcut(QKeySequence("F5"), self)
        play_shortcut.activated.connect(self.toggle_play)
        
        # ESC: 退出全屏/关闭
        esc_shortcut = QShortcut(QKeySequence("Escape"), self)
        esc_shortcut.activated.connect(self.on_escape)
        
        # 左右箭头：切换图片
        left_shortcut = QShortcut(QKeySequence("Left"), self)
        left_shortcut.activated.connect(self.prev_image)
        
        right_shortcut = QShortcut(QKeySequence("Right"), self)
        right_shortcut.activated.connect(self.next_image)
        
        # F11: 全屏
        f11_shortcut = QShortcut(QKeySequence("F11"), self)
        f11_shortcut.activated.connect(self.toggle_fullscreen)
    
    def on_escape(self):
        """ESC键处理"""
        if self.is_fullscreen:
            # 退出全屏
            self.toggle_fullscreen()
        else:
            # 关闭窗口
            self.close()
    
    def changeEvent(self, event):
        """窗口状态改变事件"""
        if event.type() == QEvent.Type.WindowStateChange:
            # 检查是否真的进入全屏
            if self.windowState() & Qt.WindowState.WindowFullScreen:
                if not self.is_fullscreen:
                    self.is_fullscreen = True
                    self.control_panel.hide()
                    QTimer.singleShot(200, self.update_image_display)
            else:
                if self.is_fullscreen:
                    self.is_fullscreen = False
                    self.control_panel.show()
                    QTimer.singleShot(200, self.update_image_display)
        super().changeEvent(event)
    
    def resizeEvent(self, event):
        """窗口大小改变时重新缩放图片"""
        if event:
            super().resizeEvent(event)
        if self.images and self.current_index < len(self.images):
            # 重新从原始图片生成pixmap并缩放
            current_img = self.images[self.current_index]
            qimg = self.pil_to_qimage(current_img)
            pixmap = QPixmap.fromImage(qimg)
            self.original_pixmap = pixmap
            scaled = self.scale_pixmap_to_fit(pixmap)
            self.current_pixmap = scaled
            self.image_label.setPixmap(scaled)
    
    def export_video(self):
        """导出为视频"""
        if not self.images:
            QMessageBox.warning(self, "提示", "没有图片可导出")
            return
        
        # 选择保存路径
        save_path, _ = QFileDialog.getSaveFileName(
            self, "导出视频", "", "MP4视频 (*.mp4);;所有文件 (*.*)"
        )
        
        if not save_path:
            return
        
        if not save_path.endswith('.mp4'):
            save_path += '.mp4'
        
        # 尝试使用opencv导出视频
        try:
            import cv2
            import numpy as np
            
            # 计算所有图片的最大尺寸（保持比例）
            max_width = 0
            max_height = 0
            for img in self.images:
                w, h = img.size
                max_width = max(max_width, w)
                max_height = max(max_height, h)
            
            # 或者使用第一张图片的尺寸（如果希望统一尺寸）
            # 但为了保持比例，我们使用最大尺寸作为视频尺寸
            # 这样每张图片都能完整显示，不会被裁剪
            video_width = max_width
            video_height = max_height
            
            # 创建视频写入器
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            fps = 1.0 / (self.interval / 1000.0)  # 根据间隔计算帧率
            out = cv2.VideoWriter(save_path, fourcc, fps, (video_width, video_height))
            
            # 写入每一帧
            for img in self.images:
                # PIL Image转numpy array
                img_array = np.array(img.convert('RGB'))
                # RGB转BGR（OpenCV使用BGR）
                img_bgr = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
                
                # 获取当前图片尺寸
                img_height, img_width = img_bgr.shape[:2]
                
                # 如果图片尺寸与视频尺寸不同，需要调整
                # 保持原始比例，居中放置（添加黑边）
                if img_width != video_width or img_height != video_height:
                    # 计算缩放比例（保持比例）
                    scale_w = video_width / img_width
                    scale_h = video_height / img_height
                    scale = min(scale_w, scale_h)  # 使用较小的比例，确保完整显示
                    
                    # 缩放图片
                    new_width = int(img_width * scale)
                    new_height = int(img_height * scale)
                    img_bgr = cv2.resize(img_bgr, (new_width, new_height), interpolation=cv2.INTER_LANCZOS4)
                    
                    # 创建与视频尺寸相同的黑色背景
                    frame = np.zeros((video_height, video_width, 3), dtype=np.uint8)
                    
                    # 计算居中位置
                    x_offset = (video_width - new_width) // 2
                    y_offset = (video_height - new_height) // 2
                    
                    # 将图片放置到中心
                    frame[y_offset:y_offset+new_height, x_offset:x_offset+new_width] = img_bgr
                    img_bgr = frame
                
                # 写入多帧（根据间隔时间）
                frame_count = int(fps * (self.interval / 1000.0))
                for _ in range(frame_count):
                    out.write(img_bgr)
            
            out.release()
            QMessageBox.information(self, "成功", f"视频已导出：{save_path}")
            
        except ImportError:
            QMessageBox.warning(
                self, "提示",
                "导出视频功能需要安装 opencv-python 库\n\n"
                "安装方法：\n"
                "1. 打开命令行（CMD 或 PowerShell）\n"
                "2. 运行命令：pip install opencv-python\n"
                "3. 安装完成后重新启动程序\n\n"
                "如果安装失败，请检查网络连接或使用国内镜像源：\n"
                "pip install opencv-python -i https://pypi.tuna.tsinghua.edu.cn/simple"
            )
        except Exception as e:
            QMessageBox.critical(self, "错误", f"导出视频失败：{str(e)}")
    
    def closeEvent(self, event):
        """关闭事件"""
        if self.timer.isActive():
            self.timer.stop()
        if self.fade_animation:
            self.fade_animation.stop()
        event.accept()


# ------------------ 放映选择对话框 ------------------
class SlideshowSelectionDialog(QDialog):
    """选择要放映的图片或文件夹的对话框"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("选择要放映的图片")
        self.setMinimumSize(600, 500)
        
        layout = QVBoxLayout(self)
        
        # 说明
        info_label = QLabel("选择要放映的图片或文件夹：")
        layout.addWidget(info_label)
        
        # 按钮区域
        btn_layout = QHBoxLayout()
        
        # 选择文件按钮
        select_files_btn = QPushButton("选择图片文件")
        select_files_btn.clicked.connect(self.select_files)
        btn_layout.addWidget(select_files_btn)
        
        # 选择文件夹按钮
        select_folder_btn = QPushButton("选择文件夹")
        select_folder_btn.clicked.connect(self.select_folder)
        btn_layout.addWidget(select_folder_btn)
        
        # 移除按钮
        remove_btn = QPushButton("移除选中")
        remove_btn.clicked.connect(self.remove_selected)
        btn_layout.addWidget(remove_btn)
        
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        
        # 列表显示已选择的路径
        self.path_list = QListWidget()
        self.path_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        layout.addWidget(self.path_list)
        
        # 按钮框
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        # 设置按钮文本为中文
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("确定")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("取消")
        layout.addWidget(buttons)
        
        # 如果父窗口有当前图片，自动添加
        if parent and hasattr(parent, 'parent_window') and parent.parent_window:
            if parent.parent_window.original_file_path:
                self.path_list.addItem(parent.parent_window.original_file_path)
    
    def select_files(self):
        """选择图片文件"""
        files, _ = QFileDialog.getOpenFileNames(
            self, "选择图片文件", "",
            "图片文件 (*.png *.jpg *.jpeg *.bmp);;所有文件 (*.*)"
        )
        for file in files:
            if file not in [self.path_list.item(i).text() for i in range(self.path_list.count())]:
                self.path_list.addItem(file)
    
    def select_folder(self):
        """选择文件夹"""
        folder = QFileDialog.getExistingDirectory(self, "选择文件夹")
        if folder:
            if folder not in [self.path_list.item(i).text() for i in range(self.path_list.count())]:
                self.path_list.addItem(folder)
    
    def remove_selected(self):
        """移除选中的项"""
        for item in self.path_list.selectedItems():
            self.path_list.takeItem(self.path_list.row(item))
    
    def get_selected_paths(self) -> List[str]:
        """获取所有选择的路径"""
        paths = []
        for i in range(self.path_list.count()):
            paths.append(self.path_list.item(i).text())
        return paths

