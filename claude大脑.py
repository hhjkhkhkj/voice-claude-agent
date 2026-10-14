# -*- coding: utf-8 -*-
"""Claude 大脑：把「一句话」交给 Claude Code 去干，拿回「一段话」。

它和 客服大脑.py 的区别一句话说完：
    客服大脑只会**说**，这个会**动手**——读文件、搜代码、跑命令。

在语音链路里的位置：
    录音 → 识别 → 【Claude 大脑】→ 合成 → 播放
                     ↑
              它是「慢思考」，允许它慢（几秒到几分钟）

【为什么用白名单而不是全放行】
    headless 模式没法弹窗问你"允许吗"，不给权限它就干脆不干。
    而语音助手最怕的是**听错**——你随口一句被识别成删除命令，全放行就真删了。
    所以先只给只读工具（Read/Glob/Grep），要动文件时再加，一个一个加。
    加一个工具的方法：把名字塞进下面的「允许工具」，逗号分隔。
"""

import glob as _glob
import os
import shutil
import subprocess
import sys
import time

# —————— 找 claude.exe ——————
def 找claude():
    """先看 PATH，没有就去 VS Code 扩展目录里翻。"""
    在path = shutil.which("claude")
    if 在path:
        return 在path

    模式 = os.path.expanduser(
        r"~\.vscode\extensions\anthropic.claude-code-*\resources\native-binary\claude.exe"
    )
    找到的 = _glob.glob(模式)
    if 找到的:
        # 有多个版本时取最新的（版本号排序）
        return sorted(找到的)[-1]

    raise FileNotFoundError(
        "找不到 claude.exe。\n"
        "  找过：PATH、" + 模式 + "\n"
        "  如果是新装的 VS Code 扩展，版本号目录名变了，去 "
        r"C:\Users\娅土豆\.vscode\extensions\ 下看一眼实际的目录名。"
    )


CLAUDE = 找claude()

# 允许 Claude 用的工具。
#   Read/Glob/Grep —— 只读，安全
#   Bash           —— 能跑命令（开浏览器、跑脚本、装包…都靠它）
#   WebSearch/Fetch—— 联网查
#   Edit/Write     —— 改文件、写文件
#   mcp__windows-mcp —— **控制屏幕**：鼠标点击、键盘输入、截图、看窗口
#                       （配置在 ~/.claude.json，走 uvx 启动。
#                        想只放某几个动作就写全名，例如
#                        "mcp__windows-mcp__Screenshot,mcp__windows-mcp__Click"）
#
# ★ 放开 Bash 就等于放开了这台机器上的任意命令。语音识别会听错，
#   中文专有名词尤其容易错。不放心就把 Bash 去掉，退回只读。
#
# 想要完全不限制（不推荐），可以改用 --dangerously-skip-permissions。
允许工具 = ("Read,Glob,Grep,Bash,WebSearch,WebFetch,Edit,Write,"
            "mcp__windows-mcp")

# 默认工作目录 —— 它在这里面找文件。
# ★ 用**专属目录**，不要用 python-study：
#   `--continue` 接的是"该目录下最近一次对话"，跟你在 VS Code 里对同一目录
#   聊的内容会串到一起。分开就不会。
默认工作目录 = os.path.join(os.path.dirname(os.path.abspath(__file__)), "工作区")

# ★ 语音场景的附加要求 —— 这是砍延迟最狠的一刀。
#   不加这句，Claude 会按"打字给人看"的规格回：带标题、列表、**加粗**、代码块，
#   一百多字。念出来又慢又长，而且洗 markdown 也救不了长度。
语音人设 = (
    "【语音场景】用户是**用嘴**问你的，你的回答会被合成成声音念给他听。所以：\n"
    "· 用口语，**两三句话，100 字以内**，先给结论\n"
    "· 不要 markdown、标题、列表、表格、代码块、表情符号\n"
    "· 细节不要念出来，打字的部分用户自己会在屏幕上看\n"
    "· 需要动手（读文件、查东西）就直接动手，做完一句话报结果\n\n"
    "用户说的是："
)

# 这个进程里有没有可续接的对话。
# ★ 踩过的坑：第一轮如果没有历史，带 --continue 会报错，然后代码退回重试，
#   等于**首轮白调一遍 Claude**（十几秒）。用这个开关记住状态，只试一次。
_有历史 = False


def 干活(问题, 工作目录=None, 记得上一句=True, 超时=600, 详细=False):
    """把问题交给 Claude Code，等它干完，返回 (它说的话, 耗时秒)。

    参数：
        问题        —— 你说的那句话
        工作目录    —— 它在哪个目录里干活
        记得上一句  —— True 就接着上一轮聊（有记忆）
        超时        —— 最多等多少秒
        详细        —— True 就把它调了哪些工具也打出来
    """
    global _有历史

    完整问题 = 语音人设 + 问题

    命令 = [CLAUDE, "-p", 完整问题, "--allowedTools", 允许工具]
    if 记得上一句 and _有历史:
        命令.append("--continue")

    环境 = os.environ.copy()
    环境["PYTHONIOENCODING"] = "utf-8"

    起始 = time.time()
    进程 = subprocess.run(
        命令,
        cwd=工作目录 or 默认工作目录,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=超时,
        env=环境,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    耗时 = time.time() - 起始

    输出 = (进程.stdout or "").strip()
    报错 = (进程.stderr or "").strip()

    if 进程.returncode != 0:
        if 详细:
            print(f"   [claude] 退出码 {进程.returncode}　{报错[:300]}")

    # 成功跑过一次，后面就能 --continue 了
    if 进程.returncode == 0 and 输出:
        _有历史 = True

    if 详细:
        print(f"   [claude] 退出码 {进程.returncode}　耗时 {耗时:.1f}s")

    if not 输出:
        输出 = f"（它没说话。退出码 {进程.returncode}）{报错[:300]}"

    return 输出, 耗时


def 忘掉历史():
    """想开一段新对话时调它。"""
    global _有历史
    _有历史 = False


if __name__ == "__main__":
    问题 = " ".join(sys.argv[1:]) or "用一句话自我介绍"
    print("claude.exe：", CLAUDE)
    print("允许工具：", 允许工具)
    print("工作目录：", 默认工作目录)
    print()
    print("问：", 问题)
    print()
    答案, 耗时 = 干活(问题, 详细=True)
    print()
    print("答：", 答案)
    print()
    print(f"（{耗时:.1f} 秒）")
