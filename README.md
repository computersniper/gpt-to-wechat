# GPT-to-WeChat (ChatGPT 表情包一键转微信)

<p align="center">
  <img src="assets/sample_chatgpt_stickers.jpg" alt="ChatGPT Sticker Sample" width="360" style="border-radius: 10px;" />
</p>

<p align="center">
  <b>一键将 ChatGPT 生成的表情包大图（3×3 网格）智能切分、抠图并无缝导入至微信（WeChat）</b><br>
  <i>Smartly segment, mat, normalize and bridge ChatGPT sticker sheets into WeChat without mouse clicking or account ban risks.</i>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.9%2B-blue.svg" alt="Python Version" />
  <img src="https://img.shields.io/badge/Platform-Windows-0078D6.svg" alt="Platform" />
  <img src="https://img.shields.io/badge/WeChat-Windows_4.x_Compatible-07C160.svg" alt="WeChat Compatible" />
  <img src="https://img.shields.io/badge/License-MIT-green.svg" alt="License" />
</p>

---

## 🌟 项目背景 (Background)

ChatGPT 新增的表情包生成功能（Stickers）非常受欢迎，但官方仅支持一键导出到苹果的 **iMessage** 和 **WhatsApp**，无法直接导入到中国大陆最常用的 **微信 (WeChat)** 中。从 ChatGPT 下载下来的通常是一张含有 9 个（3×3）独立贴纸、带黑底和白色切边的大图。

本项目专为解决该痛点而生：
- 自动定位并切分大图中的各个独立表情。
- 智能抠除黑色背景，完整保留可爱的白色贴纸描边（White Die-cut Border），生成高清晰度透明通道（Alpha Channel）。
- 规范化为微信表情官方标准格式（240×240 正方形透明 PNG，文件体积 < 500KB）。
- 提供**免物理鼠标移动劫持**的原生系统桥接与现代 Web 交互界面，秒级添加到微信！

---

## 🛡️ 架构设计与安全性说明 (Why No DLL Hook?)

在开发本项目时，我们对本地运行的最新版微信（**Weixin 4.1 64位 Qt 重构版**）进行了深入的系统级逆向与架构调研：

> [!IMPORTANT]
> **为什么不采用“内存注入 (DLL Hook) / 直接写本地数据库”插件？**
>
> 1. **微信表情是强云端资产**：
>    微信的“自定义表情”并非只是本地文件夹里的图片。添加到微信收藏夹时，客户端必须通过腾讯加密的私有协议（MMTLS）将图片上传至腾讯 CDN，服务器登记校验后才会下发元数据。如果仅仅离线强行往本地 SQLite 数据库（微信 4.x 采用 SQLCipher 4 加密，PBKDF2 迭代高达 256,000 次）写入，**云端一旦同步就会立刻将其覆盖删除**。
> 2. **反作弊与封号风险极高**：
>    微信 4.x 重构版拥有严格的进程完整性校验（TP反外挂模块）。任何尝试对 `Weixin.exe` 或 `Weixin.dll` 进行内存注入、API Hook 拦截发包的行为，都极易被腾讯安全中心检测到并处以**账号永久封禁**！
> 3. **本项目采用的最佳实践：原生 Win32 通道与剪贴板流**：
>    - **零物理鼠标劫持**：完全不移动用户的真实鼠标指针，不抢占屏幕焦点。
>    - **原生系统剪贴板通道**：直接注册 Windows 原生 `PNG` 与 `CF_DIB` 剪贴板格式，保留完整透明度。在微信中按 `Ctrl+V` 即贴即发，右键即可一键“添加到表情”，安全合规，绝无封号风险！

---

## ✨ 核心特性 (Features)

- 🔍 **智能连通域与网格检测 (Smart Segmentation)**：基于形态学孔洞填充与轮廓过滤算法，完美识别大图中的 9 个（或任意数量）表情区域。
- ✂️ **黑底智能抠除与描边保护 (Border Preservation)**：自适应膨胀掩模，去除纯黑底色同时 100% 保护白色描边与主体颜色。
- 📐 **微信标准规格自适应 (WeChat Spec Optimization)**：自动居中并采用 Lanczos 高阶插值采样重调为 240×240 / 300×300 规范表情。
- 📋 **免鼠标一键直达 (Zero-Click Bridge)**：单张一键推入系统剪贴板，支持在微信聊天窗口中直接粘贴发送。
- 📦 **批量打包导出 (Batch Export)**：一键将所有切分出来的透明表情打包为 ZIP 压缩包，方便在微信“管理表情”中批量全选导入。
- 🖥️ **精美 Web 可视化操作界面 (Modern WebUI)**：提供棋盘格透明背景实时预览、阈值微调滑块与一键下载。
- 💻 **全功能 CLI 命令行**：支持无头环境批量处理脚本集成。

---

## 🚀 快速上手 (Quick Start)

### 1. 环境准备

确保已安装 Python 3.9 或更高版本（Windows 系统推荐）：

```bash
# 克隆仓库
git clone https://github.com/computersniper/gpt-to-wechat.git
cd gpt-to-wechat

# 安装依赖
pip install -r requirements.txt
```

### 2. 启动可视化 Web 界面（推荐）

```bash
python main.py
# 或者运行:
streamlit run ui/app.py
```
启动后浏览器将自动打开交互界面：
1. 上传 ChatGPT 生成的表情包大图（或点击“🖼️ 加载内置示例图”快速体验）。
2. 界面将实时显示切分出的 9 个透明表情。
3. 点击任意表情下方的 **『📋 复制』** 按钮。
4. 切换到微信（如“文件传输助手”或任意聊天窗口），按下 **`Ctrl + V`** 发送！
5. 在聊天记录中**右键该图片 ➔ “添加到表情”**，即可永久添加到表情收藏夹！

---

### 3. 使用命令行工具 (CLI)

```bash
# 智能切分大图并保存到 output/stickers 目录
python cli.py process assets/sample_chatgpt_stickers.jpg

# 切分同时打包为 ZIP 文件
python cli.py process assets/sample_chatgpt_stickers.jpg --zip

# 自定义分辨率与背景阈值
python cli.py process input.png --size 300 --threshold 40 --output my_stickers/
```

**CLI 参数说明**：
| 参数 | 说明 | 默认值 |
| :--- | :--- | :--- |
| `input` | 输入的 ChatGPT 表情图片路径 | 必填 |
| `-o, --output` | 表情切片保存目录 | `output/stickers` |
| `--size` | 输出正方形尺寸（微信推荐 240） | `240` |
| `--threshold`| 黑色背景亮度阈值 | `35` |
| `--margin` | 贴纸外边距填充像素 | `8` |
| `--zip` | 是否额外导出打包 ZIP | `False` |
| `--copy-first`| 处理完成后自动将第1张表情放入剪贴板 | `False` |

---

## 📂 项目结构 (Project Structure)

```text
gpt-to-wechat/
├── assets/                  # 示例图片与项目资源
│   └── sample_chatgpt_stickers.jpg
├── core/                    # 核心算法与桥接模块
│   ├── __init__.py
│   ├── segmenter.py         # ChatGPT 表情智能切图与透明抠图算法
│   ├── wechat_bridge.py     # Win32 原生免鼠标剪贴板与微信桥接
│   └── exporter.py          # 表情批量导出与 ZIP 压缩工具
├── ui/                      # 可视化用户界面
│   └── app.py               # Streamlit 交互式 Web 应用
├── tests/                   # 自动化单元测试
│   └── test_core.py         # 核心切图与导出测试用例
├── output/                  # 默认输出目录
├── cli.py                   # 命令行入口
├── main.py                  # 主程序快速启动脚本
├── requirements.txt         # 依赖声明
├── LICENSE                  # 开源协议 (MIT)
└── README.md                # 项目文档
```

---

## 🧪 单元测试 (Running Tests)

运行项目自带的单元测试：

```bash
python -m unittest tests/test_core.py
```

---

## 🤝 贡献与反馈 (Contributing)

欢迎提交 Issue 和 Pull Request！如果你有关于更智能的切图算法、跨平台支持或微信集成的优化想法，欢迎与我们交流。

## 📄 开源许可 (License)

本项目基于 [MIT License](LICENSE) 开源发布。
