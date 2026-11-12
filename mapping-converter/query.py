#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Mapping 对照查询器：MCP / Feather gen1 / Feather gen2 / intermediary 互查。

输入（extracted/<mc>/，与 convert.py 共用同一批文件）：
    calamus-intermediary-gen1.tiny   official -> intermediary
    calamus-intermediary-gen2.tiny   official -> intermediary
    feather-gen1.tiny                intermediary -> named
    feather-gen2.tiny                intermediary -> named
    joined.srg + fields.csv / methods.csv

产出：
    out/<mc>/index.js                viewer.html 用的索引（window.__MAP_JSON__）

用法：
    python query.py build  [mc]          生成索引
    python query.py verify [mc]          与 convert.py 的产物交叉校验
    python query.py <关键词> [选项]       查询
    python query.py --open               生成索引并打开网页

设计要点（详见 README §11）：
    * official 名是唯一稳定键；
    * 描述符一律归一化到 official 空间后再当 key，展示时按需重写；
    * 方法只按 (owner, name, desc) 精确对齐，绝不用「仅名字」兜底。
"""

import argparse
import json
import os
import shutil
import sys
import time
import webbrowser
import zlib
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from convert import load_mcp, parse_tiny, read_lines, remap_desc  # noqa: E402


NS = ["obf", "mcp", "inter1", "feather1", "inter2", "feather2"]
NS_LABEL = {
    "obf": "obf",
    "mcp": "mcp",
    "inter1": "inter gen1",
    "feather1": "feather gen1",
    "inter2": "inter gen2",
    "feather2": "feather gen2",
}

# 成员元组的下标
M_OBF, M_SRG, M_NAMED, M_I1, M_F1, M_I2, M_F2, M_DESC = range(8)
# 成员槽位 -> 命名空间下标（srg 与 named 同属 mcp 列）
SLOT_NS = [0, 1, 1, 2, 3, 4, 5]


# --------------------------------------------------------------------------
# 命名空间解析
# --------------------------------------------------------------------------

def expand_ns(values):
    """把 --ns 的简写展开成具体列集合；None 表示全部。"""
    if not values:
        return None
    out = set()
    for v in values:
        v = v.strip().lower()
        if v in ("all", "*", ""):
            return None
        if v in ("obf", "official", "混淆"):
            out.add("obf")
        elif v in ("mcp", "srg"):
            out.add("mcp")
        elif v in ("inter", "intermediary"):
            out.update(("inter1", "inter2"))
        elif v in ("inter1", "intermediary1"):
            out.add("inter1")
        elif v in ("inter2", "intermediary2"):
            out.add("inter2")
        elif v in ("feather", "named"):
            out.update(("feather1", "feather2"))
        elif v in ("feather1", "named1"):
            out.add("feather1")
        elif v in ("feather2", "named2"):
            out.add("feather2")
        else:
            raise SystemExit("未知命名空间: %s（可用 obf/mcp/inter1/inter2/feather1/feather2）" % v)
    return out


# --------------------------------------------------------------------------
# 建索引
# --------------------------------------------------------------------------

def _rev_class_map(cal_classes):
    """intermediary 类名 -> [obf 类名]（理论上 1:1，client/server 分裂时可能多个）。"""
    m = {}
    for c in cal_classes:
        m.setdefault(c.names[1], []).append(c.names[0])
    return m


def _cal_name_map(cal_classes):
    """intermediary 类名 -> {(kind, 成员 inter 名[, desc]): 成员 obf 名}。"""
    m = {}
    for c in cal_classes:
        d = {}
        for _desc, names in c.fields:
            if len(names) > 1:
                d[("f", names[1])] = names[0]
        for desc, names in c.methods:
            if len(names) > 1:
                d[("m", names[1], desc)] = names[0]
        m[c.names[1]] = d
    return m


def build_index(ext, mc):
    t0 = time.time()
    mcp_classes, _fn, _mn = load_mcp(ext)
    _n1, cal1 = parse_tiny(os.path.join(ext, "calamus-intermediary-gen1.tiny"))
    _n2, cal2 = parse_tiny(os.path.join(ext, "calamus-intermediary-gen2.tiny"))
    _n3, fea1 = parse_tiny(os.path.join(ext, "feather-gen1.tiny"))
    _n4, fea2 = parse_tiny(os.path.join(ext, "feather-gen2.tiny"))

    rev = {}
    for c in cal1:
        rev[c.names[1]] = c.names[0]
    for c in cal2:
        rev[c.names[1]] = c.names[0]

    def to_obf_desc(desc):
        return remap_desc(desc, lambda x: rev.get(x, x))

    recs = {}

    def rec(obf):
        r = recs.get(obf)
        if r is None:
            r = {"n": [obf, None, None, None, None, None], "f": [], "m": [], "k": {}}
            recs[obf] = r
        return r

    def slot(r, kind, key, obf_name, desc):
        full = (kind,) + key
        e = r["k"].get(full)
        if e is None:
            e = [obf_name, None, None, None, None, None, None, desc]
            r["k"][full] = e
            (r["f"] if kind == "f" else r["m"]).append(e)
        return e

    # ---- 1) MCP：official -> srg / named ----
    for obf, c in mcp_classes.items():
        r = rec(obf)
        r["n"][1] = c.srg
        for f in c.fields:
            e = slot(r, "f", (f["obf"], ""), f["obf"], "")
            e[M_SRG] = f["srg"]
            e[M_NAMED] = f["named"]
        for m in c.methods:
            e = slot(r, "m", (m["obf"], m["desc"]), m["obf"], m["desc"])
            e[M_SRG] = m["srg"]
            e[M_NAMED] = m["named"]

    # ---- 2) calamus：补 intermediary 列 ----
    for cal, col_i, col_n in ((cal1, M_I1, 2), (cal2, M_I2, 4)):
        for c in cal:
            r = rec(c.names[0])
            r["n"][col_n] = c.names[1]
            for desc, names in c.fields:
                e = slot(r, "f", (names[0], ""), names[0], "")
                e[col_i] = names[1]
                if not e[M_DESC]:
                    e[M_DESC] = desc
            for desc, names in c.methods:
                e = slot(r, "m", (names[0], desc), names[0], desc)
                e[col_i] = names[1]

    # ---- 3) feather：intermediary -> named，并回 official key ----
    for fea, cal, col_i, col_n in ((fea1, cal1, M_F1, 3), (fea2, cal2, M_F2, 5)):
        rev_multi = _rev_class_map(cal)
        nmap = _cal_name_map(cal)
        for fc in fea:
            inter = fc.names[0]
            obfs = rev_multi.get(inter)
            if not obfs:
                continue
            names_map = nmap.get(inter, {})
            for obf in obfs:
                r = rec(obf)
                if r["n"][col_n] is None:
                    r["n"][col_n] = fc.names[1]
                for desc, names in fc.fields:
                    inter_name, named = names[0], names[1]
                    obf_name = names_map.get(("f", inter_name))
                    if obf_name:
                        e = slot(r, "f", (obf_name, ""), obf_name, "")
                    else:
                        # calamus 没有这条（feather 独有），用 named 名当身份
                        e = slot(r, "f", ("#" + named, ""), None, "")
                    e[col_i] = named
                    if not e[M_DESC]:
                        e[M_DESC] = to_obf_desc(desc)
                for desc, names in fc.methods:
                    inter_name, named = names[0], names[1]
                    obf_desc = to_obf_desc(desc)
                    # 注意：calamus 的名字表按 obf 空间 desc 建键，这里必须用归一化后的 desc
                    obf_name = names_map.get(("m", inter_name, obf_desc))
                    if obf_name:
                        e = slot(r, "m", (obf_name, obf_desc), obf_name, obf_desc)
                    else:
                        e = slot(r, "m", ("#" + named, obf_desc), None, obf_desc)
                    e[col_i] = named

    # ---- 4) 输出 ----
    out_classes = []
    n_fields = n_methods = 0
    for obf, r in recs.items():
        n_fields += len(r["f"])
        n_methods += len(r["m"])
        fields = sorted(r["f"], key=lambda e: (e[M_SRG] or e[M_OBF] or e[M_F1] or e[M_F2] or ""))
        methods = sorted(r["m"], key=lambda e: (e[M_SRG] or e[M_OBF] or e[M_F1] or e[M_F2] or "", e[M_DESC]))
        out_classes.append([r["n"], fields, methods])
    out_classes.sort(key=lambda c: (c[0][1] or c[0][5] or c[0][3] or c[0][0]))

    payload = {
        "version": mc,
        "built": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "namespaces": NS,
        "counts": {
            "classes": len(out_classes),
            "fields": n_fields,
            "methods": n_methods,
            "members": n_fields + n_methods,
        },
        "classes": out_classes,
    }
    payload["build_ms"] = int((time.time() - t0) * 1000)
    return payload


def write_index_js(path, payload):
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    # 模板字符串装载，页面里 JSON.parse 一次（实测 15ms，远快于 5MB 对象字面量）
    if "`" in body or "${" in body:
        js = "window.__MAP_JSON__ = %s;\n" % json.dumps(body, ensure_ascii=False)
    else:
        js = "window.__MAP_JSON__ = `%s`;\n" % body
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(js)
    return len(js.encode("utf-8"))


def load_index(path):
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    text = text.strip()
    text = text[text.index("=") + 1:].strip()
    if text.endswith(";"):
        text = text[:-1].strip()
    if text.startswith("`") and text.endswith("`"):
        text = text[1:-1]
    else:
        text = json.loads(text)
    return json.loads(text)


# --------------------------------------------------------------------------
# 查询
# --------------------------------------------------------------------------

def _is_subsequence(needle, hay):
    i = 0
    for ch in hay:
        if i < len(needle) and ch == needle[i]:
            i += 1
    return i == len(needle)


def name_score(q, name, fuzzy):
    if not name:
        return 0
    low = name.lower()
    if low == q:
        return 100
    simple = low.rsplit("/", 1)[-1]
    if simple == q:
        return 92
    if low.endswith("/" + q):
        return 85
    if q in low:
        return 65
    if fuzzy and len(q) >= 3 and _is_subsequence(q, low):
        return 40
    return 0


def search(index, query, ns=None, kind=None, exact=False, limit=20, allow_ctors=False, fuzzy=False):
    q = query.strip()
    if not q:
        return []
    ql = q.replace(".", "/").lower()
    cls = index["classes"]
    hits = []
    for ci, (names, fields, methods) in enumerate(cls):
        if kind in (None, "class"):
            best = 0
            for i, n in enumerate(names):
                if ns is not None and NS[i] not in ns:
                    continue
                best = max(best, name_score(ql, n, fuzzy))
            if best and (not exact or best >= 92):
                hits.append((best, 0, ci, None, None))
        for kind_name, bucket in (("field", fields), ("method", methods)):
            if kind not in (None, kind_name):
                continue
            for e in bucket:
                if not allow_ctors and (e[M_OBF] == "<init>" or e[M_F1] == "<init>" or e[M_F2] == "<init>"):
                    continue
                best = 0
                best_i = 0
                for i in range(7):
                    if ns is not None and NS[SLOT_NS[i]] not in ns:
                        continue
                    s = name_score(ql, e[i], fuzzy)
                    if s > best:
                        best, best_i = s, i
                if not best:
                    continue
                if exact and best < 92:
                    continue
                hits.append((best, 1 if kind_name == "field" else 2, ci, e, best_i))
    hits.sort(key=lambda h: (-h[0], h[1], cls[h[2]][0][1] or cls[h[2]][0][5] or cls[h[2]][0][0]))
    return hits[:limit]


def fmt_name(value):
    return value if value else "—"


def render_class(names, fields, methods, indent="  "):
    lines = ["[类] %s" % (names[1] or names[5] or names[3] or names[0])]
    for i, label in enumerate(NS_LABEL.values()):
        lines.append("%s%-14s %s" % (indent, label, fmt_name(names[i])))
    lines.append("%s%-12s %d 字段 / %d 方法" % (indent, "成员", len(fields), len(methods)))
    return "\n".join(lines)


def render_member(kind, e, owner_names, name_i):
    label = "字段" if kind == "field" else "方法"
    owner = owner_names[1] or owner_names[5] or owner_names[3] or owner_names[0]
    main = e[name_i] or e[M_NAMED] or e[M_SRG] or e[M_OBF] or e[M_F2] or "?"
    desc = e[M_DESC] if kind == "method" else ""
    mcp = e[M_NAMED] or e[M_SRG]
    if e[M_NAMED] and e[M_SRG] and e[M_NAMED] != e[M_SRG]:
        mcp = "%s  [%s]" % (e[M_NAMED], e[M_SRG])
    values = [e[M_OBF], mcp, e[M_I1], e[M_F1], e[M_I2], e[M_F2]]
    lines = ["[%s] %s.%s%s" % (label, owner, main, desc)]
    for lbl, val in zip(NS_LABEL.values(), values):
        lines.append("  %-14s %s" % (lbl, fmt_name(val)))
    return "\n".join(lines)


def cmd_search(args):
    path = os.path.join(HERE, "out", args.version, "index.js")
    if not os.path.exists(path):
        raise SystemExit("没有索引：%s\n先运行 python query.py build %s" % (path, args.version))
    index = load_index(path)
    ns = expand_ns(args.ns)
    hits = search(index, args.keyword, ns=ns, kind=args.kind, exact=args.exact,
                  limit=args.limit, allow_ctors=args.ctors, fuzzy=args.fuzzy)
    if args.json:
        out = []
        for score, k, ci, e, name_i in hits:
            names = index["classes"][ci][0]
            if e is None:
                out.append({"kind": "class", "names": dict(zip(NS, names)),
                            "fields": len(index["classes"][ci][1]),
                            "methods": len(index["classes"][ci][2])})
            else:
                out.append({"kind": "field" if k == 1 else "method",
                            "owner": dict(zip(NS, names)),
                            "names": dict(zip(NS, e[:7])), "desc": e[M_DESC]})
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 0
    if not hits:
        print("没有匹配：%s" % args.keyword)
        print("提示：默认不显示 <init>（用 --ctors）；只看某一代用 --ns feather1 / feather2。")
        return 0
    for score, k, ci, e, name_i in hits:
        names, fields, methods = index["classes"][ci]
        if e is None:
            print(render_class(names, fields, methods))
        else:
            print(render_member("field" if k == 1 else "method", e, names, name_i))
        print("")
    print("共 %d 条（--limit %d）" % (len(hits), args.limit))
    return 0


# --------------------------------------------------------------------------
# 交叉校验
# --------------------------------------------------------------------------

def cmd_verify(args):
    idx_path = os.path.join(HERE, "out", args.version, "index.js")
    merged_path = os.path.join(HERE, "out", args.version, "merged.intermediary-mcp-feather.tiny")
    if not os.path.exists(idx_path):
        raise SystemExit("没有索引，先运行 python query.py build %s" % args.version)
    if not os.path.exists(merged_path):
        raise SystemExit("没有 %s，先运行 python convert.py %s" % (merged_path, args.version))

    index = load_index(idx_path)
    by_mcp = {}
    for names, fields, methods in index["classes"]:
        by_mcp.setdefault(names[1], []).append((names, fields, methods))

    checked = 0
    bad = []
    cur = None
    for line in read_lines(merged_path):
        if not line or line.startswith("tiny\t"):
            continue
        p = line.split("\t")
        if p[0] == "c":
            inter, mcp, feather = p[1], p[2], p[3]
            cands = by_mcp.get(mcp) or []
            hit = [c for c in cands if c[0][4] == inter and c[0][5] == feather]
            cur = hit[0] if hit else None
            checked += 1
            if cur is None:
                bad.append("CLASS %s -> %s / %s" % (mcp, inter, feather))
            continue
        if cur is None:
            continue
        kind = p[1]
        desc, inter_name, mcp_name, fea_name = p[2], p[3], p[4], p[5]
        bucket = cur[1] if kind == "f" else cur[2]
        ok = False
        for e in bucket:
            if e[M_F2] == fea_name and (e[M_NAMED] == mcp_name or e[M_SRG] == mcp_name):
                ok = True
                break
        checked += 1
        if not ok:
            bad.append("%s %s.%s" % (kind.upper(), cur[0][1], mcp_name))
    print("校验 %d 条，失败 %d 条" % (checked, len(bad)))
    for b in bad[:20]:
        print("  ! " + b)
    return 0 if not bad else 1


# --------------------------------------------------------------------------
# 入口
# --------------------------------------------------------------------------

def cmd_export(args):
    """导出「静态托管所需的最小文件集」：index.html + out/<mc>/index.js。"""
    idx = os.path.join(HERE, "out", args.version, "index.js")
    viewer = os.path.join(HERE, "viewer.html")
    if not os.path.exists(idx):
        raise SystemExit("没有索引：%s\n先运行 python query.py build %s" % (idx, args.version))
    dest = os.path.abspath(args.output)
    target_idx = os.path.join(dest, "out", args.version, "index.js")
    os.makedirs(os.path.dirname(target_idx), exist_ok=True)
    shutil.copyfile(viewer, os.path.join(dest, "index.html"))
    shutil.copyfile(idx, target_idx)
    size = os.path.getsize(target_idx)
    with open(target_idx, "rb") as f:
        gz = len(zlib.compress(f.read(), 9))
    print("== 导出 %s 到 %s" % (args.version, dest))
    print("   index.html")
    print("   out/%s/index.js  (%.2f MB，gzip 后 %.2f MB)" % (
        args.version, size / 1048576.0, gz / 1048576.0))
    print("")
    print("   直接把这个目录丢给任意静态服务器即可；运行时不需要 Python。")
    return 0


def cmd_build(args):
    ext = os.path.join(HERE, "extracted", args.version)
    if not os.path.isdir(ext):
        raise SystemExit("缺少 %s\n先运行 python fetch.py %s" % (ext, args.version))
    for name in ("calamus-intermediary-gen1.tiny", "calamus-intermediary-gen2.tiny",
                 "feather-gen1.tiny", "feather-gen2.tiny", "joined.srg"):
        if not os.path.exists(os.path.join(ext, name)):
            raise SystemExit("缺少 %s\n先运行 python fetch.py %s" % (name, args.version))
    print("== 构建索引 %s" % args.version)
    payload = build_index(ext, args.version)
    path = os.path.join(HERE, "out", args.version, "index.js")
    size = write_index_js(path, payload)
    c = payload["counts"]
    print("   %d 类 / %d 字段 / %d 方法（共 %d 条成员）" % (
        c["classes"], c["fields"], c["methods"], c["members"]))
    print("   -> %s (%.2f MB, 构建 %d ms)" % (path, size / 1048576.0, payload["build_ms"]))
    if args.open:
        viewer = os.path.join(HERE, "viewer.html")
        webbrowser.open("file:///%s?v=%s" % (viewer.replace("\\", "/"), args.version))
    return 0


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "build":
        p = argparse.ArgumentParser(prog="query.py build")
        p.add_argument("version", nargs="?", default="1.12.2")
        p.add_argument("--open", action="store_true", help="构建后用浏览器打开 viewer.html")
        return cmd_build(p.parse_args(argv[1:]))
    if argv and argv[0] == "export":
        p = argparse.ArgumentParser(prog="query.py export")
        p.add_argument("version", nargs="?", default="1.12.2")
        p.add_argument("-o", "--output", default="dist", help="输出目录，默认 dist")
        return cmd_export(p.parse_args(argv[1:]))
    if argv and argv[0] == "verify":
        p = argparse.ArgumentParser(prog="query.py verify")
        p.add_argument("version", nargs="?", default="1.12.2")
        return cmd_verify(p.parse_args(argv[1:]))

    p = argparse.ArgumentParser(prog="query.py", description="Mapping 对照查询器")
    p.add_argument("keyword", help="类名 / 方法名 / 字段名，支持部分匹配，a.b.C 会被归一化成 a/b/C")
    p.add_argument("-v", "--version", default="1.12.2")
    p.add_argument("--ns", action="append", help="限定命名空间，可重复：obf/mcp/inter1/inter2/feather1/feather2")
    p.add_argument("--kind", choices=["class", "field", "method"], help="只看某一类")
    p.add_argument("--exact", action="store_true", help="只保留完全匹配")
    p.add_argument("--limit", type=int, default=20)
    p.add_argument("--ctors", action="store_true", help="显示 <init> 构造函数")
    p.add_argument("--fuzzy", action="store_true", help="启用子序列模糊匹配（较慢）")
    p.add_argument("--json", action="store_true")
    p.add_argument("--open", action="store_true", help="构建索引并打开网页")
    args = p.parse_args(argv)
    if args.open:
        return cmd_build(argparse.Namespace(version=args.version, open=True))
    return cmd_search(args)


if __name__ == "__main__":
    sys.exit(main())
