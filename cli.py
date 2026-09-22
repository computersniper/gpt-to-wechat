"""
GPT-to-WeChat Command-Line Interface.
"""

import argparse
import os
import sys
from rich.console import Console
from rich.table import Table

project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from core.segmenter import StickerSegmenter
from core.wechat_bridge import WeChatBridge
from core.exporter import StickerExporter

console = Console()


def process_command(args):
    input_path = args.input
    if not os.path.exists(input_path):
        console.print(f"[bold red]错误：文件未找到: {input_path}[/bold red]")
        sys.exit(1)

    out_dir = args.output or os.path.join(project_root, "output", "stickers")
    os.makedirs(out_dir, exist_ok=True)

    console.print(f"[bold green]🔍 正在处理 ChatGPT 表情图片:[/bold green] {input_path}")
    segmenter = StickerSegmenter(
        bg_threshold=args.threshold,
        target_size=args.size,
        margin=args.margin
    )

    stickers = segmenter.process(input_path, output_dir=out_dir, prefix=args.prefix)

    if not stickers:
        console.print("[bold yellow]⚠️ 未检测到有效表情，请尝试调整 --threshold 参数[/bold yellow]")
        sys.exit(1)

    table = Table(title="✨ 切分结果列表")
    table.add_column("序号", justify="center", style="cyan")
    table.add_column("保存路径", style="green")
    table.add_column("分辨率", justify="center")
    table.add_column("像素面积", justify="right")

    for s in stickers:
        table.add_row(f"#{s.index:02d}", s.path or "Memory", f"{s.image.width}x{s.image.height}", str(s.area))

    console.print(table)
    console.print(f"\n[bold green]✅ 成功切分 {len(stickers)} 个表情，并保存至: {out_dir}[/bold green]")

    if args.zip:
        zip_path = os.path.join(out_dir, f"{args.prefix}_all.zip")
        StickerExporter.export_to_zip(stickers, zip_path, prefix=args.prefix)
        console.print(f"[bold blue]📦 打包完成: {zip_path}[/bold blue]")

    if args.copy_first and stickers:
        WeChatBridge.copy_image_to_clipboard(stickers[0].image)
        console.print("[bold magenta]📋 表情 #01 已复制到系统剪贴板！可以直接在微信中 Ctrl+V 粘贴。[/bold magenta]")

    if args.push_wechat and stickers:
        console.print("[bold green]🚀 正在免鼠标推送到微信...[/bold green]")
        WeChatBridge.copy_image_to_clipboard(stickers[0].image)
        ok = WeChatBridge.paste_to_active_chat()
        if ok:
            console.print("[bold green]✅ 成功推送到微信输入区！在微信中按 Enter 发送即可！[/bold green]")
        else:
            console.print("[bold yellow]⚠️ 未能自动获取微信窗口焦点，表情已在剪贴板中，请在微信中按 Ctrl+V 粘贴。[/bold yellow]")


def ui_command(args):
    console.print("[bold green]🚀 正在启动 Web 交互界面...[/bold green]")
    import subprocess
    cmd = [sys.executable, "-m", "streamlit", "run", os.path.join(project_root, "ui", "app.py")]
    subprocess.run(cmd)


def mcp_command(args):
    console.print("[bold green]🤖 正在启动 WeChat & ChatGPT Stickers MCP Server (stdio)...[/bold green]")
    from core.mcp_server import run_server
    run_server()


def main():
    parser = argparse.ArgumentParser(
        description="GPT-to-WeChat: 将 ChatGPT 生成的表情包大图智能切分并适配微信"
    )
    subparsers = parser.add_subparsers(dest="command")

    # Process command
    p_proc = subparsers.add_parser("process", help="切分表情图片")
    p_proc.add_argument("input", help="ChatGPT 表情大图路径")
    p_proc.add_argument("-o", "--output", help="输出目录 (默认 output/stickers)")
    p_proc.add_argument("--size", type=int, default=240, help="输出正方形规格 (默认 240)")
    p_proc.add_argument("--threshold", type=int, default=35, help="背景暗色判定阈值 (默认 35)")
    p_proc.add_argument("--margin", type=int, default=8, help="边距保留 (默认 8)")
    p_proc.add_argument("--prefix", default="sticker", help="文件名前缀 (默认 sticker)")
    p_proc.add_argument("--zip", action="store_true", help="是否同时打包为 ZIP 文件")
    p_proc.add_argument("--copy-first", action="store_true", help="处理后自动将第一张表情复制到剪贴板")
    p_proc.add_argument("--push-wechat", action="store_true", help="处理后免鼠标自动粘贴推送到微信")

    # UI command
    subparsers.add_parser("ui", help="启动可视化 Web 界面")

    # MCP command
    subparsers.add_parser("mcp", help="以 MCP Server (Model Context Protocol) 模式运行")

    args = parser.parse_args()

    if args.command == "process":
        process_command(args)
    elif args.command == "ui":
        ui_command(args)
    elif args.command == "mcp":
        mcp_command(args)
    else:
        # If no arguments provided, show help
        parser.print_help()


if __name__ == "__main__":
    main()
