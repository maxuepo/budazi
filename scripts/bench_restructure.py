"""Test the 'restructure' mode (fill skipped logic, fix order, keep the user's voice).

Writes scripts/restructure_report.md.
"""
import json
import re
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from budazi import config
from budazi.app import load_voice_samples
from budazi.polish import Polisher

# (raw, must keep)
FIXED = [
    # conclusion first, reasons after
    ("所以我决定不用那个云服务了。上个月账单出来了，三百多美元。嗯其实我们一天也就几百个请求，本地跑完全够。",
     ["300|三百", "本地", "不用"]),
    # skipped step: A -> C
    ("这个登录老是掉线，我看了一下token是一个小时就过期，那就加个refresh token吧。", ["token", "refresh token", "小时"]),
    # request in the middle, background scattered
    ("你帮我写个脚本吧。就是每天我都要手动下载那个报表，从后台。然后还要改格式，转成Excel，再发邮件给老板，"
     "大概要半个小时。对，每天早上九点前要发。", ["Excel", "邮件", "9|九", "半个小时|30"]),
    # jumpy, order mixed, with a constraint
    ("别动数据库啊。那个首页太慢了，我觉得是图片太大，好几张都是五六兆的。你压缩一下，然后懒加载。数据库那边是别人负责的。",
     ["数据库", "别|不要", "图片", "5|五", "压缩", "懒加载"]),
    # reasoning chain with a question
    ("我在想要不要用Rust重写。Python那个版本CPU占用老是百分之百。不过团队里没人会Rust。你觉得值得吗？",
     ["Rust", "Python", "100|百分之百", "没人会", "？"]),
    # English, out of order
    ("so we should probably just cache it. the API is rate limited to like 100 calls a minute and we're hitting "
     "it on every page load. yeah and the data only changes once a day anyway.",
     ["cache", "100", "rate limit", "once a day"]),
]
hist = [json.loads(l) for l in (ROOT / "history.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
REAL = [(h["raw"], []) for h in hist if len(h["raw"]) >= 60][-3:]

cfg, key = config.load()
voice = load_voice_samples(ROOT / "history.jsonl", 3)
p = Polisher(key, cfg.polish_base_url, cfg.polish_model, timeout_s=30)
p.warmup()
VARIANTS = [("restructure", cfg.long_model, "梳理（Kimi）")]
num = re.compile(r"\d+")
stats = {v[2]: {"t": [], "miss": 0, "newnum": 0} for v in VARIANTS}
lines = [f"\n> 文风样本（取自你的历史记录）：\n" + "\n".join(f"> - {s}" for s in voice) + "\n"]
for title, cases in (("构造的跳跃/颠倒样例", FIXED), ("你的真实口述", REAL)):
    lines.append(f"\n# {title}\n")
    for i, (raw, must) in enumerate(cases, 1):
        lines.append(f"\n## {i}\n**原文**：{raw}\n")
        for level, model, name in VARIANTS:
            v = load_voice_samples(ROOT / "history.jsonl", 3, exclude_raw=raw)  # no peeking
            text, dt = p.polish(raw, cfg.dictionary, model=model, level=level, voice_samples=v)
            low = text.lower()
            missing = [m for m in must if not any(a.lower() in low for a in m.split("|"))]
            new_nums = sorted(set(num.findall(text)) - set(num.findall(raw)) - {"1", "2", "3"})
            s = stats[name]
            s["t"].append(dt); s["miss"] += len(missing); s["newnum"] += len(new_nums)
            flag = (f"  ⚠️ 缺少：{missing}" if missing else "") + \
                   (f"  ❓ 新出现的数字：{new_nums}" if new_nums else "")
            lines.append(f"**{name}**（{dt*1000:.0f} ms）：\n\n{text}{flag}\n")
head = ["# 梳理模式测试\n"]
for name, s in stats.items():
    head.append(f"- {name}：丢失信息 {s['miss']} 处，凭空多出的数字 {s['newnum']} 处，"
                f"中位数 {statistics.median(s['t'])*1000:.0f} ms，最慢 {max(s['t'])*1000:.0f} ms")
out = "\n".join(head + lines)
(ROOT / "scripts" / "restructure_report.md").write_text(out, encoding="utf-8")
print(out)
