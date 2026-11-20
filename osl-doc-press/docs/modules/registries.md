---
title: 20 registries
---

# 20 registries

> 一句话定位：给"游戏内容"建立一张统一的表——每个条目有唯一的名字和数字 ID，并负责让客户端与服务端的数字 ID 对得上。

| 项 | 值 |
|---|---|
| 模块 id | `registries` |
| Maven | `net.ornithemc.osl-gen2:registries:0.4.0+mc14w27a-mc17w46a` |
| 端 | 双端 |
| 依赖 | `ploceus.dependOslModule('registries', '0.24.0')` |
| 依赖的 OSL 模块 | `core`, `entrypoints`, `lifecycle-events`, `executors`, `networking`, `networking-impl` |

本模块提供三件事：**注册表框架**（`Registry` 及配套接口，可用来登记你自己的一类内容）、**命名与资源键**（`ResourceKey` / `NamespacedIdentifier`，给每个条目一个稳定名字）、以及**数字 ID 同步**（`SyncedRegistries`，让客户端与服务端、存档与当前游戏对同一个内容使用同一个数字 ID）。`blocks`、`items`、`biomes`、`entities` 等模块都是在它之上包装原版注册表的薄壳。

## 事件

### `RegistryEvents`

Reference: `net.ornithemc.osl.registries.api.RegistryEvents`

**作用**：注册表生命周期的三个时间点。你在这里建自己的注册表、往里注册条目，或赶在"冻结"之前做最后一次写入。

**需要**：只在 mod 的 entrypoint（`ModInitializer` / `init` 入口）里静态注册回调，不要在游戏跑起来之后补注册——事件在启动阶段就触发完了。

**返回**：无。三个字段都是 `Event<Runnable>`，用 `register(() -> { ... })` 挂一个无参回调。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `INIT_REGISTRIES` | 游戏启动时、原版注册表装载完之后、原版 bootstrap 运行与注册表冻结之前触发；**创建注册表**（`Registries.registerSimple` 等）应当写在这里 | 每个进程只在首次 `Bootstrap.init()` 时触发一次 | 无（`void`） |
| `BOOTSTRAP_REGISTRIES` | 注册表装载完之后、真正调用各注册表的 bootstrap 之前触发 | 同上；注意原版 bootstrap 可能因类加载而提前跑过 | 无（`void`） |
| `REGISTRIES_FROZEN` | 所有注册表已被引导、冻结并通过校验之后触发 | 此时再往注册表写东西会抛 `IllegalStateException`（注册表已冻结） | 无（`void`） |

触发顺序（据实现）：`INIT_REGISTRIES` → 原版 `Bootstrap.init()` → `BOOTSTRAP_REGISTRIES` → 各注册表的 `Bootstrap#init` → 冻结全部注册表 → 校验（有注册表引导后仍为空则抛 `IllegalStateException`）→ `REGISTRIES_FROZEN`。

```java
RegistryEvents.INIT_REGISTRIES.register(() -> {
    // 自定义注册表只在这一刻创建
    Registries.registerSimple(RegistryKeys.from("cookie_recipe"), CookieRecipes::init);
});
```

## 注册表核心

### `Registry`

Reference: `net.ornithemc.osl.registries.api.registry.Registry`

**作用**：一张"某类内容的全部已知条目"的表。每个条目同时拥有一个唯一的数字 ID 和一个唯一的 namespaced ID，因此注册表天然是序列化（存档、网络包）的基础。实现类由 OSL 提供（包装原版注册表的实现，或纯 Java 实现），**mod 作者不要自己实现这个接口**。

**需要**：通过 `Registries` 创建（自定义内容），或直接用各模块给你的现成实例（`BlockRegistry.REGISTRY`、`ItemRegistry.REGISTRY` 等）。注册必须在注册表冻结之前完成。

**返回**：查询类方法按名字 / ID / 对象三者互查，详见下表；写操作在冻结后一律抛 `IllegalStateException`。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `identifier()` | 这个注册表自身的 ID（如 `minecraft:block`） | — | `NamespacedIdentifier` |
| `get(int id)` | 按数字 ID 查条目 | `id` ≥ 0；未注册的 ID 返回 `null`（纯 Java 实现下越界会抛 `IndexOutOfBoundsException`） | `T` 或 `null` |
| `get(ResourceKey key)` / `get(NamespacedIdentifier id)` | 按名字查条目 | 实际以 `key.identifier()` 为准（资源键的注册表部分不做校验） | `T`；未命中返回 `null` |
| `getId(T value)` | 查条目对应的数字 ID | 条目须已注册 | `int`；未注册返回 `-1` |
| `getKey(T value)` / `getIdentifier(T value)` | 查条目对应的资源键 / 名字 | 同上 | `ResourceKey<T>` / `NamespacedIdentifier`；未注册返回 `null` |
| `keySet()` / `identifierSet()` | 全部资源键 / 全部名字 | — | `Set`（是否为底层实时视图取决于实现） |
| `freeze()` | 冻结注册表，之后禁止再写入 | 通常在启动阶段由 OSL 调用；defaulted 注册表要求默认值已注册，否则抛 `IllegalStateException` | 注册表自身（便于链式调用） |
| `register(Registry registry, ResourceKey key, V value)` | 静态工具：往指定注册表注册一个条目 | 注册表可写；名字与 ID 都不能重复，对象不能重复注册 | 注册后的 `value`；冲突时抛 `IllegalStateException` |
| `register(Registry registry, NamespacedIdentifier id, V value)` | 静态工具：按名字注册（内部合成资源键） | 同上 | 同上 |
| `register(Registry registry, int id, ResourceKey key, V value)` | **（已废弃，请改用不带 `id` 的重载）** 手动指定数字 ID 注册 | 同上 | 同上 |
| `register(Registry registry, int id, NamespacedIdentifier identifier, V value)` | **（已废弃，请改用不带 `id` 的重载）** | 同上 | 同上 |
| `Registry.Bootstrap#init()` | 嵌套接口：注册表的"引导"回调，在冻结前统一调用，是往注册表里填内容的最后机会 | 由 `Registries.registerSimple` / `registerDefaulted` 传入 | 无（`void`） |

```java
public static final Registry<CookieRecipe> COOKIE_RECIPE =
    Registries.registerSimple(RegistryKeys.from("cookie_recipe"), CookieRecipes::init);

// 在 CookieRecipes 的静态初始化里填内容
Registry.register(COOKIE_RECIPE, NamespacedIdentifiers.from("example", "chocolate_chip"), new ChocolateChipRecipe());
```

### `WritableRegistry`

Reference: `net.ornithemc.osl.registries.api.registry.WritableRegistry`

**作用**：`Registry` 的"可写"版本，多出两个注册方法。OSL 内部用它实现冻结逻辑；你只有在需要"通用地"接收一个可写注册表（例如写工具方法）时才会碰到它。

**需要**：拿到一个实际可写的注册表实例（`Registries.registerSimple` 的返回值实现了它）；冻结后调用会抛 `IllegalStateException`。

**返回**：注册后的条目。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `register(ResourceKey key, V value)` | 自动分配下一个数字 ID 并注册 | 未冻结；名字/ID/对象都不重复 | `value` |
| `register(int id, ResourceKey key, V value)` | **（已废弃，请改用 `register(ResourceKey, Object)`）** 指定数字 ID 注册 | 同上 | `value` |

### `DefaultedRegistry`

Reference: `net.ornithemc.osl.registries.api.registry.DefaultedRegistry`

**作用**：带"默认值"的注册表：查不到任何东西时返回默认条目，而不是 `null`。原版的方块注册表就是这种（默认是空气），因此 `BlockRegistry.REGISTRY` 的类型是 `DefaultedRegistry<Block>`。

**需要**：用 `Registries.registerDefaulted` 创建时给出默认值的名字，并**务必在冻结前把该名字的条目注册进去**，否则冻结会抛 `IllegalStateException`。

**返回**：查询方法在未命中时回落到默认值（据实现，`getId` / `getKey` / `getIdentifier` 也会回落到默认条目的 ID / 键 / 名字）。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `getDefaultIdentifier()` | 默认条目的名字 | — | `NamespacedIdentifier` |

## 资源键与命名

命名规则总结（来自 `core` 模块的 `NamespacedIdentifier` / `NamespacedIdentifiers`）：一个名字写成 `namespace:path`，缺省命名空间是 `minecraft`。

- 命名空间：非空，只允许 `a-z`、`0-9`、`-`、`_`、`.`；一般用你的 mod id。
- 路径：非空，额外允许 `/`（用于分组，例如 `example:food/cookie`）；**不允许大写字母和空格**，推荐 snake_case。
- 不合法时构造/解析会抛运行时异常 `NamespacedIdentifierException`（解析失败则是 `NamespacedIdentifierParseException`）。
- 资源键 = 注册表名 + 条目名两段，两段各自都要满足上述规则；因此同一个条目名可以安全地出现在不同注册表里。

### `ResourceKey`

Reference: `net.ornithemc.osl.registries.api.registry.ResourceKey`

**作用**：条目的"全限定名"——由"所属注册表 + 注册表内名字"两段组成，例如 `(minecraft:block, minecraft:stone)`。序列化、跨版本对齐、`IdMapper` 的重映射都以它为键。

**需要**：用 `ResourceKeys` / `RegistryKeys` 创建；两段都必须是合法的 `NamespacedIdentifier`（命名空间只允许 `[a-z0-9-._]`，路径额外允许 `/`，均不能为空；不合法时抛运行时异常 `NamespacedIdentifierException`）。缺省命名空间是 `minecraft`。

**返回**：两个只读访问器。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `registry()` | 所属注册表的 ID | — | `NamespacedIdentifier` |
| `identifier()` | 条目在注册表内的名字 | — | `NamespacedIdentifier` |

### `ResourceKeys`

Reference: `net.ornithemc.osl.registries.api.registry.ResourceKeys`

**作用**：资源键工厂。所有重载都做了实例缓存：同样的（注册表, 名字）组合拿到的永远是同一个对象，可以直接用 `==` 或 `equals` 比较。

**需要**：参数必须是合法 `NamespacedIdentifier`；参数顺序不要搞混（注册表在前、条目名在后）。

**返回**：`ResourceKey` 实例。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `from(NamespacedIdentifier identifier)` | 为"名为 `identifier` 的注册表"造键 | 据实现，注册表部分取根注册表 `minecraft:root`，条目部分取 `identifier` | `ResourceKey<T>` |
| `from(ResourceKey registry, NamespacedIdentifier identifier)` | 为注册表 `registry` 里的条目 `identifier` 造键 | `registry` 是该注册表的键 | `ResourceKey<T>` |
| `from(NamespacedIdentifier registry, NamespacedIdentifier identifier)` | 同上，但注册表用名字给出 | — | `ResourceKey<T>` |

### `RegistryKeys`

Reference: `net.ornithemc.osl.registries.api.registry.RegistryKeys`

**作用**：常用注册表的键常量，以及"造注册表键"的快捷方法。写自定义内容时给 `Registries.registerSimple` 传的就是这种键。

**需要**：`from(String)` 使用缺省命名空间 `minecraft`（想用自己的命名空间请用 `from(NamespacedIdentifier)`）。

**返回**：注册表键（`ResourceKey<Registry<T>>`）。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `BLOCK` / `ITEM` / `BIOME` | 方块 / 物品 / 生物群系注册表的键（`minecraft:block` 等） | — | `ResourceKey<Registry<...>>` |
| `BLOCK_ENTITY_TYPE` / `ENTITY_TYPE` | 方块实体类型 / 实体类型注册表的键 | 1.12.2 上这两个常量声明为**裸 `ResourceKey`**（泛型参数在源码里被注掉了），赋值给带泛型的变量需要强转 | 裸 `ResourceKey` |
| `from(String identifier)` | 用缺省命名空间造注册表键 | `identifier` 需符合路径字符规则 | `ResourceKey<Registry<T>>` |
| `from(NamespacedIdentifier identifier)` | 用给定名字造注册表键 | 同上 | `ResourceKey<Registry<T>>` |

### `LegacyStringIds`

Reference: `net.ornithemc.osl.registries.api.registry.LegacyStringIds`

**作用**：在"老式 PascalCase 字符串 ID"和 namespaced ID 之间转换。原版早期系统（实体名、统计、数据修复）用的就是老式 ID，而 mod 内容没有硬编码对照表，所以这里是**通用**转换规则，不做词序调整。

**需要**：只做机械转换，不保证与原版的特殊改名一致（例如原版 `LavaSlime` 实际对应 `minecraft:magma_cube`，这类改名是硬编码表，不在本方法能力范围内）。

**返回**：转换结果字符串 / `NamespacedIdentifier`。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `fromIdentifier(NamespacedIdentifier identifier)` | namespaced ID → 老式 ID | — | `String`，形如 `TntMinecart`（`minecraft` 命名空间会被省略）或 `example.ChocolateChipCookie` |
| `fromIdentifier(String namespace, String identifier)` | 同上，分段传入 | 下划线被去掉、每个词首字母大写 | `String` |
| `toIdentifier(String id)` | 老式 ID → namespaced ID | 含 `.` 时前半段当命名空间，否则用 `minecraft`；大写字母转小写并在词间插 `_`，连续大写不插（`MinecartTNT` → `minecraft:minecart_tnt`） | `NamespacedIdentifier` |

## 注册表的创建与查找

### `Registries`

Reference: `net.ornithemc.osl.registries.api.registry.Registries`

**作用**：根注册表（"存放所有注册表的注册表"）以及创建注册表的工厂。一个注册表就是"一类内容"的容器；注册表本身也被注册，因此可以用键查找。

**需要**：在 `RegistryEvents.INIT_REGISTRIES` 的监听器里调用；键不能和已有注册表重名；注册表标识在创建时就固定，之后不能改。

**返回**：新建的注册表实例（已自动登记到根注册表，其 `Bootstrap` 会在冻结前被调用一次）。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `REGISTRY` | 根注册表，持有所有已注册的注册表 | 只读用途；不要往里乱塞东西 | `Registry<? extends Registry<?>>` |
| `get(ResourceKey key)` | 按键查注册表 | 实际以 `key.identifier()` 在根注册表里查找 | `Registry<T>`；不存在返回 `null` |
| `registerSimple(ResourceKey key, Registry.Bootstrap bootstrap)` | 创建一个普通（可写、无默认值）注册表 | 名字不与已有注册表冲突；`bootstrap` 不能为 `null`（引导时会调用 `init()`） | 新建的 `Registry<T>` |
| `registerDefaulted(ResourceKey key, NamespacedIdentifier defaultIdentifier, Registry.Bootstrap bootstrap)` | 创建一个带默认值的注册表 | 同上；默认条目必须在冻结前注册，否则冻结抛 `IllegalStateException` | 新建的 `DefaultedRegistry<T>` |

引导阶段的失败行为（据实现）：某个 `Bootstrap#init()` 抛异常会被包装成 `IllegalStateException("error while bootstrapping registry ...", cause)`；引导结束后仍为空的注册表（`keySet()` 为空）会让启动直接失败，抛 `IllegalStateException("Registry ... is empty after bootstrap!")`。

## 通用数字 ID 映射

### `IdMap`

Reference: `net.ornithemc.osl.registries.api.registry.IdMap`

**作用**：一个简单的双向 `int ↔ 对象` 映射，可以手动分配 ID，也可以自动分配（取当前最大 ID + 1）。它是"轻量版注册表"，适合给不需要完整注册表语义的内部结构编号。1.12.2 上 OSL 自身没有使用它（旧版本的 `blockstates` 用得多），但作为公开工具保留。

**需要**：ID 必须 ≥ 0；ID 唯一，但对象唯一性不保证（同一个对象可以挂多个 ID，此时 `getId` 返回其中任意一个）。

**返回**：见下表；查不到时 `getId` 返回 `-1`、`get` 返回 `null`。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `put(T value)` | 用下一个可用 ID 放入对象 | — | 传入的对象 |
| `put(T value, int id)` | 用指定 ID 放入对象 | `id` ≥ 0，否则抛 `IllegalArgumentException` | 传入的对象 |
| `getId(T value)` | 查对象的 ID | — | `int`；不存在返回 `-1` |
| `get(int id)` | 查 ID 对应的对象 | — | `T` 或 `null` |
| `has(T value)` | 是否登记过该对象 | — | `boolean` |
| `iterator()` | 遍历所有对象（按 ID） | 实现自 `Iterable` | `Iterator<T>` |
| `clear()` | 清空并重置 ID 计数 | — | 无（`void`） |

## ID 同步（Registry Sync）

**为什么需要**：游戏用**数字 ID** 而不是名字来序列化内容（存档更小、网络包更省）。这些 ID 是自动分配的，通常就是"注册顺序"。也就是说，同一个 mod 包在服务端和客户端、在两个不同的存档里，可能拿到不同的 ID。一旦不一致，客户端就会把"石头"读成别的方块、把物品 ID 指错，轻则错乱，重则崩溃或写坏存档。

**OSL 做了什么**：给注册表算出一张"老 ID → 新 ID"的对照表，然后把每个注册表的数字 ID 重排成目标端（服务端 / 存档）的 ID，并且把所有"以数字 ID 为下标或键"的结构（统计数组、方块状态表、模型缓存、实体名列表等）一起搬移。玩家登录时服务端把对照表发给客户端（走 `networking` 的自定义通道），客户端应用后与服务器保持一致；断开多人连接时回滚；单人游戏与存档则通过存档目录里的 `registry_mappings.dat` 持久化。

**mod 作者通常要不要关心**：多数情况下**不用**。`blocks` / `items` / `biomes` / `entities` 这四个模块已经在 `INIT_REGISTRIES` 阶段替你把对应注册表登记进了同步，并挂好了内置的 mapper / fixer。只有以下两种情况才需要你动手：① 你自己建的注册表，其数字 ID 会被写进存档或网络包；② 你自己维护了一张"以数字 ID 为下标/键"的表，需要跟着一起重排。

### `SyncedRegistries`

Reference: `net.ornithemc.osl.registries.api.registry.SyncedRegistries`

**作用**：ID 同步的公开入口：声明"这个注册表要同步"，并为它挂上额外的 ID 搬运工（`IdMapper`）与修补器（`IdFixer`）。

**需要**：在 `RegistryEvents.INIT_REGISTRIES` 的监听器里调用（各内置模块正是这么做的）。注册表必须存在且内部可清空（OSL 自己包装/创建的注册表满足；随便传一个第三方实现会抛 `IllegalArgumentException`）。同一个注册表不能重复声明同步；同一个注册表下 mapper / fixer 的名字不能重复。**对未同步的注册表调用 `registerMapper` / `registerFixer` 会抛 `IllegalArgumentException`**。

**返回**：无（均为 `void`）。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `register(ResourceKey registry)` | 声明该注册表参与同步（会自动为它注册一个重排注册表本身的 mapper） | 注册表已用 `Registries` 创建/登记；未重复声明 | 无（`void`）；未知注册表 / 不可清空 / 重复声明抛 `IllegalArgumentException` |
| `registerMapper(ResourceKey registry, NamespacedIdentifier identifier, IdMapper mapper)` | 为已同步的注册表挂一个 ID 搬运工 | 该注册表已 `register`；`identifier` 在该注册表下唯一（仅用于日志与去重） | 无（`void`） |
| `registerFixer(ResourceKey registry, NamespacedIdentifier identifier, IdFixer fixer)` | 为已同步的注册表挂一个"修 ID"回调 | 同上 | 无（`void`） |

```java
RegistryEvents.INIT_REGISTRIES.register(() -> {
    SyncedRegistries.register(MY_REGISTRY_KEY);
    SyncedRegistries.registerMapper(MY_REGISTRY_KEY,
        NamespacedIdentifiers.from("example", "my_table"), ArrayMapper.of(() -> MY_TABLE, a -> MY_TABLE = a));
});
```

### `RegistryMappings`

Reference: `net.ornithemc.osl.registries.api.registry.sync.RegistryMappings`

**作用**：一张"老 ID ↔ 新 ID"对照表，OSL 在搬运时把它传给你的 mapper / fixer。表里既有按条目名查的映射，也有按老 ID 查的映射。

**需要**：你只读它，不要修改；映射方向请注意——`remap` 是"老 → 新"，`unmap` 是"新 → 老"，名字里的"新/老"以"目标端使用的新 ID"为准。

**返回**：`int`；查不到返回 `-1`。映射结果是负数时表示"该条目在目标端不存在"，mapper 通常应据此丢弃这个下标/键。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `remap(ResourceKey key)` | 按名字取新 ID | 名字属于当前同步的注册表 | `int`（`-1` 表示未知） |
| `remap(int id)` | 按老 ID 取新 ID | `id` 是本地当前 ID | `int`（`-1` 表示未知） |
| `unmap(ResourceKey key)` | 按名字取老 ID | 同上 | `int` |
| `unmap(int id)` | 按新 ID 取老 ID | `id` 是目标端 ID | `int` |

### `IdMapper`

Reference: `net.ornithemc.osl.registries.api.registry.sync.IdMapper`

**作用**：一个"会跟着 ID 一起搬家"的结构（数组、列表、以 ID 为键的 map，或存了 ID 字段的对象）。OSL 提供了 8 个实现可直接用；你也可以为自己的结构实现它。

**需要**：由你实现时，`apply` 要先把旧内容备份（否则 `undo` 无法还原），再按 `mappings.remap(oldId)` 把值搬到新下标/新键，`newId < 0` 的条目丢弃；`undo` 要在没 `apply` 过时安全地什么都不做。

**返回**：无（均为 `void`）。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `apply(RegistryMappings mappings)` | 按对照表把内容搬到新 ID | 结构当前持有的是"本地老 ID"排布 | 无（`void`） |
| `undo(RegistryMappings mappings)` | 撤销上一次 `apply`，恢复原排布 | 之前确实 `apply` 过（实现里用标记位判断） | 无（`void`） |

### `IdFixer`

Reference: `net.ornithemc.osl.registries.api.registry.sync.IdFixer`

**作用**：当 ID 可以"推导或重新生成"、用 mapper 反而多余甚至不可行时，用它做修补。典型例子：方块状态表（可以由方块 ID + metadata 重新算出来）、旧版本里存了 ID 字段的对象。

**需要**：在注册表被重排之后被调用；实现里要按映射后的状态**重新生成**内容，而不是依赖旧内容。

**返回**：无（`void`）。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `apply()` | 重新计算/修正绑定的结构 | 绑定的注册表已经完成 ID 重排 | 无（`void`） |

## ID 搬运工（`IdMapper` 的内置实现）

### `ArrayMapper`

Reference: `net.ornithemc.osl.registries.api.registry.sync.ArrayMapper`

**作用**：给"对象数组 `T[]`，用 ID 当下标"的结构做搬移（`null` 视为空槽）。方块/物品的统计数组就是这种结构。

**需要**：数组可能为 `null` 或需要扩容，所以用 `Supplier` 取、`Consumer` 存，而不是直接持有数组引用（字段被替换后仍能工作）。`apply` 会先备份原数组，`undo` 用备份还原。

**返回**：搬移结果写回你提供的数组字段；方法本身无返回值。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `of(Supplier getter, Consumer setter)` | 用取值/存值回调包装一个数组字段 | `getter` 不能返回 `null` | `ArrayMapper` |
| `of(DynamicArray array)` | 用 `DynamicArray` 包装 | — | `ArrayMapper` |
| `apply(RegistryMappings mappings)` | 把非 `null` 的值从老下标搬到新下标 | 见 `IdMapper` | 无（`void`） |
| `undo(RegistryMappings mappings)` | 还原到搬移前的数组 | 之前 `apply` 过 | 无（`void`） |

### `BooleanArrayMapper`

Reference: `net.ornithemc.osl.registries.api.registry.sync.BooleanArrayMapper`

**作用**：同上，但针对 `boolean[]`（`false` 当作空槽）。原版的"是否已解锁配方 / 是否已发现"之类的标记数组会用到。

**需要**：因为 `boolean` 没有 `null`，搬移时**每个下标的值都会被复制**（包括 `false`）。

**返回**：写回你提供的数组字段；方法无返回值。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `of(Supplier getter, Consumer setter)` | 包装 `boolean[]` 字段 | — | `BooleanArrayMapper` |
| `of(DynamicBooleanArray array)` | 用 `DynamicBooleanArray` 包装 | — | `BooleanArrayMapper` |
| `apply(RegistryMappings mappings)` / `undo(RegistryMappings mappings)` | 搬移 / 还原 | 同 `ArrayMapper` | 无（`void`） |

### `IntArrayMapper`

Reference: `net.ornithemc.osl.registries.api.registry.sync.IntArrayMapper`

**作用**：针对 `int[]`（`0` 当作空槽）。

**需要**：与布尔版本一样，**每个下标的值都会被复制**（包括 `0`），所以 `0` 语义不是"空缺"的结构要小心。

**返回**：写回你提供的数组字段；方法无返回值。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `of(Supplier getter, Consumer setter)` | 包装 `int[]` 字段 | — | `IntArrayMapper` |
| `of(DynamicIntArray array)` | 用 `DynamicIntArray` 包装 | — | `IntArrayMapper` |
| `apply(RegistryMappings mappings)` / `undo(RegistryMappings mappings)` | 搬移 / 还原 | 同 `ArrayMapper` | 无（`void`） |

### `IntegerMapMapper`

Reference: `net.ornithemc.osl.registries.api.registry.sync.IntegerMapMapper`

**作用**：给 `Map<Integer, T>`（以 ID 为键）做搬移。`apply` 备份整张表，`undo` 用备份还原。

**需要**：map 必须是可清空、可写的；键必须真的是 ID（不是打包过的复合键，那种要自己写 mapper）。

**返回**：写回原 map；方法无返回值。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `of(Map registry)` | 包装一个 `Map<Integer, ?>` | 传入的 map 会被**原地**修改 | `IntegerMapMapper` |
| `apply(RegistryMappings mappings)` / `undo(RegistryMappings mappings)` | 搬移 / 还原 | 同 `IdMapper` | 无（`void`） |

### `Int2ObjectMapMapper`

Reference: `net.ornithemc.osl.registries.api.registry.sync.Int2ObjectMapMapper`

**作用**：fastutil `Int2ObjectMap` 版本的"以 ID 为键"搬移（物品模型缓存等用的就是它）。

**需要**：map 必须可清空、可写；同样会**原地**修改传入的 map。

**返回**：写回原 map；方法无返回值。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `of(Int2ObjectMap registry)` | 包装一个 fastutil map | 传引用，不复制 | `Int2ObjectMapMapper` |
| `apply(RegistryMappings mappings)` / `undo(RegistryMappings mappings)` | 搬移 / 还原（用备份） | 同 `IdMapper` | 无（`void`） |

### `DynamicInt2ObjectMapMapper`

Reference: `net.ornithemc.osl.registries.api.registry.sync.DynamicInt2ObjectMapMapper`

**作用**：给"内容会随游戏进程变化"的 fastutil map 做搬移（例如资源包重载就会重建的模型缓存）。它**不做备份**，`undo` 靠反向映射当场算回去。

**需要**：适合内容会变的 map；因为不备份，`undo` 之前如果内容被大改，结果以当前内容为准。

**返回**：写回原 map；方法无返回值。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `of(Int2ObjectMap cache)` | 包装一个动态 map | 传引用，不复制 | `DynamicInt2ObjectMapMapper` |
| `apply(RegistryMappings mappings)` | 用 `remap` 把所有键换成新 ID | 键须是纯 ID | 无（`void`） |
| `undo(RegistryMappings mappings)` | 用 `unmap` 把键换回去 | 之前 `apply` 过 | 无（`void`） |

### `ListMapper`

Reference: `net.ornithemc.osl.registries.api.registry.sync.ListMapper`

**作用**：给 `List<T>`（以 ID 为下标）做搬移，必要时用 `null` 补齐空档（例如原版的实体名列表 `Entities.NAMES`）。

**需要**：列表必须可清空、可写、允许 `null` 元素；`null` 元素视为空槽，不会被搬移。

**返回**：写回原 list；方法无返回值。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `of(List registry)` | 包装一个 `List<?>` | 传引用，不复制 | `ListMapper` |
| `apply(RegistryMappings mappings)` / `undo(RegistryMappings mappings)` | 搬移 / 还原（用备份） | 同 `IdMapper` | 无（`void`） |

### `Id2ObjectBiMapMapper`

Reference: `net.ornithemc.osl.registries.api.registry.sync.Id2ObjectBiMapMapper`

**作用**：给原版 `net.minecraft.util.Id2ObjectBiMap`（ID ↔ 对象双向表）做搬移。方块状态表、生物群系变体表、方块/物品颜色表都是这种结构。

**需要**：`Id2ObjectBiMap` **允许重复值**，所以不能靠遍历值来枚举全部 ID——实现里先按 ID 集合把 `id → 对象` 全部复制到备份表，再清空原表按对照表重建（`undo` 用备份还原）。

**返回**：写回原 map；方法无返回值。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `of(Id2ObjectBiMap registry)` | 包装一个原版双向表 | 传引用，不复制 | `Id2ObjectBiMapMapper` |
| `apply(RegistryMappings mappings)` / `undo(RegistryMappings mappings)` | 搬移 / 还原（用备份） | 同 `IdMapper` | 无（`void`） |

## 动态数组工具

这三个类本身不参与同步，只是给上表的数组搬运工提供"字段里的数组可以被扩容/替换"的抽象：它们不保存数组引用，而是每次通过 `Supplier` 取、`Consumer` 存，所以数组字段被整体替换后依然有效。

### `DynamicArray`

Reference: `net.ornithemc.osl.registries.api.registry.sync.DynamicArray`

**作用**：把"存在字段里的 `T[]`"包装成可按需增长的对象数组视图。

**需要**：`getter` 必须始终返回非 `null` 数组；写入越界下标前会自动扩容（按当前长度每次增长 50% 直到够用，因此实际容量可能大于请求值）。`length()` 指的是"最后一个非 `null` 元素的下标 + 1"，不是容量。

**返回**：读/写/扩容结果见下表。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `of(int capacity)` | 造一个自带独立数组的实例（常用于备份） | `capacity` ≥ 0 | `DynamicArray<T>` |
| `of(Supplier getter, Consumer setter)` | 包装一个真实字段 | `getter` 非空返回 | `DynamicArray<T>` |
| `capacity()` / `length()` | 当前数组长度 / 有效长度 | — | `int` |
| `get(int index)` / `set(int index, T value)` | 按下标读写（不检查越界） | — | 读到 `T`，`set` 返回被写入的值 |
| `add(int index, T value)` | 写入并自动扩容 | `index` ≥ 0 | 写入的值 |
| `addAll(DynamicArray array)` | 把另一个数组的内容复制进来（从头覆盖） | 两个数组元素类型兼容 | 无（`void`） |
| `clear()` | 全部填 `null` | — | 无（`void`） |
| `grow(int capacity)` | 确保容量至少为 `capacity` | — | 无（`void`）（会调用 `setter` 换数组） |
| `length(T[] array)` / `grow(T[] array, int capacity)` | 静态工具：算有效长度 / 扩容并返回（可能返回新数组） | — | `int` / `T[]` |

### `DynamicBooleanArray`

Reference: `net.ornithemc.osl.registries.api.registry.sync.DynamicBooleanArray`

**作用**：`DynamicArray` 的 `boolean[]` 版本（`false` 作空值）。

**需要**：无 `null` 概念，`length()` 就等于容量；`clear()` 会全部填 `false`。

**返回**：见下表。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `of(int capacity)` / `of(Supplier getter, Consumer setter)` | 造独立实例 / 包装字段 | 同 `DynamicArray` | `DynamicBooleanArray` |
| `capacity()` / `length()` | 容量（两者相同） | — | `int` |
| `get(int index)` / `set(int index, boolean value)` | 按下标读写 | — | `boolean` |
| `add(int index, boolean value)` | 写入并自动扩容 | `index` ≥ 0 | 写入的值 |
| `addAll(DynamicBooleanArray array)` / `clear()` / `grow(int capacity)` | 复制内容 / 全填 `false` / 扩容 | — | 无（`void`） |
| `grow(boolean[] array, int capacity)` | 静态扩容工具 | — | `boolean[]` |

### `DynamicIntArray`

Reference: `net.ornithemc.osl.registries.api.registry.sync.DynamicIntArray`

**作用**：`DynamicArray` 的 `int[]` 版本（`0` 作空值）。

**需要**：无 `null` 概念，`length()` 等于容量；`clear()` 全部填 `0`。

**返回**：见下表。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `of(int capacity)` / `of(Supplier getter, Consumer setter)` | 造独立实例 / 包装字段 | 同 `DynamicArray` | `DynamicIntArray` |
| `capacity()` / `length()` | 容量（两者相同） | — | `int` |
| `get(int index)` / `set(int index, int value)` | 按下标读写 | — | `int` |
| `add(int index, int value)` | 写入并自动扩容 | `index` ≥ 0 | 写入的值 |
| `addAll(DynamicIntArray array)` / `clear()` / `grow(int capacity)` | 复制内容 / 全填 `0` / 扩容 | — | 无（`void`） |
| `grow(int[] array, int capacity)` | 静态扩容工具 | — | `int[]` |
