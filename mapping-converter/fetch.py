#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
下载 Minecraft 1.12.2 的 calamus-intermediary / feather / MCP 映射文件，
并把需要的内部文件解包到 extracted/ 目录。

用法:
    python fetch.py                # 默认 1.12.2
    python fetch.py 1.12.2 1.8.9   # 指定版本

依赖: 仅标准库 (urllib / zipfile / json / re)
"""

import io
import json
import os
import re
import sys
import urllib.request
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))

ORNITHE = "https://maven.ornithemc.net/releases/net/ornithemc"
FORGE = "https://maven.minecraftforge.net/de/oceanlabs/mcp"

DEFAULT_VERSIONS = ["1.12.2"]

# 固定某些 build（不跟随 maven 最新），格式: {mc: {artifact: version}}
PINNED_BUILDS = {
    "1.12.2": {"feather": "1.12.2+build.28"},
}


def http_get(url, timeout=180):
    req = urllib.request.Request(url, headers={"User-Agent": "mapping-converter/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def fetch_to(url, path):
    if os.path.exists(path) and os.path.getsize(path) > 0:
        print("  [skip] %s" % os.path.basename(path))
        return path
    print("  [get ] %s" % url)
    data = http_get(url)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(data)
    print("         -> %s (%d bytes)" % (os.path.basename(path), len(data)))
    return path


def maven_versions(group_path):
    """读取 maven-metadata.xml 里的 version 列表。"""
    url = "%s/%s/maven-metadata.xml" % (ORNITHE, group_path)
    xml = http_get(url).decode("utf-8", "replace")
    return re.findall(r"<version>([^<]+)</version>", xml)


def latest_build(versions, mc, prefix=""):
    """从 1.12.2+build.N 这类版本号里取 N 最大的那个。"""
    best = None
    best_n = -1
    for v in versions:
        if not v.startswith(mc + prefix + "+build."):
            continue
        try:
            n = int(v.rsplit("build.", 1)[1])
        except ValueError:
            continue
        if n > best_n:
            best_n, best = n, v
    return best


def mcp_keys(mc):
    """MCP 的 artifact 版本号不一定等于 MC 版本，例如 1.12.2 -> 1.12。"""
    keys = [mc]
    parts = mc.split(".")
    if len(parts) >= 2:
        short = ".".join(parts[:2])
        if short not in keys:
            keys.append(short)
    return keys


def mcp_stable_for(mc):
    """优先用 mcp_stable：返回 (key, build) 或 None。"""
    try:
        xml = http_get(FORGE + "/mcp_stable/maven-metadata.xml").decode("utf-8", "replace")
    except Exception:
        return None
    versions = re.findall(r"<version>([^<]+)</version>", xml)
    for key in mcp_keys(mc):
        cands = []
        for v in versions:
            if not v.endswith("-" + key):
                continue
            build = v[: -(len(key) + 1)]
            try:
                cands.append((int(build), build))
            except ValueError:
                pass
        if cands:
            return key, max(cands)[1]
    return None


def mcp_snapshot_for(mc):
    """否则退回到 mcp_snapshot：返回 (key, snapshot) 或 None。"""
    data = json.loads(http_get(FORGE + "/versions.json").decode("utf-8"))
    for key in mcp_keys(mc):
        entry = data.get(key)
        if not entry:
            continue
        snaps = entry.get("snapshot") or []
        if not snaps:
            continue
        # snapshot 是 20180814 这样的整数
        return key, max(int(s) for s in snaps)
    return None


def unzip_member(jar, member, out_path):
    with zipfile.ZipFile(jar) as z:
        names = [n for n in z.namelist() if n.endswith(member)]
        if not names:
            print("  [warn] %s 中没有 %s" % (os.path.basename(jar), member))
            return None
        data = z.read(names[0])
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "wb") as f:
        f.write(data)
    print("  [ext ] %s -> %s (%d bytes)" % (names[0], os.path.relpath(out_path, HERE), len(data)))
    return out_path


def main(argv):
    versions = argv[1:] or DEFAULT_VERSIONS

    for mc in versions:
        print("=" * 70)
        print("Minecraft %s" % mc)
        print("=" * 70)

        raw = os.path.join(HERE, "raw", mc)
        ext = os.path.join(HERE, "extracted", mc)

        # ---------- calamus intermediary (gen1 / gen2) ----------
        cal1_url = "%s/calamus-intermediary/%s/calamus-intermediary-%s-v2.jar" % (ORNITHE, mc, mc)
        cal1 = fetch_to(cal1_url, os.path.join(raw, "calamus-intermediary-gen1-%s-v2.jar" % mc))

        cal2_url = "%s/calamus-intermediary-gen2/%s/calamus-intermediary-gen2-%s-v2.jar" % (ORNITHE, mc, mc)
        cal2 = fetch_to(cal2_url, os.path.join(raw, "calamus-intermediary-gen2-%s-v2.jar" % mc))

        # ---------- feather (gen1 / gen2) ----------
        f1_ver = PINNED_BUILDS.get(mc, {}).get("feather") or latest_build(maven_versions("feather"), mc)
        f1 = None
        if f1_ver:
            f1_url = "%s/feather/%s/feather-%s-v2.jar" % (ORNITHE, f1_ver, f1_ver)
            f1 = fetch_to(f1_url, os.path.join(raw, "feather-gen1-%s-v2.jar" % f1_ver))

        f2_ver = PINNED_BUILDS.get(mc, {}).get("feather-gen2") or latest_build(maven_versions("feather-gen2"), mc)
        f2 = None
        if f2_ver:
            f2_url = "%s/feather-gen2/%s/feather-gen2-%s-v2.jar" % (ORNITHE, f2_ver, f2_ver)
            f2 = fetch_to(f2_url, os.path.join(raw, "feather-gen2-%s-v2.jar" % f2_ver))

        # ---------- MCP: joined.srg ----------
        srg_url = "%s/mcp/%s/mcp-%s-srg.zip" % (FORGE, mc, mc)
        srg = fetch_to(srg_url, os.path.join(raw, "mcp-%s-srg.zip" % mc))

        # ---------- MCP: names (fields/methods/params.csv) ----------
        # 优先 stable 通道，其次 snapshot
        mcp_zip = None
        stable = mcp_stable_for(mc)
        if stable:
            key, build = stable
            ver = "%s-%s" % (build, key)
            mcp_url = "%s/mcp_stable/%s/mcp_stable-%s.zip" % (FORGE, ver, ver)
            mcp_zip = fetch_to(mcp_url, os.path.join(raw, "mcp_stable-%s.zip" % ver))
        else:
            snap = mcp_snapshot_for(mc)
            if snap:
                key, snapshot = snap
                ver = "%s-%s" % (snapshot, key)
                mcp_url = "%s/mcp_snapshot/%s/mcp_snapshot-%s.zip" % (FORGE, ver, ver)
                mcp_zip = fetch_to(mcp_url, os.path.join(raw, "mcp_snapshot-%s.zip" % ver))
            else:
                print("  [warn] no MCP name csv found for %s" % mc)

        # ---------- 解包 ----------
        print("-" * 70)
        print("extract:")
        if cal1:
            unzip_member(cal1, "mappings.tiny", os.path.join(ext, "calamus-intermediary-gen1.tiny"))
        if cal2:
            unzip_member(cal2, "mappings.tiny", os.path.join(ext, "calamus-intermediary-gen2.tiny"))
        if f1:
            unzip_member(f1, "mappings.tiny", os.path.join(ext, "feather-gen1.tiny"))
        if f2:
            unzip_member(f2, "mappings.tiny", os.path.join(ext, "feather-gen2.tiny"))
        if srg:
            unzip_member(srg, "joined.srg", os.path.join(ext, "joined.srg"))
        if mcp_zip:
            for csv in ("fields.csv", "methods.csv", "params.csv"):
                unzip_member(mcp_zip, csv, os.path.join(ext, csv))

        # ---------- 摘要 ----------
        print("-" * 70)
        print("summary:")
        for name in ("calamus-intermediary-gen1.tiny", "calamus-intermediary-gen2.tiny",
                     "feather-gen1.tiny", "feather-gen2.tiny"):
            p = os.path.join(ext, name)
            if os.path.exists(p):
                with open(p, "r", encoding="utf-8", errors="replace") as f:
                    head = f.readline().rstrip("\n")
                print("  %-34s %s" % (name, head))
        for name in ("joined.srg", "fields.csv", "methods.csv", "params.csv"):
            p = os.path.join(ext, name)
            if os.path.exists(p):
                with open(p, "r", encoding="utf-8", errors="replace") as f:
                    lines = f.read().splitlines()
                print("  %-34s %d 行, 首行: %s" % (name, len(lines), lines[0][:60] if lines else ""))

        print()


if __name__ == "__main__":
    main(sys.argv)
