---
title: 03 blocks
---

# 03 blocks

> 一句话定位：给 1.12.2 的方块注册表加一个公开入口——注册自己的方块、查询方块 ID 与名字，并在注册后自动补上翻译键。

| 项 | 值 |
|---|---|
| 模块 id | `blocks` |
| Maven | `net.ornithemc.osl-gen2:blocks:0.3.1+mc15w36a-mc17w46a` |
| 端 | 双端 |
| 依赖 | `ploceus.dependOslModule('blocks', '0.24.0')` |
| 依赖的 OSL 模块 | `core`, `entrypoints`, `blockstates`, `registries` |

原版 1.12.2 的 `Block.REGISTRY` 是内部结构，注册时机也只开在 `Block.init` 里。本模块把这张表包装成 OSL 的 `DefaultedRegistry<Block>`，在原版方块全部注册完成之后抛出 `BlockEvents.REGISTER_BLOCKS`，让你在那里登记自己的方块。注册表同时被登记进 ID 同步（含方块状态表、挖掘统计数组、客户端方块颜色表），所以数字 ID 会在客户端与服务端、存档之间自动对齐。

## 事件

### `BlockEvents`

Reference: `net.ornithemc.osl.blocks.api.BlockEvents`

**作用**：方块生命周期的唯一事件——原版方块注册完成之后触发，是注册自定义方块的正确时机。

**需要**：在 mod 的 entrypoint 里静态注册回调；回调里只做注册与静态初始化，不要访问尚未就绪的世界/客户端状态。

**返回**：无（`void`）。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `REGISTER_BLOCKS` | 原版方块注册完成后触发（据实现，注入在 `Block.init` 中原版注册表校验之前） | 回调里调用 `BlockRegistry.register(...)`；此时注册表已解锁、尚未冻结 | 无（`void`） |

```java
BlockEvents.REGISTER_BLOCKS.register(() -> {
    BlockRegistry.register(NamespacedIdentifiers.from("example", "cookie_block"), new CookieBlock());
});
```

## 注册表

### `BlockRegistry`

Reference: `net.ornithemc.osl.blocks.api.BlockRegistry`

**作用**：方块注册表的静态门面，同时直接暴露 `REGISTRY` 字段方便遍历/读取。数字 ID 由注册顺序决定，名字是 namespaced ID；`REGISTRY` 是**带默认值**的注册表（`DefaultedRegistry`），因此查询未命中的行为由原版的「默认条目」机制决定，而不是一律返回 `null`。

**需要**：`register` 只能在 `Block` 类初始化之后、注册表冻结之前调用——也就是在 `REGISTER_BLOCKS` 回调里。太早调用抛 `IllegalStateException("register called too early: registry locked!")`；冻结后注册抛 `IllegalStateException("registry is frozen!")`；名字或对象重复注册同样抛 `IllegalStateException`。

**返回**：注册方法返回传入的方块本身；查询方法见下表。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `REGISTRY` | 方块注册表实例 | 只读使用；写入请走 `register` | `DefaultedRegistry<Block>` |
| `register(NamespacedIdentifier identifier, T block)` | 用名字注册方块（数字 ID 自动分配） | 时机见上；名字唯一 | 注册后的方块 |
| `register(ResourceKey<Block> key, T block)` | 用资源键注册方块 | 同上；实际只取 `key.identifier()` | 注册后的方块 |
| `register(int id, NamespacedIdentifier key, T block)` | **（已废弃，请改用不带 `id` 的重载）** 手动指定数字 ID | 同上；`id` 不能与已有方块冲突 | 注册后的方块 |
| `getId(Block block)` | 查方块的数字 ID | 方块已注册 | `int`；未注册返回 `-1` |
| `getIdentifier(Block block)` / `getKey(Block block)` | 查方块的名字 / 资源键 | 同上 | 未注册方块的返回值取决于原版 `DefaultedIdRegistry` 的回退行为（源码未明确说明） |
| `getBlock(int id)` | 按数字 ID 查方块 | — | 查不到时由原版默认值机制回落（通常是空气；源码未明确说明具体范围） |
| `getBlock(NamespacedIdentifier identifier)` / `getBlock(ResourceKey<Block> key)` | 按名字查方块 | — | 同上 |
| `identifierSet()` / `keySet()` | 全部名字 / 全部资源键 | — | `Set` |

**翻译键**：如果方块自己没有设置过名字键（原版字段为空），OSL 会在第一次调用 `getTranslationKey()` 时按注册名生成 `<namespace>.<path>`（路径里的 `/` 换成 `.`），例如 `example.cookie_block`；连注册名都查不到时用 `unknown`。因此你的语言文件直接写 `example.cookie_block=Cookie Block` 即可。

**ID 同步**：本模块已经把方块注册表登记进同步，并内置了三样东西：方块状态表的修补器（按"方块 ID + metadata"重新生成状态 ID）、`stats/mined` 统计数组搬运工（双端）、客户端方块颜色表的搬运工。你注册方块时不需要额外做什么。
