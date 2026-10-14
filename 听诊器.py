# -*- coding: utf-8 -*-
"""听诊器：麦克风到底有没有听到你。

它只做一件事——把麦克风收到的音量实时画成条，同时写进 _听诊.log。
先说 5 秒不说话（量房间底噪），再一直说话。看条动不动就知道哪儿坏了。

跑法：
    py 听诊器.py           测设备 1（Wireless Mic Rx，你新插的）
    py 听诊器.py 2         测设备 2（笔记本内置阵列）
"""

import os
import sys
import time

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import numpy as np
import sounddevice as sd

本目录 = os.path.dirname(os.path.abspath(__file__))
日志 = os.path.join(本目录, "_听诊.log")

设备号 = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 1
采样率 = 16000
块长 = 0.1
块采样 = int(采样率 * 块长)
静音秒数 = 5
说话秒数 = 15

行 = []


def 记(内容):
    print(内容, flush=True)
    行.append(内容)


try:
    设备名 = sd.query_devices(设备号)["name"]
except Exception as 错:
    设备名 = f"（读不到名字：{错}）"

记(f"设备 {设备号}：{设备名}")
记(f"采样率 {采样率}　共 {静音秒数 + 说话秒数} 秒")
记("")

try:
    流 = sd.InputStream(samplerate=采样率, channels=1, dtype="int16", device=设备号)
    流.start()
except Exception as 错:
    记(f"❌ 打不开这个设备：{错}")
    with open(日志, "w", encoding="utf-8") as 文件:
        文件.write("\n".join(行))
    sys.exit(1)

底噪段 = []
说话段 = []
最高 = 0.0

for 第 in range((静音秒数 + 说话秒数) * 10):
    数据, _ = 流.read(块采样)
    音量 = float(np.abs(数据).mean()) / 32768.0
    最高 = max(最高, 音量)

    在静音段 = 第 < 静音秒数 * 10
    if 在静音段:
        底噪段.append(音量)
        提示 = "【别说话】"
    else:
        说话段.append(音量)
        提示 = "【一直说话】"

    条 = "#" * min(int(音量 * 200), 60)
    记(f"  {第 * 块长:5.1f}s {音量:.4f} {提示} |{条}")

流.stop()
流.close()

底噪峰 = max(底噪段) if 底噪段 else 0.0
底噪均 = float(np.mean(底噪段)) if 底噪段 else 0.0
说话峰 = max(说话段) if 说话段 else 0.0
说话均 = float(np.mean(说话段)) if 说话段 else 0.0

记("")
记("=" * 56)
记(f"底噪（不说话时）  峰值 {底噪峰:.4f}　平均 {底噪均:.4f}")
记(f"说话时            峰值 {说话峰:.4f}　平均 {说话均:.4f}")
记(f"全程最高           {最高:.4f}")
记("")
记("【现在的判定逻辑】")
记(f"  判定线 = max(底噪峰值 × 1.8, 0.01) = max({底噪峰:.4f} × 1.8, 0.01) = "
   f"{max(底噪峰 * 1.8, 0.01):.4f}")
记("")
if 说话峰 < 0.01:
    记("❌ 诊断：麦克风**完全没收到声音**。")
    记("   去查：① 无线麦接收器上的静音/音量旋钮　② 联想 F4（麦克风硬件静音键）")
    记("        ③ 接收器的线插紧了没　④ 麦克风电池/开关")
elif 说话峰 < max(底噪峰 * 1.8, 0.01):
    记("❌ 诊断：麦克风听到了，但**判定线比你的说话音量还高**。")
    记("   原因：底噪峰值太高（无线接收器自噪声大 / 增益开太满）。")
    exit_msg = "   修法：手动指定判定线，绕开自动量噪。"
    记(exit_msg)
else:
    比率 = 说话峰 / max(底噪峰, 0.0001)
    记(f"✅ 诊断：麦克风是好的。说话峰值是底噪的 {比率:.1f} 倍。")
    if 比率 < 3:
        记("   ⚠️ 但倍数不够宽（<3 倍），VAD 会不稳，容易误切。")

with open(日志, "w", encoding="utf-8") as 文件:
    文件.write("\n".join(行))

print()
print("日志写到：", 日志)
