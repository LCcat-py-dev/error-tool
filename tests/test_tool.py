"""tool.py 的测试集。

跑法（在仓库根目录）：
    python -m unittest discover -s tests -v

特点：只用标准库、不依赖第三方测试框架、不需要网络。
被问到"你凭什么说它认得出这些错"的时候，答案是这里。
"""

import contextlib
import io
import os
import sys
import tempfile
import unittest

# 让 `python -m unittest` 在任意目录下跑都能 import 到仓库根目录的 tool.py
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import tool


def capture(func, *args, **kwargs):
    """把 func 的 stdout 抓成字符串返回。"""

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        func(*args, **kwargs)
    return buf.getvalue()

def run_code(code, filename='<string>', **kwargs):
    return capture(tool.safe_run_code, code, filename, **kwargs)

def run_source(source, filename='main.py', encoding='utf-8'):
    """把源码写成临时文件再跑，返回 (输出, 文件所在目录)。"""

    folder = tempfile.mkdtemp(prefix='error-tool-test-')
    path = os.path.join(folder, filename)

    with open(path, 'wb') as f:
        f.write(source.encode(encoding))

    return capture(tool.safe_run_file, path), folder


class TestFindBadChar(unittest.TestCase):
    """符号表查找是纯函数，跟 Python 版本无关，单独测。"""

    def test_full_width_paren(self):
        text = 'print（"hi"）'
        self.assertEqual(tool.find_bad_char(text, 6), '（')

    def test_full_width_comma(self):
        text = 'print(1，2)'
        self.assertEqual(tool.find_bad_char(text, 8), '，')

    def test_full_width_operator(self):
        text = 'a ＝ 1'
        self.assertEqual(tool.find_bad_char(text, 3), '＝')

    def test_invisible_full_width_space(self):
        text = 'a = 1　2'
        self.assertEqual(tool.find_bad_char(text, 6), '\u3000')

    def test_invisible_zero_width(self):
        text = 'a = 1\u200b2'
        self.assertEqual(tool.find_bad_char(text, 6), '\u200b')

    def test_normal_ascii_returns_none(self):
        self.assertIsNone(tool.find_bad_char('print(1)', 6))

    def test_none_inputs(self):
        self.assertIsNone(tool.find_bad_char(None, 3))
        self.assertIsNone(tool.find_bad_char('abc', None))

    def test_offset_out_of_range(self):
        self.assertIsNone(tool.find_bad_char('abc', 99))

    def test_all_symbols_have_ascii_hint(self):
        """符号表里每一条都得给出英文写法，不许留空。"""

        for char, hint in tool.SYMBOL_MAP.items():
            with self.subTest(char=char):
                self.assertTrue(hint and hint.strip())


class TestReadSource(unittest.TestCase):

    def test_utf8(self):
        text, enc = self._read('print(1)', 'utf-8')
        self.assertEqual(text, 'print(1)')
        self.assertEqual(enc, 'utf-8-sig')

    def test_utf8_bom(self):
        text, enc = self._read('print(1)', 'utf-8-sig')
        self.assertEqual(text, 'print(1)')
        self.assertEqual(enc, 'utf-8-sig')

    def test_gbk(self):
        text, enc = self._read('print("中文")', 'gbk')
        self.assertEqual(text, 'print("中文")')
        self.assertEqual(enc, 'gbk')

    def test_utf16(self):
        text, enc = self._read('print("中文")', 'utf-16')
        self.assertEqual(text, 'print("中文")')
        self.assertEqual(enc, 'utf-16')

    def test_undecodable(self):
        folder = tempfile.mkdtemp(prefix='error-tool-test-')
        path = os.path.join(folder, 'bad.py')

        with open(path, 'wb') as f:
            f.write(b'\xff\xfe\xff\x00\x81')

        text, enc = tool.read_source(path)
        self.assertIsNone(text)
        self.assertIsNone(enc)

    def _read(self, source, encoding):
        folder = tempfile.mkdtemp(prefix='error-tool-test-')
        path = os.path.join(folder, 'x.py')

        with open(path, 'wb') as f:
            f.write(source.encode(encoding))

        return tool.read_source(path)


class TestSyntaxReport(unittest.TestCase):

    def test_full_width_paren_gives_hint(self):
        out = run_code('print（"hi"）')
        self.assertIn('语法错误', out)
        self.assertIn('中文符号', out)

    def test_missing_colon(self):
        out = run_code('if True\n    pass')
        self.assertIn('语法错误', out)
        self.assertIn('第1行', out)

    def test_print_statement_python2_style(self):
        out = run_code('print "hi"')
        self.assertIn('语法错误', out)

    def test_unclosed_paren_reports_line(self):
        out = run_code('x = [1, 2\ny = 3')
        self.assertIn('语法错误', out)
        self.assertIn('第', out)

    def test_caret_points_at_column(self):
        out = run_code('print（"hi"）')
        lines = out.splitlines()
        text_pos = [i for i, line in enumerate(lines) if line.startswith('print（')]
        self.assertTrue(text_pos, out)
        caret = lines[text_pos[0] + 1]
        self.assertIn('^', caret)

    def test_syntax_error_matrix(self):
        """一批肯定编译不过的写法，都得走语法错误分支。"""

        samples = [
            'if x = 1:\n    pass',
            'def f()\n    pass',
            'for i in range(3)\n    print(i)',
            'while True\n    break',
            'class A\n    pass',
            'x = 1 +\n',
            'try:\n    pass\nfinally',
            'def f(:\n    pass',
            '1 = 2',
            'return 1',
            'nonlocal x',
            '**kw = 1',
            'x = {1: 2, }}}',
            'lambda x:',
        ]

        for src in samples:
            with self.subTest(src=src):
                self.assertIn('语法错误', run_code(src))

    def test_syntax_error_in_imported_module(self):
        """import 一个本身有语法错的模块，也算语法错误，并且指出是哪个文件。"""

        folder = tempfile.mkdtemp(prefix='error-tool-test-')
        mod = os.path.join(folder, 'broken_mod.py')

        with open(mod, 'w', encoding='utf-8') as f:
            f.write('def oops(:\n    pass\n')

        main = os.path.join(folder, 'main.py')

        with open(main, 'w', encoding='utf-8') as f:
            f.write('import broken_mod\n')

        out = capture(tool.safe_run_file, main)
        self.assertIn('语法错误', out)
        self.assertIn('broken_mod', out)

    def test_null_bytes(self):
        out = run_code('a = 1\x00b = 2')
        self.assertIn('空字符', out)


class TestRuntimeReport(unittest.TestCase):

    def test_keyerror(self):
        out = run_code("d = {'a': 1}\nprint(d['b'])")
        self.assertIn('报错位置', out)
        self.assertIn('第2行', out)
        self.assertIn('KeyError', out)

    def test_nameerror(self):
        out = run_code('print(undefined_name)')
        self.assertIn('NameError', out)

    def test_zero_division(self):
        out = run_code('1 / 0')
        self.assertIn('ZeroDivisionError', out)

    def test_attribute_error(self):
        out = run_code('"abc".push(1)')
        self.assertIn('AttributeError', out)

    def test_type_error(self):
        out = run_code('1 + "a"')
        self.assertIn('TypeError', out)

    def test_index_error(self):
        out = run_code('x = [1]\nprint(x[9])')
        self.assertIn('IndexError', out)

    def test_error_inside_library_points_back_to_user_line(self):
        """库内部抛错时，报错位置要指回自己那一行，而不是 json 源码。"""

        out = run_code('import json\njson.loads(123)')
        self.assertIn('报错位置', out)
        self.assertIn('第2行', out)
        self.assertNotIn('decoder.py', out)

    def test_shows_offending_code_line(self):
        """跑真实文件时，要把出错那行源码打出来。"""

        out, _ = run_source('x = 1\ny = 2\nprint(z)\n')
        self.assertIn('报错代码', out)
        self.assertIn('print(z)', out)


class TestSafeRunCode(unittest.TestCase):

    def test_normal_code_runs(self):
        out = run_code('print("hello")')
        self.assertIn('hello', out)

    def test_main_guard_is_set(self):
        out = run_code("if __name__ == '__main__':\n    print('is main')")
        self.assertIn('is main', out)

    def test_file_variable_available(self):
        out = run_code("print(__file__)", file_path='D:/x/y.py')
        self.assertIn('y.py', out)

    def test_keyboard_interrupt_is_caught(self):
        out = run_code('raise KeyboardInterrupt')
        self.assertIn('程序被中断', out)

    def test_silent_success_prints_nothing_extra(self):
        out = run_code('x = 1')
        self.assertEqual(out.strip(), '')


class TestSafeRunFile(unittest.TestCase):

    def test_missing_file(self):
        out = capture(tool.safe_run_file, os.path.join(tempfile.gettempdir(), 'nope_12345.py'))
        self.assertIn('不存在', out)

    def test_gbk_file_runs_and_warns(self):
        out, _ = run_source('print("中文")', encoding='gbk')
        self.assertIn('编码', out)
        self.assertIn('中文', out)

    def test_utf16_file_runs(self):
        out, _ = run_source('print(1 + 1)', encoding='utf-16')
        self.assertIn('2', out)

    def test_sibling_module_import(self):
        folder = tempfile.mkdtemp(prefix='error-tool-test-')

        with open(os.path.join(folder, 'helper.py'), 'w', encoding='utf-8') as f:
            f.write('VALUE = 42\n')

        path = os.path.join(folder, 'main.py')

        with open(path, 'w', encoding='utf-8') as f:
            f.write('import helper\nprint(helper.VALUE)\n')

        out = capture(tool.safe_run_file, path)
        self.assertIn('42', out)

    def test_file_variable_is_absolute(self):
        folder = tempfile.mkdtemp(prefix='error-tool-test-')
        path = os.path.join(folder, 'main.py')

        with open(path, 'w', encoding='utf-8') as f:
            f.write('import os\nprint(os.path.isabs(__file__))\n')

        out = capture(tool.safe_run_file, path)
        self.assertIn('True', out)


class TestNoThirdPartyDependency(unittest.TestCase):
    """README 承诺"零第三方依赖"，这条测试守住它。"""

    def test_only_stdlib_imports(self):
        allowed = {'os', 'sys', 'traceback'}
        path = os.path.join(ROOT, 'tool.py')
        found = set()

        with open(path, encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line.startswith('import '):
                    found.add(line.split()[1].split('.')[0])

        self.assertEqual(found - allowed, set())


if __name__ == '__main__':
    unittest.main(verbosity=2)
