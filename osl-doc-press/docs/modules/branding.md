---
title: 07 branding
---

# 07 branding

> 一句话定位：把游戏里显示的"品牌字符串"（标题界面的版本信息、F3 调试界面的游戏信息）变成一条可插拔的组件链。

| 项 | 值 |
|---|---|
| 模块 id | `branding` |
| Maven | `net.ornithemc.osl-gen2:branding:0.4.4+mc16w05b-mc1.12.2` |
| 端 | 仅客户端（`environment: "client"`） |
| 依赖 | `ploceus.dependOslModule('branding', '0.24.0')` |

模块把"品牌字符串"抽象成若干**上下文**（`BrandingContext`），每个上下文各自维护一串**组件**（component）。每个组件由一个 `Operation` 决定如何作用在字符串上，并带一个 `priority` 决定先后顺序。mod 只需在启动时往对应上下文里挑一个唯一的 key 注册组件，OSL 在渲染标题界面与调试界面时把整条组件链跑一遍，拼出最终文本。

> 注意本模块**只影响文本**：1.12.2 上的挂钩点是标题界面渲染时的版本字符串与调试界面 `getGameInfo` 的结果。窗口标题、窗口图标、启动器显示名等**不在**本模块范围内（源码中没有对应挂钩点）。

## 事件

### `BrandingPatchEvents`

Reference: `net.ornithemc.osl.branding.api.BrandingPatchEvents`

**作用**：提供唯一的注册入口事件。游戏启动、客户端拿到 `Minecraft` 实例后立刻触发一次，把 `BrandingModifierRegistry` 交给所有监听器，mod 在这里注册自己的品牌组件。

**需要**：把监听器写进 mod 入口点（`init` / `client-init`）里；事件的回调只触发一次，晚于此时注册不会被 1.12.2 的标题界面/调试界面应用。

**返回**：无（事件对象本身只是容器，通过 `invoker()` 由 OSL 调用）。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `REGISTER_MODIFIER_COMPONENT` | 静态字段，类型 `Event<Consumer<BrandingModifierRegistry>>`；游戏启动时触发，用于注册品牌组件。用 `register(registry -> {...})` 挂监听器 | 必须在客户端初始化之前注册监听器；回调参数由 OSL 传入，不要自己 new | 无（事件无返回值） |

```java
BrandingPatchEvents.REGISTER_MODIFIER_COMPONENT.register(registry -> {
    registry.register(BrandingContext.ALL, "cookie", Operation.APPEND, "/Cookie");
    registry.register(BrandingContext.TITLE_SCREEN, "cookie-title", Operation.APPEND, " (yum)");
});
```

## 上下文与操作

### `BrandingContext`

Reference: `net.ornithemc.osl.branding.api.BrandingContext`

**作用**：枚举，指定"这条组件作用在哪个界面"。每个非 `ALL` 的常量在内部对应一份独立的组件表，因此同一段文本在不同界面可以被改得不一样。

**需要**：注册组件时作为第一个参数传入；查询/应用文本时用具体的上下文。

**返回**：枚举常量本身；`ALL` 只能用于注册，不能用于应用。

| 常量 | 含义 | 需要 | 返回 |
|---|---|---|---|
| `TITLE_SCREEN` | 启动后显示的标题界面：文字来自版本信息（如 `1.12.2`），挂在渲染上 | 注册组件时作为上下文，或作为 `BrandingPatch.apply` 的参数 | 枚举常量 |
| `DEBUG_OVERLAY` | 游戏中按 F3 显示的调试界面：文字来自 `getGameInfo` | 同上 | 枚举常量 |
| `ALL` | 上述全部上下文；注册时展开到每一个具体上下文 | **仅用于注册**。因为它本身没有组件表，把它交给 `apply` 会抛 `IllegalArgumentException` | 枚举常量 |

### `Operation`

Reference: `net.ornithemc.osl.branding.api.Operation`

**作用**：枚举，决定一条组件如何修改品牌字符串。内部把字符串维护成一个 `List<String>` 缓冲区，其中一个下标指向"原始部分"（即游戏自己给出的那段文本）。

**需要**：注册组件时选择；`apply` 由 OSL 在拼字符串时调用，mod 一般不需要手动调。

**返回**：`apply` 返回"原始部分"的新下标（`int`）。

| 常量 / 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `PREPEND` | 把 value 插到缓冲区最前面，并让原始部分下标后移 | value 非 null | — |
| `APPEND` | 把 value 追加到缓冲区末尾 | value 非 null | — |
| `REPLACE` | 把**原始部分**替换为 value | 缓冲区中必须存在原始部分下标 | — |
| `SET` | 语义为"整串替换"（见下方注意事项） | 缓冲区中必须存在原始部分下标 | — |
| `apply(List<String> buffer, int original, String value)` | 对缓冲区施加一次操作 | `buffer` 至少包含下标 `original`；`original` 为原始部分当前位置 | 原始部分的新下标 |

**注意事项（源码与注释不一致）**：`SET` 的注释写的是"用一个新值替换整个品牌字符串"，但 1.12.2 的实现实际是把缓冲区**清空后只留下原始部分**并返回下标 0 —— 传入的 `value` 完全没有被使用。使用 `SET` 前请在游戏里实测；如需"整串替换"，目前可靠的做法是 `REPLACE`。

## 注册表

### `BrandingModifierRegistry`

Reference: `net.ornithemc.osl.branding.api.BrandingModifierRegistry`

**作用**：组件注册表接口。由 OSL 实现并通过 `BrandingPatchEvents` 交给 mod，**mod 作者只调用、不实现**。

**需要**：只能使用事件回调里拿到的那个实例；组件 key 在"同一个上下文内"必须唯一。

**返回**：三个 `register` 都是 `void`，失败以异常或日志形式体现（见下表）。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `register(BrandingContext context, String key, Operation operation, String value)` | 最简注册，等价于 `priority = 0`、`required = true` | `key` 在该上下文内唯一 | 无（void） |
| `register(BrandingContext context, String key, Operation operation, String value, int priority)` | 带优先级的注册，`required = true` | 同上 | 无（void） |
| `register(BrandingContext context, String key, Operation operation, String value, int priority, boolean required)` | 完整注册 | 同上；`context` 为 `ALL` 时递归注册到每个具体上下文 | 无（void） |

**优先级与冲突语义**（源自实现）：

- `priority` 小的先应用；`priority` 相同时按注册先后顺序（先注册先应用）。
- 同一个 key 重复注册：`required = true` 时抛 `IllegalStateException`（消息含 key）；`required = false` 时只打警告并**忽略这次注册**。
- `REPLACE` / `SET` 之间互斥：如果已存在一个 `REPLACE` 或 `SET` 组件，新注册的同类组件视为冲突。已存在的是 `required` 时，新注册失败（`required` 抛 `IllegalStateException`，否则警告并忽略）；已存在的不是 `required` 时，旧组件被移除、新的生效。

## 应用入口

### `BrandingPatch`

Reference: `net.ornithemc.osl.branding.api.BrandingPatch`

**作用**：手动把当前上下文里的组件链作用到一段文本上。正常游戏流程里 OSL 自己会调；当你在别处（自定义界面、日志、导出）想复用同一套品牌文本时用它。

**需要**：`context` 必须是具体上下文（`TITLE_SCREEN` / `DEBUG_OVERLAY`）；`s` 是原始文本，通常就是游戏原本会显示的那段。

**返回**：修饰后的字符串（`String`）。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `apply(BrandingContext context, String s)` | 依次应用该上下文的全部组件，拼接后返回 | `context` 不能是 `ALL`；`s` 不应为 null（源码未判空） | 修饰后的字符串；`context` 为 `ALL` 时抛 `IllegalArgumentException`；某个组件抛异常时包成 `RuntimeException` 抛出 |

## 与 1.12.2 原版的交互（读懂行为需要）

- 原版标题界面在版本类型不是 `release` 时会自己拼 `/版本类型`。OSL 把 `Minecraft.getVersionType()` 的结果固定成 `release`，改为在启动时检查 `--versionType` 运行参数：只要它存在且不等于 `release`，就先自己注册一条 `APPEND` 组件 `"/" + versionType`（key 为 `OSL|VersionType`，`required = true`）。因此**如果你也注册一条 `required = true` 的同 key 组件，会直接抛异常**。
- 该内置组件通过 `BrandingContext.ALL` 注册，所以标题界面和 F3 界面都会出现 `/版本类型`。
- `REGISTER_MODIFIER_COMPONENT` 触发的时刻在 `Minecraft` 初始化开始（`MinecraftClientEvents.START`）时，早于标题界面第一次渲染。
