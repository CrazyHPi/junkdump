#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MCP（Model Context Protocol）服务器：把 mapping 对照查询暴露给 LLM。

传输：stdio + newline-delimited JSON-RPC 2.0（MCP 标准），不依赖任何第三方库。
数据：out/<mc>/index.js（由 query.py build 生成），与 CLI、网页共用同一份索引，
      搜索逻辑直接 import query.py，保证三边结果完全一致。

用法：
    python mcp_server.py                 以 stdio 方式启动（给 MCP 客户端用）
    python mcp_server.py --config        打印客户端配置片段
    python mcp_server.py --version 1.12.2   指定默认版本

工具：
    mapping_search      六套命名空间里搜类 / 字段 / 方法
    mapping_class       一个类的全部名字 + 成员表
    mapping_member      一个字段 / 方法的所有名字
    mapping_convert     把名字从一套命名空间换到另一套
    mapping_descriptor  重写描述符里的类名
    mapping_stats       数据版本与规模
"""

import argparse
import json
import os
import sys
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from convert import remap_desc  # noqa: E402
from query import (  # noqa: E402
    M_DESC, M_F1, M_F2, M_I1, M_I2, M_NAMED, M_OBF, M_SRG,
    NS, load_index, name_score, search,
)

SERVER_NAME = "mapping-lookup"
SERVER_VERSION = "1.0.0"
PROTOCOLS = ["2025-06-18", "2025-03-26", "2024-11-05"]

LABEL = ["obf", "mcp", "intermediary1", "feather1", "intermediary2", "feather2"]
# 类列号(0..5) -> 成员元组槽位；mcp 列对应成员元组里的 srg(1)/named(2) 两个槽
MEMBER_SLOT = {0: M_OBF, 1: M_NAMED, 2: M_I1, 3: M_F1, 4: M_I2, 5: M_F2}
# 一个命名空间可能对应多个成员槽（mcp 列既有 srg 名也有 named 名）
SLOTS_FOR_NS = {0: (M_OBF,), 1: (M_SRG, M_NAMED), 2: (M_I1,), 3: (M_F1,), 4: (M_I2,), 5: (M_F2,)}


def member_value(e, ns_idx):
    if ns_idx == 1:
        return e[M_NAMED] or e[M_SRG]
    return e[MEMBER_SLOT[ns_idx]]


class RpcError(Exception):
    def __init__(self, code, message):
        Exception.__init__(self, message)
        self.code = code
        self.message = message
NS_ALIAS = {
    "obf": 0, "official": 0, "混淆": 0,
    "mcp": 1, "srg": 1,
    "inter1": 2, "intermediary1": 2,
    "feather1": 3, "named1": 3,
    "inter2": 4, "intermediary2": 4,
    "feather2": 5, "named2": 5,
}

NOTES = (
    "official(混淆) 名是唯一稳定键；描述符在索引里统一归一化到 official 空间；"
    "方法只按 (owner, name, desc) 精确对齐，不做仅名字兜底。"
    "Feather gen1 与 gen2 对 800 个匿名内部类命名不同，两列分开看，不要混用。"
    "tiny 不含继承关系，本工具不提供父类/接口。"
)


# --------------------------------------------------------------------------
# JSON-RPC 小工具
# --------------------------------------------------------------------------

def ok(mid, result):
    return {"jsonrpc": "2.0", "id": mid, "result": result}


def err(mid, code, message):
    return {"jsonrpc": "2.0", "id": mid, "error": {"code": code, "message": message}}


def write_msg(stream, obj):
    stream.write((json.dumps(obj, ensure_ascii=False) + "\n").encode("utf-8"))
    stream.flush()


# --------------------------------------------------------------------------
# 数据
# --------------------------------------------------------------------------

def available_versions():
    out = os.path.join(HERE, "out")
    versions = []
    if os.path.isdir(out):
        for name in sorted(os.listdir(out)):
            if os.path.exists(os.path.join(out, name, "index.js")):
                versions.append(name)
    return versions


class Dataset:
    """一份索引 + 各命名空间的正反向类名表。"""

    def __init__(self, version, index):
        self.version = version
        self.index = index
        self.classes = index["classes"]
        self.obf_to = {}
        self.name_to_obf = {}
        for i in range(6):
            fwd, rev = {}, {}
            for names, _f, _m in self.classes:
                if names[i]:
                    fwd[names[0]] = names[i]
                    rev[names[i]] = names[0]
            self.obf_to[i] = fwd
            self.name_to_obf[i] = rev

    def desc_to(self, desc, target):
        if not desc or target == 0:
            return desc
        fwd = self.obf_to[target]
        return remap_desc(desc, lambda x: fwd.get(x, x))

    def resolve_classes(self, name, ns_idx=None):
        """按全名 / 简单名精确解析类，返回 [(score, ci)]。"""
        q = name.strip().replace(".", "/").lower()
        out = []
        for ci, (names, _f, _m) in enumerate(self.classes):
            best = 0
            for i in range(6):
                if ns_idx is not None and i != ns_idx:
                    continue
                best = max(best, name_score(q, names[i], False))
            if best >= 92:
                out.append((best, ci))
        out.sort(key=lambda x: -x[0])
        return out


class Server:
    def __init__(self, default_version=None):
        self.default_version = default_version
        self.cache = {}

    def dataset(self, version=None):
        v = version or self.default_version
        if not v:
            versions = available_versions()
            if not versions:
                raise RuntimeError("没有可用索引，先运行 python query.py build 1.12.2")
            v = versions[-1]
        if v in self.cache:
            return self.cache[v]
        path = os.path.join(HERE, "out", v, "index.js")
        if not os.path.exists(path):
            raise RuntimeError("没有 %s 的索引（%s），先运行 python query.py build %s" % (v, path, v))
        ds = Dataset(v, load_index(path))
        self.cache[v] = ds
        return ds


# --------------------------------------------------------------------------
# 渲染
# --------------------------------------------------------------------------

def fmt_member_line(ds, e, kind, desc_ns):
    mcp = e[M_NAMED] or e[M_SRG]
    srg = e[M_SRG] if (e[M_NAMED] and e[M_SRG] and e[M_NAMED] != e[M_SRG]) else ""
    main = mcp or e[M_F2] or e[M_F1] or e[M_OBF] or "?"
    tail = ""
    if e[M_F2] and e[M_F2] != main:
        tail = "  -> feather2: " + e[M_F2]
    elif e[M_F1] and e[M_F1] != main and not e[M_F2]:
        tail = "  -> feather1: " + e[M_F1]
    if kind == "method":
        desc = ds.desc_to(e[M_DESC], desc_ns)
        return "  %s%s %s%s" % (main, " (" + srg + ")" if srg else "", desc, tail)
    return "  %s%s%s" % (main, " (" + srg + ")" if srg else "", tail)


def render_class(ds, ci, include_members=True, member_kind="all", member_limit=40, desc_ns=5):
    names, fields, methods = ds.classes[ci]
    title = names[1] or names[5] or names[3] or names[0]
    lines = ["class " + title]
    for i in range(6):
        lines.append("  %-13s %s" % (LABEL[i], names[i] or "—"))
    lines.append("  %-13s %d fields / %d methods" % ("members", len(fields), len(methods)))
    if not include_members:
        return "\n".join(lines)
    if member_kind in ("all", "field") and fields:
        lines.append("fields:")
        for e in fields[:member_limit]:
            lines.append(fmt_member_line(ds, e, "field", desc_ns))
        if len(fields) > member_limit:
            lines.append("  ... 还有 %d 个字段（调大 member_limit）" % (len(fields) - member_limit))
    if member_kind in ("all", "method") and methods:
        lines.append("methods:")
        for e in methods[:member_limit]:
            lines.append(fmt_member_line(ds, e, "method", desc_ns))
        if len(methods) > member_limit:
            lines.append("  ... 还有 %d 个方法（调大 member_limit）" % (len(methods) - member_limit))
    return "\n".join(lines)


def render_member(ds, e, kind, owner_names, desc_ns):
    lines = ["%s %s" % ("field" if kind == "field" else "method",
                        (owner_names[1] or owner_names[5] or owner_names[0]) + "." +
                        (e[M_NAMED] or e[M_SRG] or e[M_F2] or e[M_OBF] or "?"))]
    values = [
        ("obf", e[M_OBF]),
        ("mcp", (e[M_NAMED] or "") + ("  [" + e[M_SRG] + "]" if e[M_SRG] and e[M_NAMED] and e[M_SRG] != e[M_NAMED] else "") if (e[M_NAMED] or e[M_SRG]) else ""),
        ("intermediary1", e[M_I1]),
        ("feather1", e[M_F1]),
        ("intermediary2", e[M_I2]),
        ("feather2", e[M_F2]),
    ]
    for label, value in values:
        lines.append("  %-13s %s" % (label, value or "—"))
    if kind == "method" and e[M_DESC]:
        lines.append("  %-13s %s" % ("descriptor", ds.desc_to(e[M_DESC], desc_ns)))
    return "\n".join(lines)


# --------------------------------------------------------------------------
# 工具实现
# --------------------------------------------------------------------------

def tool_search(srv, args):
    ds = srv.dataset(args.get("version"))
    query = (args.get("query") or "").strip()
    if not query:
        raise ValueError("query 不能为空")
    ns_name = (args.get("namespace") or "all").lower()
    ns_map = {
        "all": None, "obf": {"obf"}, "mcp": {"mcp"},
        "inter": {"inter1", "inter2"}, "inter1": {"inter1"}, "inter2": {"inter2"},
        "feather": {"feather1", "feather2"}, "feather1": {"feather1"}, "feather2": {"feather2"},
    }
    if ns_name not in ns_map:
        raise ValueError("namespace 只能是 all/obf/mcp/inter1/inter2/feather1/feather2")
    kind = args.get("kind") or "all"
    if kind not in ("all", "class", "field", "method"):
        raise ValueError("kind 只能是 all/class/field/method")
    limit = int(args.get("limit") or 15)
    limit = max(1, min(50, limit))
    hits = search(ds.index, query, ns=ns_map[ns_name],
                  kind=None if kind == "all" else kind,
                  exact=bool(args.get("exact")), limit=limit)
    if not hits:
        return ("没有匹配：%s\n提示：支持部分匹配；<init> 默认不出现；可用 namespace 收窄到 feather1/feather2。" % query, {"hits": []})
    lines = ["%d 条命中（namespace=%s, kind=%s）" % (len(hits), ns_name, kind)]
    structured = []
    for idx, (score, k, ci, e, name_i) in enumerate(hits, 1):
        names = ds.classes[ci][0]
        if e is None:
            lines.append("%d. [class] %s" % (idx, names[1] or names[5] or names[3] or names[0]))
            lines.append("   obf=%s  mcp=%s  feather1=%s  feather2=%s" % (
                names[0], names[1] or "—", names[3] or "—", names[5] or "—"))
            structured.append({"kind": "class", "names": dict(zip(NS, names))})
        else:
            kind_label = "field" if k == 1 else "method"
            owner = names[1] or names[5] or names[0]
            main = e[name_i] or e[M_NAMED] or e[M_SRG] or e[M_F2] or "?"
            desc = (" " + ds.desc_to(e[M_DESC], 5)) if (k == 2 and e[M_DESC]) else ""
            lines.append("%d. [%s] %s.%s%s" % (idx, kind_label, owner, main, desc))
            lines.append("   obf=%s  mcp=%s  feather1=%s  feather2=%s" % (
                e[M_OBF] or "—", e[M_NAMED] or e[M_SRG] or "—", e[M_F1] or "—", e[M_F2] or "—"))
            structured.append({"kind": kind_label, "owner": dict(zip(NS, names)),
                               "names": dict(zip(NS, e[:7])), "desc": e[M_DESC]})
    if len(hits) >= limit:
        lines.append("（只显示前 %d 条，可用 limit 调大，最多 50）" % limit)
    return ("\n".join(lines), {"hits": structured})


def tool_class(srv, args):
    ds = srv.dataset(args.get("version"))
    name = (args.get("name") or "").strip()
    if not name:
        raise ValueError("name 不能为空")
    cands = ds.resolve_classes(name)
    if not cands:
        hits = search(ds.index, name, kind="class", limit=5)
        if not hits:
            raise ValueError("找不到类：%s" % name)
        ci = hits[0][2]
    else:
        ci = cands[0][1]
    desc_ns = NS_ALIAS.get((args.get("descriptor_namespace") or "feather2").lower(), 5)
    text = render_class(
        ds, ci,
        include_members=args.get("include_members", True) is not False,
        member_kind=(args.get("member_kind") or "all"),
        member_limit=max(1, min(300, int(args.get("member_limit") or 40))),
        desc_ns=desc_ns,
    )
    names, fields, methods = ds.classes[ci]
    return (text, {"names": dict(zip(NS, names)),
                   "fields": len(fields), "methods": len(methods)})


def tool_member(srv, args):
    ds = srv.dataset(args.get("version"))
    name = (args.get("name") or "").strip()
    if not name:
        raise ValueError("name 不能为空")
    owner = (args.get("owner") or "").strip()
    kind = args.get("kind") or "all"
    limit = max(1, min(50, int(args.get("limit") or 10)))
    owner_ids = set()
    if owner:
        for _s, ci in ds.resolve_classes(owner):
            owner_ids.add(ci)
    q = name.replace(".", "/").lower()
    found = []
    for ci, (names, fields, methods) in enumerate(ds.classes):
        if owner_ids and ci not in owner_ids:
            continue
        for kind_name, bucket in (("field", fields), ("method", methods)):
            if kind not in ("all", kind_name):
                continue
            for e in bucket:
                best = 0
                for i in range(7):
                    best = max(best, name_score(q, e[i], False))
                if best >= 92:
                    found.append((best, kind_name, ci, e))
    if not found:
        return ("没有精确匹配的成员：%s\n试试 mapping_search（支持部分匹配）。" % name, {"members": []})
    found.sort(key=lambda x: -x[0])
    desc_ns = NS_ALIAS.get((args.get("descriptor_namespace") or "feather2").lower(), 5)
    lines = ["%d 条成员命中" % len(found[:limit])]
    structured = []
    for score, kind_name, ci, e in found[:limit]:
        names = ds.classes[ci][0]
        lines.append("")
        lines.append(render_member(ds, e, kind_name, names, desc_ns))
        structured.append({"kind": kind_name, "owner": dict(zip(NS, names)),
                           "names": dict(zip(NS, e[:7])), "desc": e[M_DESC]})
    return ("\n".join(lines), {"members": structured})


def tool_convert(srv, args):
    ds = srv.dataset(args.get("version"))
    name = (args.get("name") or "").strip()
    if not name:
        raise ValueError("name 不能为空")
    src = (args.get("from") or "all").lower()
    dst = (args.get("to") or "feather2").lower()
    if dst not in NS_ALIAS:
        raise ValueError("to 只能是 obf/mcp/inter1/inter2/feather1/feather2")
    dst_i = NS_ALIAS[dst]
    src_i = NS_ALIAS.get(src)
    if src != "all" and src_i is None:
        raise ValueError("from 只能是 all/obf/mcp/inter1/inter2/feather1/feather2")
    q = name.replace(".", "/").lower()

    # 先按类解析
    cands = ds.resolve_classes(name, src_i)
    if cands:
        lines = []
        structured = []
        for score, ci in cands[:5]:
            names = ds.classes[ci][0]
            target = names[dst_i]
            lines.append("%s  ->  %s: %s" % (names[src_i] if src_i is not None else name, dst, target or "（该命名空间没有这个名字）"))
            for i in range(6):
                if i == dst_i:
                    continue
                lines.append("  %-13s %s" % (LABEL[i], names[i] or "—"))
            structured.append({"kind": "class", "names": dict(zip(NS, names)), "target": target})
        return ("\n".join(lines), {"matches": structured})

    # 再按成员解析
    owner = (args.get("owner") or "").strip()
    owner_ids = set()
    if owner:
        for _s, ci in ds.resolve_classes(owner):
            owner_ids.add(ci)
    hits = []
    for ci, (names, fields, methods) in enumerate(ds.classes):
        if owner_ids and ci not in owner_ids:
            continue
        for kind_name, bucket in (("field", fields), ("method", methods)):
            for e in bucket:
                matched = False
                for i in range(6):
                    if src_i is not None and i != src_i:
                        continue
                    if any(name_score(q, e[s], False) >= 92 for s in SLOTS_FOR_NS[i]):
                        matched = True
                        break
                if matched:
                    hits.append((kind_name, ci, e))
    if not hits:
        raise ValueError("找不到 %s；先用 mapping_search 确认名字拼写。" % name)
    lines = ["%d 条成员命中" % len(hits[:5])]
    structured = []
    for kind_name, ci, e in hits[:5]:
        names = ds.classes[ci][0]
        target = member_value(e, dst_i)
        src_shown = member_value(e, src_i) if src_i is not None else name
        lines.append("")
        lines.append("%s %s.%s  ->  %s: %s" % (
            kind_name, names[1] or names[5] or names[0], src_shown or "?",
            dst, target or "（该命名空间没有这个名字）"))
        lines.append(render_member(ds, e, kind_name, names, 5))
        structured.append({"kind": kind_name, "owner": dict(zip(NS, names)),
                           "names": dict(zip(NS, e[:7])), "target": target})
    return ("\n".join(lines), {"matches": structured})


def tool_descriptor(srv, args):
    ds = srv.dataset(args.get("version"))
    desc = (args.get("desc") or "").strip()
    if not desc:
        raise ValueError("desc 不能为空，例如 (Lbua;D)V")
    src = (args.get("from") or "obf").lower()
    dst = (args.get("to") or "feather2").lower()
    if src not in NS_ALIAS or dst not in NS_ALIAS:
        raise ValueError("from/to 只能是 obf/mcp/inter1/inter2/feather1/feather2")
    src_i, dst_i = NS_ALIAS[src], NS_ALIAS[dst]
    rev = ds.name_to_obf[src_i]
    fwd = ds.obf_to[dst_i]

    used = []

    def mapper(cls_name):
        obf = rev.get(cls_name, cls_name)
        out = fwd.get(obf, obf)
        used.append((cls_name, obf, out))
        return out

    out_desc = remap_desc(desc, mapper)
    lines = ["%s  ->  %s: %s" % (src, dst, out_desc)]
    if used:
        lines.append("涉及的类型：")
        for a, b, c in used:
            lines.append("  %s (%s)  ->  %s" % (a, b, c))
    return ("\n".join(lines), {"descriptor": out_desc,
                               "types": [{"from": a, "obf": b, "to": c} for a, b, c in used]})


def tool_stats(srv, args):
    versions = available_versions()
    if not versions:
        raise RuntimeError("没有可用索引，先运行 python query.py build 1.12.2")
    lines = ["可用版本：%s" % ", ".join(versions)]
    structured = {"versions": []}
    for v in versions:
        ds = srv.dataset(v)
        c = ds.index["counts"]
        lines.append("%s: %d 类 / %d 字段 / %d 方法（构建于 %s）" % (
            v, c["classes"], c["fields"], c["methods"], ds.index.get("built", "?")))
        structured["versions"].append({"version": v, "counts": c, "built": ds.index.get("built")})
    lines.append("")
    lines.append("命名空间：" + ", ".join(LABEL))
    lines.append("说明：" + NOTES)
    structured["notes"] = NOTES
    return ("\n".join(lines), structured)


TOOL_HANDLERS = {
    "mapping_search": tool_search,
    "mapping_class": tool_class,
    "mapping_member": tool_member,
    "mapping_convert": tool_convert,
    "mapping_descriptor": tool_descriptor,
    "mapping_stats": tool_stats,
}

VERSION_PROP = {
    "type": "string",
    "description": "MC 版本目录名，默认用最新可用索引",
}

TOOLS = [
    {
        "name": "mapping_search",
        "description": (
            "在 MCP / Feather gen1 / Feather gen2 / intermediary / 混淆名 六套命名空间里搜索类、字段、方法。"
            "返回每条命中的各命名空间名字。适合「这个类在另一套 mapping 里叫什么」。"
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "类名 / 方法名 / 字段名，支持部分匹配；a.b.C 会归一化成 a/b/C"},
                "namespace": {
                    "type": "string",
                    "enum": ["all", "obf", "mcp", "inter1", "inter2", "feather1", "feather2"],
                    "description": "只在某一套命名空间里匹配，默认 all",
                },
                "kind": {"type": "string", "enum": ["all", "class", "field", "method"], "description": "默认 all"},
                "exact": {"type": "boolean", "description": "只保留全名或简单名完全相等的"},
                "limit": {"type": "integer", "minimum": 1, "maximum": 50, "description": "默认 15"},
                "version": VERSION_PROP,
            },
            "required": ["query"],
        },
    },
    {
        "name": "mapping_class",
        "description": "看一个类的全部六套名字和成员表（字段/方法）。名字可以来自任意一套命名空间。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "类名，全名或简单名都行，例如 ClientPlayerEntity / net/minecraft/client/entity/AbstractClientPlayer"},
                "include_members": {"type": "boolean", "description": "是否列成员，默认 true"},
                "member_kind": {"type": "string", "enum": ["all", "field", "method"], "description": "只列字段或只列方法"},
                "member_limit": {"type": "integer", "minimum": 1, "maximum": 300, "description": "最多列多少条成员，默认 40"},
                "descriptor_namespace": {"type": "string", "enum": ["obf", "mcp", "inter1", "inter2", "feather1", "feather2"], "description": "描述符里的类名用哪套命名空间显示，默认 feather2"},
                "version": VERSION_PROP,
            },
            "required": ["name"],
        },
    },
    {
        "name": "mapping_member",
        "description": "查一个字段或方法在各套命名空间里的名字。成员名可能重名，可用 owner 限定所属类。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "字段名或方法名，例如 lerpSteps / openScreen / field_71184_b"},
                "owner": {"type": "string", "description": "所属类（任意命名空间），用于消歧"},
                "kind": {"type": "string", "enum": ["all", "field", "method"], "description": "默认 all"},
                "limit": {"type": "integer", "minimum": 1, "maximum": 50, "description": "默认 10"},
                "descriptor_namespace": {"type": "string", "enum": ["obf", "mcp", "inter1", "inter2", "feather1", "feather2"], "description": "默认 feather2"},
                "version": VERSION_PROP,
            },
            "required": ["name"],
        },
    },
    {
        "name": "mapping_convert",
        "description": "把名字从一套命名空间翻译到另一套，例如 feather2 的 ClientPlayerEntity -> mcp 的 AbstractClientPlayer。类与成员都支持。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "要翻译的类名或成员名"},
                "from": {"type": "string", "enum": ["all", "obf", "mcp", "inter1", "inter2", "feather1", "feather2"], "description": "源命名空间，默认 all（自动识别）"},
                "to": {"type": "string", "enum": ["obf", "mcp", "inter1", "inter2", "feather1", "feather2"], "description": "目标命名空间，默认 feather2"},
                "owner": {"type": "string", "description": "成员重名时用所属类消歧"},
                "version": VERSION_PROP,
            },
            "required": ["name"],
        },
    },
    {
        "name": "mapping_descriptor",
        "description": "把 JVM 描述符里的类名从一套命名空间重写到另一套，例如 (Lbua;D)V -> (Lnet/minecraft/.../AbstractClientPlayer;D)V。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "desc": {"type": "string", "description": "JVM 描述符，例如 (Lbua;D)V"},
                "from": {"type": "string", "enum": ["obf", "mcp", "inter1", "inter2", "feather1", "feather2"], "description": "描述符当前的命名空间，默认 obf"},
                "to": {"type": "string", "enum": ["obf", "mcp", "inter1", "inter2", "feather1", "feather2"], "description": "目标命名空间，默认 feather2"},
                "version": VERSION_PROP,
            },
            "required": ["desc"],
        },
    },
    {
        "name": "mapping_stats",
        "description": "列出可用的 MC 版本索引、各类数量，以及这套 mapping 的已知限制。",
        "inputSchema": {"type": "object", "properties": {}},
    },
]


# --------------------------------------------------------------------------
# 服务器
# --------------------------------------------------------------------------

class McpServer:
    def __init__(self, default_version=None):
        self.srv = Server(default_version)

    def initialize(self, params):
        requested = params.get("protocolVersion")
        version = requested if requested in PROTOCOLS else PROTOCOLS[0]
        return {
            "protocolVersion": version,
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
            "instructions": (
                "Minecraft 1.12.2 mapping 对照查询（MCP / Feather gen1 / Feather gen2 / intermediary / 混淆名）。"
                "先 mapping_search 找实体，再 mapping_class / mapping_member 看细节，"
                "mapping_convert 做跨命名空间翻译。"
            ),
        }

    def call_tool(self, params):
        name = params.get("name")
        arguments = params.get("arguments") or {}
        handler = TOOL_HANDLERS.get(name)
        if handler is None:
            raise RpcError(-32602, "Unknown tool: %s" % name)
        try:
            text, structured = handler(self.srv, arguments)
            return {
                "content": [{"type": "text", "text": text}],
                "structuredContent": structured,
                "isError": False,
            }
        except Exception as exc:  # 工具错误要回给模型，而不是让进程崩掉
            traceback.print_exc(file=sys.stderr)
            return {
                "content": [{"type": "text", "text": "错误：%s" % exc}],
                "isError": True,
            }

    def handle(self, msg):
        if not isinstance(msg, dict):
            return err(None, -32600, "Invalid Request")
        if "id" not in msg:
            return None  # notification：不需要回复
        mid = msg["id"]
        method = msg.get("method")
        params = msg.get("params") or {}
        try:
            if method == "initialize":
                return ok(mid, self.initialize(params))
            if method == "ping":
                return ok(mid, {})
            if method == "tools/list":
                return ok(mid, {"tools": TOOLS})
            if method == "tools/call":
                return ok(mid, self.call_tool(params))
            if method in ("resources/list",):
                return ok(mid, {"resources": []})
            if method in ("resources/templates/list",):
                return ok(mid, {"resourceTemplates": []})
            if method in ("prompts/list",):
                return ok(mid, {"prompts": []})
            return err(mid, -32601, "Method not found: %s" % method)
        except RpcError as exc:
            return err(mid, exc.code, exc.message)
        except Exception as exc:
            traceback.print_exc(file=sys.stderr)
            return err(mid, -32603, "Internal error: %s" % exc)


def print_config(args):
    script = os.path.abspath(__file__)
    cfg = {
        "mcpServers": {
            "mapping-lookup": {
                "command": sys.executable or "python",
                "args": [script],
            }
        }
    }
    print(json.dumps(cfg, ensure_ascii=False, indent=2))
    print("")
    print("把这个 JSON 合并进客户端的 MCP 配置即可（Claude Desktop 是 claude_desktop_config.json，")
    print("Cline / Continue 等是各自的 mcp.json）。Windows 上建议把 command 写成 python 的绝对路径。")
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(prog="mcp_server.py", description="Mapping 对照查询的 MCP 服务器")
    p.add_argument("--version", dest="default_version", help="默认 MC 版本，默认用最新索引")
    p.add_argument("--config", action="store_true", help="打印客户端配置片段后退出")
    args = p.parse_args(argv)
    if args.config:
        return print_config(args)

    server = McpServer(args.default_version)
    stdin = sys.stdin.buffer
    stdout = sys.stdout.buffer
    sys.stderr.write("[mapping-lookup] MCP server started (stdio)\n")
    sys.stderr.flush()
    while True:
        line = stdin.readline()
        if not line:
            break
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line.decode("utf-8"))
        except Exception:
            write_msg(stdout, err(None, -32700, "Parse error"))
            continue
        resp = server.handle(msg)
        if resp is not None:
            write_msg(stdout, resp)
    return 0


if __name__ == "__main__":
    sys.exit(main())
