"""
Sticker Export and Packaging Utilities.
"""

import io
import os
import zipfile
from typing import List, Union
from PIL import Image
from core.segmenter import StickerResult


class StickerExporter:
    """
    Handles exporting and packaging of stickers into files and ZIP archives.
    """

    @staticmethod
    def export_to_zip(stickers: List[Union[StickerResult, Image.Image]], output_zip_path: str, prefix: str = "wechat_sticker") -> str:
        """
        Packs a list of stickers into a single ZIP file.
        """
        os.makedirs(os.path.dirname(os.path.abspath(output_zip_path)), exist_ok=True)
        with zipfile.ZipFile(output_zip_path, 'w', compression=zipfile.ZIP_DEFLATED) as zip_file:
            for idx, item in enumerate(stickers, 1):
                img = item.image if isinstance(item, StickerResult) else item
                byte_io = io.BytesIO()
                img.save(byte_io, format="PNG")
                zip_file.writestr(f"{prefix}_{idx:02d}.png", byte_io.getvalue())
        return output_zip_path

    @staticmethod
    def export_to_bytes_zip(stickers: List[Union[StickerResult, Image.Image]], prefix: str = "wechat_sticker") -> bytes:
        """
        Packs a list of stickers into an in-memory ZIP byte buffer.
        """
        byte_io = io.BytesIO()
        with zipfile.ZipFile(byte_io, 'w', compression=zipfile.ZIP_DEFLATED) as zip_file:
            for idx, item in enumerate(stickers, 1):
                img = item.image if isinstance(item, StickerResult) else item
                img_bytes = io.BytesIO()
                img.save(img_bytes, format="PNG")
                zip_file.writestr(f"{prefix}_{idx:02d}.png", img_bytes.getvalue())
        return byte_io.getvalue()
