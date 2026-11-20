---
title: 18 localization
---

# 18 localization

> 一句话定位：统一的翻译查询入口（`L10n`）+ 语言/语言元数据模型，把原版语言文件和每个命名空间的 lang 文件合成一张表。

| 项 | 值 |
|---|---|
| 模块 id | `localization` |
| Maven | `net.ornithemc.osl-gen2:localization:0.2.1+mc13w26a-mc18w01a` |
| 端 | 双端（`environment: "*"`，但翻译数据来自客户端语言系统） |
| 依赖 | `ploceus.dependOslModule('localization', '0.24.0')` |

1.12.2 的翻译 API 只有 `I18n` 那种"传键拿字符串"的弱接口，既不支持命名空间，也不方便做带参数的格式化和"取不到就用默认值"。本模块提供 `L10n`（`get` / `getOrDefault` / `has` / `getLanguage`），并把**原版语言文件 + 各命名空间 `assets/<ns>/lang/...`** 合并进同一张表，因此 mod 的翻译可以完全放在自己的命名空间里，不会和别的 mod 撞键。`Language` / `LanguageMetadata` 则描述了"语言"本身，以及资源包如何声明一门新语言。

## 翻译查询

### `L10n`

Reference: `net.ornithemc.osl.localization.api.L10n`

**作用**：mod 侧唯一的翻译查询入口。所有取值都走"当前选中语言对应的那张翻译表"，与游戏界面看到的是同一份数据。

**需要**：翻译键（如 `block.example.cookie`）与语言文件里写的键**完全一致**；不需要也不能加命名空间前缀。客户端上应在语言/资源包加载完成之后再查询（即 `MinecraftClientEvents.READY` 之后、或任意 tick 事件里）。

**返回**：字符串（未命中时返回键本身或你给的默认值），`has` 返回 `boolean`，`getLanguage` 返回 `Language`。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `getLanguage()` | 当前选择的语言 | 若选中语言代码在语言表里不存在，会回退到默认语言（资源包格式 < 3 时为 `en_US`，否则 `en_us`）；连默认语言都不存在时返回 `null`（源码未额外判空） | `Language` |
| `get(String key)` | 取翻译 | 键不存在时**不会**报错 | 翻译文本；键不存在时返回 `key` 本身 |
| `get(String key, Object... args)` | 取翻译并格式化 | 参数按 `String.format` 规则填进翻译文本（见下方"格式化规则"） | 格式化后的文本；格式化失败时返回 `format error: ` + 翻译文本 |
| `getOrDefault(String key, String defaultLocalization)` | 取翻译，允许兜底 | `defaultLocalization` 不做格式化；键存在则忽略它 | 翻译文本或 `defaultLocalization` |
| `has(String key)` | 判断翻译是否存在 | — | `boolean`：存在于当前表则 `true` |

```java
String name = L10n.get("block.example.cookie");                       // 未命中 -> "block.example.cookie"
String msg  = L10n.get("message.example.greeting", player.getName()); // 支持 %s / %d / %1$s
String safe = L10n.getOrDefault("message.example.missing", "Hello!");  // 未命中 -> "Hello!"
```

## 键解析与格式化规则（务必看）

**键解析**：

- 键是**扁平的、无命名空间的**字符串；内容就是 lang 文件里等号左边 / JSON 对象键的原文。
- 一张表里包含：原版会加载的 `lang/<语言代码>.lang` 与 `.json`，**以及**资源包中每个命名空间的 `assets/<命名空间>/lang/<语言代码>.lang` 与 `.json`（后者由 resource-loader 提供）。
- 所有文件都写进**同一张** `Map<String, String>`，**后加载的覆盖先加载的**。加载顺序是：先回退语言（`en_US`/`en_us`），再当前语言 —— 所以当前语言的同名键会覆盖回退语言。
- 文件名大小写：当资源包格式 < 3 且语言代码不是全小写时，还会额外尝试全小写的文件名（历史兼容）；1.12.2 的资源包格式 ≥ 3，一般只用语言代码原样。
- `.lang` 格式：每行 `键=值`，按**第一个** `=` 切分，`#` 开头的行与空行被忽略。`.json` 格式：扁平的 `{"键": "值"}` 对象（值必须是字符串）。
- 解析失败的语言文件只记一条警告日志，不影响其它文件。

**格式化规则**：

- 语言文件**加载时**，所有"数字格式说明符"会被就地改写成 `%s`：正则 `%(\d+\$)?[\d\.]*[df]`，也就是 `%d`、`%f`、`%1$d`、`%.2f` 等。
- 因此 `L10n.get(key, args)` 实际执行的是 `String.format(翻译文本, args)`，而 `%d` 位置上的值按 `toString()` 输出：**不会有本地化的千分位和小数点**，传 `3` 和传 `"3"` 结果相同。
- `%s`、`%%` 等其余说明符按 JVM 默认 `Locale` 的 `String.format` 语义处理。
- 参数个数/类型不匹配时**不抛异常**，返回 `format error: ` + 已翻译文本（注意拼的是翻译后的文本，不是键）。
- `getOrDefault` 不做格式化；需要格式化时请用 `get`。

## 语言

### `Language`

Reference: `net.ornithemc.osl.localization.api.language.Language`

**作用**：一门语言的元数据视图：代码、名称、地区、是否双向文字。

**需要**：mod 一般**不实现**它 —— 原版 `net.minecraft.client.resource.language.Language` 已通过接口注入实现（仅客户端类），自定义语言则是通过资源包元数据声明、由 OSL 用工厂创建。

**返回**：见下表（前四个是纯读取方法）。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `code()` | 语言代码，如 `en_us`（同时是 lang 文件名与元数据里的键） | — | `String` |
| `name()` | 语言显示名，如 `English` | — | `String` |
| `region()` | 地区显示名，如 `United States` | — | `String` |
| `bidirectional()` | 是否双向文字（阿拉伯语等从右往左的语言） | — | `boolean` |
| `Language.Factory`（嵌套接口） | 由代码/名称/地区/双向标志创建 `Language` 实例 | `create(String code, String name, String region, boolean bidirectional)`；**注意**：默认的元数据序列化器实际按 `(code, region, name, bidirectional)` 顺序调用，与接口参数命名相反，源码未明确说明以哪边为准 —— 自己实现工厂时请以"第二参是 region、第三参是 name"为准 | `Language` |

### `LanguageMetadata`

Reference: `net.ornithemc.osl.localization.api.language.LanguageMetadata`

**作用**：资源包 `pack.mcmeta` 里 `language` 段的解析结果，保存该资源包声明的所有语言。它同时提供"段名 + 序列化器 + 段类型"三件套，供资源包元数据系统使用。

**需要**：mod 一般只读（通过资源包遍历），不直接解析它。

**返回**：`getLanguages()` 返回语言集合；两个静态字段是元数据段描述。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `NAME` | 常量 `"language"`，即 `pack.mcmeta` 中的段名 | 只读常量 | `String` |
| `SERIALIZER` | 该段的 JSON 反序列化器 | 由 OSL 提供的默认实现 | `ResourceMetadata.Section.Serializer<LanguageMetadata>` |
| `SECTION` | 该段的类型对象（`ResourceMetadata.Section.of("language", SERIALIZER)`），可传给 `ResourcePack.getMetadata(section)` | 只读常量 | `ResourceMetadata.Section<LanguageMetadata>` |
| `getLanguages()` | 该元数据包含的语言 | 可能为空集合 | `Collection<Language>` |

## 如何注册一门自定义语言

1. 在你的资源包根目录的 `pack.mcmeta` 里加一个 `language` 段（键 = 语言代码）：

```json
{
  "pack": { "description": "Example Mod Languages", "pack_format": 3 },
  "language": {
    "xx_yy": { "name": "Example", "region": "Example Region", "bidirectional": false }
  }
}
```

2. 放翻译文件（`.lang` 或 `.json` 均可）：`assets/<你的命名空间>/lang/xx_yy.lang`。

3. 客户端重建语言列表时会遍历资源包栈读取这个段；选中该语言后，`L10n` 就会从 `xx_yy` 的翻译表取值。

**校验规则**（违反会抛 `JsonParseException`，该资源包的这整段被丢弃并记警告）：

| 规则 | 说明 |
|---|---|
| 语言代码长度 | 不能超过 16 个字符 |
| `region` / `name` | 必填，且不能为空字符串 |
| `bidirectional` | 可省略，缺省为 `false` |
| 同一段内重复代码 | 抛异常（"Duplicate language ... defined"） |
| 跨资源包重复代码 | 不报错，**先遍历到的包获胜**（后续包的同名语言被忽略） |

## 与资源包语言文件的关系

- OSL **不替换**原版的语言加载，而是在原版加载的同一条流程里补两件事：把每个命名空间的 `assets/<ns>/lang/<code>.lang|json` 也读进来；以及在需要时补读 `.json` / 小写文件名的变体。
- 结果写进**原版那张** `translations` 表，因此 `L10n.get` 与游戏界面（`I18n` 那类调用）看到的是同一份数据 —— 用 `L10n` 查到的东西，界面上也能显示。
- 语言切换由客户端原版流程驱动（切换语言时会同步给 OSL 记录）；**API 没有暴露"主动重新加载语言/资源包"的入口**，`Localization` 里的 reload 方法属于内部实现，不属于公开 API。
- 专用服务器上 OSL 的翻译表不会被填充（相关注入只在客户端），`L10n.get` 通常直接返回键本身；源码未明确说明服务端是否有意支持本地化。
