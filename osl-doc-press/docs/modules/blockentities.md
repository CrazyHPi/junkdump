---
title: 05 blockentities
---

# 05 blockentities

> 一句话定位：给 1.12.2 的方块实体（block entity / tile entity）补上「可注册的类型」，让自定义方块实体拥有自己的数字 id 与命名空间 id，并能安全地存档、读档、被数据修复器识别。

| 项 | 值 |
|---|---|
| 模块 id | `blockentities` |
| Maven | `net.ornithemc.osl-gen2:blockentities:0.1.1+mc16w32a-mc18w01a` |
| 端 | 双端 |
| 依赖 | `ploceus.dependOslModule('blockentities', '0.24.0')`（另需 `core`、`entrypoints`、`registries`） |

模块整体用途：1.12.2 的方块实体没有「注册类型」这一步，原版靠 `BlockEntity.REGISTRY` 把「id 字符串 → 类」登记起来，存档里只写 id 字符串。本模块把这个表包装成 OSL 的注册表：你可以给自定义方块实体分配命名空间 id（如 `example:cookie`），拿到稳定的数字 id，并让它出现在原版的 id→类映射里，从而正常参与 `BlockEntity` 的创建、存档与读档；同时模块会为这些自定义 id 补上数据修复（DataFixer）映射，旧存档里残留的短 id 也能被纠正。注册入口是启动期的一个事件，不要在静态初始化里抢跑（见下文「注册时机」）。

## 注册表

### `BlockEntityTypeRegistry`

Reference: `net.ornithemc.osl.blockentities.api.BlockEntityTypeRegistry`

**作用**：方块实体类型注册表的静态门面。绝大多数操作都从这里走：注册新类型、按 id / 命名空间 id / 资源键查类型、取某个类型被分配的数字 id。它内部维护的是一张 `registries` 模块的 `Registry<BlockEntityType<?>>`，并且**在 `BlockEntity` 类初始化之前是锁住的**，早于该时刻注册会直接抛异常。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `REGISTRY`（static final 字段） | 底层注册表本身，需要遍历或使用 `Registry` 接口的高级操作时用 | 无 | `Registry<BlockEntityType<?>>` |
| `register(NamespacedIdentifier identifier, BlockEntityType.Builder type)` | 用命名空间 id 注册一个类型 | 必须在注册表解锁后调用（即在 `REGISTER_BLOCK_ENTITY_TYPES` 事件里）；`identifier` 的命名空间建议用你自己的 mod id | 注册后的 `BlockEntityType<T>`；过早调用抛 `IllegalStateException` |
| `register(ResourceKey<BlockEntityType<?>> key, BlockEntityType.Builder type)` | 同上，用资源键注册 | 同上 | 同上 |
| `getId(BlockEntityType<?> type)` | 取该类型的数字 id（与原版 id 空间一致，存档和网络里用的就是它） | `type` 已注册 | `int` |
| `getIdentifier(BlockEntityType<?> type)` | 取该类型的命名空间 id | 同上 | `NamespacedIdentifier` |
| `getKey(BlockEntityType<?> type)` | 取该类型的资源键 | 同上 | `ResourceKey<BlockEntityType<?>>` |
| `getBlockEntityType(int id)` | 按数字 id 反查类型 | `id` 为已分配的数字 id | `BlockEntityType<?>`；源码未在此说明查不到时的行为（按查表语义应为 `null`） |
| `getBlockEntityType(NamespacedIdentifier identifier)` | 按命名空间 id 反查 | 同上 | `BlockEntityType<?>` |
| `getBlockEntityType(ResourceKey<BlockEntityType<?>> key)` | 按资源键反查 | 同上 | `BlockEntityType<?>` |
| `identifierSet()` | 全部命名空间 id | 无 | `Set<NamespacedIdentifier>` |
| `keySet()` | 全部资源键 | 无 | `Set<ResourceKey<BlockEntityType<?>>>` |

### 注册时机（重要）

- 注册表初始为锁定状态，在 `net.minecraft.block.entity.BlockEntity` 的静态初始化开始时解锁。
- 原版方块实体在这一步注册完成后，模块立刻触发一次 `BlockEntityEvents.REGISTER_BLOCK_ENTITY_TYPES`。
- 所以：**自定义类型只能在 `REGISTER_BLOCK_ENTITY_TYPES` 的监听器里注册**；在 mod 的初始化入口里直接调用 `register` 会因为「注册表仍锁着」而抛 `IllegalStateException`（异常消息为 `register called too early: registry locked!`）。
- 注册成功后，该类型同时被写进原版的 id→类映射（使用同一个数字 id 和 `namespace:path` 形式的 id 字符串），因此 `BlockEntity` 的存档/读档能按名字找到你的类。

**谁实现什么**：`BlockEntityTypeRegistry` 是工具类，不需要实现；你只需要在事件里调用它的 `register`。

## 类型与构建

### `BlockEntityType`

Reference: `net.ornithemc.osl.blockentities.api.blockentity.BlockEntityType`

**作用**：一个「方块实体类型」的抽象：它记住方块实体的类，并负责创建实例。注册表里存的就是它；原版读档时按 id 取到已登记的类再自行实例化（本模块注册时写进原版表的正是这个类），所以 `create()` 主要供需要自己造实例的代码使用。该接口由模块内部实现，mod 作者不实现它，只通过 `Builder` 构建并注册。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `getType()` | 该类型对应的方块实体类 | 无 | `Class<? extends T>` |
| `create()` | 用注册时给的工厂新建一个该类型的方块实体实例 | 无；工厂不能返回 `null`，抛出的异常会原样冒泡 | 新建的方块实体实例 |

内部接口 `BlockEntityType.Builder<T>`（同样由模块内部实现，你用 `of` 拿实例即可）：

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `of(Class type, Supplier factory)`（static） | 用「类 + 工厂」构造 builder | `type` 与工厂返回类型要一致 | `Builder<T>` |
| `build()` | 生成类型实例（尚未注册） | 无 | `BlockEntityType<T>`；交给 `BlockEntityTypeRegistry.register` 才会真正注册 |

`Builder.of` 不会校验 `type` 是否有无参构造器——构造实例的动作发生在 `create()`，由你提供的工厂负责；工厂抛异常会直接冒泡给调用方（即方块实体创建时）。

### `BlockEntityTypes`

Reference: `net.ornithemc.osl.blockentities.api.blockentity.BlockEntityTypes`

**作用**：构造 builder 的便捷入口。功能上等价于 `BlockEntityType.Builder.of(...)`，写起来更短，示例代码和 javadoc 里用的都是它。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `builder(Class type, Supplier factory)`（static） | 创建类型 builder | `type` 为方块实体类，`factory` 为该类实例的工厂（通常是 `CookieBlockEntity::new`） | `BlockEntityType.Builder<T>` |

## 事件

### `BlockEntityEvents`

Reference: `net.ornithemc.osl.blockentities.api.BlockEntityEvents`

**作用**：方块实体生命周期相关的启动期事件容器（`final` 类，只有静态字段，不需要实现或继承）。目前只有一个事件：自定义方块实体类型的注册窗口。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `REGISTER_BLOCK_ENTITY_TYPES`（static final 字段） | 在原版方块实体注册完成、注册表已解锁之后触发一次 | 监听器应在 mod 的入口点里注册；只有在监听器内部才可以调用 `BlockEntityTypeRegistry.register` | `Event<Runnable>`；无返回值（`register` 监听器本身是 void） |

监听器类型是 `Runnable`，即「无参数、无返回值」：

```java
BlockEntityEvents.REGISTER_BLOCK_ENTITY_TYPES.register(() -> {
    BlockEntityTypeRegistry.register(
        NamespacedIdentifiers.from("example", "cookie"),
        BlockEntityTypes.builder(CookieBlockEntity.class, CookieBlockEntity::new)
    );
});
```

要点：

- `Event` 的 `register` 只是把监听器加入列表（`core` 模块），可以注册多个，触发时按注册顺序依次执行。
- 该事件对双端都触发（模块本身是双端模块），客户端与服务端会各自执行一次注册；这也是它挂在 `BlockEntity` 静态初始化阶段的原因——两侧都需要同一套 id。
- 它只触发一次，不要依赖它在运行期再次发生；世界重进不会重新触发。
