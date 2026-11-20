---
title: 16 keybinds
---

# 16 keybinds

> 一句话定位：在游戏设置里注册自己的按键，并保证玩家的自定义按键绑定能被正确保存与恢复。

| 项 | 值 |
|---|---|
| 模块 id | `keybinds` |
| Maven | `net.ornithemc.osl-gen2:keybinds:0.3.0+mc17w16a-mc1.12.2` |
| 端 | 仅客户端（`environment: "client"`） |
| 依赖 | `ploceus.dependOslModule('keybinds', '0.24.0')` |

1.12.2 原版把按键列表放在 `GameOptions.keyBindings` 里，构造设置时一次性建好，之后没有公开的扩展点，所以 mod 只能靠反射/ASM。本模块在 `GameOptions` 构造、读取 `options.txt` **之前**插入一次回调，让你把按键加进那份数组；因为早于读取，玩家上一次设置的键位能被原版正常匹配回来。

## 两套命名（新 API 与旧 API）

本模块的 api 包里同时存在 `Keybind*` 与 `KeyBinding*` 两组类型，**它们不是别名，而是两代 API**：

| 类型 | 状态 | 说明 |
|---|---|---|
| `KeybindEvents` / `KeybindRegistry` | 现行 API | 事件是 `Event<Runnable>`，注册用静态方法 `KeybindRegistry.register(...)` |
| `KeyBindingEvents` / `KeyBindingRegistry` | **（已废弃，请改用 `KeybindEvents` / `KeybindRegistry`）** | 事件是 `Event<Consumer<KeyBindingRegistry>>`，注册通过回调参数里的注册表实例 |

两者指向**同一份**注册表实现，且在同一个注入点触发：旧事件先触发，新事件紧随其后，最后一起写进 `GameOptions.keyBindings`。因此新代码只监听 `KeybindEvents` 即可；同时监听两个不会重复注册（除非你两边都 `register`）。

## 事件

### `KeybindEvents`

Reference: `net.ornithemc.osl.keybinds.api.KeybindEvents`

**作用**：注册按键的推荐入口。游戏启动、构造 `GameOptions` 时触发一次（早于读取 `options.txt`），此时应调用 `KeybindRegistry.register(...)` 把按键加进去。

**需要**：在 mod 入口点（`init`/`client-init`）里 `register` 监听器；监听器本身是 `Runnable`，无参数。

**返回**：无（事件无返回值，也不传递注册表——用静态的 `KeybindRegistry`）。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `REGISTER_KEYBINDS` | 静态字段，类型 `Event<Runnable>` | 必须在 `GameOptions` 构造完成前注册监听器（即入口点里）；只触发一次，之后注册的监听器不会再被调用 | 无（事件无返回值） |

```java
KeybindEvents.REGISTER_KEYBINDS.register(() -> {
    KeybindRegistry.register("key.example.cookie", Keyboard.KEY_Z, "key.categories.example");
});
```

### `KeyBindingEvents`

Reference: `net.ornithemc.osl.keybinds.api.KeyBindingEvents`

**作用**：（已废弃，请改用 `KeybindEvents`）旧版注册入口，回调里给出一个 `KeyBindingRegistry` 实例。

**需要**：同上，在入口点里注册监听器；回调参数由 OSL 传入。

**返回**：无（事件无返回值）。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `REGISTER_KEYBINDS` | 静态字段，类型 `Event<Consumer<KeyBindingRegistry>>` | 与 `KeybindEvents.REGISTER_KEYBINDS` 在同一注入点触发，但**先于**它 | 无（事件无返回值） |

## 注册表

### `KeybindRegistry`

Reference: `net.ornithemc.osl.keybinds.api.KeybindRegistry`

**作用**：现行 API 的注册工具类（全是静态方法），在 `KeybindEvents.REGISTER_KEYBINDS` 回调里使用。

**需要**：在事件触发期间调用（或至少在 `GameOptions` 存在之后，见下方"兜底路径"）；`name` / `category` 可以直接给翻译键（源码注释如此），这样设置界面会显示本地化名称。

**返回**：注册后的 `net.minecraft.client.options.KeyBinding`。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `getCategories()` | 取当前所有按键分类 | 返回的是原版分类集合本身（不是副本）；事件触发前为 `null` | `Set<String>` |
| `register(String name, int defaultKeyCode, String category)` | 新建并注册一个按键；等价于 `register(new KeyBinding(name, defaultKeyCode, category))` | `defaultKeyCode` 用 1.12.2 的 LWJGL2 键码（`org.lwjgl.input.Keyboard.KEY_*`，`KEY_NONE` 表示默认不绑定）；`category` 会顺带登记进分类表 | 传入/新建的 `KeyBinding` 实例 |
| `register(KeyBinding keybind)` | 注册一个已经建好的按键 | `keybind` 非 null；同一个实例不要重复注册 | 同一个 `KeyBinding` 实例 |

**行为细节**：

- 新分类会被加入原版分类集合与排序表，排序值取"当前数量 + 1"，即**新分类排在列表最后**。
- 事件触发期间注册的按键先进入待定列表，事件结束后一次性追加到 `GameOptions.keyBindings`。
- **兜底路径**：如果在事件之后（`GameOptions` 已存在）才调用 `register`，会直接把按键追加到 `options.keyBindings`（实现上按数组拼接），源码注释称之为"手动追加"。这种按键仍然可用，但注册得越晚越容易碰上界面/配置已经初始化完的情况，**建议始终在事件里注册**。

### `KeyBindingRegistry`

Reference: `net.ornithemc.osl.keybinds.api.KeyBindingRegistry`

**作用**：（已废弃，请改用 `KeybindRegistry`）旧版注册表接口，实例只在 `KeyBindingEvents.REGISTER_KEYBINDS` 回调里由 OSL 提供，**mod 作者只调用、不实现**。

**需要**：只能使用回调参数给的实例；生命周期仅限回调期间。

**返回**：两个 `register` 都返回注册后的 `KeyBinding`。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `register(String name, int defaultKeyCode, String category)` | 新建并注册按键 | 同 `KeybindRegistry.register(String, int, String)` | `KeyBinding` |
| `register(KeyBinding keybind)` | 注册已有按键 | 同 `KeybindRegistry.register(KeyBinding)` | `KeyBinding` |

## 使用按键

本模块只负责**注册**，不提供按键状态的查询。注册之后用原版方式读状态即可：

```java
private static KeyBinding cookieKey; // 在 KeybindEvents 里赋值

// 在客户端 tick（如 MinecraftClientEvents.TICK_END）里查询
while (cookieKey.wasPressed()) { /* ... */ }
if (cookieKey.isPressed()) { /* 按住 */ }
```

> 1.12.2 说明：按键状态由原版在客户端 tick 中维护，因此查询放在客户端 tick 事件里（如 `MinecraftClientEvents.TICK_END`）、并且只在客户端主线程访问。
