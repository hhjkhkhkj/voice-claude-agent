# -*- coding: utf-8 -*-
"""测一下网页后端通不通（不用开浏览器）

跑法：先把后端起起来，然后
    py voice_agent\测后端.py            用「餐馆」测
    py voice_agent\测后端.py 诊所        用「诊所」测

它拿本地那段 录音.wav 当输入，走完整条链路，把结果打出来。
"""

import os
import sys

import requests

本目录 = os.path.dirname(os.path.abspath(__file__))
录音 = os.path.join(本目录, "录音.wav")
地址 = "http://127.0.0.1:8020/对话"

租户 = sys.argv[1] if len(sys.argv) > 1 else "餐馆"

if not os.path.exists(录音):
    print("❌ 没有测试音频：", 录音)
    print("   先跑一次 录音转文字.py 录一段。")
    raise SystemExit(1)

print(f"把 {os.path.basename(录音)} 打给【{租户}】……")
print()

with open(录音, "rb") as 文件:
    响应 = requests.post(
        地址,
        params={"租户": 租户},          # 用 params，requests 会自动做 URL 编码
        files={"音频": ("声音.wav", 文件, "audio/wav")},
        timeout=180,
    )

print("HTTP", 响应.status_code)
try:
    结果 = 响应.json()
except Exception:
    print("返回的不是 JSON：", 响应.text[:500])
    raise SystemExit(1)

if 结果.get("错误"):
    print("❌", 结果["错误"])
else:
    print("👤 识别：", 结果["问题"])
    print("🤖 回复：", 结果["回复"])
    print("🔊 音频：", round(len(结果["音频"]) / 1024, 1), "KB (base64)")
