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
        "message": "Sticker copied to Windows clipboard. Press Ctrl+V in WeChat to paste." if ok else "Failed to access clipboard."
    }


@mcp.tool()
def copy_all_stickers_to_clipboard(file_paths: List[str]) -> Dict[str, Any]:
    """
    Copies MULTIPLE transparent sticker images simultaneously into Windows system clipboard using CF_HDROP.
    Allows pasting ALL stickers at once into WeChat chat box via Ctrl+V.

    :param file_paths: List of absolute paths to sticker PNG files.
    :return: Operation result.
    """
    valid_paths = [os.path.abspath(p) for p in file_paths if os.path.exists(p)]
    if not valid_paths:
        return {"error": "No valid sticker files found in the provided paths."}

    ok = WeChatBridge.copy_files_to_clipboard(valid_paths)
    return {
        "success": ok,
        "copied_count": len(valid_paths),
        "message": f"Successfully copied all {len(valid_paths)} stickers to clipboard! Press Ctrl+V in WeChat to paste all at once." if ok else "Failed to copy files to clipboard."
    }


@mcp.tool()
def push_sticker_to_wechat(image_path: Optional[str] = None, image_paths: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    Pushes one or multiple sticker images directly to the active WeChat chat window without moving physical mouse.

    :param image_path: Path to a single sticker image to send (optional).
    :param image_paths: List of sticker image paths to send simultaneously (optional).
    :return: Operation result.
    """
    targets = []
    if image_paths:
        targets.extend([p for p in image_paths if os.path.exists(p)])
    if image_path and os.path.exists(image_path) and image_path not in targets:
        targets.append(image_path)

    if not targets:
        return {"error": "No valid image paths provided."}

    if not WeChatBridge.is_wechat_running():
        return {"error": "WeChat is not currently running. Please launch and login to WeChat first."}

    if len(targets) == 1:
        copied = WeChatBridge.copy_image_to_clipboard(targets[0])
        pasted = WeChatBridge.paste_to_active_chat()
    else:
        pasted = WeChatBridge.paste_files_to_active_chat(targets)
        copied = pasted or WeChatBridge.copy_files_to_clipboard(targets)

    if pasted:
        return {
            "status": "success",
            "pushed_count": len(targets),
            "message": f"{len(targets)} sticker(s) pasted into active WeChat window! User can press Enter to send, then right click -> Add to Stickers."
        }
    else:
        return {
            "status": "partial_success",
            "pushed_count": len(targets) if copied else 0,
            "message": f"{len(targets)} sticker(s) copied to clipboard, but could not focus WeChat window. User can manually press Ctrl+V."
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
