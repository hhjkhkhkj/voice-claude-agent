# -*- coding: utf-8 -*-
"""完整链路：跟它说话 → 它听懂 → 它想 → 它说给你听

    🎤 录音 → 📝 转文字 → 🧠 AI 回复 → 🔊 合成 → ▶️ 播放

跑法：
    py 完整跑一遍.py                    诊所客服，录 5 秒
    py 完整跑一遍.py --租户 餐馆         换一个租户（同一套代码！）
    py 完整跑一遍.py 8                  录 8 秒

这就是"通用语音客服平台"的第一条能跑的链路——
**同一套代码，换个 json 就是另一个客服。**
"""

import os
import sys

_本目录 = os.path.dirname(os.path.abspath(__file__))
_项目根 = os.path.dirname(_本目录)
for _路径 in (_本目录, _项目根):
    if _路径 not in sys.path:
        sys.path.insert(0, _路径)

import 客服大脑
import 文字转语音
import 录音转文字

# —————— 解析参数 ——————
参数表 = list(sys.argv[1:])

租户 = "诊所"
if "--租户" in 参数表:
    位置 = 参数表.index("--租户")
    if 位置 + 1 < len(参数表):
        租户 = 参数表[位置 + 1]
    参数表 = 参数表[:位置] + 参数表[位置 + 2:]

秒数 = 5
for 参数 in 参数表:
    if 参数.isdigit():
        秒数 = int(参数)

# 提前读配置——租户名写错了就马上报错，别等录完音才发现
配置 = 客服大脑.读配置(租户)

print("=" * 56)
print(f"语音客服 · {配置['名字']}")
print("=" * 56)
print()

# ① 录音
路径 = 录音转文字.录音(秒数)
print()

# ② 转文字
问题 = 录音转文字.转文字(路径)
print("👤 您说：", 问题)
print()
if not 问题.strip():
    print("⚠️ 没听清，再说一次吧。")
    sys.exit(0)

# ③ AI 想
print("🧠 客服思考中……")
回复 = 客服大脑.想(问题, 租户)
print(f"🤖 {配置['名字']}：", 回复)
print()

# ④⑤ 合成 + 播放
音频 = 文字转语音.转语音(回复)
文字转语音.播放(音频)

print()
print("=" * 56)
print("一轮结束")
print("=" * 56)
