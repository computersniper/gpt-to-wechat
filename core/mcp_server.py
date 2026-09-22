"""
WeChat & ChatGPT Stickers Model Context Protocol (MCP) Server.

Enables AI Agents (Claude Desktop, Cursor, Antigravity, etc.)
to slice ChatGPT stickers and interact with WeChat via standard MCP tools.
"""

import os
import sys
from typing import List, Optional, Dict, Any

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from mcp.server.fastmcp import FastMCP
from core.segmenter import StickerSegmenter
from core.wechat_bridge import WeChatBridge
from core.exporter import StickerExporter

# Initialize FastMCP server
mcp = FastMCP("gpt-to-wechat-mcp", dependencies=["pillow", "scikit-image", "scipy", "pywin32", "psutil"])


@mcp.tool()
def check_wechat_status() -> Dict[str, Any]:
    """Check if WeChat desktop client is currently running on the Windows machine."""
    running = WeChatBridge.is_wechat_running()
    pids = WeChatBridge.get_wechat_pids()
    hwnd = WeChatBridge.find_wechat_window()
    return {
        "is_running": running,
        "pids": pids,
        "has_active_window": hwnd is not None,
        "hwnd": hwnd
    }


@mcp.tool()
def split_chatgpt_stickers(
    image_path: str,
    output_dir: Optional[str] = None,
    target_size: int = 240,
    threshold: int = 35
) -> Dict[str, Any]:
    """
    Intelligently segment a ChatGPT sticker sheet into individual transparent WeChat-ready emojis.

    :param image_path: Absolute path to the ChatGPT sticker image (e.g. 3x3 grid).
    :param output_dir: Directory where transparent PNG stickers will be saved. Default is 'output/stickers'.
    :param target_size: Output dimension in pixels (default 240 for WeChat recommended spec).
    :param threshold: Dark background cutoff threshold (default 35).
    :return: Summary with total count and list of output file paths.
    """
    if not os.path.exists(image_path):
        return {"error": f"Image file not found: {image_path}"}

    out_dir = output_dir or os.path.join(project_root, "output", "stickers")
    os.makedirs(out_dir, exist_ok=True)

    segmenter = StickerSegmenter(bg_threshold=threshold, target_size=target_size)
    stickers = segmenter.process(image_path, output_dir=out_dir)

    results = []
    for s in stickers:
        results.append({
            "index": s.index,
            "path": s.path,
            "dimensions": f"{s.image.width}x{s.image.height}",
            "area": s.area
        })

    return {
        "status": "success",
        "total_stickers": len(stickers),
        "output_directory": out_dir,
        "stickers": results
    }


@mcp.tool()
def copy_sticker_to_clipboard(image_path: str) -> Dict[str, Any]:
    """
    Copies a transparent sticker image into Windows system clipboard preserving transparency.

    :param image_path: Absolute path to the transparent PNG sticker image.
    :return: Success status.
    """
    if not os.path.exists(image_path):
        return {"error": f"Sticker file not found: {image_path}"}

    ok = WeChatBridge.copy_image_to_clipboard(image_path)
    return {
        "success": ok,
        "message": "Sticker copied to Windows clipboard in PNG and DIB formats. Press Ctrl+V in WeChat to paste." if ok else "Failed to access clipboard."
    }


@mcp.tool()
def push_sticker_to_wechat(image_path: str) -> Dict[str, Any]:
    """
    Pushes a sticker image directly to the active WeChat chat window without moving physical mouse.

    :param image_path: Path to the sticker image to send.
    :return: Operation result.
    """
    if not os.path.exists(image_path):
        return {"error": f"File not found: {image_path}"}

    if not WeChatBridge.is_wechat_running():
        return {"error": "WeChat is not currently running. Please launch and login to WeChat first."}

    # 1. Put into clipboard
    copied = WeChatBridge.copy_image_to_clipboard(image_path)
    if not copied:
        return {"error": "Failed to copy image to clipboard."}

    # 2. Paste to WeChat
    pasted = WeChatBridge.paste_to_active_chat()
    if pasted:
        return {
            "status": "success",
            "message": "Sticker pasted into active WeChat window! User can press Enter to send, then right click -> Add to Stickers."
        }
    else:
        return {
            "status": "partial_success",
            "message": "Sticker copied to clipboard, but could not focus WeChat window. User can manually press Ctrl+V."
        }


@mcp.tool()
def package_stickers_to_zip(image_path: str, output_zip_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Splits ChatGPT stickers from an image and packages all of them into a ready-to-use ZIP file.

    :param image_path: Path to the ChatGPT sticker sheet image.
    :param output_zip_path: Target ZIP file path.
    :return: Path to created ZIP file.
    """
    if not os.path.exists(image_path):
        return {"error": f"Image file not found: {image_path}"}

    segmenter = StickerSegmenter()
    stickers = segmenter.process(image_path)

    zip_path = output_zip_path or os.path.join(project_root, "output", "chatgpt_wechat_stickers.zip")
    StickerExporter.export_to_zip(stickers, zip_path)

    return {
        "status": "success",
        "total_stickers": len(stickers),
        "zip_path": zip_path
    }


def run_server():
    """Starts the FastMCP server over standard I/O."""
    mcp.run()


if __name__ == "__main__":
    run_server()
