"""Compare a local Ollama model with the cloud model on all benchmark cases.

Usage: python scripts/bench_local.py [ollama_model]   (default: qwen3:8b)
Writes scripts/local_report.md.
"""
import ast
import re
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from budazi import config
from budazi.polish import Polisher

LOCAL = sys.argv[1] if len(sys.argv) > 1 else "qwen3:8b"


def cases_from(script: str, var: str):
    src = (ROOT / "scripts" / script).read_text(encoding="utf-8")
    node = next(n for n in ast.parse(src).body
                if isinstance(n, ast.Assign) and getattr(n.targets[0], "id", "") == var)
    return ast.literal_eval(node.value)


SETS = [
    ("strong", [(c[0], c[1]) for c in cases_from("bench_levels.py", "CASES")]),
    ("strong", [(c[0], c[1]) for c in cases_from("bench_merge.py", "NEW")]),
    ("concise", [(c[0], c[1]) for c in cases_from("bench_levels.py", "CASES")[:6]]),
    ("restructure", [(c[0], c[1]) for c in cases_from("bench_restructure.py", "FIXED")]),
]
cfg, key = config.load()
cloud = Polisher(key, cfg.polish_base_url, cfg.polish_model, timeout_s=30)
local = Polisher(None, "http://localhost:11434/v1", LOCAL, timeout_s=120)
cloud.warmup()
local.polish("测试", level="light")  # make sure the model is loaded
han = re.compile(r"[一-鿿]")
stats = {n: {"t": [], "miss": 0, "translated": 0, "think": 0} for n in ("cloud", "local")}
lines = []
for level, cases in SETS:
    lines.append(f"\n# {level}\n")
    for raw, must in cases:
        lines.append(f"\n**原文**：{raw}\n")
        for name, p in (("cloud", cloud), ("local", local)):
            text, dt = p.polish(raw, cfg.dictionary, level=level)
            s = stats[name]
            s["t"].append(dt)
            low = text.lower()
            missing = [m for m in must if not any(a.lower() in low for a in m.split("|"))]
            s["miss"] += len(missing)
            translated = not han.search(raw) and bool(han.search(text))
            s["translated"] += translated
            s["think"] += "think>" in text
            flag = (f"  ⚠️ 缺少：{missing}" if missing else "") + ("  ❌ 被翻译" if translated else "")
            label = "DeepSeek（云端）" if name == "cloud" else f"{LOCAL}（本地）"
            lines.append(f"- {label} {dt*1000:.0f} ms：{text}{flag}")
head = [f"# 本地 {LOCAL} vs 云端 {cfg.polish_model.split('/')[-1]}\n"]
for name, s in stats.items():
    head.append(f"- {name}: {len(s['t'])} 次，中位数 {statistics.median(s['t'])*1000:.0f} ms，"
                f"最慢 {max(s['t'])*1000:.0f} ms，丢信息 {s['miss']} 处，英文被翻译 {s['translated']} 次，"
                f"漏出思考标签 {s['think']} 次")
out = "\n".join(head + lines)
(ROOT / "scripts" / "local_report.md").write_text(out, encoding="utf-8")
print("\n".join(head))
