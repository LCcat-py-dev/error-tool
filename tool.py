# 这是一个用于辅助新手进行异常捕获的工具，本来暑假就已经写好了的，但一直躺在手机上，且功能有限，只能捕获中文字符
# 现在由AI进行重构升级，功能大幅提升，基本涵盖90%以上新手常见错误，且无其它第三方库依赖，兼容性强
# 三引号的注释是AI写的，这就是我与鱼鱼的配合

"""给初学代码做中文报错的运行器。

用法：python tool.py 你的文件.py（不给参数就跑当前目录的 main.py）
也可以 import tool，调用 safe_run_file('main.py') 或 safe_run_code('print(1)')。

环境：Python 3.7+，Windows / Linux / macOS（Windows 上实测过，3.12、3.13 跑全量用例）。
编码：UTF-8（含 BOM）、UTF-16、GBK 自动识别。
边界：它真的会执行目标文件，不是静态检查器，别拿来跑来路不明的代码；
      死循环、子线程里的异常、纯逻辑错误都抓不到。
"""

import os
import sys
import traceback

SYMBOL_MAP = {'（':'( 圆括号'
    ,'）':') 圆括号'
    ,'【':'[ 方括号'
    ,'】':'] 方括号'
    ,'“':'" 双引号'
    ,'”':'" 双引号'
    ,'‘':"' 单引号"
    ,'’':"' 单引号"
    ,'，':', 逗号'
    ,'。':'. 句号'
    ,'：':': 冒号'
    ,'；':'; 分号'
    ,'！':'! 感叹号'
    ,'、':', 逗号'
    ,'「':'" 引号'
    ,'」':'" 引号'
    ,'『':'" 引号'
    ,'』':'" 引号'
    ,'＝':'= 等号'
    ,'＋':'+ 加号'
    ,'－':'- 减号'
    ,'−':'- 减号'
    ,'＊':'* 星号'
    ,'／':'/ 斜杠'
    ,'％':'% 百分号'
    ,'＃':'# 井号'
    ,'＆':'& 与号'
    ,'｜':'| 竖线'
    ,'？':'? 问号'
    ,'～':'~ 波浪号'
    ,'＿':'_ 下划线'
    ,'＠':'@ 艾特号'
    ,'＄':'$ 美元号'
    ,'＾':'^ 脱字符'
    ,'＼':'\\ 反斜杠'
    ,'｀':'` 反引号'
    ,'＜':'< 小于号'
    ,'＞':'> 大于号'
    ,'×':'* 乘号'
    ,'÷':'/ 除号'
            }

INVISIBLE_MAP = {'\u3000':'全角空格 U+3000'
    ,'\u00a0':'不换行空格 U+00A0'
    ,'\u200b':'零宽空格 U+200B'
    ,'\u200c':'零宽不连字 U+200C'
    ,'\u200d':'零宽连接符 U+200D'
    ,'\ufeff':'BOM 零宽空格 U+FEFF'
                }

def find_bad_char(error_text, offset):
    if not error_text or not offset:
        return None

    idx = offset - 1
    if 0 <= idx < len(error_text):
        char = error_text[idx]
        if char in SYMBOL_MAP or char in INVISIBLE_MAP:
            return char

    return None

def report_syntax_error(e, run_filename=None):
    parts = []
    if e.filename and e.filename != run_filename and e.filename not in ('<string>', '<exec>'):
        parts.append(f"文件{e.filename}")
    if e.lineno is not None:
        parts.append(f"第{e.lineno}行")

    title = '，'.join(parts)
    print("\n" + "=" * 50)
    print(f"语法错误（{title}）" if title else "语法错误")

    if e.text:
        print(e.text.rstrip())
        if e.offset:
            print(" " * (e.offset - 1) + "^")

    bad_char = find_bad_char(e.text, e.offset)

    if bad_char in SYMBOL_MAP:
        print(f"小建议：这里使用了中文符号「{bad_char}」，或许可以改成英文符号「{SYMBOL_MAP[bad_char]}」")
    elif bad_char in INVISIBLE_MAP:
        print(f"小建议：这里混进了一个看不见的字符（{INVISIBLE_MAP[bad_char]}），把这行删掉重打一遍")
    elif 'null bytes' in (e.msg or ''):
        print("小建议：文件里混进了空字符（\\x00），多半是被存成了 UTF-16，用 UTF-8 重新保存一下")
    else:
        print(f"报错原因为：{e.msg}")

    print("=" * 50)

def report_runtime_error(e, run_filename):
    frames = traceback.extract_tb(e.__traceback__)
    mine = [f for f in frames if f.filename == run_filename]
    last_tb = mine[-1] if mine else frames[-1]

    print("\n" + "=" * 50)
    print(f"报错位置：文件{last_tb.filename}，第{last_tb.lineno}行")
    if last_tb.line:
        print(f"报错代码：{last_tb.line.strip()}")
    print(f"报错原因：{type(e).__name__}: {e}")
    print("=" * 50)

def safe_run_code(code, filename='<string>', file_path=None):
    try:
        compiled = compile(code, filename, 'exec')
    except SyntaxError as e:
        report_syntax_error(e, filename)
        return
    except ValueError as e:
        # Python 3.12 之前，源码里的空字符走的是 ValueError（之后改成 SyntaxError）
        print(f"\n文件{filename}没法编译：{e}")
        if 'null bytes' in str(e):
            print("小建议：文件里混进了空字符（\\x00），多半是被存成了 UTF-16，用 UTF-8 重新保存一下")
        return

    global_dict = {'__name__': '__main__', '__file__': file_path or filename}

    try:
        exec(compiled, global_dict)
    except SyntaxError as e:
        report_syntax_error(e, filename)
    except KeyboardInterrupt:
        print("\n" + "=" * 50)
        print("程序被中断了（Ctrl+C）")
        print("=" * 50)
    except Exception as e:
        report_runtime_error(e, filename)

def read_source(filename):
    with open(filename, 'rb') as f:
        raw = f.read()

    for encoding in ('utf-8-sig', 'utf-16', 'gbk'):
        try:
            return raw.decode(encoding), encoding
        except UnicodeError:
            continue

    return None, None

def safe_run_file(filename):
    try:
        code, encoding = read_source(filename)
    except FileNotFoundError:
        print(f"文件{filename}不存在")
        return
    except OSError as e:
        print(f"文件{filename}打不开：{type(e).__name__}: {e}")
        return

    if code is None:
        print(f"文件{filename}读不出来，UTF-8 / UTF-16 / GBK 都不是")
        return

    if encoding != 'utf-8-sig':
        print(f"提示：文件{filename}是 {encoding} 编码，已自动按这个读的")

    full_path = os.path.abspath(filename)
    script_dir = os.path.dirname(full_path)

    sys.path.insert(0, script_dir)

    try:
        safe_run_code(code, filename, full_path)
    finally:
        if sys.path and sys.path[0] == script_dir:
            sys.path.pop(0)

if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(errors='replace')

    target = sys.argv[1] if len(sys.argv) > 1 else 'main.py'
    safe_run_file(target)
