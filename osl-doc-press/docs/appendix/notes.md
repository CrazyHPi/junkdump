---
title: 附录 A　注意事项与已知缺陷
---

# 附录 A　逐模块注意事项与已知缺陷

写 1.12.2 mod 时最容易踩的坑集中在这里。每条都基于源码实现，并标出它影响哪个 API。

## 通用

- **事件注册要早**：所有 `Event` 都是「注册即入队」，触发时才遍历。入口点（`init` / `client-init` / `server-init`）里注册最稳妥；事件没有优先级、没有取消、没有注销。
- **事件不吞异常**：监听器抛出的异常会直接向游戏主循环冒泡，请自行 try/catch。
- **`Event` 的短路语义有坑**（core）：只有 `triFunctionFirstNonNull` / `triFunctionAnyNonNull` 真正做了 `filter(Objects::nonNull)`；其余 `...First` / `...Any`（包括名字带 NonNull 的两参数版本，实现与不带 NonNull 的完全相同）都不过滤 `null`，一旦被取到的返回值是 `null`，`findFirst()` / `findAny()` 就会抛 `NullPointerException`。写取值型监听器时要么永远返回非 null，要么改用三参的 `triFunction*NonNull`，要么自己用 `Event.of` 实现过滤。

## 01 core

- `SimpleIdRegistry` / `DefaultedIdRegistry` / `IdBiMap` 已废弃，请改用 `registries` 模块的 `Registries` / `WritableRegistry` / `DefaultedRegistry` / `IdMap`。
- `BlockPos.pack` 是本模块自定义的位布局（y 取低位），不要与原版 `BlockPos` 的长整型表示互换。

## 04 blockstates

- 在 **1.12.2** 子工程里，`BlockExtension` 只有 `isAir()` 一个方法；`buildStateDefinition` 之类的钩子只存在于更早版本的子工程。也就是说属性/状态体系在 1.12.2 上**没有自动接到 `Block`**，需要自己把 `State` 映射到 metadata。
- `libraries/blockstates/README.md` 里的 `StatefulBlock` 示例是旧版用法，对 1.12.2 不适用。

## 07 branding

- 本模块只作用于**文本品牌串**（标题界面的版本信息、F3 调试界面的游戏信息），不会修改窗口标题或图标。

## 08 commands

- `ArgumentTypes.init()` 与 `EntitySelectorOptions.init()` 在 1.12.2 子工程中没有调用点：参数类型的网络注册表与 `@e[选项]` 默认不生效，需要 mod 自己在合适时机调用一次。
- `ItemParser` / `BlockStateParser` 的 `allowTag` 被硬编码为 `false`（源码留了 TODO），因此 `#标签` 语法在 1.12.2 不可用。
- `CommandSourceStack.requestSuggestions` 直接返回 `null`（源码未说明原因），客户端补全需走 `ClientPlayNetworkHandlerExtension`。

## 09 config

- 只提供**序列化能力**，没有自动网络同步：全模块没有 `forNetwork()` 调用点，也不会自己发包。
- JSON 侧没有为 `Identifier` / `BlockPos` 注册对象序列化器（NBT / 网络侧有），用这两个选项写 JSON 会在序列化时 NPE。
- 没有"配置变更"事件或回调。

## 13 entrypoints

- `fabric.mod.json` 里的键名是字面量 `init` / `client-init` / `server-init`（无命名空间前缀）。
- 客户端在 `Main.main` 开头调用 `init` → `client-init`；服务端在 `MinecraftServer.main` 开头调用 `init` → `server-init`。此时游戏实例还不存在。

## 16 keybinds

- `Keybind*` 与 `KeyBinding*` 是**两代 API**，后者已 `@Deprecated`。两者在同一注入点触发（`GameOptions` 构造、`load()` 之前），旧事件先执行。

## 17 lifecycle-events

- 只有 tick 与世界加载/关闭；**没有**世界卸载、玩家连接/断开、资源包重载、语言切换事件。需要时只能自己写 mixin 或轮询 tick。
- `MinecraftInstance.get()` / `MinecraftServerInstance.get()` 在实例被清空后会抛 `IllegalStateException`。

## 19 networking

- 通道名上限 255 字符（原版为 20）；负载长度没有任何检查，实际受 Minecraft 自身包长限制。
- 监听器**默认在网络线程**执行；`ensureOnMainThread()` 会让 OSL 重投递到主线程并**再次**调用回调。
- 对端没有安装 OSL 时，`send` 会静默丢弃（握手阶段交换的通道表里没有该通道）。

## 20 registries

- 数字 ID 由注册顺序决定，所以必须靠 ID 同步让两端一致；正常使用 `blocks` / `items` / `biomes` / `entities` 时同步已由这些模块代做，一般不必直接碰 `registry.sync`。

## 21 resource-loader

- 1.12.2 子工程是客户端环境：`ServerResourceLoaderEvents` 不会触发，`server()` 相关 API 在 1.12.2 没有实际接线。
- 多个同为 `required` + `BOTTOM` 的资源包之间没有稳定顺序，不要依赖它们之间的相对优先级。

## 22 text-components

- 没有独立的 `Action` 类型：只有 `ClickEvent.Action`（4 个值）与 `HoverEvent.Action`（只有 `SHOW_TEXT`）。
- 客户端与服务端共用同一份文本模型（不存在"两套同名类"），也没有仅客户端的文本类型。
- `TextComponents.resolve` 按"确切运行时类"查找：直接把 `TextComponent` 传进去通常只会得到它的 `toString()`。

---

