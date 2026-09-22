"""
Unit tests for gpt-to-wechat core functions.
"""

import os
import sys
import unittest
from PIL import Image

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from core.segmenter import StickerSegmenter, split_stickers
from core.wechat_bridge import WeChatBridge
from core.exporter import StickerExporter


class TestStickerProcessing(unittest.TestCase):

    def setUp(self):
        self.sample_image_path = os.path.join(project_root, "assets", "sample_chatgpt_stickers.jpg")
        self.test_output_dir = os.path.join(project_root, "output", "test_stickers")

    def test_segmenter_detects_9_stickers(self):
        self.assertTrue(os.path.exists(self.sample_image_path), "Sample test image must exist")
        segmenter = StickerSegmenter(bg_threshold=35, target_size=240)
        stickers = segmenter.process(self.sample_image_path, output_dir=self.test_output_dir)

        # Must detect all 9 stickers
        self.assertEqual(len(stickers), 9)

        # Check properties of first sticker
        s1 = stickers[0]
        self.assertEqual(s1.image.size, (240, 240))
        self.assertEqual(s1.image.mode, "RGBA")

        # Verify transparency in corner
        alpha_corner = s1.image.getpixel((0, 0))[3]
        self.assertEqual(alpha_corner, 0, "Corner should be transparent")

    def test_exporter_zip(self):
        segmenter = StickerSegmenter(bg_threshold=35, target_size=240)
        stickers = segmenter.process(self.sample_image_path)
        zip_bytes = StickerExporter.export_to_bytes_zip(stickers)
        self.assertGreater(len(zip_bytes), 1000)

    def test_wechat_bridge_detection(self):
        # Checks WeChat running detection without error
        running = WeChatBridge.is_wechat_running()
        self.assertIsInstance(running, bool)

    def test_copy_files_to_clipboard(self):
        import glob
        files = sorted(glob.glob(os.path.join(project_root, "output", "stickers", "sticker_*.png")))
        if files:
            ok = WeChatBridge.copy_files_to_clipboard(files)
            self.assertTrue(ok)


if __name__ == "__main__":
    unittest.main()
