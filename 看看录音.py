# -*- coding: utf-8 -*-
"""看看刚录的那段 wav 里，到底有没有声音。

为什么要这一步：
    识别出来是空的，可能是
      ① 麦克风压根没采到声音（设备选错 / 系统里被静音 / 音量拉到 0）
      ② 采到了，但音量太低，识别不出来
      ③ 声音正常，那问题在识别那一步
    量一下振幅，就能分清是哪种。

跑法：py 看看录音.py
"""

import os
import sys

import numpy as np
import soundfile as sf

本目录 = os.path.dirname(os.path.abspath(__file__))
# 不带参数就看默认那个录音；也可以指定文件：
#   py 看看录音.py C:\...\回复.wav
文件 = sys.argv[1] if len(sys.argv) > 1 else os.path.join(本目录, "录音.wav")

if not os.path.exists(文件):
    print("❌ 没有这个文件：", 文件)
    print("   先跑一次 录音转文字.py，把录音生成出来。")
    raise SystemExit(1)

数据, 采样率 = sf.read(文件)          # 注意：sf.read 默认就读成 float64
时长 = len(数据) / 采样率
平均 = float(np.abs(数据).mean())

# 文件真正存成什么格式，要看 sf.info，不能看读出来的 dtype
# （sf.read 不带 dtype 参数永远给你 float64，拿它当"文件格式"会误导）
信息 = sf.info(文件)
格式说明 = f"{信息.format} / {信息.subtype}"

# 振幅统一换算成 0~1 再判：浮点本来就是 ±1.0，整数除以它的最大值
峰值 = float(np.abs(数据).max())
峰值比例 = 峰值 if np.issubdtype(数据.dtype, np.floating) else 峰值 / float(np.iinfo(数据.dtype).max)

print(f"文件　　：{文件}")
print(f"时长　　：{时长:.2f} 秒")
print(f"采样率　：{采样率}")
print(f"文件格式：{格式说明}")
print(f"峰值　　：{峰值:.4f}（换算成 0~1 是 {峰值比例:.4f}）")
print(f"平均　　：{平均:.4f}")
print()

if 峰值比例 < 0.001:
    print("⚠️ 几乎没有声音 —— 里面是静音")
    print("   如果是录音：查麦克风（先看笔记本 F4 上的灯亮没亮）。")
elif 峰值比例 < 0.02:
    print("⚠️ 有声音，但很小 —— 离麦克风太远，或者系统输入音量太低")
else:
    print("✅ 有声音")
    print("   → 如果听不到/识别不出，问题在后面（播放或识别），不在录音")

# —————— 顺便播一遍 ——————
# 这一句最有用：你亲耳听听录到的到底是什么，
# 比任何数字都直接——是你说的话？还是噪音？还是空的？
print()
print("▶️  播一遍你听（就是这段录音里的内容）……")
try:
    import sounddevice as sd

    播放数据, 播放采样率 = sf.read(文件, dtype="float32")
    sd.play(播放数据, 播放采样率)
    sd.wait()
    print("   播完了")
except Exception as e:
    print("   播放失败：", repr(e))
