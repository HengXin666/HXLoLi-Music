# -*- coding: utf-8 -*-
"""review.jsonl 读写单测: 走 make_server 的 HTTP (GET/POST /api/review), 所以新旧 app.py 都能跑 (反证用).
   python3 test_review.py                       (测当前 app.py)
   STUDIO_APP=app_old python3 test_review.py    (测另一份, 例如 git show :app.py > app_old.py; 用完删)
批注写到临时 review.jsonl (make_server 的 review= 参数), 不碰任何工程."""
import builtins, importlib, json, os, shutil, tempfile, threading, unittest, urllib.error, urllib.request

app = importlib.import_module(os.environ.get("STUDIO_APP", "app"))

GOOD = dict(id="r1", sel=[dict(line=0, **{"from": 0, "to": 1})], t0=1, t1=2, kind="good", tags=[], text="")
POST = dict(sel=[dict(line=0, **{"from": 0, "to": 1})], t0=1, t1=2, kind="note", text="字太挤")


NOPROXY = urllib.request.build_opener(urllib.request.ProxyHandler({}))   # 本机服务: 不走 http_proxy 环境变量


def line(rec):
    return (json.dumps(rec, ensure_ascii=False) + "\n").encode("utf-8")


class Review(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        proj = os.path.join(self.tmp, "static", "music", "番")   # repo_root 认 static/music, 不往上找到真仓库
        os.makedirs(proj)
        self.f = os.path.join(self.tmp, "review.jsonl")
        self.srv = app.make_server(proj, "127.0.0.1", 0, review=self.f)
        self.url = "http://127.0.0.1:%d/api/review" % self.srv.server_address[1]
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()

    def tearDown(self):
        self.srv.shutdown()
        self.srv.server_close()
        shutil.rmtree(self.tmp)

    def put(self, data):
        with open(self.f, "wb") as fh:
            fh.write(data)

    def raw(self):
        with open(self.f, "rb") as fh:
            return fh.read()

    def req(self, body=None):
        r = urllib.request.Request(self.url, data=None if body is None else json.dumps(body).encode("utf-8"),
                                   headers={"content-type": "application/json"}, method="GET" if body is None else "POST")
        try:
            with NOPROXY.open(r, timeout=5) as resp:
                return resp.status, json.loads(resp.read())
        except urllib.error.HTTPError as e:
            body = e.read()
            try:
                return e.code, json.loads(body or b"null")
            except ValueError:
                return e.code, body.decode("utf-8", "replace")
        except (ConnectionError, urllib.error.URLError) as e:   # 旧版异常冒出 handler: 连接直接断, 没有响应
            return None, str(e)

    def get(self):
        st, b = self.req()
        self.assertEqual(st, 200, b)
        return b

    # ---- 读: 一行坏不拖累别的行
    def test_bad_json_line_skipped_and_reported(self):
        self.put(line(GOOD) + b'{"bad\n' + line(dict(GOOD, id="r3")))
        b = self.get()
        self.assertEqual([x["id"] for x in b["items"]], ["r1", "r3"])
        self.assertEqual([x["line"] for x in b["bad_lines"]], [2])
        self.assertIn("JSON", b["bad_lines"][0]["error"])
        self.assertEqual(b["bad_lines"][0]["head"], '{"bad')

    def test_valid_json_wrong_shape_is_bad_line(self):
        # 服务端能 json.loads, 前端 r.sel.some / t0 会抛: 两边校验要一致
        self.put(line(GOOD) + b"[]\n3\n" + line(dict(GOOD, sel=None)) + line(dict(GOOD, t0="1")) + line(dict(GOOD, kind="meh")))
        b = self.get()
        self.assertEqual([x["id"] for x in b["items"]], ["r1"])
        self.assertEqual([x["line"] for x in b["bad_lines"]], [2, 3, 4, 5, 6])

    def test_non_utf8_line_only_breaks_itself(self):
        self.put(line(GOOD) + b"\xff\xfe{}\n" + line(dict(GOOD, id="r3")))
        b = self.get()
        self.assertEqual([x["id"] for x in b["items"]], ["r1", "r3"])
        self.assertEqual([x["line"] for x in b["bad_lines"]], [2])
        self.assertIn("UTF-8", b["bad_lines"][0]["error"])

    # ---- 写: 坏行原样搬, 末行无换行时只补分隔符
    def test_append_after_last_line_without_newline(self):
        old = line(GOOD) + b'{"bad'          # 末行是坏行且没有换行
        self.put(old)
        st, rec = self.req(POST)
        self.assertEqual(st, 201, rec)
        self.assertEqual(self.raw(), old + b"\n" + line(rec))   # 末行字节不变, 只加分隔; 新记录独占一行
        b = self.get()
        self.assertEqual([x["id"] for x in b["items"]], ["r1", rec["id"]])
        self.assertEqual([(x["line"], x["head"]) for x in b["bad_lines"]], [(2, '{"bad')])   # 仍是坏行, 仍是第 2 行

    def test_append_keeps_bad_lines_byte_for_byte(self):
        old = line(GOOD) + b'{"bad\r\n' + b"\xff\xfe\n" + b"   \n" + line(dict(GOOD, id="r5"))
        self.put(old)
        st, rec = self.req(POST)
        self.assertEqual(st, 201, rec)
        self.assertEqual(self.raw(), old + line(rec))

    def test_post_rejects_record_that_would_be_bad_line(self):
        self.put(line(GOOD))
        st, b = self.req(dict(POST, sel="x"))
        self.assertEqual(st, 400, b)
        self.assertEqual(self.raw(), line(GOOD))

    def test_write_failure_midway_leaves_file_untouched(self):
        # 故障注入: 写 review 相关文件时只写进一半就 ENOSPC (磁盘满), 不管实现是追加还是临时文件
        old = line(GOOD) + b'{"bad\n'
        self.put(old)
        real_open = builtins.open
        target = os.path.dirname(self.f)

        class Half:
            def __init__(self, fh):
                self.fh = fh

            def __enter__(self):
                return self

            def __exit__(self, *a):
                self.fh.close()

            def write(self, data):
                self.fh.write(data[:len(data) // 2])
                self.fh.flush()
                raise OSError(28, "No space left on device")

            def __getattr__(self, k):
                return getattr(self.fh, k)

        def fake_open(path, mode="r", *a, **k):
            fh = real_open(path, mode, *a, **k)
            if isinstance(path, str) and os.path.dirname(os.path.abspath(path)) == target and any(c in mode for c in "wax"):
                return Half(fh)
            return fh
        app.open = fake_open   # 模块级 open 覆盖内建, 只影响 app.py
        try:
            st, b = self.req(POST)
        finally:
            del app.open
        self.assertEqual(st, 500, b)
        self.assertIn("标注没写进去", b["error"])
        self.assertEqual(self.raw(), old)                              # 原文件一个字节没动 (旧版: 半行已追加)
        self.assertEqual(sorted(os.listdir(target)), ["review.jsonl", "static"])   # 不留临时文件


if __name__ == "__main__":
    unittest.main()
