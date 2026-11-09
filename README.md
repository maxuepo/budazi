# 不打字 budazi

**Windows 按住说话 · 语音输入（自用版）** ｜ 中文 · [English](README.en.md)

在任何输入框里**按住 Ctrl 说话，松开**，整理好的文字就出现在光标位置。适合给 ChatGPT、Claude、各种 AI agent 写长指令，也适合日常打字。

- 🎙 **语音识别在本地**：SenseVoice-Small，CPU 就能跑，不占显卡，中英混说都行
- ✍️ **AI 整理**：去掉"嗯、呃、那个"，处理"不对，改成……"，合并重复，理顺语序；四个档位可选
- ⚡ **快**：短句松开后约 0.5 秒出字；长段边说边识别，松开后只需等润色
- 🖥 **不打扰**：屏幕底部小提示条显示录音 / 整理状态，不抢焦点，快捷键 Ctrl+C 不会误触发

> 灵感来自商业产品 Typeless，是个人手搓的自用版本，与 Typeless 没有任何关系。

---

## ⚠️ 声明：作者自用的小工具

这是作者自己用的小工具，开源出来给有兴趣的朋友下载研究、安装使用。

- 采用 [MIT 许可证](LICENSE)：**随便用**，个人、商业、修改、再发布都可以，保留版权声明即可。
- **按现状提供，不做任何担保**（no warranty）：没有售后，不保证稳定或适合你的用途，使用中出了问题作者不承担责任。
- 语音识别模型 SenseVoice 和你选用的大模型，各自还有它们自己的许可条款，需要单独遵守。

## 🔒 隐私说明

- **本项目不收集任何数据**：没有统计、没有遥测、没有作者的服务器，作者看不到你说了什么。
- **录音不出电脑**：语音识别完全在本地完成。
- **唯一会离开电脑的**：开启"云端 AI 润色"时，**识别出来的文字**会发给**你自己配置的**大模型服务商（默认 Fireworks），按该服务商的隐私政策处理。
- **想完全离线**：用本地模型（Ollama，见下文"方案 B"），或者在托盘菜单里关掉「AI 润色」。
- **本地记录**：`history.jsonl` 记录每次的原文和整理结果，方便你回看；录音默认不保存（`keep_recordings = 0`）。这些文件都只在你电脑上，并且已在 `.gitignore` 里，不会被提交。
- **权限**：为了实现"按住说话、自动粘贴"，程序需要监听全局按键、读写剪贴板。少数杀毒软件可能因此提示，代码全部公开，可以自行检查。

---

## 安装（Windows 10 / 11）

1. **装 uv**（Python 包管理器，会自动装好 Python）：

   ```powershell
   winget install astral-sh.uv
   ```

2. **下载代码**，进入项目目录，安装依赖：

   ```powershell
   git clone https://github.com/maxuepo/budazi.git budazi
   cd budazi
   uv sync
   ```

3. **下载语音识别模型**（SenseVoice-Small，约 230 MB，来自 Hugging Face）：

   ```powershell
   uv run python scripts/download_model.py
   ```

4. **配置 AI 润色**（二选一，不配也能用，只是输出识别原文）：

   **方案 A：云端（效果好、速度快）**
   - 在 [Fireworks](https://fireworks.ai) 注册并创建 API key（或任何兼容 OpenAI 接口的服务）
   - 在项目目录新建 `api_key.txt`，第一行写 key；或者设置环境变量 `FIREWORKS_API_KEY`
   - 费用参考：短句约 $0.0003 / 次；长段用 Kimi 约 $0.005 / 次。重度使用每月几美元

   **方案 B：本地（完全离线、免费）**
   - 安装 [Ollama](https://ollama.com)，运行 `ollama pull qwen3:8b`（约 5 GB，需要显卡或较好的 CPU）
   - 把 `config.example.toml` 复制成 `config.toml`，按里面"方案 B"的说明改几行
   - 本地模型比云端慢，整理效果也弱一些

5. **启动**：双击 `start.bat`（后台运行，没有窗口）。右下角会弹出"已启动"通知。

   调试时可以用命令行启动，能看到日志：

   ```powershell
   uv run python -m budazi.app
   ```

6. **开机自启（可选）**：按 `Win + R` 输入 `shell:startup`，把 `start.bat` 的快捷方式放进去。

---

## 使用

| 操作 | 效果 |
|---|---|
| 按住 Ctrl 说话，松开 | 文字粘贴到光标位置 |
| 按住时又按了别的键 / 点鼠标 / 滚滚轮 | 当作快捷键，取消这次录音 |
| 轻点 Ctrl / 快速 Ctrl+C | 什么都不发生 |
| 右键托盘图标 | 开关 AI 润色、切换档位、重新粘贴上一条、打开历史、退出 |

**四个档位**

| 档位 | 做什么 | 适合 |
|---|---|---|
| 轻度 | 去口头禅、改口误、加标点 | 想保留原话 |
| 重度（默认） | 再合并重复、理顺语序 | 日常使用 |
| 精炼 | 删铺垫、先说重点，约原文一半长 | 给 AI 下指令 |
| 梳理 | 补上跳掉的逻辑、调整先后顺序，尽量保留你的文风 | 想法比较跳跃时 |

## 自定义

- **设置**：把 `config.example.toml` 复制为 `config.toml` 再改（热键、模型、档位、按程序切换风格等，里面都有注释）。
- **个人词表**：把 `dictionary.example.txt` 复制为 `dictionary.txt`，加上你常说的人名、项目名、术语，识别听错时润色会按词表改回来。
- `config.toml`、`dictionary.txt`、`api_key.txt` 都在 `.gitignore` 里，不会被提交。

## 常见问题

- **按 Ctrl 没反应**：看屏幕底部有没有"录音中"提示条；没有的话，查看项目目录下的 `budazi.log`。
- **管理员权限的窗口里粘贴不进去**：Windows 的权限隔离，需要本程序也以管理员身份运行。
- **粘贴后剪贴板被冲掉**：程序粘贴后会恢复原来的剪贴板，但只能恢复文字，图片会丢。
- **识别不准**：把错的词加进 `dictionary.txt`；或在 `config.toml` 里设 `keep_recordings = 20` 保存录音，配合 `scripts/compare_live.py` 排查。

## 项目结构

| 文件 | 作用 |
|---|---|
| `budazi/app.py` | 热键、托盘、主流程 |
| `budazi/audio.py` | 录音（300 ms 预录，开头不丢字） |
| `budazi/live.py` | 长段边说边分段识别 |
| `budazi/asr.py` | SenseVoice 语音识别（sherpa-onnx） |
| `budazi/polish.py` | 各档位的润色提示词、调用大模型 |
| `budazi/overlay.py` | 屏幕底部状态提示条（Win32 分层窗口，不抢焦点） |
| `budazi/winput.py` | 粘贴、恢复剪贴板、获取前台程序 |
| `scripts/` | 模型下载、各档位效果对比测试 |

## 致谢

- [SenseVoice](https://github.com/FunAudioLLM/SenseVoice)（FunAudioLLM）· [sherpa-onnx](https://github.com/k2-fsa/sherpa-onnx)（k2-fsa）
- 默认云端模型：DeepSeek、Kimi（通过 Fireworks）

## 许可证

[MIT](LICENSE) —— 随便用，按现状提供，不做任何担保。
