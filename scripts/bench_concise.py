"""Compare 'strong' vs 'concise' on your real dictations (history.jsonl) and fixed samples.

Writes scripts/concise_report.md.
"""
import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from budazi import config
from budazi.polish import Polisher

FIXED = [
    ("我想让你帮我优化一下首页的加载速度。现在首页打开要五秒多，太慢了。图片也没压缩。所以就是说，我希望你帮我把首页加载"
     "速度优化一下，目标是两秒以内。", ["5|五", "2|两", "图片", "压缩"]),
    ("把超时改成三十秒，不要改重试次数，重试次数还是三次，然后日志级别改成debug。", ["30|三十", "不要|别|不改", "3|三", "debug"]),
    ("你觉得这个方案怎么样，就是用redis做缓存，会不会有问题？", ["redis", "？"]),
    ("这个很重要很重要，千万不要删数据库，千万不要。", ["千万不要|绝对不要|不要", "数据库"]),
    ("我现在的想法是先做一个最简单的版本，嗯，就是只支持中文，然后呢等这个跑通了再加英文，再加那个就是词典，对，个人词典，"
     "最后再考虑流式。", ["中文", "英文", "个人词典", "流式"]),
    ("嗯我觉得吧，这个PR整体来说其实写得还行，就是说那个error handling那块我觉得还是有点问题的，没有处理超时的情况，"
     "然后test覆盖率也不太够，大概只有百分之四十左右，我觉得至少要到百分之八十才能合。",
     ["PR", "error handling", "超时", "40|四十", "80|八十"]),
]
hist = [json.loads(l) for l in (ROOT / "history.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
REAL = [(h["raw"], []) for h in hist if len(h["raw"]) >= 60][-4:]

cfg, key = config.load()
p = Polisher(key, cfg.polish_base_url, cfg.polish_model, timeout_s=30)
p.warmup()
VARIANTS = [("strong", cfg.long_model, "现在的重度（Kimi）"),
            ("concise", cfg.polish_model, "精炼（DeepSeek）"),
            ("concise", cfg.long_model, "精炼（Kimi）")]
stats = {v[2]: {"t": [], "ratio": [], "miss": 0} for v in VARIANTS}
lines = []
for title, cases in (("你的真实口述", REAL), ("固定样例（检查有没有丢信息）", FIXED)):
    lines.append(f"\n# {title}\n")
    for i, (raw, must) in enumerate(cases, 1):
        lines.append(f"\n## {i}\n**原文**（{len(raw)} 字）：{raw}\n")
        for level, model, name in VARIANTS:
            text, dt = p.polish(raw, cfg.dictionary, model=model, level=level)
            low = text.lower()
            missing = [m for m in must if not any(a.lower() in low for a in m.split("|"))]
            s = stats[name]
            s["t"].append(dt); s["ratio"].append(len(text) / len(raw)); s["miss"] += len(missing)
            flag = f"  ⚠️ 缺少：{missing}" if missing else ""
            lines.append(f"**{name}**（{len(text)} 字，{dt*1000:.0f} ms）：\n\n{text}{flag}\n")
head = ["# 重度 vs 精炼\n"]
for name, s in stats.items():
    head.append(f"- {name}：平均长度为原文的 {statistics.mean(s['ratio'])*100:.0f}%，丢失信息 {s['miss']} 处，"
                f"中位数 {statistics.median(s['t'])*1000:.0f} ms，最慢 {max(s['t'])*1000:.0f} ms")
out = "\n".join(head + lines)
(ROOT / "scripts" / "concise_report.md").write_text(out, encoding="utf-8")
print(out)
