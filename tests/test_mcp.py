"""
Tests for gpt-to-wechat MCP Server tools.
"""

import os
import sys
import unittest

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from core.mcp_server import (
    check_wechat_status,
    split_chatgpt_stickers,
    copy_sticker_to_clipboard,
    package_stickers_to_zip
)


class TestMCPServer(unittest.TestCase):

    def setUp(self):
        self.sample_img = os.path.join(project_root, "assets", "sample_chatgpt_stickers.jpg")

    def test_check_wechat_status(self):
        status = check_wechat_status()
        self.assertIn("is_running", status)
        self.assertIsInstance(status["is_running"], bool)

    def test_split_chatgpt_stickers(self):
        out_dir = os.path.join(project_root, "output", "mcp_test_stickers")
        res = split_chatgpt_stickers(self.sample_img, output_dir=out_dir)
        self.assertEqual(res.get("status"), "success")
        self.assertEqual(res.get("total_stickers"), 9)
        self.assertEqual(len(res.get("stickers")), 9)

    def test_package_stickers_to_zip(self):
        out_zip = os.path.join(project_root, "output", "mcp_test.zip")
        res = package_stickers_to_zip(self.sample_img, output_zip_path=out_zip)
        self.assertEqual(res.get("status"), "success")
        self.assertTrue(os.path.exists(out_zip))
        if os.path.exists(out_zip):
            os.remove(out_zip)


if __name__ == "__main__":
    unittest.main()
