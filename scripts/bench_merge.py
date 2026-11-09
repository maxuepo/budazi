"""Compare current 'strong' cleanup vs a candidate that also merges repeats across sentences.

Writes scripts/merge_report.md.
"""
import ast
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from budazi import config, polish
from budazi.polish import Polisher

MERGE_RULE = (
    "2b. 跨句合并：口述时常常开头说一遍目的、中间展开、结尾又换个说法再说一遍。"
    "整段里不相邻的句子如果表达的是同一个意思，合并成一句，放在最合适的位置（通常是开头），"
    "并把两处各自独有的细节（目标、数字、条件、原因）都并进这一句。"
    "只合并真正同一个意思的句子；说的是不同对象、不同步骤、不同问题的句子，即使措辞相似也要分开保留。\n"
)
EXAMPLES = """

示例（只用来说明规则，不要照抄内容）：
原文：我们周二，不对，周三下午开会，在那个，在二楼。
整理：我们周三下午在二楼开会。

原文：我想让你帮我重构一下登录模块。现在代码太乱了，好几个函数都超过两百行。所以就是说，嗯，帮我把登录模块重构一下，拆成小函数。
整理：我想让你帮我重构一下登录模块，拆成小函数。现在代码太乱了，好几个函数都超过两百行。

原文：我想看看，就是，这个缓存到底有没有用。我加了缓存，但是好像没变快。我就是想知道这个缓存到底有没有起作用。
整理：我加了缓存，但是好像没变快，想知道这个缓存到底有没有起作用。

原文：先改前端的按钮颜色。然后再改后端的接口超时。
整理：先改前端的按钮颜色，然后再改后端的接口超时。"""
# The merge rule + examples are now part of SYSTEM_PROMPT_STRONG; "candidate" is a slot
# for trying the next prompt idea against it (edit CANDIDATE below).
CANDIDATE = polish.SYSTEM_PROMPT_STRONG
RUNS = 2
CAND_MODEL = sys.argv[1] if len(sys.argv) > 1 else None  # optional other model for candidate
REPORT = "merge_report_" + CAND_MODEL.split("/")[-1] + ".md" if CAND_MODEL else "merge_report.md"
polish.PROMPTS["candidate"] = CANDIDATE

# old cases from bench_levels.py (regression check)
src = (ROOT / "scripts" / "bench_levels.py").read_text(encoding="utf-8")
node = next(n for n in ast.parse(src).body
            if isinstance(n, ast.Assign) and getattr(n.targets[0], "id", "") == "CASES")
OLD = [(raw, must, []) for raw, must in ast.literal_eval(node.value)]

# (raw, must keep, should appear at most once)
NEW = [
    # opening and closing sentences say the same thing (cross-sentence repeat)
    ("呃，我想看看这个周报能不能自动生成。因为每周五都要写，挺烦的，嗯要从那个Jira里面拉数据。然后呢再整理成表格。"
     "我就是想呃，我就是想知道这个周报能不能用脚本自动生成，然后发到那个Slack频道里。",
     ["Jira", "Slack", "周五", "表格"], ["自动生成"]),
    ("我想让你帮我优化一下首页的加载速度。现在首页打开要五秒多，太慢了。图片也没压缩。所以就是说，我希望你帮我把首页加载"
     "速度优化一下，目标是两秒以内。", ["5|五", "2|两", "图片", "压缩"], ["加载速度"]),
    ("这个脚本主要是用来备份数据库的。每天凌晨三点跑一次，备份到S3。嗯，对，就是一个备份数据库的脚本。保留最近七天的。",
     ["3|三", "S3", "7|七"], ["备份数据库"]),
    ("I need you to write a function that parses the log file. It should extract the timestamps and "
     "error codes. Yeah so basically a function to parse the log file, and it should skip empty lines.",
     ["timestamp", "error code", "empty lines"], ["log file"]),
    ("我的意思是这样的，嗯，配置文件不要提交到git里面。因为里面有API key。反正就是配置文件别提交，加到gitignore里。",
     ["git", "API key", "gitignore"], ["配置文件"]),
    # guards: similar wording, different content -> must stay separate
    ("先把A分支合到main。然后再把B分支合到develop。", ["A", "main", "B", "develop"], []),
    ("第一个问题是登录页面报错。第二个问题也是报错，是在支付页面。", ["登录", "支付"], []),
    ("你帮我看看这个函数为什么慢。另外你也看看那个函数为什么占内存这么多。", ["慢", "内存"], []),
]

cfg, key = config.load()
p = Polisher(key, cfg.polish_base_url, cfg.polish_model, timeout_s=20)
p.warmup()
lines, times = ["# 跨句合并：现在的重度 vs 候选规则\n"], {"strong": [], "candidate": []}
score = {"strong": [0, 0, 0], "candidate": [0, 0, 0]}  # [missing, repeats, bad self-correction]
for title, cases in (("新样例：前后重复 + 防误合并", NEW), ("老样例：回归检查", OLD)):
    lines.append(f"\n# {title}\n")
    for i, (raw, must, once) in enumerate(cases, 1):
        lines.append(f"\n## {i}\n**原文**：{raw}\n")
        for lv, name in (("strong", "现在的重度"), ("candidate", "加跨句合并+示例")):
          for run in range(RUNS):
            text, dt = p.polish(raw, cfg.dictionary, level=lv,
                                model=CAND_MODEL if lv == "candidate" else None)
            times[lv].append(dt)
            low = text.lower()
            missing = [m for m in must if not any(a.lower() in low for a in m.split("|"))]
            repeats = [o for o in once if low.count(o.lower()) > 1]
            bad_fix = "不对" in text and "不对" in raw
            score[lv][0] += len(missing)
            score[lv][1] += len(repeats)
            score[lv][2] += bad_fix
            flags = (f"  ⚠️ 缺少：{missing}" if missing else "") + \
                    (f"  🔁 仍重复：{repeats}" if repeats else "") + \
                    ("  ❌ 口误没改干净" if bad_fix else "")
            lines.append(f"**{name} 第{run+1}遍**（{dt*1000:.0f} ms）：\n\n{text}{flags}\n")

head = []
for lv, name in (("strong", "现在的重度"), ("candidate", "加跨句合并+示例")):
    head.append(f"- {name}（每条跑 {RUNS} 遍）：丢失信息 {score[lv][0]} 处，没合并的重复 {score[lv][1]} 处，"
                f"口误没改干净 {score[lv][2]} 处，"
                f"中位数 {statistics.median(times[lv])*1000:.0f} ms，最慢 {max(times[lv])*1000:.0f} ms")
lines[1:1] = head
report = ROOT / "scripts" / REPORT
report.write_text("\n".join(lines), encoding="utf-8")
print("\n".join(lines))
