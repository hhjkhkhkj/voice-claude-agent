# -*- coding: utf-8 -*-
r"""一直听着 —— 不用按按钮，你直接说话就行

    循环：等你说话 → 录下来 → 识别 → 写进 最近一句.json → 回去接着等

跑法：
    py C:\Users\娅土豆\python-study\voice_agent\按钮\一直听着.py
停：
    Ctrl + C

【它替代了什么】
    之前要"按按钮"才开始录。现在不用 —— 它一直听着，
    你开口它就录，说完它自己停，然后等着听下一句。
    这就是"外接一个麦克风"：麦克风一直开着。

【配合谁】
    watch_voice.py 盯着 最近一句.json，一变就通知 agent。
    两个一起跑，才形成闭环：
        一直听着.py  →  写文件  →  watch_voice.py  →  agent

【注意】
    · 它占着麦克风，跑着的时候别同时开别的录音程序
    · 麦克风是**一直开着的**——介意的话用完 Ctrl+C 停掉
"""

import json
import os
import sys
import time

_本目录 = os.path.dirname(os.path.abspath(__file__))
_voice根 = os.path.dirname(_本目录)
_项目根 = os.path.dirname(_voice根)
for _路径 in (_voice根, _项目根):
    if _路径 not in sys.path:
        sys.path.insert(0, _路径)

import 录音转文字

结果文件 = os.path.join(_本目录, "最近一句.json")


def 写结果(文字):
    with open(结果文件, "w", encoding="utf-8") as 文件:
        json.dump({"时间": time.time(), "文字": 文字}, 文件, ensure_ascii=False)


print("=" * 52)
print("一直听着 —— 你直接说话就行（Ctrl+C 停）")
print("=" * 52)
print()

轮 = 0
while True:
    轮 += 1
    try:
        # 第一轮慢一点（等你准备好），之后立刻重新开始听
        路径 = 录音转文字.录音到说完(准备=(2 if 轮 == 1 else 0))
        文字 = 录音转文字.转文字(路径)

        if 文字.strip():
            写结果(文字)
            print("   → 已写进文件，agent 会看到")
        else:
            print("   （没听清，接着说）")
        print()

    except KeyboardInterrupt:
        print()
        print("停了。")
        break
    except Exception as e:
        print("   ⚠️ 出错：", repr(e))
        time.sleep(1)
