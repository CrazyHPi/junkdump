---
title: 21 resource-loader
---

# 21 resource-loader

::: warning 0.26.0 变更
本章按 **0.24.0** 的 API 整理。0.26.0 新增了 `DataReloaders`、`SimpleJsonResourceReloader`、`PackSourcePosition`、`MinecraftServerExtension`、`WorldDataExtension` 与 `ResourcePackRepository.addSource(Source, PackSourcePosition)`，并开始支持服务端数据包，详见[变更历史](/changelog#resource-loader-0-10-0-0-12-0)。
:::

> 一句话定位：把 1.13+ 的"资源包 + 资源管理器 + 两阶段异步重载"整套体系反向移植到 1.12.2，让 mod 能像写 1.13+ 数据包一样写 `assets/` 与 `data/`，并按依赖顺序参与重载。

| 项 | 值 |
|---|---|
| 模块 id | `resource-loader` |
| Maven | `net.ornithemc.osl-gen2:resource-loader:0.10.0+mc1.8.2-pre5-mc1.12.2` |
| 版本 | `0.10.0+mc1.8.2-pre5-mc1.12.2`（1.12.2 命中该子工程） |
| 端 | **1.12.2 上仅客户端**。子工程 `fabric.mod.json` 的 `environment` 为 `client`；API 里有服务端类与事件，但 1.12.2 没有服务端接线（见下） |
| 依赖 | `ploceus.dependOslModule('resource-loader', '0.24.0')`；传递依赖 `core`、`lifecycle-events`、`executors`、`crash-reports`、`text-components` |

模块做了三件事：

1. **资源包层**：把每个 mod 内置的资源、玩家放在 `resourcepacks/` 的包、Vanilla 内置包、服务器下发的包统一成 `ResourcePack`，交给 `ResourcePackRepository` 排序与选择。
2. **资源访问层**：`ResourceManager` 按命名空间提供 `assets/<ns>/...` 与 `data/<ns>/...` 的查找（`1.13+` 风格 `Identifier`），同时保留一条给 1.12.2 老代码用的"直接路径"通道。
3. **重载层**：`ResourceReloader` / `SimpleResourceReloader` / `ResourceReloadListener` + 依赖排序，把"后台加载 → 主线程应用"两阶段跑起来，并暴露进度与事件。

## 1.12.2 的三个前提（先看这个）

| 前提 | 影响 |
|---|---|
| 模块在 1.12.2 上 `environment = client` | 客户端一切正常；**服务端不会加载本模块**。`ServerResourceLoaderEvents` 的 6 个事件在 1.12.2 上不会触发，`ResourcePackRepository.server()` / `ResourceManager.server()` 会被构造出来但**从未被 init / reset**（没有包、没有重载器、没有事件），`ResourcePackRepository.serverPackSource()` 在 1.12.2 恒为 `null`（子工程只提供客户端 pack source 实现）。源码层面没有 1.12.2 的服务端接线。 |
| 资源包格式号 | 1.12.2 支持的 `pack_format` 是 **1**（`< 15w31a` → 1）。`PackCompatibility.forFormat(1)` = `COMPATIBLE`，其它值只会得到 `TOO_OLD` / `TOO_NEW`（不影响加载，只影响界面显示）。 |
| 资源位置校验按版本放宽 | 1.12.2 的格式号 < 3、< 4，所以 `ResourceLocation` 只检查"命名空间里不能有大写字母"，**路径完全不校验**（允许大写、任意字符）。这是版本相关行为，不要当成 1.13+ 的严格规则。 |

## 如何加一个内置资源包（打包进 mod）

### 方式 A：什么都不做（自动）

OSL 会把**每个已加载 mod 的根目录**当成一个资源包，全部合成一个包，id 为 `<loader>-mod-resources`（Fabric 上是 `fabric-mod-resources`，Quilt 上是 `quilt-mod-resources`），显示名形如 `Fabric Mod Resources`。它是**必需包**（永远选中、玩家无法关闭），默认位置 `PackPosition.BOTTOM`，即优先级最低。

所以你只要按标准布局放文件即可，不需要 API 调用：

```
src/main/resources/
  assets/<你的 namespace>/lang/en_us.json
  assets/<你的 namespace>/textures/...
  data/<你的 namespace>/recipes/...
```

`pack.mcmeta` 与 `pack.png` 是**可选**的：模块内部会为 mod 包生成一份（`pack_format` = 支持的格式号，`description` = mod 元数据里的 description，图标取 mod 的 `icon`）。若你自己放了 `pack.mcmeta`，会以你的为准。

### 方式 B：把一个子目录注册成独立资源包

想按功能 / 端拆分资源（例如客户端资源单独一包），用：

```java
ResourcePackRepository.registerBundledModResourcePack(
    "example-cookie-assets",                  // 包 id，必须全局唯一
    "Cookie Assets",                          // 显示名
    FabricLoader.getInstance().getModContainer("example").get(),
    "client/cookies"                          // mod 内的子目录（资源包根）
);
```

- 注册出来的包同样是**必需包**（required = true）、`fixedPosition = false`、默认位置 `BOTTOM`。
- 目录内仍按资源包结构摆放：`client/cookies/assets/<ns>/...`、`client/cookies/data/<ns>/...`。
- 必须在**资源包仓库首次发现资源包之前**调用（写在 `ClientModInitializer#initClient` 里，或 `INIT_RESOURCE_PACK_REPOSITORY` 回调里）。重复 id 会抛 `IllegalStateException`。

### 方式 C：运行时自定义来源

`INIT_RESOURCE_PACK_REPOSITORY` 里 `packRepository.addSource(...)`，自己实现 `ResourcePackRepository.Source`，产出 `ResourcePackSummary`（可以是虚拟包，也可以来自目录 / zip / 网络）。见下面的 `ResourcePackRepository`。

## 资源包优先级（`PackPosition`）

**顺序模型**：选择列表（`getSelectedPacks()`）的**下标越大优先级越高**——同一路径的资源由最靠后的包提供；`getResourceStack(...)` 返回的列表也是同样顺序（末尾 = 最优先）。

| 包 | required | fixedPosition | 默认位置 | 说明 |
|---|---|---|---|---|
| 玩家 `resourcepacks/` 目录里的包 | 否 | 否 | `TOP` | 可以自由勾选 / 排序 |
| 服务器下发的包（id `server`） | 是 | **是** | `TOP` | 永远最高优先级，且位置不可移动 |
| Vanilla 内置包（id `vanilla`） | 是 | 否 | `BOTTOM` | 永远选中 |
| mod 内置资源（`fabric-mod-resources`） | 是 | 否 | `BOTTOM` | 永远选中，优先级低于玩家包 |
| `registerBundledModResourcePack` 注册的包 | 是 | 否 | `BOTTOM` | 同上 |

`BOTTOM` / `TOP` 的插入规则：`TOP` 插到列表末尾、但会停在"连续且固定为 TOP"的块之前（所以服务器包始终压在最上面）；`BOTTOM` 插到列表开头、跳过"连续且固定为 BOTTOM"的块。多个 `BOTTOM` 必需包之间的相对顺序取决于发现顺序，源码不保证稳定，**不要依赖"我的包比另一个 mod 的包优先"**。

## 重载流程（阶段与顺序）

一次完整重载 = **资源包仓库重载** + **资源重载**：

```
repository.reload()
├─ START_RESOURCE_PACKS_RELOAD
├─ 清空并关闭旧包 → 各 Source 重新发现资源包 → 重建选择列表（必需包补插）
├─ 重新 open 所有选中包
└─ END_RESOURCE_PACKS_RELOAD

resourceManager.reload(packs) / startReload(...)
├─ 用新包列表重建 命名空间 → 包 的索引
├─ 排序重载器（拓扑排序 + 依赖）
├─ START_RESOURCE_RELOAD（此时已定稿 packs 与 reloaders 列表）
├─ 所有 reloader 的 prepareSharedState(state)      （按排序顺序，同步执行）
├─ reload 阶段：各 reloader 在后台执行器上加载资源   （可并行，各自 CompletableFuture）
├─ 屏障：等所有 reloader 的 reload 阶段结束
├─ apply 阶段：各 reloader 在主线程执行器上应用资源  （按排序顺序，串行）
└─ END_RESOURCE_RELOAD（全部完成后，在主线程执行器上）
```

要点：

- **两阶段**：`reload` 阶段不在主线程，**不能**碰世界 / 渲染状态；`apply` 阶段在主线程，才允许改游戏状态。
- **apply 是串行的、按重载器排序顺序**；reload 可以并行。
- `SimpleResourceReloader` 自动帮你实现"后台 reload → 屏障 → 主线程 apply"；要更细的控制就实现 `ResourceReloader`，自己在合适的时机调用 `previousStep.await(...)`。
- 顺序由 `registerReloaderDependencies` 决定；没有声明的重载器排在最后，彼此无顺序保证。用 `AssetsReloaders.BEFORE_VANILLA` / `AFTER_VANILLA` 可以把你的重载器整体放到所有 Vanilla 重载器之前 / 之后。
- 1.12.2 上 `ReloadableResourceManager#reload(...)` 使用"直接执行器"（`newReentrantDirectExecutor`），所以它是**同步阻塞**的：调用返回时重载已经完成，异常也已抛出。

## 事件

### `ClientResourceLoaderEvents`

Reference: `net.ornithemc.osl.resource.loader.api.client.ClientResourceLoaderEvents`

**作用**：客户端资源包仓库 / 资源管理器 / 重载的全部钩子。回调请在 mod 初始化器里注册。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `INIT_RESOURCE_PACK_REPOSITORY` | 资源包仓库刚创建时触发；**这里加自定义 `Source`** | `Consumer<ResourcePackRepository>`；回调里不能假定已有任何包（发现还没开始） | 无（void） |
| `INIT_RESOURCE_MANAGER` | 资源管理器初始化时触发（Vanilla 的全部 reload listener 已登记完）；**这里注册重载器** | `Consumer<ReloadableResourceManager>`；注册完 OSL 会立刻对新增的重载器跑一次 partial reload | 无（void） |
| `START_RESOURCE_PACKS_RELOAD` | 资源包仓库即将 reload（发现 + 重建选择）之前 | `Consumer<ResourcePackRepository>` | 无（void） |
| `END_RESOURCE_PACKS_RELOAD` | 资源包仓库 reload 之后（选择列表已重建） | `Consumer<ResourcePackRepository>` | 无（void） |
| `START_RESOURCE_RELOAD` | 资源重载开始前（packs 与 reloaders 列表已定稿） | `BiConsumer<ResourceManager, ResourceReloadContext>` | 无（void） |
| `END_RESOURCE_RELOAD` | 资源重载全部结束后（主线程） | `BiConsumer<ResourceManager, ResourceReloadContext>` | 无（void） |

```java
ClientResourceLoaderEvents.INIT_RESOURCE_MANAGER.register(manager -> {
    manager.registerReloader(CookiesManager.IDENTIFIER, new CookiesManager());
});
```

### `ServerResourceLoaderEvents`

Reference: `net.ornithemc.osl.resource.loader.api.server.ServerResourceLoaderEvents`

**作用**：服务端对应的一组事件（同名、同参数、同语义）。

**需要**：在 1.12.2 上**不会触发**——模块在 1.12.2 只有客户端接线（`environment = client`，子工程没有任何服务端 mixin）。注册本身无害，但回调永远不会被调用。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `INIT_RESOURCE_PACK_REPOSITORY` / `INIT_RESOURCE_MANAGER` | 同客户端，对应服务端仓库 / 管理器 | `Consumer<ResourcePackRepository>` / `Consumer<ReloadableResourceManager>` | 无（void） |
| `START_RESOURCE_PACKS_RELOAD` / `END_RESOURCE_PACKS_RELOAD` | 服务端资源包仓库重载前后 | `Consumer<ResourcePackRepository>` | 无（void） |
| `START_RESOURCE_RELOAD` / `END_RESOURCE_RELOAD` | 服务端资源重载前后 | `BiConsumer<ResourceManager, ResourceReloadContext>` | 无（void） |

## 资源包仓库

### `ResourcePackRepository`

Reference: `net.ornithemc.osl.resource.loader.api.resource.repository.ResourcePackRepository`

**作用**：管理"有哪些包可用 / 哪些被选中 / 选中顺序如何"。

**需要**：客户端用 `client()`；不要自己 new。返回的实例是全局单例（按资源类型缓存），`getSelectedPacks()` / `getAvailablePacks()` 返回的是**内部可变列表本体**，不要直接修改，请走 `setSelectedPacks`。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `client()` | 客户端的仓库（`CLIENT_ASSETS`） | — | `ResourcePackRepository` |
| `server()` | 服务端的仓库（`SERVER_DATA`）。在 1.12.2 上未被接线 | — | `ResourcePackRepository` |
| `clientPackSource()` | 客户端 pack source（Vanilla 内置包 + 服务器包） | 仓库已发现过包，否则可能为 `null` | `ClientPackSource` |
| `serverPackSource()` | 服务端 pack source。1.12.2 上恒为 `null` | — | `ServerPackSource` |
| `registerBundledModResourcePack(String id, String name, ModContainer mod, String directory)` | 把一个 mod 的子目录注册成独立的内置资源包（必需包，BOTTOM） | `id` 全局唯一且未被注册过，否则抛 `IllegalStateException`；必须在仓库首次发现前调用 | 无（void） |
| `addSource(Source source)` | 追加一个资源包来源 | 建议在 `INIT_RESOURCE_PACK_REPOSITORY` 里调用；发现阶段外的追加要等下一次 `reload()` 才生效 | 无（void） |
| `reload()` | 重新跑一遍：关闭旧包 → 各来源重新发现 → 重建选择列表（必需包补插）→ 重新打开选中包。前后触发 `START/END_RESOURCE_PACKS_RELOAD` | 已注册来源 | 无（void） |
| `getAvailablePacks()` | 所有可用包的摘要 | — | `Collection<ResourcePackSummary>`（内部列表） |
| `getSelectedPacks()` | 所有已选中包的摘要，**顺序即优先级（末尾最高）** | — | `Collection<ResourcePackSummary>`（内部列表） |
| `getUnselectedPacks()` | 可用但未选中的包 | — | `Collection<ResourcePackSummary>` |
| `openSelectedPacks()` | 打开所有选中包，得到真正可读的包对象列表 | — | `List<ResourcePack>`（顺序 = 优先级） |
| `setSelectedPacks(Collection<String> packs)` | 用 id 列表设置选中集合（不存在的 id 会被忽略），必需包自动补回；被取消选中的包会被 `close()` | id 来自 `ResourcePackSummary#getId()` | 无（void） |
| `getPack(String id)` | 按 id 查摘要 | — | `ResourcePackSummary`，不存在时为 `null` |
| `close()` | 关闭所有包（选中 + 可用） | — | 无（void） |
| `Source#loadResourcePacks(Consumer<ResourcePackSummary> consumer)` | 自定义来源的唯一方法：把发现的每个包交给 consumer | 每次 `reload()` 都会被调用；`summary` 为 `null` 时不要传（说明该包没有可用元数据） | 无（void） |

### `ClientPackSource`

Reference: `net.ornithemc.osl.resource.loader.api.resource.repository.ClientPackSource`

**作用**：客户端专有的 pack source，对应 Vanilla 内置包与服务器下发包。一般只用来读取。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `DEFAULT_PACK_ID` | Vanilla 内置包的 id，值 `"vanilla"` | — | `String` |
| `SERVER_PACK_ID` | 服务器下发包的 id，值 `"server"` | — | `String` |
| `getDefaultResourcePack()` | Vanilla 内置资源包 | 已加载过包 | `ResourcePack` |
| `getServerResourcePack()` | 服务器下发的资源包；没有时为 `null` | 同上 | `ResourcePack` |
| `loadResourcePacks(Consumer<ResourcePackSummary>)` | 继承自 `Source`，产出上述两个包（不可自己实现，构造被实现类限制） | — | 无（void） |

### `ServerPackSource`

Reference: `net.ornithemc.osl.resource.loader.api.resource.repository.ServerPackSource`

**作用**：服务端专有的 pack source（`data` 侧）。1.12.2 上不存在实现，只能拿到 `null`。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `DEFAULT_PACK_ID` | 值 `"vanilla"` | — | `String` |
| `getDefaultResourcePack()` | Vanilla 内置数据包 | 已加载过包 | `ResourcePack` |
| `loadResourcePacks(Consumer<ResourcePackSummary>)` | 继承自 `Source` | — | 无（void） |

### `ResourcePackSummary`

Reference: `net.ornithemc.osl.resource.loader.api.resource.repository.ResourcePackSummary`

**作用**：一个资源包的"摘要"：从 `pack.mcmeta` 读出来的标题 / 描述 / 兼容性 + 选择所需的元信息。仓库里流转的都是它，而不是包本体。

**需要**：自己造包时用两个 `create` 工厂。**关键陷阱**：若包的 `pack.mcmeta` 缺失 / 无法解析（`pack` 节里必须有 `pack_format` 与 `description`），`create` 返回 `null`——该包会被静默丢弃（只留一条 warn 日志）。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `create(ResourcePack pack, String id, boolean required, boolean fixedPosition, PackPosition defaultPosition)` | 用现成包创建摘要 | `pack` 有可读的 `pack.mcmeta`；`id` 在仓库内唯一 | `ResourcePackSummary`，失败为 `null` |
| `create(String id, boolean required, boolean fixedPosition, PackPosition defaultPosition, Supplier<ResourcePack> opener)` | 延迟打开（每次 `open()` 都调 `opener`） | 同上，且 `opener` 第一次取包时就要能读到元数据 | 同上 |
| `getTitle()` / `getDescription()` | 显示标题 / 描述（标题默认是包名） | — | `TextComponent` |
| `getId()` | 包 id（`setSelectedPacks` 用的就是它） | — | `String` |
| `isRequired()` | 是否必需（永远选中、玩家不可关闭） | — | `boolean` |
| `isFixedPosition()` | 位置是否固定（玩家不能拖动排序） | — | `boolean` |
| `getDefaultPosition()` | 默认插入位置 `TOP` / `BOTTOM` | — | `PackPosition` |
| `getCompatibility()` | 由 `pack_format` 推出的兼容性 | — | `PackCompatibility` |
| `open()` | 打开该包 | — | `ResourcePack` |
| `close()` | 关闭（摘要本身不做清理） | — | 无（void） |

## 资源包

### `ResourcePack`

Reference: `net.ornithemc.osl.resource.loader.api.resource.pack.ResourcePack`

**作用**：一个资源包的抽象：按"直接路径"或"类型 + 命名空间位置"取资源，并暴露命名空间、元数据与生命周期钩子（`extends AutoCloseable`）。

**需要**：要自己实现时，推荐继承 `AbstractResourcePack`（省掉命名空间缓存与元数据解析）；至少要实现 `getName`、`hasResource(String)`、`getResource(String)`、`getNamespaces(ResourceType)`、`hasResource(ResourceType, NamespacedIdentifier)`、`getResource(ResourceType, NamespacedIdentifier)`、`findResources(...)`。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `METADATA_FILE` / `ICON_FILE` | `"pack.mcmeta"` / `"pack.png"` | — | `String` |
| `flatStream()` | 把"容器型包"摊平成包流；普通包返回只含自己的流 | — | `Stream<ResourcePack>` |
| `getName()` | 包显示名（也用于日志 / 异常信息） | — | `String` |
| `hasResource(String path)` / `getResource(String path)` | 按**直接路径**（相对包根）访问，用于 `pack.mcmeta` / `pack.png` 这类根文件（以及 1.5.2 及更早的资源访问方式） | 路径不带前导 `/` 的建议形式；找不到时 `hasResource` 返回 `false`、`getResource` 抛 `IOException` | `boolean` / `InputStream` |
| `getNamespaces(ResourceType type)` | 该包在 `assets` 或 `data` 下提供的命名空间 | — | `Set<String>` |
| `hasResource(ResourceType type, NamespacedIdentifier location)` | 命名空间式存在性检查 | `location` 的路径相对 `assets/<ns>/` 或 `data/<ns>/` | `boolean` |
| `getResource(ResourceType type, NamespacedIdentifier location)` | 命名空间式取资源（延迟打开） | 同上 | `IOSupplier<InputStream>`；不存在时为 `null` |
| `findResources(ResourceType type, String namespace, String directory, ResourceConsumer consumer)` | 递归遍历 `<type>/<namespace>/<directory>` 下所有资源，逐个交给 consumer | `directory` 是相对命名空间目录的路径；过滤非法位置时会打 warn | 无（void） |
| `getMetadata(ResourceMetadata.Section<T> section)` / `getMetadata(String name, Section.Serializer<T> serializer)` | 读 `pack.mcmeta` 中指定节并反序列化 | 节不存在时返回 `null`；存在但解析失败时抛 `IOException`（`AbstractResourcePack` 的实现则是记 error 日志并返回 `null`） | `T` 或 `null` |
| `open()` | 包被选中 / 刚发现时的钩子（为兼容老版本而保留） | — | 无（void） |
| `close()` | 包被取消选中 / 消失时的钩子；不抛受检异常 | — | 无（void） |

### `AbstractResourcePack`

Reference: `net.ornithemc.osl.resource.loader.api.resource.pack.AbstractResourcePack`

**作用**：`ResourcePack` 的部分实现：缓存命名空间集合、把 `pack.mcmeta` 读成 `ResourceMetadata` 并按节反序列化。

**需要**：继承它只需要实现 `findNamespaces()` 以及上面的资源读取方法；`getNamespaces` 会延迟调用一次 `findNamespaces` 并缓存，`close()` 时清空缓存。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `getNamespaces(ResourceType type)` | 带缓存的命名空间查询 | 首次调用会触发 `findNamespaces()` | `Set<String>`（无该类型时为空集） |
| `findNamespaces()`（`protected abstract`） | 子类实现：扫描并返回 `类型 → 命名空间集合` | 返回值不要为 `null` | `Map<ResourceType, Set<String>>` |
| `getMetadata(String name, Serializer<T> serializer)` | 读 `pack.mcmeta` 指定节 | 解析异常被吞掉并记 error，返回 `null` | `T` 或 `null` |
| `open()` / `close()` | `open` 空实现；`close` 清命名空间缓存 | — | 无（void） |

### `ResourcePackMetadata`

Reference: `net.ornithemc.osl.resource.loader.api.resource.pack.ResourcePackMetadata`

**作用**：`pack.mcmeta` 里 `pack` 节的模型（格式号 + 描述）。

**需要**：直接用它读 `pack.mcmeta` 时传 `ResourcePackMetadata.SECTION`；写自己的包元数据时用 `SERIALIZER` 生成 JSON。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `NAME` | 节名 `"pack"` | — | `String` |
| `SERIALIZER` | 该节的 JSON 序列化器（要求 `pack_format` 是数字、`description` 存在且非 null） | — | `ResourceMetadata.Section.Serializer<ResourcePackMetadata>` |
| `SECTION` | 组合好的节类型，直接传给 `getMetadata(...)` | — | `ResourceMetadata.Section<ResourcePackMetadata>` |
| `format()` | 包的格式号（1.12.2 支持 1） | — | `int` |
| `description()` | 包描述（可以是 JSON 文本组件） | — | `TextComponent` |

### `PackPosition`

Reference: `net.ornithemc.osl.resource.loader.api.resource.pack.PackPosition`

**作用**：资源包在排序列表中的首选位置。

**需要**：只在创建 `ResourcePackSummary` 或需要复现插入规则时使用。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `TOP` / `BOTTOM` | 列表末尾（高优先级）/ 列表开头（低优先级） | — | 枚举常量 |
| `opposite()` | 相反位置 | — | `PackPosition` |
| `insert(List<ResourcePackSummary> resourcePacks, ResourcePackSummary resourcePack, boolean reverse)` | 按本位置把包插入列表：`TOP` 走到末尾但停在连续"固定且同为 TOP"的块之前，`BOTTOM` 走到开头但跳过连续"固定且同为 BOTTOM"的块；`reverse` 时用相反位置 | 列表可修改 | 无（void） |

### `PackCompatibility`

Reference: `net.ornithemc.osl.resource.loader.api.resource.pack.PackCompatibility`

**作用**：资源包格式号与当前版本是否匹配。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `COMPATIBLE` / `TOO_OLD` / `TOO_NEW` | 兼容 / 太旧 / 太新 | — | 枚举常量 |
| `isCompatible()` | 是否 `COMPATIBLE` | — | `boolean` |
| `asFormat()` | 映射成一个代表性格式号（`TOO_OLD` → 支持值 - 1，`TOO_NEW` → 支持值 + 1，否则支持值） | — | `int` |
| `forFormat(int format)` | 由格式号推兼容性（1.12.2 支持值为 1） | — | `PackCompatibility` |

### `ResourceConsumer`

Reference: `net.ornithemc.osl.resource.loader.api.resource.pack.ResourceConsumer`

**作用**：`findResources` 的回调：`(位置, 资源输入流供应器) -> void`。输入流是**延迟打开**的，用不到就别打开。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `accept(NamespacedIdentifier location, IOSupplier<InputStream> resource)` | 处理一个发现的资源 | `resource` 可能为 `null`（包内该位置读取失败） | 无（void） |

### `ResourcePackFileNotFoundException`

Reference: `net.ornithemc.osl.resource.loader.api.resource.pack.ResourcePackFileNotFoundException`

**作用**：找不到资源时抛的 `FileNotFoundException` 子类，消息格式为 `'<path>' in ResourcePack '<pack name>'`，便于定位是哪个包缺文件。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `ResourcePackFileNotFoundException(ResourcePack pack, String path)` | 构造异常并格式化消息 | `pack` 非 `null`（会调用 `getName()`） | — |

## 资源访问

### `ResourceManager`

Reference: `net.ornithemc.osl.resource.loader.api.resource.manager.ResourceManager`

**作用**：资源访问层。按命名空间查资源、枚举目录、拿全部包列表。客户端 / 服务端各一个实例（按资源类型区分）。

**需要**：用 `client()`（1.12.2 上只有客户端是活的）；读出来的 `InputStream` 由调用方负责关闭。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `client()` | 客户端资源管理器（`CLIENT_ASSETS`，全局单例） | — | `ReloadableResourceManager` |
| `server()` | 服务端资源管理器（`SERVER_DATA`；1.12.2 上未被接线） | — | `ReloadableResourceManager` |
| `getResourcePacks()` | 当前已加载的包，顺序即优先级 | — | `List<ResourcePack>`（不可修改视图） |
| `hasResource(String path)` | 按直接路径判断存在（`pack.mcmeta` 等根文件、1.5.2 及更早的访问方式） | 路径相对包根 | `boolean` |
| `getResource(String path)` / `getResourceStack(String path)` | 按直接路径取最近 / 全部 | 找不到时抛 `IOException` | `InputStream` / `List<InputStream>` |
| `getNamespaces()` | 所有包提供的命名空间 | — | `Set<String>` |
| `hasResource(NamespacedIdentifier location)` | 命名空间式存在性检查 | 路径相对 `assets/<ns>/` 或 `data/<ns>/` | `boolean` |
| `getResource(NamespacedIdentifier location)` | 取优先级最高的那个资源（延迟打开） | 同上 | `Optional<Resource>` |
| `getResourceStack(NamespacedIdentifier location)` | 取该位置所有资源，顺序即包优先级 | 同上 | `List<Resource>`（可能为空） |
| `findResources(String directory, Predicate<NamespacedIdentifier> filter)` | 跨所有命名空间递归收集目录下资源（每个位置只取最高优先级那个） | `directory` 相对**命名空间目录**（不是包根） | `Map<NamespacedIdentifier, Resource>`（按位置排序） |
| `findResources(String namespace, String directory, Predicate<NamespacedIdentifier> filter)` | 同上，限定命名空间 | 同上 | 同上 |
| `findResourceStacks(String directory, Predicate<...>)` / `findResourceStacks(String namespace, String directory, Predicate<...>)` | 同上，但每个位置返回整条资源栈 | 同上 | `Map<NamespacedIdentifier, List<Resource>>` |

### `ReloadableResourceManager`

Reference: `net.ornithemc.osl.resource.loader.api.resource.manager.ReloadableResourceManager`

**作用**：可重载的资源管理器：注册重载器、声明重载顺序、触发重载。

**需要**：在 `ClientResourceLoaderEvents.INIT_RESOURCE_MANAGER` 里注册；重载器 id 全局唯一，重复注册抛 `IllegalArgumentException`。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `addReloader(ResourceReloader reloader)` | （已废弃，请改用 `registerReloader(id, reloader)`）注册一个没有 id 的重载器，它会排在有 id 的重载器之后、顺序不定 | 非 `null` | 无（void） |
| `registerReloader(NamespacedIdentifier identifier, ResourceReloader reloader)` | 以 id 注册重载器（id 用于依赖声明与日志） | id 未被注册过，否则抛 `IllegalArgumentException` | 无（void） |
| `registerReloaderDependencies(NamespacedIdentifier identifier, NamespacedIdentifier... dependencies)` | 声明"本重载器必须在这些之后运行"。未声明依赖的重载器排最后；可用 `AssetsReloaders.BEFORE_VANILLA` / `AFTER_VANILLA` 做整体前置 / 后置 | `identifier` 应是已注册（或将要注册）的重载器 id；依赖里未注册的 id 会被忽略 | 无（void） |
| `reload(List<ResourcePack> packs)` | 阻塞式完整重载：重建包索引 → 排序重载器 → 跑两阶段 | 传入的通常是 `repository.openSelectedPacks()` | 无（void）；内部异常会在方法内抛出 |
| `startReload(List<ResourcePack> packs, Executor backgroundExecutor, Executor mainThreadExecutor, CompletableFuture<?> initialTask)` | 异步版重载：返回句柄，可查进度 | 两个执行器非 `null`；`initialTask` 是"开始前要先完成的事" | `ResourceReload` |

> 依赖排序用的是拓扑排序实现，**没有环检测**：声明循环依赖会让排序阶段无法结束。请保证依赖图是 DAG。

### `Resource`

Reference: `net.ornithemc.osl.resource.loader.api.resource.Resource`

**作用**：一个具体资源的句柄：知道来源包、位置，能按流/按文本打开，并带 `.mcmeta` 元数据（`extends Closeable`）。

**需要**：由 `ResourceManager` 返回，`open()` 出来的流由调用方关闭；`metadata()` 只有在 `hasMetadata()` 为真时才有内容。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `supplier(Path path)`（static） | 把文件路径包装成 `IOSupplier<InputStream>`（延迟打开） | 路径存在性在打开时才检查 | `IOSupplier<InputStream>` |
| `sourceName()` | 资源来自哪个包（通常是包名） | — | `String` |
| `location()` | 资源位置（相对命名空间目录的 `namespace:path`） | — | `NamespacedIdentifier` |
| `open()` | 打开为输入流 | 调用方负责关闭 | `InputStream`；失败抛 `IOException` |
| `openAsReader()` | 以 UTF-8 文本方式打开 | 同上 | `BufferedReader`；失败抛 `IOException` |
| `metadata()` | 读取同名 `.mcmeta` 元数据 | 失败抛 `IOException`；没有元数据时返回空实现 | `ResourceMetadata` |
| `hasMetadata()` | 是否存在 `.mcmeta` | — | `boolean` |

### `ResourceLocation`

Reference: `net.ornithemc.osl.resource.loader.api.resource.ResourceLocation`

**作用**：资源位置（命名空间 + 路径）的构造与校验工具。校验强度**随 MC 版本（格式号）变化**。

**需要**：1.12.2 支持格式 1，因此：命名空间**不允许大写字母**（其它字符不限），路径**完全不校验**；不合法的命名空间 / 路径会让 `of` 抛 core 的运行时异常 `NamespacedIdentifierException`。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `of(String namespace, String path)` | 构造资源位置并校验 | 1.12.2：命名空间无大写；其余按版本规则 | `NamespacedIdentifier`；非法时抛 `NamespacedIdentifierException` |
| `isValid(NamespacedIdentifier location)` | 校验命名空间 + 路径 | — | `boolean` |
| `isValidNamespace(String)` / `isValidPath(String)` | 单独校验 | — | `boolean` |
| `isCharAllowed(int chr)` | 该码点能否出现在资源位置里 | — | `boolean` |

### `ResourcePath`

Reference: `net.ornithemc.osl.resource.loader.api.resource.ResourcePath`

**作用**：路径字符串与 `java.nio.file.Path` 的换算工具（补 / 去前导 `/`，拼 `<type>/<namespace>/<path>`）。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `relative(String pathName)` | 去掉前导 `/` | 非空字符串 | `String` |
| `absolute(String pathName)` | 补上前导 `/` | 非空字符串 | `String` |
| `nameOf(ResourceType type, NamespacedIdentifier location)` | 拼出 `assets/<ns>/<path>` 或 `data/<ns>/<path>` | — | `String` |
| `of(String path)` / `of(ResourceType type, NamespacedIdentifier location)` | 以当前目录为根解析成相对 `Path` | — | `Path` |
| `of(Path root, String path)` / `of(Path root, ResourceType type, NamespacedIdentifier location)` | 以给定根解析，并把 `/` 换成平台分隔符后 `normalize()` | `root` 非 `null` | `Path` |

### `ResourceType`

Reference: `net.ornithemc.osl.resource.loader.api.resource.ResourceType`

**作用**：区分两类资源：客户端资源（`assets`）与服务端数据（`data`）。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `CLIENT_ASSETS` / `SERVER_DATA` | 对应 `assets` / `data` 目录 | — | 枚举常量 |
| `directory()` | 该类型在资源包里的目录名 | — | `String`（`"assets"` / `"data"`） |

### `ResourceMetadata`

Reference: `net.ornithemc.osl.resource.loader.api.resource.ResourceMetadata`

**作用**：资源 / 资源包的 `.mcmeta` 元数据模型，按"节（section）"读取。

**需要**：用 `supplier(...)` 或具体实现的构造拿到实例；按节读取要么用 `Section` 常量，要么自己 `Section.of(name, serializer)`。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `FILE_EXTENSION` | 元数据文件后缀 `".mcmeta"` | — | `String` |
| `EMPTY` / `EMPTY_SUPPLIER` | 空元数据（任何节都返回 `null`） | — | `ResourceMetadata` / `IOSupplier<ResourceMetadata>` |
| `supplier(IOSupplier<InputStream>)` | 用输入流供应器延迟解析元数据 | 输入流是合法 JSON 对象 | `IOSupplier<ResourceMetadata>` |
| `getSection(Section<T> section)` | 读指定节 | — | `T` 或 `null` |
| `getSection(String name, Section.Serializer<T> serializer)` | 读指定名字的节并用给定序列化器解析 | 节不存在返回 `null` | `T` 或 `null` |
| `Section.of(String name, Serializer<T> serializer)`（static） | 构造一个节类型 | — | `Section<T>` |
| `Section#name()` / `Section#serializer()` | 节名 / 序列化器 | — | `String` / `Serializer<T>` |
| `Serializer#deserialize(JsonObject json)` | 把该节的 JSON 转成值对象 | 由实现决定缺字段时的行为（`pack` 节缺字段会抛 `JsonSyntaxException`） | `T` |

## 重载

### `ResourceReloader`

Reference: `net.ornithemc.osl.resource.loader.api.resource.reload.ResourceReloader`

**作用**：重载器的根接口：参与一次资源重载的全部逻辑（准备共享状态 + 返回自身重载的 future）。

**需要**：手写实现要自己处理"后台 reload → 主线程 apply"，并在 apply 前调用 `previousStep.await(...)` 参与屏障，否则其它重载器的 apply 阶段不会被正确同步。多数情况下继承 `SimpleResourceReloader` 或 `ResourceReloadListener` 更省事。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `getName()` | 日志里显示的名字（默认类名） | — | `String` |
| `prepareSharedState(SharedState state)` | 在所有人开始前准备跨重载器共享的数据（按排序顺序同步调用） | `state` 由重载流程提供 | 无（void） |
| `reloadResources(SharedState state, ReloadStep previousStep, Executor reloadExecutor, Executor applyExecutor)` | 执行本重载器：把重活丢给 `reloadExecutor`，把改游戏状态的活丢给 `applyExecutor`，apply 前先 `previousStep.await(...)` | 返回的 future 完成才算本重载器结束 | `CompletableFuture<Void>` |
| `SharedState#resourceManager()` | 本次重载使用的资源管理器 | — | `ResourceManager` |
| `SharedState#set(Key<T>, T)` / `get(Key<T>)` | 共享状态的键值存取（键自己定义成 `SharedState.Key<T>` 常量） | 键要唯一；未设置的键返回 `null` | 无（void）/ `T` |
| `SharedState.Key<T>` | 共享状态的键类型（空接口，自己实现 / 匿名类即可） | — | — |

### `SimpleResourceReloader<T>`

Reference: `net.ornithemc.osl.resource.loader.api.resource.reload.SimpleResourceReloader<T>`

**作用**：两阶段重载器的便利实现：你只写"加载"与"应用"两个方法。

**需要**：`reloadResources(ResourceManager)` 在**后台线程**执行（不要碰世界 / 渲染状态）；`applyResources(T, ResourceManager)` 在**主线程**执行。`prepareSharedState` 为空实现，要用就覆写。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `reloadResources(ResourceManager manager)` | 在后台加载并返回结果对象 | 不修改游戏状态 | `T`（可为 `null`） |
| `applyResources(T resources, ResourceManager manager)` | 在主线程把结果应用出去 | 在屏障之后调用 | 无（void） |
| `reloadResources(SharedState, ReloadStep, Executor, Executor)` | 已实现的编排：`supplyAsync(加载, reloadExecutor) → thenCompose(previousStep::await) → thenAcceptAsync(应用, applyExecutor)` | 一般不要覆写 | `CompletableFuture<Void>` |
| `prepareSharedState(SharedState)` | 默认空实现 | — | 无（void） |

```java
public class CookiesManager implements SimpleResourceReloader<Cookies> {
    public static final NamespacedIdentifier IDENTIFIER = NamespacedIdentifiers.from("example", "cookies");

    @Override public Cookies reloadResources(ResourceManager manager) { /* 只读资源、解析 */ return new Cookies(...); }
    @Override public void applyResources(Cookies cookies, ResourceManager manager) { /* 改游戏状态 */ }
}
```

### `ResourceReloadListener`

Reference: `net.ornithemc.osl.resource.loader.api.resource.reload.ResourceReloadListener`

**作用**：只关心"重载完成后在主线程做点什么"的重载器：跳过 reload 阶段，直接在 apply 阶段调用 `resourcesReloaded`。

**需要**：适合"已有资源被别处加载好了，我只需要刷新缓存"的场景。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `resourcesReloaded(ResourceManager manager)` | 在**主线程**、所有 reload 阶段结束后调用 | `manager` 与 `ResourceManager.client()` 是同一个实例 | 无（void） |
| `prepareSharedState(SharedState)` | 默认空实现 | — | 无（void） |
| `reloadResources(SharedState, ReloadStep, Executor, Executor)` | 已实现：`previousStep.await(Unit)` 之后在 `applyExecutor` 上调用 `resourcesReloaded` | 不要覆写 | `CompletableFuture<Void>` |

### `ReloadStep`

Reference: `net.ornithemc.osl.resource.loader.api.resource.reload.ReloadStep`

**作用**：重载流程发给每个重载器的"闸门"：调用 `await(x)` 表示"我在等前面的步骤 / 等所有人 reload 完"，返回一个在条件满足后完成的 future。

**需要**：只有自己实现 `ResourceReloader` 才会碰到它；回调里必须真的把它接到自己的 future 链上（`await` 也负责登记"本重载器已完成"）。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `await(T object)` | 返回"所有重载器的 reload 阶段完成 **且** 上一个重载器的任务完成"之后会给出 `object` 的 future | `object` 可为 `null` | `CompletableFuture<T>` |

### `ResourceReload`

Reference: `net.ornithemc.osl.resource.loader.api.resource.reload.ResourceReload`

**作用**：一次资源重载的句柄：进度、阶段、结果。也可用静态工厂自行发起一次重载（例如只想重载某个子系统）。

**需要**：由 `ResourceReload.start(...)` 或 `ReloadableResourceManager#startReload` 产生；异常要通过 `checkExceptions()` 才会抛出。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `start(ResourceManager, List<ResourceReloader>, Executor bg, Executor main, CompletableFuture<?> initialTask)` | 用一组重载器发起重载 | 执行器非 `null` | `ResourceReload` |
| `start(ResourceManager, List<ResourceReloader>, Executor bg, Executor main, CompletableFuture<?> initialTask, Runnable finalTask)` | 同上，并在全部完成后（主线程）执行 `finalTask` | 同上 | `ResourceReload` |
| `start(ResourceManager, ResourceReloader, Executor bg, Executor main)` | 只跑一个重载器 | 同上 | `ResourceReload` |
| `result()` | 整体完成 future | — | `CompletableFuture<Unit>`（`Unit` 来自 core） |
| `getProgress()` | 进度 0~1（按 reload / apply 任务加权估算） | — | `float` |
| `isApplying()` | 是否已进入 apply 阶段（所有 reload 阶段结束） | — | `boolean` |
| `isDone()` | 是否已完成 | — | `boolean` |
| `checkExceptions()` | 若完成时带异常则把它（包装成非受检）抛出 | 只能在需要"失败就炸"的地方调用 | 无（void） |

### `ResourceReloadContext`

Reference: `net.ornithemc.osl.resource.loader.api.resource.reload.ResourceReloadContext`

**作用**：`START_RESOURCE_RELOAD` / `END_RESOURCE_RELOAD` 事件的上下文：本次重载实际用了哪些包、哪些重载器（且已排序）。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `resourcePacks()` | 本次重载使用的资源包（顺序即优先级） | — | `List<ResourcePack>` |
| `resourceReloaders()` | 本次重载使用的重载器（已按依赖排序，即实际执行顺序） | — | `List<ResourceReloader>` |

### `AssetsReloaders`

Reference: `net.ornithemc.osl.resource.loader.api.client.resource.reload.AssetsReloaders`

**作用**（仅客户端，且只存在于 1.12.2 这类子工程）：Vanilla 各重载器的标识符，用来给 `registerReloaderDependencies` 声明"我要在某个 Vanilla 重载器之前 / 之后跑"。这些 id 由模块在 Vanilla 注册 reload listener 时按对象身份识别出来。

| 成员 | 对应 Vanilla 重载对象 | 值 |
|---|---|---|
| `LANGUAGE_MANAGER` | 语言管理器 | `minecraft:languages` |
| `TEXTURE_MANAGER` | 纹理管理器 | `minecraft:textures` |
| `SOUND_MANAGER` | 声音管理器 | `minecraft:sounds` |
| `FONT_MANAGER` | 字体 | `minecraft:fonts` |
| `ENCHANTING_PHRASE_FONT_MANAGER` | 附魔台文字字体 | `minecraft:enchanting_phrase_fonts` |
| `GRASS_COLORS` | 草色 | `minecraft:grass_colors` |
| `FOLIAGE_COLORS` | 叶色 | `minecraft:foliage_colors` |
| `MODEL_MANAGER` | 方块 / 物品模型 | `minecraft:models` |
| `ITEM_RENDERER` | 物品渲染 | `minecraft:item_renderer` |
| `GAME_RENDERER` | 游戏渲染 | `minecraft:game_renderer` |
| `BLOCK_RENDERER` | 方块渲染 | `minecraft:block_renderer` |
| `WORLD_RENDERER` | 世界渲染（id 名是 `level_renderer`） | `minecraft:level_renderer` |
| `SEARCH_REGISTRY` | 创造模式搜索索引（1.12-pre6 起存在） | `minecraft:search_registry` |
| `BEFORE_VANILLA` | 所有 Vanilla 重载器之前（空操作占位重载器） | `osl:before_vanilla` |
| `AFTER_VANILLA` | 所有 Vanilla 重载器之后（空操作占位重载器） | `osl:after_vanilla` |

```java
// 想在模型加载完之后、其余 Vanilla 重载器之前跑
manager.registerReloaderDependencies(CookiesManager.IDENTIFIER, AssetsReloaders.MODEL_MANAGER);
// 想在所有 Vanilla 重载器之后跑
manager.registerReloaderDependencies(CookiesManager.IDENTIFIER, AssetsReloaders.AFTER_VANILLA);
```

## 完整示例：内置资源包 + 自定义重载器

```java
public class Example implements ClientModInitializer {
    @Override
    public void initClient() {
        ModContainer mod = FabricLoader.getInstance().getModContainer("example").get();

        // 1) 把一个子目录注册成独立的必需资源包（BOTTOM，低优先级）
        ResourcePackRepository.registerBundledModResourcePack("example-assets", "Example Assets", mod, "client/assets");

        // 2) 注册重载器，并声明顺序
        ClientResourceLoaderEvents.INIT_RESOURCE_MANAGER.register(manager -> {
            manager.registerReloader(CookiesManager.IDENTIFIER, new CookiesManager());
            manager.registerReloaderDependencies(CookiesManager.IDENTIFIER, AssetsReloaders.AFTER_VANILLA);
        });

        // 3) 观察重载结果（可选）
        ClientResourceLoaderEvents.END_RESOURCE_RELOAD.register((manager, ctx) -> {
            // 主线程，所有包与新资源都已就绪
        });
    }
}
```
