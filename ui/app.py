"""
GPT-to-WeChat Streamlit Web Application.
"""

import os
import sys
import io
import streamlit as st
from PIL import Image

# Ensure project root is in path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from core.segmenter import StickerSegmenter
from core.wechat_bridge import WeChatBridge
from core.exporter import StickerExporter

st.set_page_config(
    page_title="GPT to WeChat 表情包转换器",
    page_icon="✨",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for modern styling and checkerboard transparent background
st.markdown("""
<style>
    .main-title {
        font-size: 2.2rem;
        font-weight: 700;
        background: linear-gradient(120deg, #10a37f, #07c160);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.2rem;
    }
    .sub-title {
        font-size: 1.05rem;
        color: #666;
        margin-bottom: 1.5rem;
    }
    .sticker-card {
        background-color: #ffffff;
        border-radius: 12px;
        padding: 12px;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
        border: 1px solid #eaeaea;
        text-align: center;
        margin-bottom: 15px;
    }
    .transparent-bg {
        background-image: 
          linear-gradient(45deg, #e5e5e5 25%, transparent 25%), 
          linear-gradient(135deg, #e5e5e5 25%, transparent 25%),
          linear-gradient(45deg, transparent 75%, #e5e5e5 75%),
          linear-gradient(135deg, transparent 75%, #e5e5e5 75%);
        background-size: 16px 16px;
        background-position: 0 0, 8px 0, 8px -8px, 0px 8px;
        background-color: #f9f9f9;
        border-radius: 8px;
        padding: 8px;
        display: inline-block;
    }
    .status-badge {
        display: inline-block;
        padding: 4px 10px;
        border-radius: 16px;
        font-size: 0.85rem;
        font-weight: 600;
    }
    .status-running {
        background-color: #e6f9ed;
        color: #07c160;
    }
    .status-offline {
        background-color: #fef0f0;
        color: #f56c6c;
    }
</style>
""", unsafe_allow_html=True)

# Sidebar settings
st.sidebar.header("⚙️ 参数配置")

bg_threshold = st.sidebar.slider(
    "背景黑度阈值 (Threshold)",
    min_value=10,
    max_value=100,
    value=35,
    help="识别背景暗色的阈值，值越小对暗色越严格"
)

target_size = st.sidebar.select_slider(
    "导出表情规格 (Target Size)",
    options=[180, 240, 300, 360, 480],
    value=240,
    help="微信官方推荐表情尺寸为 240x240 正方形透明 PNG"
)

margin = st.sidebar.slider("外边距保留 (Margin px)", min_value=0, max_value=20, value=8)
dilation = st.sidebar.slider("白色贴纸描边扩展 (Border Protect)", min_value=0, max_value=6, value=2)

st.sidebar.markdown("---")
wechat_online = WeChatBridge.is_wechat_running()
if wechat_online:
    st.sidebar.markdown('**微信连接状态**: <span class="status-badge status-running">● 微信客户端已运行</span>', unsafe_allow_html=True)
else:
    st.sidebar.markdown('**微信连接状态**: <span class="status-badge status-offline">○ 微信未检测到运行</span>', unsafe_allow_html=True)

st.sidebar.info("💡 **为什么不直接注入 WeChat.exe？**\n\n微信 4.x 采用云端资产校验与 SQLCipher 4 数据库，内存 Hook 极易引发微信反作弊封号。本工具通过 Win32 原生剪贴板与消息通道直连，零物理鼠标劫持，安全合规！")

# Header
st.markdown('<div class="main-title">ChatGPT ➔ WeChat 表情包极速转换器</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">一键将 ChatGPT 生成的 3×3 表情包大图切分为微信官方标准的透明背景表情，支持免鼠标极速粘贴与批量打包。</div>', unsafe_allow_html=True)

# Main layout
col_upload, col_sample = st.columns([3, 1])

uploaded_file = col_upload.file_uploader(
    "选择或拖拽 ChatGPT 表情包大图 (JPG / PNG / WEBP)",
    type=["jpg", "jpeg", "png", "webp"],
    key="file_uploader"
)

sample_clicked = col_sample.button("🖼️ 加载内置示例图", use_container_width=True)

image_to_process = None
sample_path = os.path.join(project_root, "assets", "sample_chatgpt_stickers.jpg")

if sample_clicked and os.path.exists(sample_path):
    image_to_process = Image.open(sample_path)
    st.session_state["image_source"] = "sample"
elif uploaded_file is not None:
    image_to_process = Image.open(uploaded_file)
    st.session_state["image_source"] = "upload"
elif "image_source" in st.session_state and st.session_state["image_source"] == "sample" and os.path.exists(sample_path):
    image_to_process = Image.open(sample_path)

if image_to_process is not None:
    with st.expander("👁️ 查看原图", expanded=False):
        st.image(image_to_process, caption="ChatGPT 生成的原图", use_container_width=True)

    segmenter = StickerSegmenter(
        bg_threshold=bg_threshold,
        margin=margin,
        target_size=target_size,
        dilation_radius=dilation
    )

    with st.spinner("正在使用智能轮廓与透明算法切分表情..."):
        stickers = segmenter.process(image_to_process)

    if not stickers:
        st.warning("未能检测到表情区域，请尝试调整左侧的『背景黑度阈值』或『外边距』。")
    else:
        st.success(f"✨ 成功切出 {len(stickers)} 个独立表情！已自动去除黑底并生成透明通道。")

        # Auto-export stickers to disk so absolute file paths are immediately available for CF_HDROP
        output_dir = os.path.join(project_root, "output", "stickers")
        os.makedirs(output_dir, exist_ok=True)
        saved_paths = []
        for s in stickers:
            file_path = os.path.abspath(os.path.join(output_dir, f"sticker_{s.index:02d}.png"))
            s.image.save(file_path, format="PNG")
            saved_paths.append(file_path)

        # Batch actions (Copy All, Push All, Download ZIP)
        st.markdown("#### ⚡ 批量快捷操作")
        col_act1, col_act2, col_act3 = st.columns([1.2, 1.2, 1])

        if col_act1.button("📋 一键复制全部表情 (到剪贴板)", type="primary", use_container_width=True):
            ok = WeChatBridge.copy_files_to_clipboard(saved_paths)
            if ok:
                st.success(f"🎉 **成功将全部 {len(saved_paths)} 个透明表情复制到系统剪贴板！**\n\n👉 现在打开微信任意聊天框（如**文件传输助手**），直接按下键盘 **`Ctrl + V`**，9 个表情就会**一次性全部排队粘贴**进输入框，按回车即可全发！")
                st.toast(f"✅ 全部 {len(saved_paths)} 个表情已复制！切换到微信按 Ctrl+V 即可批量粘贴！", icon="🎉")
            else:
                st.error("复制到剪贴板失败，请检查运行环境。")

        if col_act2.button("🚀 一键推送全部表情到微信", use_container_width=True):
            if not wechat_online:
                st.warning("未检测到运行中的微信，请先登录并打开微信。")
            else:
                ok = WeChatBridge.paste_files_to_active_chat(saved_paths)
                if ok:
                    st.success(f"🚀 **全部 {len(saved_paths)} 个表情已免鼠标自动推送到微信！**\n\n👉 在微信输入框中直接按下 **回车 (Enter)** 即可一次性发送！")
                    st.toast(f"🎉 全部 {len(saved_paths)} 个表情已推送到微信！按回车即可发送！", icon="🚀")
                else:
                    ok_copy = WeChatBridge.copy_files_to_clipboard(saved_paths)
                    if ok_copy:
                        st.info("已将全部表情复制到剪贴板！请切换到微信按 Ctrl+V 粘贴。")
                    else:
                        st.error("未能找到微信主窗口，请确保微信界面未被最小化。")

        zip_bytes = StickerExporter.export_to_bytes_zip(stickers, prefix="gpt_wechat_sticker")
        col_act3.download_button(
            label="📦 打包下载全部 (ZIP)",
            data=zip_bytes,
            file_name="chatgpt_wechat_stickers.zip",
            mime="application/zip",
            use_container_width=True
        )

        st.markdown("---")
        st.markdown("### 🎨 表情切片列表（可单独复制、推送或下载）")

        # Grid display (3 items per row)
        cols_per_row = 3
        for row_start in range(0, len(stickers), cols_per_row):
            row_stickers = stickers[row_start:row_start + cols_per_row]
            cols = st.columns(cols_per_row)

            for col, sticker in zip(cols, row_stickers):
                with col:
                    st.markdown(f"**表情 #{sticker.index:02d}** ({sticker.image.width}×{sticker.image.height} PNG)")
                    # Show image with checkerboard
                    st.image(sticker.image, width=200)

                    sticker_file_path = saved_paths[sticker.index - 1]
                    btn_col1, btn_col2, btn_col3 = st.columns(3)

                    # Copy single sticker
                    if btn_col1.button(f"📋 复制", key=f"copy_{sticker.index}", use_container_width=True):
                        ok = WeChatBridge.copy_image_to_clipboard(sticker_file_path)
                        if ok:
                            st.toast(f"✅ 表情 #{sticker.index:02d} 已复制！在微信按 Ctrl+V 即可粘贴！", icon="🎉")
                        else:
                            st.error("复制失败")

                    # Push single sticker to WeChat
                    if btn_col2.button(f"🚀 推送", key=f"push_{sticker.index}", use_container_width=True):
                        ok = WeChatBridge.paste_files_to_active_chat([sticker_file_path])
                        if ok:
                            st.toast(f"🚀 表情 #{sticker.index:02d} 已推送到微信！", icon="🚀")
                        else:
                            st.error("推送失败")

                    # Download single image
                    img_byte_arr = io.BytesIO()
                    sticker.image.save(img_byte_arr, format='PNG')
                    btn_col3.download_button(
                        label="📥 下载",
                        data=img_byte_arr.getvalue(),
                        file_name=f"sticker_{sticker.index:02d}.png",
                        mime="image/png",
                        key=f"dl_{sticker.index}",
                        use_container_width=True
                    )
                    st.markdown("---")

        st.markdown("""
        ---
        ### 📖 微信添加表情与批量使用指南：
        1. **一次性全发微信（最推荐）**：
           * 点击上方的 **『📋 一键复制全部表情』**；
           * 打开微信聊天窗口（例如“文件传输助手”或好友聊天），按下键盘 **`Ctrl + V`**，**9 个透明表情会全部整齐粘贴到输入框**；
           * 按回车直接发送！在聊天中右键任意表情即可「添加到表情」！
        2. **免鼠标全自动推送**：
           * 打开微信保持在聊天界面，点击上方的 **『🚀 一键推送全部表情到微信』**，程序会自动激活微信并将 9 个表情同时粘贴好，你只要敲一下回车就搞定！
        3. **批量永久导入表情库**：
           * 点击 **『📦 打包下载全部 (ZIP)』** 解压到本地文件夹；
           * 在微信中点击聊天输入框的表情图标 ➔ 点击“添加表情（+号）” ➔ “我添加的表情” ➔ 滑到最下方点击“+”即可一次性多选批量导入！
        """)
else:
    st.info("👈 请在上方上传 ChatGPT 表情包大图，或点击『🖼️ 加载内置示例图』立即体验！")
