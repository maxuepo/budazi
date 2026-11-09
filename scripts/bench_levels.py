"""Compare light vs strong cleanup on rambling, repetitive transcripts.

Writes scripts/levels_report.md and prints a summary.
"""
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from budazi import config
from budazi.polish import Polisher

# (transcript as SenseVoice would give it, what must survive)
CASES = [
    ("我想要那个就是我想要你帮我把这个函数改一下，改一下这个函数，让它支持就是支持异步。",
     ["异步"]),
    ("这个bug是因为呃是因为那个缓存没有没有清掉，不是，是因为缓存的那个过期时间设错了。",
     ["过期时间"]),
    ("你先别提交啊，测试跑完再说。对了还有那个lint也要跑。先跑测试，然后lint，然后再提交。",
     ["测试", "lint", "提交"]),
    ("帮我写个脚本下载那些图片，从那个json里面读url，对，每张图存到images文件夹，文件名用id。",
     ["json", "url", "images", "id"]),
    ("把超时改成三十秒，不要改重试次数，重试次数还是三次，然后日志级别改成debug。",
     ["30", "不要改", "3", "debug"]),
    ("so basically what I want is uh I want the the button to be like disabled you know disabled "
     "when the form is invalid and and also show a tooltip.", ["disabled", "invalid", "tooltip"]),
    ("这个PR呃这个PR我看了一下，整体没问题，就是就是那个error handling那块那块要再看看，还有test覆盖率太低了。",
     ["PR", "error handling", "覆盖率"]),
    ("这个很重要很重要，千万不要删数据库，千万不要。", ["千万不要", "数据库"]),
    ("你觉得这个方案怎么样，就是用redis做缓存，会不会有问题？", ["redis", "？"]),
    ("我现在的想法是先做一个最简单的版本，嗯，就是只支持中文，然后呢等这个跑通了再加英文，再加那个就是词典，"
     "对，个人词典，最后再考虑流式。", ["中文", "英文", "个人词典", "流式"]),
    ("它那个就是它那个接口返回的是那个四零四，不对，是五零三，然后我重试了三次，三次都是五零三。",
     ["503", "3"]),
    ("嗯我在想，就是，要不要把这个，把这个配置文件，放到，放到用户目录下面，还是放在项目里，项目目录里。",
     ["配置文件", "用户目录", "项目"]),
]

cfg, key = config.load()
p = Polisher(key, cfg.polish_base_url, cfg.polish_model, timeout_s=20)
p.warmup()
rows, times = [], {"light": [], "strong": []}
for raw, must in CASES:
    out = {}
    for level in ("light", "strong"):
        text, dt = p.polish(raw, cfg.dictionary, level=level)
        times[level].append(dt)
        missing = [m for m in must if m.lower() not in text.lower()]
        out[level] = (text, dt, missing)
    rows.append((raw, out))

lines = ["# 轻度 vs 重度润色对比\n"]
for lv in ("light", "strong"):
    lines.append(f"- {lv}: 中位数 {statistics.median(times[lv])*1000:.0f} ms，"
                 f"最慢 {max(times[lv])*1000:.0f} ms")
for i, (raw, out) in enumerate(rows, 1):
    lines.append(f"\n## {i}\n**原文**：{raw}\n")
    for lv, name in (("light", "轻度"), ("strong", "重度")):
        text, dt, missing = out[lv]
        flag = f"  ⚠️ 缺少：{missing}" if missing else ""
        lines.append(f"**{name}**（{dt*1000:.0f} ms）：\n\n{text}{flag}\n")
report = ROOT / "scripts" / "levels_report.md"
report.write_text("\n".join(lines), encoding="utf-8")
print("\n".join(lines))
