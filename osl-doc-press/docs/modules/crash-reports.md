---
title: 10 crash-reports
---

# 10 crash-reports

> 一句话定位：用一套统一接口读取、扩写、构造 Minecraft 崩溃报告，并在游戏崩溃时把自己的信息塞进报告里。

| 项 | 值 |
|---|---|
| 模块 id | `crash-reports` |
| Maven | `net.ornithemc.osl-gen2:crash-reports:0.1.0+mc1.4.3-mc1.14.4` |
| 端 | 双端 |
| 依赖 | `ploceus.dependOslModule('crash-reports', '0.24.0')` |

原版崩溃报告（`net.minecraft.util.crash.CrashReport`）在 1.12.2 上字段是私有的、分段只能靠内部类拼，mod 想加一段调试信息几乎无从下手。本模块把"标题 / 异常 / 系统详情分段 / 自定义分段 / 保存到文件 / 生成文本"抽成 `CrashReport` 接口，并让原版类通过接口注入实现它，因此**游戏自己产出的崩溃报告也能直接当 API 用**。此外还提供"崩溃时自动回调"的 `CrashListener`，以及构造"带报告的异常"的工具方法。

## 工具类

### `CrashExceptions`

Reference: `net.ornithemc.osl.crashreports.api.CrashExceptions`

**作用**：构造"带崩溃报告的异常"。抛出它之后，游戏会按正常崩溃流程处理，并显示/保存这份报告。适合"mod 检测到致命配置错误，想把诊断信息一起送到崩溃界面"的场景。

**需要**：一个报告标题（会显示在 `Description:` 一行）和引发崩溃的 `Throwable`；可选一个 `Consumer<CrashReport>` 用来补充分段。

**返回**：`RuntimeException`（可直接 `throw`），异常携带的报告可再取回。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `from(String title, Throwable error)` | 构造异常与报告；报告只含系统详情（OS、Java、内存、JVM 参数、mod 列表），正文为空 | `title`、`error` 不可为 null（源码未做判空） | `RuntimeException` |
| `from(String title, Throwable error, Consumer<CrashReport> builder)` | 同上，并在返回前把报告交给 `builder` 让你 `addSection` / `getSystemReport().addDetail(...)` | `builder` 不能为 null；`builder` 里抛的异常会原样向外传播 | `RuntimeException` |

```java
if (configBroken) {
    throw CrashExceptions.from("OSL Example config is broken", new IllegalStateException("missing 'cookie'"),
        report -> report.addSection("Config").addDetail("path", configPath));
}
```

> 实现细节：返回的运行时类型其实是原版的 `net.minecraft.util.crash.CrashException`（它本身是 `RuntimeException` 的子类），因此游戏能识别它并走原版崩溃界面。不要依赖具体类型，按 `RuntimeException` 处理即可。

## 报告

### `CrashReport`

Reference: `net.ornithemc.osl.crashreports.api.crash.CrashReport`

**作用**：崩溃报告的统一视图。既代表原版 `net.minecraft.util.crash.CrashReport`（通过接口注入实现），也代表 OSL 自己构造的报告（`CrashReport.of(...)`）。所有分段、文本、保存操作都从这里出。

**需要**：通常不是自己 new，而是从"当前发生的崩溃"里拿：游戏传给 `CrashListener` 的参数、`CrashException.getReport()`、或 `CrashReport.of(...)`。

**返回**：见下表；分段相关方法返回 `CrashReportSection`，文本相关方法返回 `String`。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `getTitle()` | 报告标题（原版 `Description:` 那一行） | — | `String` |
| `getError()` | 导致崩溃的异常 | — | `Throwable` |
| `getSystemReport()` | "系统详情"分段，可直接追加条目 | — | `CrashReportSection` |
| `addSection(String name)` | 新建一个分段并加入报告，生成文本时按加入顺序输出 | `name` 是段落标题 | 新建的 `CrashReportSection` |
| `addSection(String name, int stackTraceOffset)` | 同上，并指定分段自带堆栈时跳过多少帧 | `stackTraceOffset` 从异常堆栈顶部开始计数；OSL 自建报告默认 `1`，原版报告会在此值上再 `+1` | 新建的 `CrashReportSection` |
| `getErrorMessage()` | 异常的完整堆栈文本；异常 message 为 null 的 `NPE`/`StackOverflowError`/`OutOfMemoryError` 会被替换成以报告标题为 message 的副本 | — | `String` |
| `buildFriendlyString()` | 生成完整报告文本：头部、吐槽语、时间、`Description`、堆栈、各分段、系统详情 | — | `String` |
| `buildFriendlyStringWithoutHeader()` | 只生成分段部分（无头部与描述） | — | `String` |
| `getSaveFile()` | 报告已保存到的路径 | 未保存过时可能为 null（OSL 自建报告返回 null；原版报告直接读其内部字段，源码未判空） | `Path` 或 null |
| `saveToFile(Path file)` | 把 `buildFriendlyString()` 写入文件，自动创建父目录 | **只有第一次调用会成功**；已保存过直接返回 false；写失败记日志并返回 false | `boolean` |
| `static of(String title, Throwable error)` | 构造报告 | 若 `error` 已是 `CrashException`，直接返回它内部的那份报告，避免嵌套 | `CrashReport` |

> 1.12.2 说明：接口注入让原版 `CrashReport` 实现本接口，所以 `CrashReport.of` 与游戏给的报告用法完全一致；`saveToFile` 在原版报告上走原版写文件逻辑（1.12.2 支持）。

### `CrashReportSection`

Reference: `net.ornithemc.osl.crashreports.api.crash.CrashReportSection`

**作用**：崩溃报告里的一个分段（原版 `net.minecraft.util.crash.CrashReportCategory` 通过接口注入实现它）。每个条目是"键 → 值"，值为 `CrashReportDetail` 时**延迟到生成文本时才求值**。

**需要**：从 `CrashReport.addSection(...)` 或 `getSystemReport()` 拿实例；不要自己实现。

**返回**：三个方法都是 `void`。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `addDetail(String key, CrashReportDetail<String> detail)` | 加一条惰性计算的条目 | 值在生成报告时才 `call()`，此时世界/实体可能已处于异常状态，代码要能容忍 | 无（void） |
| `addDetail(String key, Object detail)` | 加一条立即固定的条目（值由原版转成字符串） | `detail` 非 null | 无（void） |
| `addDetailError(String key, Throwable error)` | 加一条异常条目（实现上等同 `addDetail(key, error)`） | 最终排版由原版决定 | 无（void） |

> **重复 key 不会覆盖**：`addDetail` 直接调用原版的追加逻辑，同一个 key 加两次会在报告里出现两条（OSL 内部记录了条目索引，但公开 API 没有移除/替换方法）。

### `CrashReportDetail<V>`

Reference: `net.ornithemc.osl.crashreports.api.crash.CrashReportDetail<V>`

**作用**：延迟求值条目，等价于 `Callable<V>` 的语义化别名。适合放"只有在崩溃时才值得/才能算"的信息（玩家坐标、区块状态、当前 GUI 名等）。

**需要**：实现 `call()`；在 `call()` 里抛异常时该条目如何显示由原版决定（源码未明确说明是否会中断整份报告的生成），建议自己 try/catch 并返回兜底字符串。

**返回**：`call()` 返回的 `V`（实际使用中多为 `String`）。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `call()` | 计算条目值（继承自 `Callable`） | 不应做重 I/O；执行时机是报告文本生成时 | `V` |

### `CrashException`

Reference: `net.ornithemc.osl.crashreports.api.crash.CrashException`

**作用**：把自己构造的 `CrashReport` 包成一个可抛出的运行时异常；`getMessage()` 返回报告标题，`getCause()` 返回报告里的原始异常。

**需要**：一份已经建好的 `CrashReport`（一般用 `CrashReport.of(...)`）。日常更推荐 `CrashExceptions.from(...)`，它一步到位。

**返回**：`getReport()` 返回报告，其余继承自 `RuntimeException`。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `CrashException(CrashReport report)` | 构造 | `report` 非 null（源码未判空） | — |
| `getMessage()` | 报告标题 | — | `String` |
| `getCause()` | 报告中的原始异常 | — | `Throwable` |
| `getReport()` | 取回报告 | — | `CrashReport` |

## 崩溃时的回调

### `CrashListener`

Reference: `net.ornithemc.osl.crashreports.api.crash.CrashListener`

**作用**：函数式接口。游戏正在生成崩溃报告时被回调，让你把 mod 自己的信息写进报告（注册表状态、网络连接、异步任务队列……）。

**需要**：交给某个 `CrashReportPopulator` 注册（见下）。回调抛出的异常会被捕获并记日志，不会影响崩溃处理本身。

**返回**：无（`void`）。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `populateCrashReport(CrashReport report, CrashReportSection section)` | 往 `section` 里加条目；`report` 可用于 `addSection` 或读标题/异常 | `report` **可能为 null**（见 `WorldData` 的情形）；不要在回调里做重 I/O | 无（void） |

### `CrashReportPopulator`

Reference: `net.ornithemc.osl.crashreports.api.crash.CrashReportPopulator`

**作用**：注册 `CrashListener` 的入口。原版 `Minecraft`（仅客户端）、`MinecraftServer`、`World`、`WorldData` 都通过接口注入实现了它，所以直接强转就能注册。

**需要**：拿到对应实例再强转；监听器在每次崩溃填充报告时按注册顺序调用。

**返回**：`addCrashListener` 为 `void`。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `addCrashListener(CrashListener listener)` | 注册监听器 | `listener` 非 null；同一实例可注册多个 | 无（void） |

**各宿主实例的触发时机与传入的分段**（实现细节，但直接决定你写进哪一段）：

| 宿主（1.12.2 类型） | 端 | 触发点 | 传给你的 `section` | `report` 参数 |
|---|---|---|---|---|
| `net.minecraft.client.Minecraft` | 仅客户端 | 原版 `populateCrashReport` 结束时 | 系统详情分段 | 非 null |
| `net.minecraft.server.MinecraftServer` | 双端 | 原版 `populateCrashReport` 结束时 | 系统详情分段 | 非 null |
| `net.minecraft.world.World` | 双端 | 原版 `populateCrashReport` 结束时 | 该世界的分段 | 非 null |
| `net.minecraft.world.WorldData` | 双端 | 原版 `populateCrashReport` 结束时 | 存档信息分段 | **null**（回调里必须先判空） |

```java
// 在世界崩溃时把玩家坐标写进世界分段
if (world instanceof CrashReportPopulator) {
    ((CrashReportPopulator) world).addCrashListener((report, section) ->
        section.addDetail("Player position", () -> player.getPos().toString()));
}
```

> 注意：接口注入只保证上面四个类实现了该接口；向其它对象强转会 `ClassCastException`。客户端上还可以用 lifecycle-events 的 `MinecraftInstance.get()`、服务端用 `MinecraftServerInstance.get()` 拿实例，再强转成 `CrashReportPopulator`。
