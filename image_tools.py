# image_tools.py
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps
import os
from io import BytesIO

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

        left = max(0, min(left, img.width - 1))
        top = max(0, min(top, img.height - 1))
        right = max(left + 1, min(right, img.width))
        bottom = max(top + 1, min(bottom, img.height))
        return img.crop((left, top, right, bottom))

    @staticmethod
    def add_text_watermark(img: Image.Image, text: str, position="bottom-right",
                           x=None, y=None, font_path=None, font_size=36, opacity=0.7):
        """
        添加文字水印
        
        Args:
            img: 图像对象
            text: 水印文本
            position: 位置（bottom-right, bottom-left, top-left, top-right, center, custom）
            x: 自定义X坐标（当position为custom时使用）
            y: 自定义Y坐标（当position为custom时使用）
            font_path: 字体路径或字体名称
            font_size: 字体大小
            opacity: 透明度（0.0-1.0）
        """
        img = ImageTools.ensure_rgb(img).copy()
        layer = Image.new("RGBA", img.size)
        draw = ImageDraw.Draw(layer)

        # 字体
        font = None
        if font_path:
            # 尝试使用字体路径或字体名称
            try:
                # 如果是字体名称，尝试查找系统字体
                import platform
                if platform.system() == "Windows":
                    # Windows字体路径
                    font_dirs = [
                        "C:/Windows/Fonts/",
                        "C:/Windows/Fonts/"
                    ]
                    for font_dir in font_dirs:
                        for ext in [".ttf", ".ttc", ".otf"]:
                            font_file = os.path.join(font_dir, f"{font_path}{ext}")
                            if os.path.exists(font_file):
                                font = ImageFont.truetype(font_file, font_size)
                                break
                        if font:
                            break
                # 如果找不到，尝试直接使用字体名称
                if not font:
                    font = ImageFont.truetype(font_path, font_size)
            except:
                pass
        
        if not font:
            try:
                font = ImageFont.truetype("arial.ttf", font_size)
            except:
                font = ImageFont.load_default()

        bbox = draw.textbbox((0, 0), text, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        margin = 20

        # 计算位置
        if position == "custom" and x is not None and y is not None:
            # 自定义位置
            text_x = max(0, min(x, img.width - tw))
            text_y = max(0, min(y, img.height - th))
        elif position == "bottom-right":
            text_x = img.width - tw - margin
            text_y = img.height - th - margin
        elif position == "bottom-left":
            text_x = margin
            text_y = img.height - th - margin
        elif position == "top-left":
            text_x = margin
            text_y = margin
        elif position == "top-right":
            text_x = img.width - tw - margin
            text_y = margin
        else:  # center
            text_x = (img.width - tw) // 2
            text_y = (img.height - th) // 2

        draw.text((text_x, text_y), text, fill=(255, 255, 255, int(255 * opacity)), font=font)

        return Image.alpha_composite(img.convert("RGBA"), layer).convert("RGB")

    @staticmethod
    def save_image(img: Image.Image, path: str, fmt=None):
        """保存图片，支持多种格式
        
        支持的格式：
        - PNG: 无损压缩，支持透明度
        - JPEG/JPG: 有损压缩，文件小
        - TIFF/TIF: 高质量，支持多页
        - WebP: 现代格式，压缩率高
        """
        img = ImageTools.ensure_rgb(img)
        if fmt is None:
            ext = os.path.splitext(path)[1].lower()
            # 根据扩展名确定格式
            format_map = {
                ".png": "PNG",
                ".jpg": "JPEG",
                ".jpeg": "JPEG",
                ".tiff": "TIFF",
                ".tif": "TIFF",
                ".webp": "WEBP",
            }
            fmt = format_map.get(ext, "PNG")  # 默认PNG
        
        # 特殊格式处理
        save_kwargs = {}
        if fmt == "JPEG":
            # JPEG不支持透明度，确保是RGB模式
            if img.mode in ("RGBA", "LA", "P"):
                img = img.convert("RGB")
        
        img.save(path, format=fmt, **save_kwargs)

    # ========== 滤镜功能 ==========
    @staticmethod
    def grayscale(img: Image.Image) -> Image.Image:
        """转换为黑白（灰度）"""
        img = ImageTools.ensure_rgb(img)
        return img.convert("L").convert("RGB")

    @staticmethod
    def blur(img: Image.Image, radius: float = 2.0) -> Image.Image:
        """高斯模糊"""
        img = ImageTools.ensure_rgb(img)
        return img.filter(ImageFilter.GaussianBlur(radius=radius))

    @staticmethod
    def vintage(img: Image.Image) -> Image.Image:
        """复古（棕褐色调）"""
        img = ImageTools.ensure_rgb(img)
        # 棕褐色
        sepia = (112, 66, 20)
        # 转为灰度
        gray = img.convert("L")
        # 着色
        colorized = ImageOps.colorize(gray, black="black", white=sepia)
        # 混合原图与棕褐色（保留细节）
        blended = Image.blend(img, colorized, alpha=0.5)
        return blended
