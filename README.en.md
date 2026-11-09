# budazi (不打字)

**Hold-to-talk voice typing for Windows and macOS (a personal tool)** ｜ [中文](README.md) · English

*budazi* is Chinese for "no typing". In any text box, **hold Ctrl (Control on a Mac), speak, and let go**: cleaned-up text appears at your cursor. It is built for dictating long prompts to ChatGPT, Claude and other AI agents, and works for everyday typing too.

- 🎙 **Local speech recognition**: SenseVoice-Small runs on the CPU (no GPU needed) and handles Chinese, English and mixed speech, plus Japanese, Korean and Cantonese
- ✍️ **AI cleanup**: removes filler words ("um", "uh", "嗯", "那个"), applies self-corrections ("no wait, make it…"), merges repetition and fixes word order. Four levels to choose from
- ⚡ **Fast**: short phrases appear about 0.5 s after you let go. Long dictation is transcribed while you speak, so after release you only wait for the cleanup
- 🖥 **Unobtrusive**: on Windows, a small pill at the bottom of the screen shows recording and processing status without stealing focus. On a Mac, the menu bar icon changes color and plays a sound. Quick shortcuts like Ctrl+C don't trigger it
- 💻 **Windows 10 / 11 and macOS** (macOS support is experimental, see below)

> Inspired by the commercial app Typeless. This is an independent, home-made tool and is not affiliated with Typeless in any way.

---

## ⚠️ Disclaimer: a personal tool

I built this for my own use and am sharing it for anyone who wants to study it or use it.

- Licensed under the [MIT License](LICENSE): **do whatever you want with it**, including personal or commercial use, modification and redistribution. Just keep the copyright notice.
- **Provided "as is", without warranty of any kind.** There is no support and no guarantee that it works or fits your needs, and the author is not liable for anything that happens when you use it.
- The SenseVoice speech model and whichever LLM you choose each have their own license terms, which you need to follow separately.

## 🔒 Privacy

- **This project collects nothing.** There is no analytics, no telemetry and no server run by the author, so the author never sees what you say.
- **Your audio never leaves your computer.** Speech recognition runs entirely locally.
- **The only thing that leaves your computer**: when cleanup uses the cloud model, the **transcribed text** is sent to **the LLM provider you configured yourself** (Fireworks by default) and is handled under that provider's privacy policy.
- **Fully offline**: switch to "用本地模型" (local model, Ollama, see "Option B" below) in the tray menu, or turn off "AI 润色" (AI cleanup). In local mode budazi never falls back to the cloud: if the model fails, you get the raw transcript.
- **Local records**: `history.jsonl` keeps each raw transcript and its cleaned-up version so you can look back. Recordings are not saved by default (`keep_recordings = 0`). These files stay on your computer and are listed in `.gitignore`, so they are never committed.
- **Permissions**: hold-to-talk and auto-paste need a global keyboard hook and clipboard access (on a Mac you grant these yourself, see below), which a few antivirus programs may flag. All the code is public, so you can check it yourself.

---

## Installation

Steps 1 to 4 are the same on Windows and macOS; after that they differ.

1. **Install uv** (a Python package manager; it installs Python for you):

   ```powershell
   # Windows
   winget install astral-sh.uv
   ```

   ```bash
   # macOS
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

2. **Get the code** and install dependencies:

   ```bash
   git clone https://github.com/maxuepo/budazi.git budazi
   cd budazi
   uv sync
   ```

3. **Download the speech recognition model** (SenseVoice-Small, about 230 MB, from Hugging Face):

   ```bash
   uv run python scripts/download_model.py
   ```

4. **Set up AI cleanup.** Pick one. It is optional: without it you get the raw transcript.

   **Option A: cloud (best quality, fastest)**
   - Sign up at [Fireworks](https://fireworks.ai) and create an API key. Any OpenAI-compatible API works.
   - Create `api_key.txt` in the project folder with the key on the first line, or set the environment variable `FIREWORKS_API_KEY`.
   - Rough cost: about $0.0003 per short phrase and about $0.005 per long passage sent to Kimi. Heavy use comes to a few dollars a month.

   **Option B: local (fully offline, free)**
   - Install [Ollama](https://ollama.com) and run `ollama pull qwen3:8b` (about 5 GB; needs a GPU, a decent CPU or an Apple Silicon Mac).
   - Copy `config.example.toml` to `config.toml` and set `local_model` to the model you installed (`ollama list` shows them).
   - Once running, pick **"用本地模型" (use local model)** in the tray menu to switch, and switch back to the cloud any time. To start in local mode, set `backend = "local"` in `config.toml`.
   - budazi asks the model to skip its "thinking" step automatically; otherwise reasoning models add several seconds per phrase.
   - Measured on an RTX 3080 Ti with a 9B model: about 0.4 s per phrase, faster than the cloud. Small models sometimes invent conclusions on the Restructure (梳理) level, so the cloud is better for that one.

### Windows: start it

5. Double-click `start.bat`. It runs in the background with no window, and a "已启动" (started) notification appears in the bottom-right corner.

   For debugging, start it from a terminal to see the log:

   ```powershell
   uv run python -m budazi.app
   ```

6. **Start with Windows (optional)**: press `Win + R`, type `shell:startup`, and put a shortcut to `start.bat` in the folder that opens.

### macOS: start it (experimental)

> ⚠️ The macOS code is written and its logic (pasting, frontmost-app detection, sounds, single-instance lock) has been tested in a simulated environment, but it **has not been run on a real Mac yet**. If something goes wrong, check `budazi.log` or open an issue on GitHub.

5. **Start it from a terminal the first time**, so you can grant permissions and see any errors:

   ```bash
   uv run python -m budazi.app
   ```

6. **Grant permissions**: open System Settings → Privacy & Security and enable these three for the **terminal app** you run it from (Terminal or iTerm). Then **quit the terminal, reopen it** and start budazi again.
   - **Microphone**: to record
   - **Input Monitoring**: to notice you holding Control
   - **Accessibility**: to press Cmd+V for you

7. **After that**: double-click `start_mac.command` in Finder. If macOS says it can't open it, run `chmod +x start_mac.command` once in a terminal. A microphone icon appears on the right of the menu bar.

8. **Start at login (optional)**:

   ```bash
   bash scripts/mac_autostart.sh          # install
   bash scripts/mac_autostart.sh remove   # uninstall
   ```

   When started this way, macOS attributes the permissions to `.venv/bin/python`, so add that file under Input Monitoring and Accessibility too (click +, then press `Cmd+Shift+G` to type the path).

**How the Mac version differs**
- You still hold **Control** to talk. Macs copy and paste with Cmd, so Control rarely clashes. To use Right Option instead, set `hotkey = "alt_r"` in `config.toml`.
- There is no pill at the bottom of the screen. Instead the **menu bar icon turns red** while recording and amber while processing, with a short sound (Tink / Pop).
- Per-app styles use the app name in lower case, such as `code`, `terminal`, `iterm2` or `wechat`. The example config already includes these.

---

## Usage

| Action | Result |
|---|---|
| Hold Ctrl (Mac: Control), speak, release | The text is pasted at your cursor |
| While holding, press another key, click or scroll | Treated as a shortcut; the recording is cancelled |
| Tap Ctrl, or a quick Ctrl+C | Nothing happens |
| Right-click the tray icon (Mac: click the menu bar icon) | Toggle AI cleanup, switch level, **switch between cloud and local model**, re-paste the last result, open history, quit |

**Four cleanup levels**

| Level (menu name) | What it does | Good for |
|---|---|---|
| Light (轻度) | Removes filler words, applies self-corrections, adds punctuation | Keeping your exact wording |
| Strong (重度, default) | Also merges repetition and fixes word order | Everyday use |
| Concise (精炼) | Cuts the preamble and leads with the point, about half the original length | Instructions to AI |
| Restructure (梳理) | Fills in skipped reasoning and reorders, while keeping your voice | When your thoughts jump around |

The prompts are written for Chinese speakers but handle English and mixed speech too. English input stays in English and is never translated.

## Customizing

- **Settings**: copy `config.example.toml` to `config.toml` and edit it. Hotkey, models, level and per-app styles are all there with comments (in Chinese).
- **Personal word list**: copy `dictionary.example.txt` to `dictionary.txt` and add names, project names and jargon you use. When recognition mishears them, the cleanup step fixes them using your list.
- `config.toml`, `dictionary.txt` and `api_key.txt` are in `.gitignore` and never committed.

## FAQ

- **Nothing happens when I hold Ctrl**: on Windows, check for the "录音中" (recording) pill at the bottom of the screen; on a Mac, check whether the menu bar icon turns red. If not, look at `budazi.log` in the project folder.
- **On a Mac, holding Control does nothing, or the text isn't pasted**: usually a missing permission. Check that your terminal is listed under Input Monitoring and Accessibility, then quit and reopen the terminal.
- **Can't paste into an admin window**: Windows isolates elevated apps, so budazi has to run as administrator too.
- **My clipboard got overwritten**: budazi restores your previous clipboard after pasting, but only text. Images are lost.
- **Poor recognition**: add the misheard words to `dictionary.txt`. Or set `keep_recordings = 20` in `config.toml` to save recordings and investigate with `scripts/compare_live.py`.

## Project layout

| File | Purpose |
|---|---|
| `budazi/app.py` | Hotkey, tray icon, main flow |
| `budazi/audio.py` | Recording (300 ms pre-roll so the first word isn't cut) |
| `budazi/live.py` | Transcribes long dictation in chunks while you speak |
| `budazi/asr.py` | SenseVoice speech recognition (sherpa-onnx) |
| `budazi/polish.py` | Cleanup prompts for each level and LLM calls |
| `budazi/overlay.py` | Status pill, Windows only (Win32 layered window that never takes focus) |
| `budazi/system.py` | Picks the platform layer for the current OS |
| `budazi/winput.py` | Windows: pasting, clipboard restore, foreground app, sounds, single instance |
| `budazi/macinput.py` | macOS: the same (Cmd+V, AppKit, afplay, file lock) |
| `scripts/` | Model download, Mac autostart, benchmarks comparing the levels, simulated test of the Mac code (`test_mac_sim.py`) |

## Credits

- [SenseVoice](https://github.com/FunAudioLLM/SenseVoice) (FunAudioLLM) · [sherpa-onnx](https://github.com/k2-fsa/sherpa-onnx) (k2-fsa)
- Default cloud models: DeepSeek and Kimi, via Fireworks

## License

[MIT](LICENSE): use it however you like. Provided as is, without warranty of any kind.
