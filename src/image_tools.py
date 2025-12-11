# image_tools.py
from PIL import Image, ImageDraw, ImageFont
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
                           font_path=None, font_size=36, opacity=0.7):
        img = ImageTools.ensure_rgb(img).copy()
        layer = Image.new("RGBA", img.size)
        draw = ImageDraw.Draw(layer)

        # 字体
        try:
            font = ImageFont.truetype(font_path if font_path else "arial.ttf", font_size)
        except:
            font = ImageFont.load_default()

        bbox = draw.textbbox((0, 0), text, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        margin = 20

        if position == "bottom-right":
            x = img.width - tw - margin
            y = img.height - th - margin
        elif position == "bottom-left":
            x = margin
            y = img.height - th - margin
        elif position == "top-left":
            x = margin
            y = margin
        elif position == "top-right":
            x = img.width - tw - margin
            y = margin
        else:
            x = (img.width - tw) // 2
            y = (img.height - th) // 2

        draw.text((x, y), text, fill=(255, 255, 255, int(255 * opacity)), font=font)

        return Image.alpha_composite(img.convert("RGBA"), layer).convert("RGB")

    @staticmethod
    def save_image(img: Image.Image, path: str, fmt=None):
        img = ImageTools.ensure_rgb(img)
        if fmt is None:
            ext = os.path.splitext(path)[1].lower()
            if ext in [".jpg", ".jpeg"]:
                fmt = "JPEG"
            elif ext == ".png":
                fmt = "PNG"
            else:
                fmt = "PNG"
        img.save(path, format=fmt)
