---
title: 22 text-components
---

# 22 text-components

> 一句话定位：一套跨版本、双端一致的"富文本"模型（literal / translatable 文本 + Style + 点击/悬停事件），并在它和原版文本类型、JSON、brigadier 消息之间做互转。

| 项 | 值 |
|---|---|
| 模块 id | `text-components` |
| Maven | `net.ornithemc.osl-gen2:text-components:0.2.0+mc13w36a-mc1.14.4` |
| 模块版本 | `0.2.0`（`libraries/text-components/gradle.properties`） |
| 端 | 双端（api 只有一套，客户端/服务端共用同一批类） |
| 依赖 | `ploceus.dependOslModule('text-components', '0.2.0')`；运行期还需要 `core` 与 `entrypoints` 模块（源码声明 `osl_dependencies = core:0.7.0,entrypoints:0.5.0`），以及 brigadier（模块里是 `compileOnly`，需由依赖方提供） |

Minecraft 的文本类型在各版本里反复改名、拆类（1.12.2 是"聊天组件"，1.13+ 才有 `Text` / `MutableText`、`Style` 的完整 JSON 支持）。text-components 把"拼文本、加样式、加点击/悬停、序列化成 JSON、塞给原版显示"这一整套抽象成自己的 API：你用 `net.ornithemc.osl.text.api` 下的类型写代码，逻辑不随版本变化，只在"要真正显示 / 交给原版"时才用 `TextComponents.convert(...)` 转一次。

**关于"客户端与服务端各有一套同名类"**：本仓库当前版本**不是**这样。`libraries/text-components/src/main/java` 下只有一份 `api` 源码，客户端和服务端编译同一份类；1.12.2 使用的子工程 `text-components-mc13w36a-mc1.14.4` 里只有 impl/mixin（样式读取、`CommandSource` 注入、原版类型互转）。因此：

- 不存在"包名相同、不可混用的两套 `Action`"——`Action` 只以 `ClickEvent.Action` 与 `HoverEvent.Action` 两个嵌套枚举存在，客户端与服务端用的是同一个。
- 本模块 api 里**没有"仅客户端可用"的类型**：渲染、字体、GUI 全部留给调用方，OSL 只提供数据模型与转换。

## 文本模型：`text.api`

### `TextComponent`

Reference: `net.ornithemc.osl.text.api.TextComponent`

**作用**：OSL 的文本节点接口——"一段内容（字面量或翻译键）+ 一个 `Style` + 一串兄弟节点"，同时实现 brigadier 的 `com.mojang.brigadier.Message`（这样命令报错、参数提示可以直接拿它当消息用）。它同时是"树"的节点类型：`getSiblings()` 就是子节点列表。

**需要**：**不要自己去实现它**（序列化器只认 OSL 的两个内置实现，见 `TextComponents`）。用 `TextComponents.literal/translatable/builder` 创建。注意它是**可变**的：`format(...)` / `append(...)` 都直接修改自身并返回 `this`，所以别把同一个实例到处共享后又改它。

**返回**：`format` / `append` 返回 `this`；`buildString` / `buildFormattedString` / `getString` 返回字符串；`visit` 返回"访问被终止时的结果"。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `getStyle()` | 取本节点的样式 | 无 | `Style`（没设置过就是 `Style.EMPTY`） |
| `getSiblings()` | 取子节点列表 | 无 | `List<TextComponent>`（**只读视图**，要加节点请用 `append`） |
| `format(Formatting... formattings)` | 在原样式上叠加若干格式码 | 无 | `this`（修改自身） |
| `format(Style style)` | 在原样式上叠加一个样式（非 null 字段覆盖） | `style` 非 null | `this` |
| `format(UnaryOperator<Style> styler)` | 用函数改写样式 | 返回值不能是 null | `this` |
| `append(String text)` | 追加一个字面量子节点 | 无 | `this` |
| `append(TextComponent text)` | 追加一个子节点 | `text` 非 null | `this` |
| `buildString()` | 拼出**纯文本**（丢掉所有样式） | 翻译键会在此刻解析成当前语言 | `String` |
| `buildFormattedString()` | 拼出带 `§` 格式码的字符串 | 同上 | `String` |
| `visit(TextVisitor<T> visitor)` | 深度优先遍历所有文本片段，可提前终止 | 无 | `Optional<T>`：`empty` 表示遍历完了，非空表示某次 `accept` 返回了终止值 |
| `visit(Style fallback, StyledTextVisitor<T> visitor)` | 同上，但每次回调都带上"继承累积后"的样式 | `fallback` 通常是 `Style.EMPTY` | 同上 |
| `copy()` | 浅拷贝：复制本节点、共享样式对象与**同一批**子节点实例 | 无 | 新的 `TextComponent` |
| `deepCopy()` | 深拷贝（递归复制子树） | 无 | 新的 `TextComponent`（见下方注意） |
| `getString()` | brigadier `Message` 的接口方法，等价于 `buildString()` | 无 | `String` |

> 注意（按源码现实现）：`deepCopy()` 先调用 `copy()`（已把原兄弟节点塞进副本），随后又追加每个兄弟的深拷贝，**结果里兄弟节点会重复一份**。需要可靠的深拷贝时，请自己用 `literal/translatable` 重建。

#### `TextComponent.Builder`

**作用**：链式拼文本的小工具，避免写 `literal("").append(a).append(b)` 这种以空串当根的写法。

**需要**：用 `TextComponents.builder()` 取；不追加任何内容就 `build()` 会得到一个空字面量。

**返回**：`append` 返回 `this`，`build()` 返回累积出来的组件。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `append(String text)` | 追加纯文本 | 无 | `this` |
| `append(TextComponent text)` | 追加已有组件 | `text` 非 null | `this` |
| `build()` | 产出组件（多次调用返回同一个实例） | 无 | `TextComponent` |

#### `TextComponent.Serializer`（Gson 适配器，公开嵌套类）

**作用**：`TextComponent` ⇄ JSON 的读写实现。`TextComponents.fromJson/toJson` 已经在用它；只有你要自己配 `GsonBuilder` 时才需要直接引用。

**需要**：注册成 type-hierarchy adapter（对子类型也生效）；反序列化的 JSON 只能是"字符串、数组、含 `text`或`translate` 的对象"。

**返回**：`deserialize` 返回组件（JSON 为 `null` 时返回 `null`）；`serialize` 返回 `JsonElement`。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `deserialize(JsonElement json, Type type, JsonDeserializationContext context)` | 解析 JSON：字符串 → 字面量；数组 → 第一个元素为根、其余为兄弟；对象 → `text` / `translate`（+ `with` 参数）+ `extra` 兄弟 + 顶层样式字段 | `extra` 为空数组会抛 `JsonParseException`；对象既无 `text` 也无 `translate` 时抛 `JsonParseException` | `TextComponent` |
| `serialize(TextComponent text, Type type, JsonSerializationContext context)` | 写 JSON：样式字段平铺在外层，兄弟放 `extra`，内容用 `text` 或 `translate`+`with` | 只支持 OSL 的两个内置实现，其它实现抛 `IllegalArgumentException` | `JsonElement` |
| `TextComponent.Serializer.LowercaseEnumTypeAdapterFactory` | 枚举 ⇄ 小写名字的 Gson 适配器 | 只对枚举生效（非枚举返回 null 表示不接管） | 适配器实例 |

### `TextComponents`

Reference: `net.ornithemc.osl.text.api.TextComponents`

**作用**：文本组件的工厂 + 全局互转入口。日常写 mod 只需要这一个类：造文本、拼文本、和原版/JSON/brigadier 互转。

**需要**：`resolve` 与 `composite` 的参数不能为 `null`（内部直接 `getClass()`）；`resolve` 只认**注册过的确切运行时类型**，其它类型退化为"先 `toString()`、再当带 `§` 的字符串解析"（详见"1.12.2 下的互转"）。`fromJson` 要求合法的组件 JSON。

**返回**：见下表。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `literal(String t)` | 字面量文本（原样显示，不查翻译表） | `t` 非 null | `TextComponent` |
| `literal(String t, Object... args)` | 先用 `String.format(t, args)` 再包成字面量 | 格式串与参数匹配 | `TextComponent` |
| `translatable(String t)` | 翻译键（显示时按当前语言查表） | `t` 非 null | `TextComponent` |
| `translatable(String t, Object... args)` | 带参数的翻译键（支持 `%s`、`%1$s` 定位参数、`%%` 转义） | 参数个数与格式串匹配；格式串只支持 `%s`，其它格式符会在**显示时**抛 `IllegalStateException` | `TextComponent` |
| `builder()` | 链式构造器 | 无 | `TextComponent.Builder` |
| `resolve(Object o)` | 把"任意东西"转成组件：`String`（解析 `§` 代码）、原版 `net.minecraft.text.LiteralText` / `TranslatableText`（必须恰好是这两个类），其它类型走 `toString()` | `o` 非 null | `TextComponent` |
| `composite(Object... ts)` | 把多个对象依次 `resolve` 后拼成一个组件（根是空字面量） | 元素都非 null | `TextComponent` |
| `fromJson(String json)` / `fromJsonTree(JsonElement json)` | 从 JSON 反序列化 | 合法的组件 JSON | `TextComponent`（JSON 为 `null` 时为 `null`） |
| `toJson(TextComponent t)` / `toJsonTree(TextComponent t)` | 序列化成 JSON（不转义 HTML 字符） | `t` 是 OSL 内置实现 | `String` / `JsonElement` |
| `convert(TextComponent t, Class<T> type)` | 转成别的表示：`net.minecraft.text.Text`（原版文本）、`String`（带 `§` 的格式串）、`com.mojang.brigadier.Message`（原样返回） | 目标类型必须已注册 | `T`；**未注册的类型返回 `null`** |

#### 示例

```java
TextComponent msg = TextComponents.translatable("mymod.greeting", player.getName())
    .format(Formatting.GOLD, Formatting.BOLD)
    .append(TextComponents.literal(" (click)").format(Style.EMPTY.withClickEvent(ClickEvent.runCommand("/spawn"))));

String plain = msg.buildString();            // 纯文本
String json  = TextComponents.toJson(msg);   // 发到网络 / 存盘
Text mcText  = TextComponents.convert(msg, Text.class); // 交给原版显示
```

### `Style`

Reference: `net.ornithemc.osl.text.api.Style`

**作用**：不可变的文本样式：颜色 + 五个修饰开关 + `insertion`（聊天输入框预填）+ 点击事件 + 悬停事件。所有 `with...` 方法返回**新对象**（值没变化时返回 `this`），因此可以安全地当常量复用。

**需要**：用 `Style.EMPTY` 作为起点链式构造；修饰开关是 `Boolean` 而不是 `boolean`，`null` 表示"未设置 / 继承父节点"，这一点在把样式套到原版类型上时很重要。**`isEmpty()` 用引用比较（`== EMPTY`）**，所以自己拼出来的"全 null 样式"并不被视为空。

**返回**：见下表。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `EMPTY` | 空样式常量（所有字段 `null`） | 无 | `Style` |
| `getColor()` | 颜色 | 无 | `TextColor` 或 `null` |
| `isBold()` / `isItalic()` / `isUnderlined()` / `isStrikethrough()` / `isObfuscated()` | 修饰开关的布尔视图（**未设置**和**显式 false** 都返回 `false`） | 无 | `boolean` |
| `getInsertion()` | 聊天框预填文本 | 无 | `String` 或 `null` |
| `getClickEvent()` / `getHoverEvent()` | 点击 / 悬停事件 | 无 | `ClickEvent` / `HoverEvent` 或 `null` |
| `isEmpty()` | 是否是那个 `EMPTY` 常量（引用比较） | 无 | `boolean` |
| `withColor(int color)` | 用 RGB 值设自定义颜色 | 颜色值建议用 `0xRRGGBB` | 新 `Style` |
| `withColor(Formatting formatting)` | 用原版 16 色之一设颜色 | 若传入的不是颜色（如 `BOLD`），颜色会被**清空**为 `null` | 新 `Style` |
| `withColor(TextColor color)` | 直接给颜色对象（`null` 表示清空） | 无 | 新 `Style` |
| `withBold(Boolean)` / `withItalic(Boolean)` / `withUnderlined(Boolean)` / `withStrikethrough(Boolean)` / `withObfuscated(Boolean)` | 设置单个修饰（`null` 表示清空） | 无 | 新 `Style` |
| `withInsertion(String)` | 设置预填文本 | 无 | 新 `Style` |
| `withClickEvent(ClickEvent)` / `withHoverEvent(HoverEvent)` | 设置点击 / 悬停事件 | 无 | 新 `Style` |
| `withFormatting(Formatting... formattings)` | 一次性叠加若干格式码（颜色或修饰） | 遇到 `RESET` 时**整体返回 `EMPTY`**（连 insertion / 点击 / 悬停一起丢掉） | 新 `Style`（可能是 `EMPTY`） |
| `withStyle(Style style)` | 用另一个样式的**非 null 字段**覆盖自己 | `style` 为 `EMPTY` 时原样返回自己 | 新 `Style` |
| `copy()` | 复制一份（字段全同，但不是 `EMPTY` 常量） | 无 | 新 `Style` |
| `apply(StringBuilder sb)` | 把样式追加成 `§` 格式码 | 无 | 无（void） |

> `apply` 的两个细节：① 自定义 RGB 颜色**不会**输出（只有原版 16 色会写 `§0-§f`）；② 修饰只判断"是否非 null"，所以显式 `false` 的修饰也会写出对应格式码。

#### `Style.Serializer`（Gson 适配器，公开嵌套类）

**作用**：`Style` ⇄ JSON。字段名沿用原版：`color`、`bold`、`italic`、`underlined`、`strikethrough`、`obfuscated`、`insertion`、`clickEvent`、`hoverEvent`。

**需要**：注册给 `GsonBuilder`；`Style.EMPTY` 序列化时返回 `null`（即 JSON 里不出现样式对象）；反序列化非对象输入时返回 `null`。

**返回**：`deserialize` → `Style`（或 `null`）；`serialize` → `JsonElement`（或 `null`）。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `deserialize(JsonElement, Type, JsonDeserializationContext)` | 读样式：颜色字符串（原版色名或 `#rrggbb`）、布尔修饰、`clickEvent`/`hoverEvent` 子对象（`action` + `value`） | `clickEvent` / `hoverEvent` 的 `action` 名字必须是已知值，否则抛 `IllegalArgumentException` | `Style` 或 `null` |
| `serialize(Style, Type, JsonSerializationContext)` | 写样式，只写非 null 字段 | 无 | `JsonElement` 或 `null` |

> **已知问题（按源码现实现）**：悬停事件的 JSON 键写成了 `hoverEveant`（源码里的拼写错误），因此写出的 JSON 用标准 `hoverEvent` 键读不回来，反过来也一样。另外 `hoverEvent` 的 `value` **写**的是序列化后的组件对象，**读**的时候却按字符串取，往返不完全对称。需要严格兼容原版 JSON 时请自己处理悬停事件。

### `TextColor`

Reference: `net.ornithemc.osl.text.api.TextColor`

**作用**：颜色值的统一表示——要么是原版 16 色之一（可直接写成 `§` 代码），要么是任意 RGB 值（只能用于富文本，没法降级成 `§` 代码）。

**需要**：用 16 个常量或 `of(int)` / `fromFormatting(Formatting)` / `deserialize(String)` 创建（构造函数私有）。1.12.2 的原版样式里只有 16 色，所以自定义 RGB 颜色在"转成原版文本"时会被丢弃。

**返回**：见下表。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `BLACK / DARK_BLUE / DARK_GREEN / DARK_AQUA / DARK_RED / DARK_PURPLE / GOLD / GRAY / DARK_GRAY / BLUE / GREEN / AQUA / RED / LIGHT_PURPLE / YELLOW / WHITE` | 16 个原版颜色常量 | 无 | 该常量 |
| `CUSTOM_COLOR_PREFIX` | 自定义颜色的序列化前缀（`'#'`） | 无 | `char` |
| `getColor()` | RGB 值 | 无 | `int` |
| `isFormatting()` | 是否对应某个原版格式码 | 无 | `boolean` |
| `getFormatting()` | 对应的 `Formatting` | 无 | `Formatting` 或 `null`（自定义颜色时为 null） |
| `serialize()` | 序列化成字符串：原版色返回小写名（如 `red`），自定义色返回 `#` + 十六进制 | 无 | `String` |
| `of(int color)` | 用 RGB 值建自定义颜色 | 无 | `TextColor` |
| `fromFormatting(Formatting formatting)` | 把格式码转成颜色 | 传入非颜色格式码时返回 `null` | `TextColor` 或 `null` |
| `deserialize(String s)` | 解析 `red` / `#ff0000` 这样的字符串 | `#` 开头且十六进制非法时返回 `null`；非颜色色名（如 `bold`）返回 `null`；**未知名字**抛 `IllegalArgumentException` | `TextColor` 或 `null` |

> `serialize()` 对自定义颜色用 `Integer.toHexString`，**不会补零到 6 位**（例如 `0x0000AA` 会序列化成 `#aa`）。要稳定的 `#rrggbb` 表示请自己格式化。

### `Formatting`

Reference: `net.ornithemc.osl.text.api.Formatting`

**作用**：原版 22 个 `§` 格式码的枚举：16 个颜色 + 5 个修饰（`OBFUSCATED`、`BOLD`、`STRIKETHROUGH`、`UNDERLINED`、`ITALIC`）+ `RESET`。

**需要**：`byName` 参数不能为 `null`（内部先做字符串处理）；`byCode` 对未知字符抛异常。

**返回**：见下表。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `BLACK / DARK_BLUE / DARK_GREEN / DARK_AQUA / DARK_RED / DARK_PURPLE / GOLD / GRAY / DARK_GRAY / BLUE / GREEN / AQUA / RED / LIGHT_PURPLE / YELLOW / WHITE` | 16 个颜色（代码 `§0` 到 `§f`） | 无 | 该常量 |
| `OBFUSCATED / BOLD / STRIKETHROUGH / UNDERLINED / ITALIC` | 5 个修饰（`§k`、`§l`、`§m`、`§n`、`§o`） | 无 | 该常量 |
| `RESET` | 重置（`§r`） | 无 | 该常量 |
| `PREFIX` | 格式码前缀常量（`'§'`，U+00A7） | 无 | `char` |
| `getName()` | 小写名字（`bold`、`dark_red`…） | 无 | `String` |
| `getCode()` | 格式码字符（不带 `§`） | 无 | `char` |
| `isColor()` | 是否是颜色 | 无 | `boolean` |
| `getColor()` | 颜色的 RGB 值 | 无 | `Integer` 或 `null`（修饰与 `RESET` 为 null） |
| `toString()` | 返回 `§` + 代码 | 无 | `String` |
| `byName(String name)` | 按名字查：先转小写、再去掉所有非字母字符，所以 `DARK_RED`、`dark-red`、`dark red` 都能命中 | `name` 非 null；查不到返回 `null` | `Formatting` 或 `null` |
| `byCode(char code)` | 按格式码字符查（如 `'c'` → `RED`） | 必须存在 | `Formatting`；未知代码抛 `IllegalStateException` |
| `getNames(boolean colors, boolean modifiers)` | 批量取名：`colors` 决定是否含 16 色，`modifiers` 决定是否含修饰（`RESET` 只在 `modifiers` 为 true 时出现） | 无 | `Collection<String>` |

> 典型用法：`getNames(true, false)` 得到全部颜色名、`getNames(false, true)` 得到全部修饰名，可以拿来生成配置文件里的可选值列表。

### `ClickEvent`

Reference: `net.ornithemc.osl.text.api.ClickEvent`

**作用**：描述"点一下这段文本会怎样"：开链接、执行命令、补全命令、复制到剪贴板。它是不可变值对象，能被 `Style` 持有。

**需要**：用构造函数或 4 个静态工厂创建；`Action` 与值要匹配（URL 配 `OPEN_URL` 等）。**没有重写 `hashCode`**，别当 `HashMap` 的键。

**返回**：见下表。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `ClickEvent(Action action, String value)` | 直接构造 | 两者非 null | 新实例 |
| `getAction()` | 动作类型 | 无 | `ClickEvent.Action` |
| `getValue()` | 动作参数（URL / 命令 / 待复制文本） | 无 | `String` |
| `openUrl(String url)` | 打开链接 | `url` 是合法 URL（是否校验：源码未明确说明） | `ClickEvent` |
| `runCommand(String command)` | 以玩家身份执行命令 | 无 | `ClickEvent` |
| `suggestCommand(String command)` | 把命令填进聊天框 | 无 | `ClickEvent` |
| `copyToClipboard(String text)` | 复制文本到剪贴板 | 无 | `ClickEvent` |
| `equals` | 按动作 + 值判等 | 无 | `boolean` |

#### `ClickEvent.Action`（枚举）

**作用**：点击动作的四种类型。

**需要**：`byName` 只接受名字（大小写不敏感，因为内部先转大写）。

**返回**：见下表。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `OPEN_URL` | 打开 URL | 无 | 该常量 |
| `RUN_COMMAND` | 执行命令 | 无 | 该常量 |
| `SUGGEST_COMMAND` | 补全命令 | 无 | 该常量 |
| `COPY_TO_CLIPBOARD` | 复制到剪贴板 | 无 | 该常量 |
| `getName()` | 小写名字（`open_url`…） | 无 | `String` |
| `byName(String name)` | 按名字查 | 名字必须是 4 个之一；**未知名字抛 `IllegalArgumentException`，不会返回 `null`** | `ClickEvent.Action` |

> 1.12.2 注意：转成原版点击事件时只支持 `OPEN_URL` / `RUN_COMMAND` / `SUGGEST_COMMAND`，`COPY_TO_CLIPBOARD` 会被丢弃（该版本原版没有这个动作）。

### `HoverEvent`

Reference: `net.ornithemc.osl.text.api.HoverEvent`

**作用**：描述"鼠标悬停时显示什么"，目前只建模了"显示一段文本"（`SHOW_TEXT`）。同为不可变值对象。

**需要**：用构造函数或 `showText(...)` 创建；`value` 是 `Object`，取回时要自己确定类型。**没有重写 `hashCode`**。

**返回**：见下表。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `HoverEvent(Action action, Object value)` | 直接构造 | 两者非 null | 新实例 |
| `getAction()` | 动作类型 | 无 | `HoverEvent.Action` |
| `getValue()` | 动作负载（`SHOW_TEXT` 时是 `TextComponent`） | 无 | 泛型 `T`（**未检查的强转**，类型不对会在使用处 ClassCastException） |
| `showText(TextComponent text)` | 悬停显示一段文本 | `text` 非 null | `HoverEvent` |
| `equals` | 按动作 + 值判等 | 无 | `boolean` |

#### `HoverEvent.Action`（枚举）

**作用**：悬停动作类型，本版本只有 `SHOW_TEXT`（原版的显示物品、显示实体、显示成就等没有被建模）。

**需要**：`byName` 未知名字抛 `IllegalArgumentException`。

**返回**：见下表。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `SHOW_TEXT` | 悬停显示文本 | 无 | 该常量 |
| `getName()` | 小写名字（`show_text`） | 无 | `String` |
| `byName(String name)` | 按名字查 | 名字必须是 `SHOW_TEXT` | `HoverEvent.Action` |

## 访问器与工具

### `TextVisitor<T>`

Reference: `net.ornithemc.osl.text.api.TextVisitor<T>`

**作用**：遍历文本树时的回调：每个"文本片段"（字面量的内容、或翻译展开后的一段）调用一次 `accept`。用来提取纯文本、做搜索替换、统计长度等。

**需要**：由调用方实现（lambda 即可）。返回值语义是"是否终止"：返回 `TextVisitResults.CONTINUE`（即 `Optional.empty()`）继续，返回任何非空 `Optional` 就**立刻终止**整个遍历，并把该值原样作为 `visit(...)` 的结果。

**返回**：`Optional<T>`——`empty` 表示继续，非空表示终止值。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `accept(String text)` | 处理一个文本片段 | `text` 非 null（可能是空串） | `Optional<T>` |

### `StyledTextVisitor<T>`

Reference: `net.ornithemc.osl.text.api.StyledTextVisitor<T>`

**作用**：带样式的遍历回调，每段文本都附带"从这里往上累积"的样式，用来做富文本渲染（自己画字、转 HTML 等）。

**需要**：同 `TextVisitor`；样式已经与父节点合并过，不需要自己再往上找。

**返回**：`Optional<T>`，语义同 `TextVisitor`。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `accept(Style style, String text)` | 处理"一段文本 + 它的样式" | `style` 非 null（无样式时是 `Style.EMPTY`） | `Optional<T>` |

> 遍历顺序：先本节点内容，再按顺序递归子节点（深度优先）；翻译组件会先展开成若干片段再逐个回调。

### `TextVisitResults`

Reference: `net.ornithemc.osl.text.api.TextVisitResults`

**作用**：遍历回调的返回值常量，配合 `Optional<Unit>` 表达"继续 / 终止"，比手写 `Optional.empty()` / `Optional.of(Unit.INSTANCE)` 清楚。

**需要**：直接引用常量。

**返回**：两个都是 `Optional<Unit>`。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `CONTINUE` | 继续遍历（`Optional.empty()`） | 无 | `Optional<Unit>` |
| `TERMINATE` | 终止遍历（`Optional.of(Unit.INSTANCE)`） | 无 | `Optional<Unit>` |

```java
String plain = msg.buildString();   // 内部就是 visit(TextVisitResults.CONTINUE) 的写法

// 自己找第一个匹配的位置并提前退出
Optional<Integer> hit = msg.visit(text -> text.contains("foo")
    ? Optional.of(text.indexOf("foo"))
    : TextVisitResults.CONTINUE);
```

### `MessageConsumer`

Reference: `net.ornithemc.osl.text.api.MessageConsumer`

**作用**：所有"能接收文本消息"的东西的公共接口（玩家、命令源、控制台……）。这样你写工具方法时不必判断对方到底是哪种消息接收者。

**需要**：通常你只**消费**它，不用实现：1.12.2 下原版的 `net.minecraft.server.command.source.CommandSource` 已经被注入了该接口的实现，可以直接 `((MessageConsumer) source).sendMessage(component)`（内部会先 `convert` 成原版文本再发）。若你要让自定义类也能接收，就实现它（方法无返回值）。

**返回**：无（void）。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `sendMessage(TextComponent message)` | 发送一条消息 | `message` 非 null；实现方负责转成原版类型 | 无（void） |

## 1.12.2 下的互转与限制

下面这些结论来自 1.12.2 使用的子工程（`text-components-mc13w36a-mc1.14.4`）与共享 impl 源码，属于"API 行为的实际边界"，写 mod 时容易踩：

**① `TextComponents.resolve(Object)` 只认"确切运行时类型"**

| 传入的运行时类型 | 结果 |
|---|---|
| `String` | 解析其中的 `§` 格式码，切成"带样式的字面量片段" |
| 原版 `net.minecraft.text.LiteralText` / `TranslatableText`（必须恰好是这两个类） | 转换：内容 + 样式 + 递归子节点 |
| 其它一切类型（**包括 OSL 自己的 `TextComponent`、原版文本的子类、任何自定义 `Message` 实现**） | 走 `toString()`，再按 `String` 的规则解析 |

查找用的是"确切运行时类"，所以副作用比看上去大：

- 源码虽然注册了 `com.mojang.brigadier.Message` 的解析器，但那只对"类恰好是 `Message`"的实例生效，实际几乎永不命中；把 OSL 自己的 `TextComponent` 丢进 `resolve` / `composite` / 翻译参数，得到的是 `Object.toString()` 的"类名@哈希"串，**不会**被原样返回。
- 原版文本的**子类**同样不会命中。
- 需要互换原版文本时显式用 `convert(component, Text.class)`，需要把已有 `TextComponent` 拼进去时用 `append(TextComponent)`，不要走 `resolve`。

**② `TextComponents.convert(component, type)` 支持的目标类型**

| `type` | 结果 | 备注 |
|---|---|---|
| `net.minecraft.text.Text.class` | 原版文本对象 | 递归转换内容、样式、子节点 |
| `String.class` | 带 `§` 格式码的字符串（`buildFormattedString()`） | 自定义 RGB 颜色会丢 |
| `com.mojang.brigadier.Message.class` | 原样返回自身 | 因为 `TextComponent` 就是 `Message` |
| 其它 | `null` | 未注册的转换器一律返回 null |

**③ 样式转成原版时的取舍**

- 颜色：只有 16 个原版颜色能表达，自定义 RGB 会被丢弃。
- 点击事件：`OPEN_URL` / `RUN_COMMAND` / `SUGGEST_COMMAND` 可转换，`COPY_TO_CLIPBOARD` 被丢弃。
- 悬停事件：只有 `SHOW_TEXT` 可转换。
- `insertion`：1.12.2（`>= 14w02a`）支持，能转换。
- **修饰（粗体/斜体等）**：按源码现实现，转换条件写成了 `style.withBold(style.isBold()) != style`，只有在"原值为 `null`"时才成立，因此**值为 `true` 的修饰不会被写进原版样式**（疑似笔误）。需要玩家真正看到粗体/斜体时，请自行在转成原版文本后调用原版 `Style` 的 setter，或直接用 `§` 格式串。

**④ 翻译键的解析时机**

`translatable(...)` 不会立刻查表：只有在 `visit` / `buildString` / `buildFormattedString` / 转成原版文本时才展开，并且每次语言表更新后会重新展开。语言表来自 localization 模块（通过反射查找），**若没有安装该模块，翻译键会原样返回**（显示成 `mymod.greeting` 这样的键名）。展开规则：

- 只支持 `%s` 与 `%1$s` 这类定位参数，以及 `%%` 表示字面 `%`；遇到 `%d` 等其它格式符在展开时抛 `IllegalStateException`。
- 参数比占位符少时，多出来的占位符被**静默跳过**（不报错）。
- 参数是 `null` 时显示字符串 `null`。
- 参数按 `TextComponents.resolve` 的规则转换（同样受"确切类型"限制）。

**⑤ JSON 兼容性**：`toJson` 产出的结构与原版基本一致（`text` / `translate` / `with` / `extra` + 平铺样式字段），但悬停事件键名有拼写错误（见 `Style.Serializer` 的说明），跨版本/跨端交换 JSON 时要注意。
