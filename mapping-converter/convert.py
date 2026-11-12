#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
把 1.12.2 的 MCP 映射（joined.srg + 3 个 CSV）与 calamus-intermediary、
feather 三套映射互相转换，演示 ploceus / Loom 里发生的完整过程。

输入 (extracted/<mc>/):
    calamus-intermediary-gen1.tiny    official  -> intermediary
    calamus-intermediary-gen2.tiny    official  -> intermediary
    feather-gen1.tiny                 intermediary -> named
    feather-gen2.tiny                 intermediary -> named
    joined.srg                        official -> srg
    fields.csv / methods.csv / params.csv   srg -> named

输出 (out/<mc>/):
    mcp.official-srg-named.tiny       MCP 原始三列（不经 calamus）
    mcp.intermediary-named.tiny       MCP 经 calamus 转换后的结果（= ploceus 的产出）
    merged.intermediary-mcp-feather.tiny   三套名字对齐后的合并视图
    mcp-to-feather.tiny               MCP 名 -> feather 名
    feather-to-mcp.tiny               feather 名 -> MCP 名
    unresolved.txt                    无法通过 calamus 解析的 MCP 成员
    stats.json                        各阶段命中率

用法:
    python convert.py [版本号]
"""

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


# --------------------------------------------------------------------------
# 通用工具
# --------------------------------------------------------------------------

def read_lines(path):
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return f.read().splitlines()


def write_lines(path, lines):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines))
        if lines:
            f.write("\n")


def split_desc(desc):
    """把 '(ILa;[Lb;)V' 拆成 (参数描述符列表, 返回描述符)。"""
    assert desc.startswith("(")
    depth = 0
    i = 1
    args = []
    start = 1
    while i < len(desc):
        c = desc[i]
        if c == "[":
            i += 1
            continue
        if c == "L":
            j = desc.index(";", i)
            args.append(desc[start:j + 1])
            i = j + 1
            start = i
            continue
        if c == ")":
            break
        args.append(desc[start:i + 1])
        i += 1
        start = i
    return args, desc[desc.index(")") + 1:]


def remap_desc(desc, mapper):
    """把描述符里的 L<class>; 类名用 mapper 重写。"""
    out = []
    i = 0
    while i < len(desc):
        c = desc[i]
        if c == "L":
            j = desc.index(";", i)
            out.append("L" + mapper(desc[i + 1:j]) + ";")
            i = j + 1
        else:
            out.append(c)
            i += 1
    return "".join(out)


# --------------------------------------------------------------------------
# Tiny v2
# --------------------------------------------------------------------------

class TinyClass:
    __slots__ = ("names", "fields", "methods")

    def __init__(self, names):
        self.names = names          # [ns0, ns1, ...]
        self.fields = []            # [(desc, [names...])]
        self.methods = []           # [(desc, [names...])]


def parse_tiny(path):
    namespaces = None
    classes = []
    cur = None
    for line in read_lines(path):
        if not line:
            continue
        if line.startswith("tiny\t"):
            namespaces = line.split("\t")[3:]
        elif line.startswith("c\t"):
            cur = TinyClass(line.split("\t")[1:])
            classes.append(cur)
        elif line.startswith("\tm\t"):
            p = line.split("\t")
            cur.methods.append((p[2], p[3:]))
        elif line.startswith("\tf\t"):
            p = line.split("\t")
            cur.fields.append((p[2], p[3:]))
        # '\t\t' 参数行、'\tc\t' 注释行：本例不需要
    return namespaces, classes


class TinyIndex:
    """按 src 命名空间建索引，方便查 dst 名。"""

    def __init__(self, namespaces, classes):
        self.namespaces = namespaces
        self.classes = classes
        self.class_by_src = {}       # src name -> TinyClass
        self.field_by_src = {}       # (src owner, src field name) -> dst name
        self.field_desc_by_src = {}  # (src owner, src field name) -> desc
        self.method_by_src = {}      # (src owner, src name, src desc) -> dst name
        self.method_desc_by_src = {} # (src owner, src name) -> [desc...]
        for c in classes:
            src = c.names[0]
            self.class_by_src[src] = c
            for desc, names in c.fields:
                self.field_by_src[(src, names[0])] = names[1] if len(names) > 1 else None
                self.field_desc_by_src[(src, names[0])] = desc
            for desc, names in c.methods:
                self.method_by_src[(src, names[0], desc)] = names[1] if len(names) > 1 else None
                self.method_desc_by_src.setdefault((src, names[0]), []).append(desc)

    def dst_class(self, src):
        c = self.class_by_src.get(src)
        return c.names[1] if c and len(c.names) > 1 else None

    def dst_field(self, owner, name):
        return self.field_by_src.get((owner, name))

    def field_desc(self, owner, name):
        return self.field_desc_by_src.get((owner, name))

    def dst_method(self, owner, name, desc):
        """
        只做 (owner, name, desc) 精确匹配 —— 和 ploceus/mappingio 的行为一致。
        不要退化成「仅名字匹配」：1.12.2 上那样会把同名但不同签名的方法错配
        （例：BredAnimalsTrigger 的 a()Lnf; 被错配到 a(Loq;Lzv;Lzv;Lvd;)V）。
        """
        hit = self.method_by_src.get((owner, name, desc))
        if hit is not None:
            return hit, "exact"
        return None, "miss"


# --------------------------------------------------------------------------
# SRG + CSV -> MCP 模型
# --------------------------------------------------------------------------

class McpClass:
    __slots__ = ("obf", "srg", "fields", "methods")

    def __init__(self, obf, srg):
        self.obf = obf
        self.srg = srg              # MCP 的类名本身就是可读的
        self.fields = []            # dict(obf, srg, named)
        self.methods = []           # dict(obf, desc, srg, named)


def load_mcp(ext):
    classes = {}
    raw_fields = []
    raw_methods = []

    for line in read_lines(os.path.join(ext, "joined.srg")):
        if not line:
            continue
        p = line.split(" ")
        tag = p[0]
        if tag == "CL:":
            classes[p[1]] = McpClass(p[1], p[2])
        elif tag == "FD:":
            owner, name = p[1].rsplit("/", 1)
            raw_fields.append((owner, name, p[2]))
        elif tag == "MD:":
            owner, name = p[1].rsplit("/", 1)
            raw_methods.append((owner, name, p[2], p[3]))
        # PK: 忽略

    def csv_map(name):
        path = os.path.join(ext, name)
        m = {}
        if not os.path.exists(path):
            return m
        for i, line in enumerate(read_lines(path)):
            if i == 0 or not line:
                continue
            parts = line.split(",", 3)
            if len(parts) >= 2:
                m[parts[0]] = parts[1]
        return m

    field_names = csv_map("fields.csv")
    method_names = csv_map("methods.csv")

    for owner, name, srg_full in raw_fields:
        c = classes.get(owner)
        if c is None:
            continue
        srg_name = srg_full.rsplit("/", 1)[1]
        c.fields.append({"obf": name, "srg": srg_name,
                         "named": field_names.get(srg_name, srg_name)})

    for owner, name, desc, srg_full in raw_methods:
        c = classes.get(owner)
        if c is None:
            continue
        srg_name = srg_full.rsplit("/", 1)[1]
        c.methods.append({"obf": name, "desc": desc, "srg": srg_name,
                          "named": method_names.get(srg_name, srg_name)})

    return classes, field_names, method_names


# --------------------------------------------------------------------------
# 转换
# --------------------------------------------------------------------------

def build_mcp_through_intermediary(mcp, calamus):
    """MCP(official) --calamus--> intermediary，返回 {obf: inter} 与成员映射。"""
    class_map = {}
    unresolved = []
    stats = {"class_exact": 0, "class_miss": 0,
             "field_exact": 0, "field_miss": 0,
             "method_exact": 0, "method_name_only": 0, "method_miss": 0}

    # 1) 类：official -> intermediary
    for obf, c in mcp.items():
        inter = calamus.dst_class(obf)
        if inter:
            class_map[obf] = inter
            stats["class_exact"] += 1
        else:
            class_map[obf] = obf
            stats["class_miss"] += 1
            unresolved.append("CLASS %s (%s)" % (obf, c.srg))

    def m2i(cls):
        return class_map.get(cls, cls)

    # 2) 成员
    for obf, c in mcp.items():
        inter_owner = class_map[obf]
        for f in c.fields:
            inter_name = calamus.dst_field(obf, f["obf"])
            f["desc"] = calamus.field_desc(obf, f["obf"]) or ""
            f["inter_desc"] = remap_desc(f["desc"], m2i)
            if inter_name:
                f["inter"] = inter_name
                stats["field_exact"] += 1
            else:
                f["inter"] = None
                stats["field_miss"] += 1
                unresolved.append("FIELD %s/%s (%s)" % (obf, f["obf"], f["srg"]))
        for m in c.methods:
            inter_desc = remap_desc(m["desc"], m2i)
            inter_name, how = calamus.dst_method(obf, m["obf"], m["desc"])
            if inter_name:
                m["inter"] = inter_name
                m["inter_desc"] = inter_desc
                stats["method_" + how.replace("-", "_")] += 1
            else:
                m["inter"] = None
                m["inter_desc"] = inter_desc
                stats["method_miss"] += 1
                unresolved.append("METHOD %s/%s%s (%s)" % (obf, m["obf"], m["desc"], m["srg"]))

    return class_map, unresolved, stats


def write_tiny_mcp(path, mcp, class_map, namespaces):
    """
    按给定列写出 tiny v2。
    namespaces = ['official', 'srg', 'named'] 或 ['intermediary', 'named']
    """
    n = len(namespaces)
    as_intermediary = namespaces[0] == "intermediary"
    out = ["tiny\t2\t0\t" + "\t".join(namespaces)]
    for obf, c in sorted(mcp.items()):
        if as_intermediary:
            names = [class_map.get(obf, obf), c.srg][:n]
        else:
            names = [obf, c.srg, c.srg][:n]
        out.append("c\t" + "\t".join(names))
        for f in c.fields:
            if as_intermediary:
                if not f.get("inter"):
                    continue
                row = [f["inter"], f["named"]][:n]
                desc = f.get("inter_desc", "")
            else:
                row = [f["obf"], f["srg"], f["named"]][:n]
                desc = f.get("desc", "")
            out.append("\tf\t" + desc + "\t" + "\t".join(row))
        for m in c.methods:
            if as_intermediary:
                if not m.get("inter"):
                    continue
                row = [m["inter"], m["named"]][:n]
                desc = m["inter_desc"]
            else:
                row = [m["obf"], m["srg"], m["named"]][:n]
                desc = m["desc"]
            out.append("\tm\t" + desc + "\t" + "\t".join(row))
    write_lines(path, out)


def main(argv):
    mc = argv[1] if len(argv) > 1 else "1.12.2"
    ext = os.path.join(HERE, "extracted", mc)
    out = os.path.join(HERE, "out", mc)

    print("== 读取 %s" % mc)
    cal_ns, cal_classes = parse_tiny(os.path.join(ext, "calamus-intermediary-gen2.tiny"))
    fea_ns, fea_classes = parse_tiny(os.path.join(ext, "feather-gen2.tiny"))
    calamus = TinyIndex(cal_ns, cal_classes)
    feather = TinyIndex(fea_ns, fea_classes)
    mcp, field_names, method_names = load_mcp(ext)

    print("   calamus %s : %d 类" % (cal_ns, len(cal_classes)))
    print("   feather %s : %d 类" % (fea_ns, len(fea_classes)))
    print("   mcp     : %d 类, %d 字段, %d 方法" % (
        len(mcp), sum(len(c.fields) for c in mcp.values()),
        sum(len(c.methods) for c in mcp.values())))

    # ---- 1) MCP 内部：official -> srg -> named（不需要 calamus）----
    class_map_identity = {obf: obf for obf in mcp}
    write_tiny_mcp(os.path.join(out, "mcp.official-srg-named.tiny"),
                   mcp, class_map_identity, ["official", "srg", "named"])
    print("   -> mcp.official-srg-named.tiny")

    # ---- 2) 经 calamus 转到 intermediary ----
    class_map, unresolved, stats = build_mcp_through_intermediary(mcp, calamus)
    print("   join: 类 %d/%d, 字段 %d, 方法 exact %d / name-only %d / miss %d" % (
        stats["class_exact"], len(mcp), stats["field_exact"],
        stats["method_exact"], stats["method_name_only"], stats["method_miss"]))

    # 只输出解析成功的成员
    for c in mcp.values():
        c.fields = [f for f in c.fields if f.get("inter")]
        c.methods = [m for m in c.methods if m.get("inter")]
    write_tiny_mcp(os.path.join(out, "mcp.intermediary-named.tiny"),
                   mcp, class_map, ["intermediary", "named"])
    print("   -> mcp.intermediary-named.tiny")

    write_lines(os.path.join(out, "unresolved.txt"), unresolved)
    print("   -> unresolved.txt (%d 条)" % len(unresolved))

    # ---- 3) 与 feather 对齐：intermediary 是共同键 ----
    merged = ["tiny\t2\t0\tintermediary\tmcp\tfeather"]
    m2f = ["tiny\t2\t0\tmcp\tfeather"]
    f2m = ["tiny\t2\t0\tfeather\tmcp"]
    fea_by_inter = {c.names[0]: c for c in fea_classes}
    mcp_srg = {obf: c.srg for obf, c in mcp.items()}
    inter_to_srg = {class_map[obf]: c.srg for obf, c in mcp.items()}

    def to_srg(name):
        return mcp_srg.get(name, name)

    def inter_to_srg_desc(desc):
        return remap_desc(desc, lambda x: inter_to_srg.get(x, x))

    both = 0
    for obf, c in sorted(mcp.items()):
        inter = class_map[obf]
        fc = fea_by_inter.get(inter)
        if fc is None:
            continue
        both += 1
        mcp_cls = c.srg
        fea_cls = fc.names[1]
        merged.append("c\t%s\t%s\t%s" % (inter, mcp_cls, fea_cls))
        m2f.append("c\t%s\t%s" % (mcp_cls, fea_cls))
        f2m.append("c\t%s\t%s" % (fea_cls, mcp_cls))

        fea_fields = {names[0]: names[1] for _, names in fc.fields}
        for f in c.fields:
            if f["inter"] in fea_fields:
                merged.append("\tf\t%s\t%s\t%s\t%s" % (f["inter_desc"], f["inter"], f["named"], fea_fields[f["inter"]]))
                m2f.append("\tf\t%s\t%s\t%s" % (remap_desc(f.get("desc", ""), to_srg), f["named"], fea_fields[f["inter"]]))
                f2m.append("\tf\t%s\t%s\t%s" % (f["inter_desc"], fea_fields[f["inter"]], f["named"]))

        fea_methods = {(names[0], desc): names[1] for desc, names in fc.methods}
        for m in c.methods:
            key = (m["inter"], m["inter_desc"])
            if key in fea_methods:
                merged.append("\tm\t%s\t%s\t%s\t%s" % (m["inter_desc"], m["inter"], m["named"], fea_methods[key]))
                m2f.append("\tm\t%s\t%s\t%s" % (remap_desc(m["desc"], to_srg), m["named"], fea_methods[key]))
                f2m.append("\tm\t%s\t%s\t%s" % (m["inter_desc"], fea_methods[key], m["named"]))
    write_lines(os.path.join(out, "merged.intermediary-mcp-feather.tiny"), merged)
    write_lines(os.path.join(out, "mcp-to-feather.tiny"), m2f)
    write_lines(os.path.join(out, "feather-to-mcp.tiny"), f2m)
    print("   -> merged.intermediary-mcp-feather.tiny (%d 类对齐)" % both)
    print("   -> mcp-to-feather.tiny / feather-to-mcp.tiny")

    stats["classes_in_both"] = both
    stats["mcp_classes"] = len(mcp)
    stats["calamus_classes"] = len(cal_classes)
    stats["feather_classes"] = len(fea_classes)
    with open(os.path.join(out, "stats.json"), "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=2, ensure_ascii=False)
    print("   -> stats.json")
    print("done.")


if __name__ == "__main__":
    main(sys.argv)
