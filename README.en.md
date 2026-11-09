# budazi (不打字)

**Hold-to-talk voice typing for Windows (a personal tool)** ｜ [中文](README.md) · English

*budazi* is Chinese for "no typing". In any text box, **hold Ctrl, speak, and let go**: cleaned-up text appears at your cursor. It is built for dictating long prompts to ChatGPT, Claude and other AI agents, and works for everyday typing too.

- 🎙 **Local speech recognition**: SenseVoice-Small runs on the CPU (no GPU needed) and handles Chinese, English and mixed speech, plus Japanese, Korean and Cantonese
- ✍️ **AI cleanup**: removes filler words ("um", "uh", "嗯", "那个"), applies self-corrections ("no wait, make it…"), merges repetition and fixes word order. Four levels to choose from
- ⚡ **Fast**: short phrases appear about 0.5 s after you let go. Long dictation is transcribed while you speak, so after release you only wait for the cleanup
- 🖥 **Unobtrusive**: a small pill at the bottom of the screen shows recording and processing status. It never steals focus, and quick shortcuts like Ctrl+C don't trigger it

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
- **The only thing that leaves your computer**: when cloud AI cleanup is on, the **transcribed text** is sent to **the LLM provider you configured yourself** (Fireworks by default) and is handled under that provider's privacy policy.
- **Fully offline**: use a local model (Ollama, see "Option B" below) or turn off "AI 润色" (AI cleanup) in the tray menu.
- **Local records**: `history.jsonl` keeps each raw transcript and its cleaned-up version so you can look back. Recordings are not saved by default (`keep_recordings = 0`). These files stay on your computer and are listed in `.gitignore`, so they are never committed.
- **Permissions**: hold-to-talk and auto-paste need a global keyboard hook and clipboard access, which a few antivirus programs may flag. All the code is public, so you can check it yourself.

---

## Installation (Windows 10 / 11)

1. **Install uv** (a Python package manager; it installs Python for you):

   ```powershell
   winget install astral-sh.uv
   ```

2. **Get the code** and install dependencies:

   ```powershell
   git clone https://github.com/maxuepo/budazi.git budazi
   cd budazi
   uv sync
   ```

3. **Download the speech recognition model** (SenseVoice-Small, about 230 MB, from Hugging Face):

   ```powershell
   uv run python scripts/download_model.py
   ```

4. **Set up AI cleanup.** Pick one. It is optional: without it you get the raw transcript.

   **Option A: cloud (best quality, fastest)**
   - Sign up at [Fireworks](https://fireworks.ai) and create an API key. Any OpenAI-compatible API works.
   - Create `api_key.txt` in the project folder with the key on the first line, or set the environment variable `FIREWORKS_API_KEY`.
   - Rough cost: about $0.0003 per short phrase and about $0.005 per long passage sent to Kimi. Heavy use comes to a few dollars a month.

   **Option B: local (fully offline, free)**
   - Install [Ollama](https://ollama.com) and run `ollama pull qwen3:8b` (about 5 GB; needs a GPU or a decent CPU).
   - Copy `config.example.toml` to `config.toml` and change the few lines described under "方案 B" (Option B) in that file.
   - Local models are slower than the cloud and clean up text less well.

5. **Start it**: double-click `start.bat`. It runs in the background with no window, and a "已启动" (started) notification appears in the bottom-right corner.

   For debugging, start it from a terminal to see the log:

   ```powershell
   uv run python -m budazi.app
   ```

6. **Start with Windows (optional)**: press `Win + R`, type `shell:startup`, and put a shortcut to `start.bat` in the folder that opens.

---

## Usage

| Action | Result |
|---|---|
| Hold Ctrl, speak, release | The text is pasted at your cursor |
| While holding, press another key, click or scroll | Treated as a shortcut; the recording is cancelled |
| Tap Ctrl, or a quick Ctrl+C | Nothing happens |
| Right-click the tray icon | Toggle AI cleanup, switch level, re-paste the last result, open history, quit |

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

- **Nothing happens when I hold Ctrl**: check for the "录音中" (recording) pill at the bottom of the screen. If it doesn't appear, look at `budazi.log` in the project folder.
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
| `budazi/overlay.py` | Status pill (Win32 layered window that never takes focus) |
| `budazi/winput.py` | Pasting, clipboard restore, foreground app detection |
| `scripts/` | Model download and benchmarks comparing the levels |

## Credits

- [SenseVoice](https://github.com/FunAudioLLM/SenseVoice) (FunAudioLLM) · [sherpa-onnx](https://github.com/k2-fsa/sherpa-onnx) (k2-fsa)
- Default cloud models: DeepSeek and Kimi, via Fireworks

## License

[MIT](LICENSE): use it however you like. Provided as is, without warranty of any kind.
