"""把模拟器的统计队列数据库复制到可写位置并列出内容（只读，不改动模拟器文件）。"""
from __future__ import annotations

import os
import shutil
import sqlite3
import tempfile

SRC = r"F:\project\Mathemetical_modeling_202609\simulator\Jammers-simulator-full\JammersSimulatorData"
FILES = ["practice-statistics-queue.sqlite3", "formal-statistics-queue.sqlite3",
         "upload-queue.sqlite3"]


def main():
    for fn in FILES:
        src = os.path.join(SRC, fn)
        if not os.path.exists(src):
            print(f"[skip] {fn} 不存在")
            continue
        tmp = os.path.join(tempfile.gettempdir(), "dsh_" + fn)
        try:
            shutil.copyfile(src, tmp)
        except Exception as e:
            print(f"[fail] 复制 {fn}: {e!r}")
            continue
        print(f"\n===== {fn} =====")
        try:
            con = sqlite3.connect(tmp)
            cur = con.cursor()
            tabs = [r[0] for r in cur.execute(
                "select name from sqlite_master where type='table'")]
            print("表:", tabs)
            for t in tabs:
                cols = [r[1] for r in cur.execute(f"PRAGMA table_info({t})")]
                n = cur.execute(f"select count(*) from {t}").fetchone()[0]
                print(f"\n-- {t} ({n} 行) 列: {cols}")
                for row in cur.execute(f"select * from {t} limit 5"):
                    print("   ", row)
            con.close()
        except Exception as e:
            print(f"[fail] 读取 {fn}: {e!r}")


if __name__ == "__main__":
    main()
