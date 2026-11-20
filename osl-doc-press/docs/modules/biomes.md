---
title: 02 biomes
---

# 02 biomes

> 一句话定位：给 1.12.2 的生物群系注册表加一个公开入口——注册自己的群系，并给"派生/变体群系"声明父群系。

| 项 | 值 |
|---|---|
| 模块 id | `biomes` |
| Maven | `net.ornithemc.osl-gen2:biomes:0.1.1+mc16w02a-mc18w05a` |
| 端 | 双端 |
| 依赖 | `ploceus.dependOslModule('biomes', '0.24.0')` |
| 依赖的 OSL 模块 | `core`, `entrypoints`, `registries`, `localization` |

原版 1.12.2 的生物群系注册表只对内部开放，注册时机也卡得很死（`Biome` 类静态初始化时一次性建好）。本模块把这张表包装成 OSL 注册表，在 `Biome` 类初始化末尾抛出 `BiomeEvents.REGISTER_BIOMES`，于是你可以在那里登记自己的群系，并借助 `BiomeSettings` 构造原版风格的群系参数。它同时把这个注册表登记进了 ID 同步，所以客户端与服务端的生物群系数字 ID 会自动对齐。

## 事件

### `BiomeEvents`

Reference: `net.ornithemc.osl.biomes.api.BiomeEvents`

**作用**：生物群系生命周期的唯一事件——原版群系全部注册完成之后触发，是注册自定义群系的正确时机。

**需要**：在 mod 的 entrypoint 里静态注册回调（`BiomeEvents.REGISTER_BIOMES.register(() -> { ... })`）；回调里**不要**再触发类加载导致的注册表重入（例如在尚未完成初始化时提前访问 `Biome` 的静态成员）。

**返回**：无（`void`）。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `REGISTER_BIOMES` | 原版群系注册完成后触发（据实现，挂在 `Biome` 类静态初始化的末尾） | 回调里调用 `BiomeRegistry.register(...)`；此时注册表已解锁，未冻结 | 无（`void`） |

```java
BiomeEvents.REGISTER_BIOMES.register(() -> {
    BiomeRegistry.register(NamespacedIdentifiers.from("example", "cookie_fields"), new CookieFieldsBiome());
});
```

## 注册表

### `BiomeRegistry`

Reference: `net.ornithemc.osl.biomes.api.BiomeRegistry`

**作用**：生物群系注册表的静态门面（没有公开的 `REGISTRY` 字段，全部通过静态方法访问）。数字 ID 由注册顺序决定，名字是 namespaced ID。

**需要**：`register` 必须在 `Biome` 类已经初始化之后调用——也就是在 `REGISTER_BIOMES` 的回调里。太早调用会抛 `IllegalStateException("register called too early: registry locked!")`；注册表冻结后再注册同样会抛 `IllegalStateException`。名字在同一注册表内必须唯一（同名会抛 `IllegalStateException`）。

**返回**：注册方法返回传入的群系对象本身；查询方法在未命中时返回 `null`（`getId` 返回 `-1`）。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `register(NamespacedIdentifier identifier, T biome)` | 用名字注册群系（ID 自动分配） | 时机见上；`biome` 不能被重复注册 | 注册后的群系 |
| `register(ResourceKey<Biome> key, T biome)` | 用资源键注册群系 | 同上；实际只取 `key.identifier()`（注册表部分不做校验，源码未明确说明） | 注册后的群系 |
| `getId(Biome biome)` | 查群系的数字 ID | 群系已注册 | `int`；未注册返回 `-1` |
| `getIdentifier(Biome biome)` / `getKey(Biome biome)` | 查群系的名字 / 资源键 | 同上 | `NamespacedIdentifier` / `ResourceKey<Biome>`；未注册返回 `null` |
| `getBiome(int id)` | 按数字 ID 查群系 | `id` ≥ 0 | `Biome` 或 `null` |
| `getBiome(NamespacedIdentifier identifier)` / `getBiome(ResourceKey<Biome> key)` | 按名字查群系 | 名字须在本注册表内 | `Biome` 或 `null` |
| `identifierSet()` / `keySet()` | 全部名字 / 全部资源键 | — | `Set` |

注册表本身已经由本模块包好（键 `minecraft:biome`）并登记进 ID 同步，因此**不需要**你自己再调用 `SyncedRegistries`。

## 群系设置与扩展

### `BiomeSettings`

Reference: `net.ornithemc.osl.biomes.api.biome.BiomeSettings`

**作用**：构造原版 `net.minecraft.world.biome.Biome.Settings`（群系参数构造器：深度、尺度、温度、降水、类别等）。相比 `new Biome.Settings(name)`，这里故意不传显示名，让 OSL 在注册后按注册名自动生成名字与翻译键。

**需要**：通常作为自定义 `Biome` 子类的 `super(...)` 参数使用；想在客户端显示中文/自定义名字时，用 `localization` 模块提供 `biome.<namespace>.<path>` 这个翻译键即可（不提供也有一个由注册名生成的回退名）。

**返回**：可继续链式配置的 `Biome.Settings` 实例。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `builder()` | 新建一个不带显示名的群系设置构造器 | 无；客户端会据注册名自动生成 legacy 名（`LegacyStringIds` 风格）与翻译键 `biome.<namespace>.<path>` | `Biome.Settings` |

### `BiomeExtension`

Reference: `net.ornithemc.osl.biomes.api.biome.BiomeExtension`

**作用**：给 `Biome.Settings` 补上"父群系"这个概念，用来创建**变体群系**（类似原版的 mutated 群系：以某个已有群系为模板派生出来的群系）。接口本身没有顶层方法，真正可用的是嵌套的 `BiomeExtension.SettingsExtension`。

**需要**：`Biome.Settings` 由 OSL 的 mixin 实现了 `SettingsExtension`，所以你要把 `Biome.Settings` 实例强转成 `BiomeExtension.SettingsExtension` 再调用；父群系必须是**已经注册过的**群系名，否则注册变体群系时会抛 `IllegalStateException("Error registering mutated biome ...: parent ... does not exist!")`。

**返回**：见下表。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `BiomeExtension.SettingsExtension#parent(NamespacedIdentifier identifier)` | 声明本群系派生自哪个群系（写进设置的 `parent` 字段） | 群系实现由 OSL 提供；`identifier` 是父群系的注册名，且注册父群系的顺序要在本群系之前 | 传入的 `Biome.Settings` 本身（可链式调用） |

```java
Biome.Settings settings = BiomeSettings.builder();
// 声明派生自平原：注册时会记下"变体 → 父群系 ID"的关系
((BiomeExtension.SettingsExtension) settings).parent(NamespacedIdentifiers.from("minecraft", "plains"));
BiomeRegistry.register(NamespacedIdentifiers.from("example", "cookie_plains"), new CookiePlainsBiome(settings));
```

一旦设置了父群系，注册时 OSL 会把这个群系登记进原版的"变体群系 → 父群系 ID"表；这张表也参与 ID 同步，所以父群系的数字 ID 变化会被一并重排，你不需要自己处理。
