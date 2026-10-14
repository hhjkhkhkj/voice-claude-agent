# -*- coding: utf-8 -*-
r"""盯着「最近一句.json」——一变就把识别到的文字打出来。

【它给谁用】
    Monitor 工具用。Monitor 会把这里的**每一行 stdout 变成一条通知**。
    所以检测到一次新内容，就打印一行。

【为什么要它】
    终端里的 agent 不是常驻程序，没法"一直挂着耳朵"。
    但 Monitor 可以替它盯着 —— 文件一变，agent 就自动被叫醒。
    这样用户按完按钮，就不需要再打字告诉 agent 了。

跑法（一般不用手动跑，由 Monitor 拉起来）：
    py watch_voice.py
"""

import json
import os
import sys
import time

# ★ 这一行是救命的，别删。
#   bash 把 Python 拉起来时，Windows 默认按 GBK 编码输出，
#   碰到 emoji（👂🎤）直接 UnicodeEncodeError 崩掉 —— 脚本第一行 print 就死。
#   表现是：监听程序好好写着文件，监视器却一条通知都没发。
#   （这个坑在中文 Windows + bash + 非 ASCII 输出 时必踩。）
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

本目录 = os.path.dirname(os.path.abspath(__file__))
结果文件 = os.path.join(本目录, "最近一句.json")

上次时间 = 0.0
if os.path.exists(结果文件):
    上次时间 = os.path.getmtime(结果文件)

print("👂 盯着语音结果文件……", flush=True)

while True:
    time.sleep(0.4)
    try:
        if not os.path.exists(结果文件):
            continue
        现在 = os.path.getmtime(结果文件)
        if 现在 <= 上次时间:
            continue
        上次时间 = 现在

        with open(结果文件, encoding="utf-8") as 文件:
            数据 = json.load(文件)
        文字 = (数据.get("文字") or "").strip()
        print("🎤 用户说：" + 文字 if 文字 else "🎤 （没听清）", flush=True)
    except Exception as e:
        print("读结果文件出错：" + repr(e), flush=True)
