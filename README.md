# error-tool · 新手 Python 报错助手

[![tests](https://github.com/LCcat-py-dev/error-tool/actions/workflows/tests.yml/badge.svg)](https://github.com/LCcat-py-dev/error-tool/actions/workflows/tests.yml)

> 替你运行 `.py` 文件，把英文报错翻成中文提示，并指出全角标点、看不见的字符这类中文输入法坑。

## 这是什么

给刚学 Python 的人用的小工具：先把目标文件编译一遍（编译不过就是语法错误），再执行；出错时用中文重新讲一遍，尽量指到具体是哪一行、哪个字符。

单文件、零第三方依赖，只 import 了 `os`、`sys`、`traceback`。

初版是暑假在手机上写的，只能认出中文标点；现在这一版把常见新手错误覆盖到 90% 左右，Windows 上用 3.12、3.13 跑过全量用例。

## 效果

**1. 全角括号**

```python
print（"hi"）
```

```
==================================================
语法错误（第1行）
print（"hi"）
     ^
小建议：这里使用了中文符号「（」，或许可以改成英文符号「( 圆括号」
==================================================
```

**2. 运行期错误**

```python
d = {'a': 1}
print(d['b'])
```

```
==================================================
报错位置：文件main.py，第2行
报错代码：print(d['b'])
报错原因：KeyError: 'b'
==================================================
```

**3. 看不见的全角空格**

下面这行 `1` 和 `2` 之间是一个全角空格，肉眼跟普通空格几乎一样：

```python
a = 1　2
```

```
==================================================
语法错误（第1行）
a = 1　2
     ^
小建议：这里混进了一个看不见的字符（全角空格 U+3000），把这行删掉重打一遍
==================================================
```

## 安装与用法

不用安装，把 `tool.py` 放到你的项目目录即可。

```bash
python tool.py 你的文件.py
```

- 不带参数时，跑当前目录的 `main.py`
- 也可以当模块用：

```python
import tool

tool.safe_run_file('main.py')
tool.safe_run_code('print(1)')
```

- 目标文件里 `import` 同目录模块、用 `__file__`、按相对路径找文件，行为都跟 `python 你的文件.py` 一致

## 它认得出什么

| 类别 | 例子 | 提示 |
|---|---|---|
| 全角标点 | `（ ） 【 】 “ ” ‘ ’ ， 。 ： ； ！ 、 「 」 『 』` | 指出是哪个符号，给出英文写法 |
| 全角运算符 | `＝ ＋ － ＊ ／ ％ ＃ ＆ ｜ ？ ～ ＿ ＠ ＄ ＾ ＼ ｀ ＜ ＞ × ÷ −` | 同上，共 40 个可见符号 |
| 看不见的字符 | 全角空格 U+3000、不换行空格、零宽空格/连接符、BOM | 报出具体码位，建议删掉重打 |
| 常见语法错误 | 缺冒号、括号不闭合、缩进不对、`print "hi"`、`if x = 1`、f-string 括号 | 行号 + 源码行 + `^` 指针 + Python 原话 |
| 运行期错误 | `NameError`、`KeyError`、`IndexError`、`TypeError`、`ValueError`、`ZeroDivisionError`、`AttributeError`、`ModuleNotFoundError` 等 | 文件、行号、出错的代码行、异常类型和消息 |
| 库内部报错 | `json.loads(123)`、`open(...).read()` 解码失败 | 指回**你自己**那一行，而不是库文件 |
| import / eval 里的语法错误 | `import 有错的模块`、`eval('1 ＋ 2')` | 走语法错误那套，报出出错文件、caret 和中文提示 |
| 文件编码 | UTF-8（含 BOM）、UTF-16、GBK | 自动识别，读不了会明确说 |

## 它怎么做的

1. `compile()` 目标文件；失败就是语法错误，用 `SyntaxError.offset` 指到那一列，再查符号表给建议（caret 前的空格数严格等于 `offset - 1`）。
2. 编译成功才 `exec()`；运行期异常取 traceback 里**用户文件**最内层的那一帧，找不到才退回最后一帧。
3. 运行期才冒出 `SyntaxError`（`import` 模块、`eval`/`exec` 字符串）也转进语法错误分支。
4. 执行环境补了 `__file__`（绝对路径），并把目标文件所在目录临时放进 `sys.path`，模拟 `python 文件.py`。

## 测试

测试集在 `tests/test_tool.py`，**41 条用例、只用标准库**，不需要装任何测试框架：

```bash
python -m unittest discover -s tests -v
```

覆盖的东西：

| 分组 | 数量 | 测什么 |
|---|---|---|
| `TestFindBadChar` | 9 | 符号表/不可见字符表的查表逻辑（纯函数，跨版本稳定） |
| `TestReadSource` | 5 | UTF-8、BOM、GBK、UTF-16、读不出来的荒字节 |
| `TestSyntaxReport` | 7 | 全角括号、缺冒号、Py2 式 `print`、caret 位置、null 字节、import 的坏模块 |
| `TestRuntimeReport` | 8 | KeyError / NameError / ZeroDivisionError / AttributeError / TypeError / IndexError；库内部报错要指回用户行 |
| `TestSafeRunCode` | 5 | 正常执行、`__name__`、`__file__`、Ctrl+C |
| `TestSafeRunFile` | 5 | 文件不存在、GBK/UTF-16 文件、同目录 import、`__file__` 是绝对路径 |
| `TestNoThirdPartyDependency` | 1 | 守住"零依赖"这个承诺：`tool.py` 只能 import `os`/`sys`/`traceback` |

CI 在 `.github/workflows/tests.yml`，每次 push 在 Python **3.9 / 3.12 / 3.13** 上各跑一遍，三个绿勾才算过。

改代码的流程就是：本地跑一遍 → push → 看 Actions。红了说明新代码破坏了上面某一条，不用自己记。

## 支持范围

- **Python 3.7+**：CI 覆盖 3.9 / 3.12 / 3.13；Linux 上跑通（CI），Windows 上 3.12、3.13 实测过
- **零依赖**：只用了标准库
- **不支持 Python 2**（用了 f-string）
- 中文控制台直接可读；控制台不是 UTF-8 时不会崩，显示不了的字符会变 `?`

## 已知局限

| 情况 | 为什么 |
|---|---|
| 死循环（`while` 忘写 `i += 1`） | 要能打断就得换线程/子进程跑，等于重做执行模型 |
| 子线程里的异常 | 只有 `threading.excepthook` 接得住，现在还是原生 traceback（主程序照常往下跑） |
| 纯逻辑错误 | 变量都在、只是语义写错，没有异常可抓 |
| 运行期的"原因" | 仍是 Python 英文原文，外面套了中文标签 |
| 全角字符的 caret | 全角字符占两列，等宽字体下 `^` 可能视觉上偏左，Python 自带 traceback 也一样 |

## 安全提醒

它**真的会执行**目标文件，不是静态检查器。别拿它跑来路不明的代码；不带参数时默认跑 `main.py` 只是为了省事。

## 目录结构

```
tool.py                      # 全部代码
tests/test_tool.py           # 41 条用例
.github/workflows/tests.yml  # CI：3.9 / 3.12 / 3.13
LICENSE                      # MIT
```

## 关于这份文档

本 README 由 AI 编写，以后此类 `.md` 也由 AI 代劳。
