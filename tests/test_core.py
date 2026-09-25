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

    def test_segmenter_grid_mode_and_checkerboard(self):
        # Create a synthetic checkerboard with 3x3 colored stickers
        import numpy as np
        h, w = 600, 600
        canvas = np.zeros((h, w, 3), dtype=np.uint8)
        # 8x8 checkerboard pattern
        for y in range(0, h, 8):
            for x in range(0, w, 8):
                val = 255 if ((x // 8) + (y // 8)) % 2 == 0 else 200
                canvas[y:y+8, x:x+8] = val

        # Place 9 colored squares (representing stickers)
        for r in [50, 250, 450]:
            for c in [50, 250, 450]:
                canvas[r:r+100, c:c+100] = [200, 50, 50]

        img = Image.fromarray(canvas)
        bg_type = StickerSegmenter.detect_background_type(canvas)
        self.assertEqual(bg_type, "checkerboard")

        segmenter = StickerSegmenter(mode="auto", target_size=240)
        stickers = segmenter.process(img)
        self.assertEqual(len(stickers), 9)
        self.assertEqual(stickers[0].image.size, (240, 240))
        self.assertEqual(stickers[0].image.mode, "RGBA")


if __name__ == "__main__":
    unittest.main()
