---
title: 11 entities
---

# 11 entities

> 一句话定位：给 1.12.2 的实体类型注册表加一个公开入口——注册实体类型、拿到可创建实体的工厂，并顺带处理实体名、刷怪蛋和旧存档的 ID 修复。

| 项 | 值 |
|---|---|
| 模块 id | `entities` |
| Maven | `net.ornithemc.osl-gen2:entities:0.1.3+mc16w32a-mc18w01a` |
| 端 | 双端 |
| 依赖 | `ploceus.dependOslModule('entities', '0.24.0')` |
| 依赖的 OSL 模块 | `core`, `entrypoints`, `registries` |

原版 1.12.2 的实体类型注册表（`Entities.REGISTRY`）在 `Entities` 类静态初始化时一次性填好，同时维护一张按数字 ID 索引的实体名列表，两者都不对外开放。本模块把注册表包装成 OSL 的 `Registry<EntityType<?>>`，在原版实体全部注册完成后抛出 `EntityEvents.REGISTER_ENTITY_TYPES`；注册时它会把你的实体类登记进原版注册表与实体名列表，并让数据修复表认识你生成的老式 ID。实体类型注册表同样已登记进 ID 同步。

> 注：`net.ornithemc.osl.entities.api.client` 包属于 **entities-rendering** 模块（仅客户端），不在本章范围内。

## 事件

### `EntityEvents`

Reference: `net.ornithemc.osl.entities.api.EntityEvents`

**作用**：实体类型生命周期的唯一事件——原版实体注册完成之后触发，是注册自定义实体类型的正确时机。

**需要**：在 mod 的 entrypoint 里静态注册回调；回调里不要触发 `Entities` 的重新初始化一类操作。

**返回**：无（`void`）。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `REGISTER_ENTITY_TYPES` | 原版实体注册完成后触发（据实现，注入在 `Entities` 类静态初始化的末尾） | 回调里调用 `EntityTypeRegistry.register(...)`；此时注册表已解锁、尚未冻结 | 无（`void`） |

```java
EntityEvents.REGISTER_ENTITY_TYPES.register(() -> {
    EntityType<CookieMonsterEntity> type = EntityTypeRegistry.register(
        NamespacedIdentifiers.from("example", "cookie_monster"),
        EntityTypes.builder(CookieMonsterEntity.class, CookieMonsterEntity::new));
    EntityTypeRegistry.registerSpawnEgg(type, 0x8B4513, 0xFFFFFF);
});
```

## 注册表

### `EntityTypeRegistry`

Reference: `net.ornithemc.osl.entities.api.EntityTypeRegistry`

**作用**：实体类型注册表的静态门面，同时暴露 `REGISTRY` 字段。数字 ID 就是原版实体 ID（注册时取原版注册表的下一个空位），名字是 namespaced ID；此外还维护"老式字符串 ID"（如 `CookieMonster`、`example.CookieMonster`）与实体类型之间的对应关系，供原版按名字查实体类的逻辑使用。

**需要**：`register` 只能在 `Entities` 类初始化之后、注册表冻结之前调用（即 `REGISTER_ENTITY_TYPES` 回调里）。太早调用抛 `IllegalStateException("register called too early: registry locked!")`；冻结后注册抛 `IllegalStateException("registry is frozen!")`；名字或对象重复注册抛 `IllegalStateException`。若算出的数字 ID 在原版实体名列表里已有值，注册会抛 `IllegalStateException("Name for entity type ... was already set (...)")`。

**返回**：注册方法返回构建好的 `EntityType<T>`；查询方法见下表（`getId` 未命中返回 `-1`，其余未命中返回 `null`）。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `REGISTRY` | 实体类型注册表实例 | 只读使用；写入请走 `register` | `Registry<EntityType<?>>` |
| `register(NamespacedIdentifier identifier, EntityType.Builder<T> type)` | 用名字注册实体类型（会调用 `type.build()`） | 时机见上；名字唯一；实体类需能被原版注册表接受 | `EntityType<T>` |
| `register(ResourceKey<EntityType<?>> key, EntityType.Builder<T> type)` | 用资源键注册实体类型 | 同上；实际只取 `key.identifier()` | `EntityType<T>` |
| `registerSpawnEgg(EntityType<?> type, int baseColor, int spotsColor)` | 为已注册的实体类型登记一个刷怪蛋的外观数据 | `type` 必须已注册；同一 identifier 不能重复登记；必须在冻结前调用（1.12.2 有刷怪蛋数据注册表，故可用；更高版本会抛 `UnsupportedOperationException`） | 无（`void`）；不满足条件时抛 `IllegalArgumentException` |
| `getId(EntityType<?> type)` | 查实体类型的数字 ID | 已注册 | `int`；未注册返回 `-1` |
| `getIdentifier(EntityType<?> type)` / `getKey(EntityType<?> type)` | 查实体类型的名字 / 资源键 | 同上 | 未注册返回 `null` |
| `getLegacyId(Class<? extends Entity> type)` | 查实体类对应的老式字符串 ID（写进原版实体名列表的那个） | 实体类已通过本模块或原版注册 | `String`；未注册返回 `null` |
| `getEntityType(int id)` | 按数字 ID 查实体类型 | — | `EntityType<?>` 或 `null` |
| `getEntityType(NamespacedIdentifier identifier)` / `getEntityType(ResourceKey<EntityType<?>> key)` | 按名字查实体类型 | — | `EntityType<?>` 或 `null` |
| `getEntityType(String legacyId)` | 按老式字符串 ID 查实体类 | `legacyId` 形如 `CookieMonster` / `example.CookieMonster` | `Class<? extends Entity>` 或 `null` |
| `identifierSet()` / `keySet()` / `legacyIdSet()` | 全部名字 / 全部资源键 / 全部老式 ID | — | `Set` |

**老式 ID 从哪来**：原版实体自带其历史名字（如 `Creeper`），原样复用；你注册的自定义类型没有历史名字，OSL 按注册名生成——`example:cookie_monster` → `example.CookieMonster`（`minecraft` 命名空间会被省略）。这个名字会写进原版实体名列表，并被数据修复表使用，所以旧版本存档里按名字存的实体在升级后仍能对上。

**ID 同步**：实体类型注册表已登记同步，原版实体名列表这一个"以 ID 为下标"的结构也挂好了搬运工；旧存档的数据修复表里会自动补上你的实体从老式 ID 到 namespaced ID 的映射。你注册实体类型时不需要额外处理同步。

## 实体类型

### `EntityType`

Reference: `net.ornithemc.osl.entities.api.entity.EntityType`

**作用**：一个"实体类型"的抽象：知道实体类是什么、显示名用什么翻译键、怎么在世界里造一个新实例。`EntityTypeRegistry` 里存的就是它。

**需要**：不要直接实现它，用 `EntityTypes.builder(...)`（或 `EntityType.Builder.of(...)`）构造；拿到实例后交给 `EntityTypeRegistry.register(...)` 注册。

**返回**：见下表。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `getType()` | 实体类 | — | `Class<? extends T>` |
| `getTranslationKey()` | 显示名的翻译键，形如 `entity.<legacyId>`（首次调用时生成并缓存） | 类型须已注册；未注册时 legacy ID 为 `null`，键会退化成 `entity.null` | `String` |
| `create(World world)` | 按工厂造一个新实体实例 | `world` 非空；工厂由构建时提供 | 新实体 `T`；工厂抛异常时原样抛出 |
| `EntityType.Builder#of(Class type, Function factory)` | 静态工厂：用"实体类 + `World → T` 工厂函数"造一个建造器 | `factory` 不能返回 `null` | `EntityType.Builder<T>` |
| `EntityType.Builder#build()` | 产出最终的类型对象 | — | `EntityType<T>` |

### `EntityTypes`

Reference: `net.ornithemc.osl.entities.api.entity.EntityTypes`

**作用**：`EntityType.Builder` 的便捷入口，省掉一次显式的 `EntityType.Builder.` 前缀。

**需要**：工厂函数一般是 `CookieMonsterEntity::new`（要求实体类有 `(World)` 构造器，与原版实体一致）。

**返回**：可继续 `build()` 的建造器。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `builder(Class type, Function factory)` | 新建实体类型建造器 | `type` 为实体类，`factory` 接受 `World` 并返回其实例 | `EntityType.Builder<T>` |
