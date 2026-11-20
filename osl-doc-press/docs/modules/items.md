---
title: 15 items
---

# 15 items

> 一句话定位：给 1.12.2 的物品注册表加一个公开入口——注册物品、给方块自动配 `BlockItem`、查询物品 ID 与名字。

| 项 | 值 |
|---|---|
| 模块 id | `items` |
| Maven | `net.ornithemc.osl-gen2:items:0.3.2+mc14w26a-mc17w46a` |
| 端 | 双端 |
| 依赖 | `ploceus.dependOslModule('items', '0.24.0')` |
| 依赖的 OSL 模块 | `core`, `entrypoints`, `registries`, `blocks` |

原版 1.12.2 的物品注册表（`Item.REGISTRY`）只在 `Item.init` 内部开放，而且"方块对应的物品"还有一张单独的 `block → item` 表要维护，很容易漏。本模块把注册表包装成 OSL 的 `Registry<Item>`，在原版物品注册完成后抛出 `ItemEvents.REGISTER_ITEMS`，并提供几个便利重载把 `BlockItem` 和那张表一起处理好。物品注册表也已登记进 ID 同步（含统计数组与客户端模型/颜色缓存），数字 ID 会自动对齐。

## 事件

### `ItemEvents`

Reference: `net.ornithemc.osl.items.api.ItemEvents`

**作用**：物品生命周期的唯一事件——原版物品注册完成之后触发，是注册自定义物品（含 `BlockItem`）的正确时机。

**需要**：在 mod 的 entrypoint 里静态注册回调；如果物品要引用你刚注册的方块，注意方块注册事件在物品之前发生（`BlockItem` 依赖方块），轮到本事件时方块通常已经注册完毕。

**返回**：无（`void`）。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `REGISTER_ITEMS` | 原版物品注册完成后触发（据实现，注入在 `Item.init` 的末尾） | 回调里调用 `ItemRegistry.register(...)`；此时注册表已解锁、尚未冻结 | 无（`void`） |

```java
ItemEvents.REGISTER_ITEMS.register(() -> {
    ItemRegistry.register(NamespacedIdentifiers.from("example", "cookie"), new CookieItem());
    ItemRegistry.register(ExampleBlocks.COOKIE_BLOCK); // 自动造 BlockItem
});
```

## 注册表

### `ItemRegistry`

Reference: `net.ornithemc.osl.items.api.ItemRegistry`

**作用**：物品注册表的静态门面，同时暴露 `REGISTRY` 字段。数字 ID 由注册顺序决定，名字是 namespaced ID。与方块不同，这里的 `REGISTRY` 是**不带默认值**的普通注册表：查不到就是 `null`。

**需要**：`register` 只能在 `Item` 类初始化之后、注册表冻结之前调用（即 `REGISTER_ITEMS` 回调里）。太早调用抛 `IllegalStateException("register called too early: registry locked!")`；冻结后注册抛 `IllegalStateException("registry is frozen!")`；名字或对象重复注册同样抛 `IllegalStateException`。

**返回**：注册方法返回注册后的物品；查询方法见下表（`getId` 未命中返回 `-1`，其余未命中返回 `null`）。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `REGISTRY` | 物品注册表实例 | 只读使用；写入请走 `register` | `Registry<Item>` |
| `register(Block block)` | 给方块造一个默认 `BlockItem` 并注册 | 时机见上；`block` 必须**已注册**（物品名字取自方块注册表，取不到名字时行为未定义，源码未明确说明） | `BlockItem` |
| `register(T item)`（`T extends BlockItem`） | 注册你自己写的 `BlockItem` 子类，名字取自它关联的方块 | 同上 | 注册后的物品 |
| `register(Block block, T item)` | 把任意物品注册为"某个方块的物品"，同时登记到原版的 `block → item` 表 | 同上；这样 `ItemRegistry.getItem(block)` / `Item.byBlock` 才能取到它 | 注册后的物品 |
| `register(NamespacedIdentifier identifier, T item)` | 用名字注册普通物品 | 时机见上；名字唯一 | 注册后的物品 |
| `register(ResourceKey<Item> key, T item)` | 用资源键注册普通物品 | 同上；实际只取 `key.identifier()` | 注册后的物品 |
| `register(int id, NamespacedIdentifier key, T item)` | **（已废弃，请改用 `register(NamespacedIdentifier, Item)` 或 `register(ResourceKey, Item)`）** 手动指定数字 ID | 同上；`id` 不能与已有物品冲突 | 注册后的物品 |
| `getId(Item item)` | 查物品的数字 ID | 物品已注册 | `int`；未注册返回 `-1` |
| `getIdentifier(Item item)` / `getKey(Item item)` | 查物品的名字 / 资源键 | 同上 | `NamespacedIdentifier` / `ResourceKey<Item>`；未注册返回 `null` |
| `getItem(int id)` | 按数字 ID 查物品 | — | `Item` 或 `null` |
| `getItem(NamespacedIdentifier identifier)` / `getItem(ResourceKey<Item> key)` | 按名字查物品 | — | `Item` 或 `null` |
| `getItem(Block block)` | 查某个方块对应的物品（原版 `Item.byBlock`） | 方块须有对应物品 | `Item` 或 `null` |
| `identifierSet()` / `keySet()` | 全部名字 / 全部资源键 | — | `Set` |

**翻译键**：物品第一次调用 `getTranslationKey()` 时，如果没有名字键，OSL 会按注册名生成 `<namespace>.<path>`（`/` → `.`），例如 `example.cookie`；查不到注册名时用 `unknown`。语言文件直接写 `example.cookie=Cookie` 即可。

**ID 同步**：本模块已经把物品注册表登记进同步，并内置了统计数组搬运工（`stats/crafted`、`stats/used`、`stats/broken`、`stats/picked_up`、`stats/dropped`）以及客户端侧的颜色表、模型位置表、模型缓存搬运工。注册物品时不需要你自己处理同步。
