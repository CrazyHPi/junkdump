# Mapping 互转实验：MCP ↔ calamus-intermediary ↔ Feather

以 **Minecraft 1.12.2** 为样本，把 Ornithe 生态里三套 mapping 的真实文件拉下来，
完整走一遍「MCP 名字 / intermediary 名 / Feather 名字」之间的互相转换，
并给出实测命中率和踩坑记录。

对应实现：`ploceus`（Gradle 插件，MCP 的转换逻辑在 `mcp/` 包里）、`linkie-core`（运行时转换）。

---

## 1. 目录结构

```
mapping-converter/
├── README.md                 ← 本文档
├── fetch.py                  ← 下载 + 解包（可换版本号复用）
├── convert.py                ← 实际执行转换，产出 out/
├── query.py                  ← 查询器：建索引 + 命令行查询（见 §11）
├── viewer.html               ← 查询器的离线网页（读 out/<mc>/index.js）
├── mcp_server.py             ← MCP 服务器，把查询暴露给 LLM（见 §12）
├── raw/1.12.2/               ← 原始 jar/zip
│   ├── calamus-intermediary-gen1-1.12.2-v2.jar
│   ├── calamus-intermediary-gen2-1.12.2-v2.jar
│   ├── feather-gen1-1.12.2+build.28-v2.jar
│   ├── feather-gen2-1.12.2+build.2-v2.jar
│   ├── mcp-1.12.2-srg.zip
│   └── mcp_stable-39-1.12.zip
├── extracted/1.12.2/         ← 从 jar/zip 里抽出来的实际 mapping 文本
│   ├── calamus-intermediary-gen1.tiny
│   ├── calamus-intermediary-gen2.tiny
│   ├── feather-gen1.tiny
│   ├── feather-gen2.tiny
│   ├── joined.srg
│   └── fields.csv / methods.csv / params.csv
└── out/1.12.2/               ← 转换产物
    ├── mcp.official-srg-named.tiny         MCP 原始三列（不经 calamus）
    ├── mcp.intermediary-named.tiny         MCP 经 calamus 转换后（= ploceus 的产出）
    ├── merged.intermediary-mcp-feather.tiny 三套名字对齐的合并视图
    ├── mcp-to-feather.tiny                 MCP 名 → Feather 名
    ├── feather-to-mcp.tiny                 Feather 名 → MCP 名
    ├── unresolved.txt                      无法解析的 MCP 成员
    └── stats.json                          各阶段命中率
```

---

## 2. 下载了什么（真实坐标）

| 文件 | Maven 坐标 | 大小 | 命名空间头 |
|---|---|---|---|
| calamus gen1 | `net.ornithemc:calamus-intermediary:1.12.2:v2` | 239 KB | `official intermediary` |
| calamus gen2 | `net.ornithemc:calamus-intermediary-gen2:1.12.2:v2` | 247 KB | `official intermediary` |
| feather gen1 | `net.ornithemc:feather:1.12.2+build.28:v2` | 438 KB | `intermediary named` |
| feather gen2 | `net.ornithemc:feather-gen2:1.12.2+build.2:v2` | 459 KB | `intermediary named` |
| MCP SRG | `de.oceanlabs.mcp:mcp:1.12.2:srg@zip` | 654 KB | 纯文本 `joined.srg` |
| MCP 名字 | `de.oceanlabs.mcp:mcp_stable:39-1.12@zip` | 379 KB | 3 个 CSV |

> **坑 1：1.12.2 的 MCP artifact 版本号是 `1.12`，不是 `1.12.2`。**
> `mcp_stable:39-1.12.2` 和 `mcp_snapshot:20180814-1.12.2` 都是 404。
> 这也解释了 ploceus 为什么提供 `mcpMappings(channel, mc, build)` 这个可以显式指定 mc 的重载：
> 1.12.2 项目要写 `mcpMappings("stable", "1.12", "39")`。

> **坑 2：calamus gen1 对 1.12.2 也不带 `-client`/`-server` 后缀。**
> 只有 b1.0 ~ 1.3 这一段才用 `intermediary client_official server_official` 格式
> （见 `CalamusGen1Provider` 注释）。1.3+ 统一是单一 `official` 列，
> 所以 `calamus-intermediary:1.12.2:v2` 存在，而 `calamus-intermediary:1.12.2-client` 是 404。

---

## 3. 格式速查

### 3.1 Tiny v2（calamus / feather）

```
tiny	2	0	official	intermediary
c	a	net/minecraft/unmapped/C_49122968
	f	Z	A	f_55433676
	m	(I)La;	a	m_56077948
```

- `c` 行：类，后面按 header 顺序跟各命名空间的类名
- `f` / `m` 行：字段 / 方法，格式是 `<desc> <各命名空间的名字>`
- **`desc` 永远用「第一列（源）命名空间」的类名**。calamus 的 desc 是 obf 名（`La;`），
  feather 的 desc 是 intermediary 名（`Lnet/minecraft/unmapped/C_xxx;`）。这条规则是后面所有
  描述符重写的依据。
- 构造函数 `<init>` 不在 tiny 里（tiny 约定不能重命名构造器），所以 calamus 没有构造函数映射。

### 3.2 SRG（`joined.srg`，36 083 行）

```
PK: net/minecraft/client net/minecraft/client
CL: v net/minecraft/advancements/critereon/BredAnimalsTrigger
FD: a/A net/minecraft/util/text/TextFormatting/field_96303_A
MD: a/a (I)La; net/minecraft/util/text/TextFormatting/func_175744_a (I)Lnet/minecraft/util/text/TextFormatting;
```

| 标签 | 含义 | 注意 |
|---|---|---|
| `PK:` | 包 | 忽略 |
| `CL:` | `obf → srg 类名` | srg 类名本身就是可读名（MCP 不改类名） |
| `FD:` | `obf 所有者/obf 名 → srg 所有者/srg 名` | **没有描述符** |
| `MD:` | `obf 所有者/obf 名 obf_desc → srg 所有者/srg 名 srg_desc` | desc 是 **obf 类名**，不是 srg 类名 |

### 3.3 MCP CSV

```
fields.csv    searge,name,side,desc        字段 srg 名 -> 可读名
methods.csv   searge,name,side,desc        方法 srg 名 -> 可读名
params.csv    param,name,side              参数，param 形如 p_175744_a_0_
```

`params.csv` 的 `p_<methodId>_<index>_` 需要两步反查才能定位到方法（详见 4.5）。

---

## 4. 转换 A：MCP → intermediary → named（ploceus 的路径）

对应 `ploceus/src/main/java/net/ornithemc/ploceus/mcp/io/McpReader.java`。
`convert.py` 里的 `build_mcp_through_intermediary()` 是同一套逻辑的精简实现。

### 4.1 建骨架：official → srg / named

读 `joined.srg`，在内存里建一棵 `official → [srg, named]` 的树：

```python
mappings.visitNamespaces(OFFICIAL, [SRG, NAMED])   # Java 版
```

- 类：srg 名 == named 名（MCP 不重命名类）
- 成员：先只写 srg 列；如果 srg 名还是 `field_xxx` / `func_xxx`（即 CSV 里没有），
  就认为它「未被命名」，named 列留空

### 4.2 读 calamus，把 intermediary 列接上

这一步是**整个转换的关键**：

```java
MappingReader.read(files.readIntermediary(), mappings);   // official -> intermediary
```

内存树此时是 `official → [intermediary, srg, named]`。
`MemoryMappingTree.visitNamespaces` 是**合并**语义（不是覆盖），所以后续
`visitNamespaces(official, [srg, named])` 会把两列并进去而不是把 intermediary 冲掉。

### 4.3 回填字段 / 方法名（CSV）

CSV 里没有 owner，所以 4.1 阶段必须缓存 `fieldClasses[srg名] = {类...}`、
`methodClasses[srg名] = {类...}`，然后逐行回填：

```java
String[] args = line.split("[,]", 4);
String srg = args[0], named = args[1], javadoc = args[3];
for (String cls : fieldClasses.get(srg)) {
    mappings.visitClass(cls);
    mappings.visitField(srg, null);            // 字段没有 desc，传 null
    mappings.visitDstName(FIELD, 0, named);
    mappings.visitComment(FIELD, javadoc);     // 第 4 列当 javadoc
}
```

> 一个 srg 名可能对应多个类（不同类里的同名 obf 字段），所以缓存是 `Collection`，
> 回填时要遍历全部 owner。

### 4.4 参数名

```java
String[] parts = srg.split("_");        // p_175744_a_0_
String methodId = parts[1];             // 175744
int idx = Integer.parseInt(parts[2]);   // 0
if (methodId.startsWith("i")) continue; // synthetic，跳过
String srgMethod = methods.get(methodId);          // 175744 -> func_175744_a
mappings.visitMethodArg(-1, idx, null);            // -1 = 按局部变量槽位定位
mappings.visitDstName(METHOD_ARG, 0, named);
```

### 4.5 切源命名空间

最后一步把源列从 `official` 换成 `intermediary`，并只保留 `named` 作为目标列：

```java
read(files).accept(new MappingSourceNsSwitch(
    new MappingDstNsReorder(visitor, NAMED),
    INTERMEDIARY, true));
```

产物就是 `mcp.intermediary-named.tiny`：

```
tiny	2	0	intermediary	named
c	net/minecraft/unmapped/C_49122968	net/minecraft/util/text/TextFormatting
	f	Z	f_55433676	fancyStyling
	f	Ljava/lang/String;	f_45885641	controlString
	f	I	f_25101100	colorIndex
	m	(I)Lnet/minecraft/unmapped/C_49122968;	m_56077948	fromColorIndex
```

### 4.6 实测命中率（1.12.2，gen2）

| 阶段 | 数量 | 说明 |
|---|---|---|
| 类 official → intermediary | **3344 / 3344** | 100% |
| 字段（按名字，无 desc） | **11915 / 11915** | 100% |
| 方法 精确（名字+desc） | **11143 / 20817** | 53.5% |
| 方法 未解析 | **9674** | 见 §7 |

---

## 5. 转换 B：Feather（直通，不转换）

feather 的文件本身就是 `intermediary named`，Loom 拿到的就是现成的
「intermediary → named」层，**不需要 calamus 参与**：

```java
builder.mappings(featherMappingsSpec(build), spec -> {
    if (intermediaryGeneration.get() > 1) spec.containsUnpick();
});
```

它和 calamus 的关系只是「上游用同一代 calamus 构建，所以 intermediary 名一致」，
而不是「运行时用 calamus 转换」。

---

## 6. 转换 C：MCP ↔ Feather（借 intermediary 对表）

因为两边都能落到 intermediary，互转就是一次**三元组对齐**：

```
mcp 名  →  (official, member, desc)  →  calamus  →  (intermediary, member, desc)  →  feather 名
```

`convert.py` 里：

1. 用 `class_map[obf]` 得到类的 intermediary 名
2. 用 `calamus.dst_method(obf, name, desc)` 得到成员的 intermediary 名
3. 把 desc 里的类名用 `class_map` 重写（`remap_desc`），因为跨命名空间后 desc 必须换名
4. 用 `(intermediary 类, intermediary 成员名, intermediary desc)` 去 feather 里查

产出 `merged.intermediary-mcp-feather.tiny`：

```
tiny	2	0	intermediary	mcp	feather
c	net/minecraft/unmapped/C_49122968	net/minecraft/util/text/TextFormatting	net/minecraft/text/Formatting
	f	Z	f_55433676	fancyStyling	modifier
	f	Ljava/lang/String;	f_45885641	controlString	key
	m	(I)Lnet/minecraft/unmapped/C_49122968;	m_56077948	fromColorIndex	byId
	m	(Ljava/lang/String;)Ljava/lang/String;	m_43649046	getTextWithoutFormattingCodes	strip
	m	()Z	m_87640893	isFancyStyling	isModifier
```

再由它派生两个方向的「重命名表」：

- `mcp-to-feather.tiny`（`tiny 2 0 mcp feather`）：给 MCP 项目换到 Feather 名
- `feather-to-mcp.tiny`（`tiny 2 0 feather mcp`）：反向

实测可对齐：**3344 类 / 11129 字段 / 10813 方法**。

---

## 7. 坑与限制（实测）

### 7.1 方法只有 ~53.5% 能 join 上

`joined.srg` 有 20 817 个方法，calamus gen2 只有 11 145 个，精确匹配上 11 143 个。
剩下 9 674 个对不上，抽查原因有四类：

**(a) 两套「合并 jar」对双端类取了不同的一侧。**
例：`BredAnimalsTrigger`

```
SRG:      MD: v/a ()Lnf; ...        MD: v/a (Lnp;)V ...     (np = PlayerAdvancements)
calamus:  m   ()Lnf;      b  m_53715249                    ← 同签名，obf 名是 b 不是 a
          m   (Loq;Lzv;Lzv;Lvd;)V a  m_01443877            ← SRG 里完全没有
```

同一个类，MCP 的 joined 和 Ornithe 的 merge 保留了不同的成员名/成员集合。
凡是「client 和 server 都存在但成员不同」的类，都可能出现这种错位。

**(b) bridge 方法。** 匿名内部类的桥接方法在 gen2 里被丢掉，原名被回填给真实方法：

```
gen1:  m ()Ljava/lang/String; a    m_6342544
       m ()Ljava/lang/Object; call call        ← bridge，保留
gen2:  m ()Ljava/lang/String; a    call        ← bridge 被删，用它的名字命名真实方法
```

**(c) 未被混淆的名字。** `toString` / `values` / `call` 这类本来就不混淆的方法，
tiny 里通常不出现（没有重命名就不需要记录）。

**(d) 千万不要用「仅名字」兜底。** 如果 desc 对不上就退化成只比名字，会把同名但不同
签名的方法错配。实测反例：

```
SRG  v/a()Lnf;                 -> func_192163_a   （无参，返回 ResourceLocation）
CAL  v/a(Loq;Lzv;Lzv;Lvd;)V                      （4 参，返回 void）
```

两者 obf 名都是 `a`，但完全是两个方法。`convert.py` 只做 `(owner, name, desc)` 精确匹配，
ploceus/mappingio 的 `visitMethod(src, desc)` 同理，这也是那 9 674 条只能标记为未解析的原因。

### 7.2 字段只能按名字 join

`FD:` 行没有描述符，所以字段只能 `(owner, name)` 匹配。
ploceus 里对应 `mappings.visitField(src, null)`。好在 1.12.2 实测 11 915 个字段全部命中。

### 7.3 gen1 和 gen2 的 intermediary 名不能混用

| | gen1 | gen2 |
|---|---|---|
| official `cca` | `C_1175303` | `C_64080336` |
| 方法总数 | 12 298 | 11 145 |

官方名一样，intermediary 名不同。所以 feather-gen1 只能配 calamus-gen1，
feather-gen2 只能配 calamus-gen2。ploceus 用同一个 `intermediaryGeneration` 属性
同时决定两者的坐标，就是为了防止混搭。

### 7.4 描述符的命名空间

tiny 的 desc 用「第一列」的类名。所以：

- 从 MCP 转出去：`(La;)V` 里的 `a` 要换成 `Lnet/minecraft/unmapped/C_xxx;`
- 从 intermediary 转回 MCP：要换成 `Lnet/minecraft/util/text/TextFormatting;`

`convert.py` 的 `remap_desc()` 和 `ploceus` 的 `MappingSourceNsSwitch` 都在处理这件事。

### 7.5 无法「凭空反推」

- Feather 里没有的成员，转换不出 MCP 名（反之亦然）
- 一个 intermediary 类可能对应多个 official 名（client/server 分裂），反向要选边
- 所以「互转」实际是「在已知交集上做重命名表」，不是无损双射

---

## 8. 复现

```bash
cd mapping-converter
python fetch.py 1.12.2     # 下载 + 解包（已下过会跳过）
python convert.py 1.12.2   # 转换，产出 out/1.12.2/
```

换版本只需要 `python fetch.py 1.8.9 && python convert.py 1.8.9`，
但要注意该版本的 MCP artifact 版本号（见坑 1）和 calamus/feather 是否发布了对应 build。

`fetch.py` 的逻辑：
1. 从 `maven.ornithemc.net` 拉 calamus gen1/gen2、feather gen1/gen2（feather 默认取 build 号最大的，可用 `PINNED_BUILDS` 固定某个 build）
2. 从 `maven.minecraftforge.net` 拉 `mcp:<mc>:srg` 和 `mcp_stable` / `mcp_snapshot`
3. 从每个 jar/zip 里抽出 `mappings/mappings.tiny` / `joined.srg` / `*.csv`

---

## 9. 与 ploceus / linkie-core 的对照

| 步骤 | ploceus（Java / Loom） | linkie-core（Kotlin） | 本文脚本 |
|---|---|---|---|
| 读 calamus | `McpFiles.readIntermediary()` | `loadIntermediaryFromTinyInputStream` | `parse_tiny` |
| 读 SRG | `McpReader.readSrg` | `parser/srg` + `MappingsBuilderVisitor` | `load_mcp` |
| 回填 CSV | `readFields` / `readMethods` / `readParams` | `loadMCPFromURLZip` 里的三个 CSV 方法 | `load_mcp` |
| 切命名空间 | `MappingSourceNsSwitch` | `rewireIntermediaryFrom`（靠 obf 名搬运） | `build_mcp_through_intermediary` |
| 描述符重写 | mappingio 内部 | `remapDescriptor` | `remap_desc` |
| 输出 | Loom 的 layered mapping tree | `TinyExporter` | `write_tiny_mcp` |

两者的共同点：**都把 official（obf）名当作唯一稳定键**，
并且都必须在类级别先对齐、再对齐成员。

---

## 10. 快速验证命令

```bash
# 看某个类的三套名字
grep -A20 '^c\tnet/minecraft/unmapped/C_49122968' out/1.12.2/merged.intermediary-mcp-feather.tiny

# 看 MCP 名到 Feather 名的差异
grep -A12 '^c\tnet/minecraft/util/text/TextFormatting' out/1.12.2/mcp-to-feather.tiny

# 统计
cat out/1.12.2/stats.json
```

---

## 11. 查询器：`query.py` + `viewer.html`

`convert.py` 负责「批量转换」，查询器负责「随手查」：输入任意一套命名空间里的
**类名 / 方法名 / 字段名**，立刻看到同一实体在其余各套 mapping 里叫什么。

```bash
python query.py build 1.12.2     # 生成 out/1.12.2/index.js（约 3.9 MB）
python query.py ClientPlayerEntity
python query.py verify 1.12.2    # 与 convert.py 的 merged 产物逐行比对
python query.py --open           # 生成索引并用浏览器打开 viewer.html
```

### 11.1 查询的七列

| 列 | 来源 | 说明 |
|---|---|---|
| obf | `joined.srg` 的 `CL:` / calamus | 混淆名，唯一的稳定键 |
| mcp | `joined.srg` + `fields.csv` / `methods.csv` | 类名用 srg 名，成员名优先 CSV 里的可读名 |
| inter gen1 | `calamus-intermediary-gen1` |  |
| feather gen1 | `feather-gen1` |  |
| inter gen2 | `calamus-intermediary-gen2` |  |
| feather gen2 | `feather-gen2` |  |

### 11.2 对齐规则（与 `convert.py` 一致）

1. 类按 official 名对齐（1.12.2 实测 3344 / 3344 全部命中）
2. 字段按 `(owner, obf 名)`；SRG 的 `FD:` 行没有描述符，描述符取 calamus
3. 方法按 `(owner, obf 名, obf 描述符)` **精确**匹配，不做「仅名字」兜底（§7.1d 的反例）
4. **描述符统一归一化到 official 空间**再当 key：feather 的 desc 是 intermediary 类名，
   必须先重写成 obf 名，否则 `(La;)V` 与 `(Lnet/minecraft/unmapped/C_xxx;)V` 永远对不上
   （实现里踩过一次这个坑，症状是 5456 条方法全部「未对齐」）
5. 两侧独有的成员都保留：MCP 有而 feather 没有的、feather 有而 MCP 没有的（如 `<init>`），
   缺失列显示 `—`

### 11.3 命令行

```bash
python query.py <关键词> [选项]

  --ns obf|mcp|inter1|inter2|feather1|feather2   限定某一列，可重复
  --kind class|field|method                       只看类 / 字段 / 方法
  --exact                                         只保留全名或简单名完全相等的
  --limit N                                       默认 20
  --ctors                                         显示 <init>（默认隐藏）
  --fuzzy                                         子序列模糊匹配（默认关，较慢）
  --json                                          机器可读输出
```

```
$ python query.py ClientPlayerEntity
[类] net/minecraft/client/entity/AbstractClientPlayer
  obf            bua
  mcp            net/minecraft/client/entity/AbstractClientPlayer
  inter gen1     net/minecraft/unmapped/C_7106153
  feather gen1   net/minecraft/client/entity/living/player/ClientPlayerEntity
  inter gen2     net/minecraft/unmapped/C_23527099
  feather gen2   net/minecraft/client/entity/living/player/ClientPlayerEntity
  成员           4 字段 / 13 方法
```

`verify` 会把 `out/<mc>/merged.intermediary-mcp-feather.tiny` 的每一行（25286 行）拿去索引里找，
用于确认查询器和 `convert.py` 看到的是同一套对应关系。

### 11.4 网页

`viewer.html` 单文件、离线、无第三方依赖：

```bash
python query.py build 1.12.2 --open
# 或者直接双击 viewer.html（默认 1.12.2；?v=1.12.3 换版本；&q=xxx 预填查询）
```

- **为什么用 `<script src="out/<v>/index.js">` 而不是 `fetch`**：`file://` 下 fetch/XHR 会被 CORS 拦，
  script 标签不受影响。索引写成 `window.__MAP_JSON__ = \`...\``，页面 `JSON.parse` 一次。
- 左侧结果、右侧详情：类卡片给出六套名字（可复制、可点击互跳），成员表按
  MCP / Feather gen1 / Feather gen2 / 混淆名 / 描述符 五列列出，描述符里的类型名可以点。
- 快捷键：`/` 聚焦、`↑↓` 选择、`Enter` 展开、`Esc` 清空。

**托管到服务器**：页面只有 `out/<版本>/index.js` 这一个外部引用（CSS/JS 全内联，无字体无 CDN），
所以静态托管只需要两个文件：

```bash
python query.py export 1.12.2 -o dist
```

```
dist/
├── index.html            ← viewer.html 的副本
└── out/1.12.2/index.js   ← 3.92 MB（gzip 后 0.83 MB）
```

- **运行时不需要 Python / Node / 数据库**，纯静态
- 服务器必须把 `.js` 当 JS 返回（`application/javascript` / `text/javascript`）；
  若开了 `X-Content-Type-Options: nosniff` 又返回 `text/plain`，浏览器会拒绝执行
- 建议开 gzip/brotli：4 MB → 0.83 MB
- `index.js` 重建后内容会变，缓存头建议 `no-cache`（或按版本目录做长缓存）
- 多版本共存 = 多个 `out/<版本>/index.js`，页面用 `?v=` 切换
- 放到子路径（如 `https://x.com/mapping/`）也不用改，路径是相对 HTML 的

### 11.5 实测性能（1.12.2 全量，Node 22 / V8）

| 项 | 数值 |
|---|---|
| 索引体积 | 3.9 MB（gzip 0.84 MB） |
| 页面加载（含 `JSON.parse`） | ≈ 60 ms |
| 首次搜索（含建小写表） | ≈ 28 ms |
| 后续每次搜索 | ≈ 5 – 17 ms |
| 规模 | 3344 类 / 35758 条成员 |

### 11.6 已知限制

- 只显示 tiny / SRG 里真实存在的名字，**不做反推**：缺失列就是 `—`
- 继承关系不在 tiny 里，查询器不提供「父类 / 接口」
- gen1 与 gen2 的 named 名对 **800 个类**不同（匿名内部类，`ParrotEntity$1` vs `ParrotEntity$00658210`），
  所以两列分开显示，不要混用
- 构造函数只在 feather 里有（calamus 与 MCP 都不记录），默认不显示，需要时加 `--ctors`

---

## 12. MCP 服务器（给 LLM 用）

`mcp_server.py` 把查询器包成一个 **MCP（Model Context Protocol）服务器**：
stdio 传输、**零第三方依赖**，索引和搜索逻辑直接 `import query`，
所以命令行、网页、MCP 三边看到的对应关系完全一致。

```bash
python mcp_server.py --config     # 打印客户端配置片段（带本机绝对路径）
```

```json
{
  "mcpServers": {
    "mapping-lookup": {
      "command": "C:\\...\\Python38\\python.exe",
      "args": ["F:\\...\\mapping-converter\\mcp_server.py"]
    }
  }
}
```

Claude Desktop 合并进 `claude_desktop_config.json`，Cline / Continue 等合并进各自的 `mcp.json`。
Windows 上 `command` 建议写 python 的绝对路径。

### 12.1 工具

| 工具 | 用途 | 典型问法 |
|---|---|---|
| `mapping_search` | 六套命名空间里搜类 / 字段 / 方法 | 「含 player 的类都有哪些」 |
| `mapping_class` | 一个类的六套名字 + 成员表 | 「AbstractClientPlayer 有哪些方法」 |
| `mapping_member` | 一个字段 / 方法的所有名字 | 「lerpSteps 在 MCP 里叫什么」 |
| `mapping_convert` | 名字跨命名空间翻译（类与成员都支持） | 「ClientPlayerEntity 对应 MCP 的哪个类」 |
| `mapping_descriptor` | 重写 JVM 描述符里的类名 | 「`(Lbua;D)V` 换成 feather 名」 |
| `mapping_stats` | 版本、规模、已知限制 | 「这套 mapping 有多大」 |

一次真实调用（`mapping_convert`）：

```
net/minecraft/client/entity/living/player/ClientPlayerEntity  ->  mcp: net/minecraft/client/entity/AbstractClientPlayer
  obf           bua
  intermediary1 net/minecraft/unmapped/C_7106153
  feather1      net/minecraft/client/entity/living/player/ClientPlayerEntity
  intermediary2 net/minecraft/unmapped/C_23527099
  feather2      net/minecraft/client/entity/living/player/ClientPlayerEntity
```

### 12.2 协议实现

- stdio + **newline-delimited JSON-RPC 2.0**（MCP 标准），stdout 只走协议，日志一律 stderr
- 支持协议版本 `2025-06-18` / `2025-03-26` / `2024-11-05`，按客户端请求回显
- 处理 `initialize` / `ping` / `tools/list` / `tools/call`；通知（无 `id`）不回包
- 工具内部异常 → `isError: true` 的 content（模型能读到错误文本），协议层错误 → JSON-RPC error
- 每个工具同时返回 `structuredContent`，方便程序化客户端

**验证方式**：除了自带的协议级测试，还用官方 `@modelcontextprotocol/sdk`（1.32.2）跑过真实客户端——
握手、`tools/list`、6 个工具调用、`structuredContent` 解析全部通过。

### 12.3 注意

- 索引在进程内缓存，**重建索引后要重启服务器**
- 默认用 `out/` 下最新的版本目录，也可以用 `--version 1.12.2` 固定
- 工具输出对 token 友好：搜索结果每条两行，类的成员默认最多 40 条，超出会提示调大 `member_limit`
