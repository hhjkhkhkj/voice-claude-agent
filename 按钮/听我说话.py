r"""一个页面，一个大按钮：按住说话 → 松开变文字 → 写进文件

【为什么要这个】
    终端里的 agent 没法被动听 —— 它不是常驻程序，
    "你发消息 → 它干活 → 这一轮结束"，命令跑完就停了。
    所以"什么时候开始录"这个开关，必须握在**你**手里。
    这个页面就是那个开关。

【跑法】
    py C:\Users\娅土豆\python-study\voice_agent\按钮\听我说话.py
    浏览器开  http://127.0.0.1:8030

【怎么跟 agent 配合】
    按完按钮说完，跟 agent 说一句"我说完了"，
    它就去读 最近一句.json —— 那里面是刚识别出来的字。
"""

import json
import os
import subprocess
import sys
import tempfile
import time

_本目录 = os.path.dirname(os.path.abspath(__file__))
_voice根 = os.path.dirname(_本目录)
_项目根 = os.path.dirname(_voice根)
for _路径 in (_voice根, _项目根):
    if _路径 not in sys.path:
        sys.path.insert(0, _路径)

import uvicorn
from fastapi import FastAPI, File, UploadFile
from fastapi.responses import HTMLResponse

import 录音转文字

页面路径 = os.path.join(_本目录, "按钮.html")
结果文件 = os.path.join(_本目录, "最近一句.json")


def _找ffmpeg():
    from shutil import which

    找到了 = which("ffmpeg")
    if 找到了:
        return 找到了
    备选 = r"D:\Download\ffmpeg\bin\ffmpeg.exe"
    return 备选 if os.path.exists(备选) else None


FFMPEG = _找ffmpeg()

app = FastAPI()


@app.get("/")
def 首页():
    with open(页面路径, encoding="utf-8") as 文件:
        return HTMLResponse(文件.read())


def 转成wav(原始):
    if 原始[:4] == b"RIFF":
        return 原始
    if not FFMPEG:
        raise RuntimeError("没找到 ffmpeg")
    with tempfile.TemporaryDirectory() as 临时:
        进的 = os.path.join(临时, "in.webm")
        出的 = os.path.join(临时, "out.wav")
        with open(进的, "wb") as f:
            f.write(原始)
        结果 = subprocess.run(
            [FFMPEG, "-y", "-i", 进的, "-ar", "16000", "-ac", "1", 出的],
            capture_output=True,
        )
        if 结果.returncode != 0:
            raise RuntimeError("音频转换失败：" + 结果.stderr.decode("utf-8", "ignore")[-300:])
        with open(出的, "rb") as f:
            return f.read()


@app.post("/听")
async def 听(音频: UploadFile = File(...)):
    """收一段录音 → 识别 → 写进文件 → 把文字返回给页面显示。"""
    try:
        原始 = await 音频.read()
        if not 原始:
            return {"错误": "没收到音频", "文字": ""}

        文字 = 录音转文字.识别字节(转成wav(原始), "声音.wav")

        # 写进文件，agent 就能读到了
        with open(结果文件, "w", encoding="utf-8") as f:
            json.dump({"时间": time.time(), "文字": 文字}, f, ensure_ascii=False)

        return {"文字": 文字}
    except Exception as e:
        print("出错：", repr(e))
        return {"错误": f"{type(e).__name__}: {e}", "文字": ""}


@app.get("/最近一句")
def 最近一句():
    if not os.path.exists(结果文件):
        return {"文字": "", "时间": 0}
    with open(结果文件, encoding="utf-8") as f:
        return json.load(f)


if __name__ == "__main__":
    print("=" * 56)
    print("语音开关 · 按钮版")
    print("=" * 56)
    print("ffmpeg：", FFMPEG or "⚠️ 没找到")
    print()
    print("浏览器打开 →  http://127.0.0.1:8030")
    print("按住按钮说话，松开就出文字。")
    print()
    print("识别结果会写进：", 结果文件)
    print()
    uvicorn.run(app, host="0.0.0.0", port=8030)
