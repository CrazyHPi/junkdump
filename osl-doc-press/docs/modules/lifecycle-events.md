---
title: 17 lifecycle-events
---

# 17 lifecycle-events

::: warning 0.26.0 变更
本章按 **0.24.0** 的 API 整理。0.26.0 中整个 `LifecycleEvents` 已标记 `@Deprecated`，建议改用 `RegistryEvents.BOOTSTRAP_REGISTRIES`，详见[变更历史](/changelog#lifecycle-events-0-6-1-0-7-0)。
:::

> 一句话定位：1.12.2 上最完整的"游戏生命周期"事件入口——启动、初始化完成、tick、世界加载、关闭，双端都有。

| 项 | 值 |
|---|---|
| 模块 id | `lifecycle-events` |
| Maven | `net.ornithemc.osl-gen2:lifecycle-events:0.6.1+mc13w36a-mc19w07a` |
| 端 | 双端（`environment: "*"`；客户端类只在客户端存在） |
| 依赖 | `ploceus.dependOslModule('lifecycle-events', '0.24.0')` |

其它 mod 里的 `mods.toml`/`FMLInitializationEvent` 那套钩子在 Ornithe 上不存在，本模块把它们换成一串静态 `Event` 字段：`BOOTSTRAP_*`（注册表引导）、`MinecraftClientEvents`（客户端启动/关闭/tick）、`ClientWorldEvents`（客户端世界 tick）、`MinecraftServerEvents`（服务端启动/关闭/tick/世界加载，**单人集成服务器与专用服务器都会触发**）、`ServerWorldEvents`（每个维度 tick）。配合 `MinecraftInstance` / `MinecraftServerInstance` 两个实例访问器，就能在不写 mixin 的情况下覆盖绝大多数"我需要一个入口"的场景。

## 注册方式（所有事件通用）

所有事件都是 `public static final Event<...>` 字段，来自 `net.ornithemc.osl.core.api.events.Event`：

- `EVENT.register(listener)` 添加监听器；监听器按注册先后顺序被调用。
- 监听器必须**尽早**注册：`BOOTSTRAP_START` / `MinecraftClientEvents.START` / `MinecraftServerEvents.START` 都在入口点之后极短时间内触发，因此应在 `init` / `client-init` / `server-init` 入口点里注册。
- 事件没有优先级、没有取消机制、也没有 `unregister`（源码未提供）。
- 监听器抛出的异常**不会**被 OSL 捕获，会直接向上冒泡（源码未做保护），请自行 try/catch。

## 注册表引导（双端）

### `LifecycleEvents`

Reference: `net.ornithemc.osl.lifecycle.api.LifecycleEvents`

**作用**：包围原版 `Bootstrap.init()`（方块/物品/注册表/矿物词典的静态初始化）。想在原版内容全部就绪的边界上做一次性的注册或检查时用它。

**需要**：监听器要在入口点里注册；`Bootstrap.init()` 可能被重复调用，但这两个事件对**每个进程只触发一次**（实现里用静态标志位守卫，后续调用不再触发）。

**返回**：无（`Event<Runnable>`，无参数无返回值）。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `BOOTSTRAP_START` | 在原版 `Bootstrap.init()` 的入口处触发（早于所有原版注册表填充） | 只在进程生命周期里触发一次 | 无 |
| `BOOTSTRAP_END` | 在原版 `Bootstrap.init()` 的末尾触发（原版注册已完成） | 只在进程生命周期里触发一次 | 无 |

## 客户端

### `MinecraftClientEvents`

Reference: `net.ornithemc.osl.lifecycle.api.client.MinecraftClientEvents`

**作用**：客户端主生命周期的五个时机。几乎所有"客户端要初始化一次"或"每 tick 要做点事"的代码都挂在这里。

**需要**：监听器在客户端入口点（`init` / `client-init`）里注册；参数是 `net.minecraft.client.Minecraft` 实例，**不要**把它存到静态字段长期持有（关闭后实例会被丢弃，源码在 `STOP` 之后才清空引用）。

**返回**：无（事件不返回值）。

| 成员 | 触发时机（1.12.2 注入点） | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `START` | `Minecraft` 初始化方法（Ornithe 映射名 `init`，即构造流程）的**最开头**。此时实例已创建并被 OSL 记为当前实例，但资源管理器、渲染、字体、音效都还没就绪 | 不要在这里访问纹理/字体/音效等资源系统（都还没初始化） | 无 |
| `READY` | 同一初始化方法的**末尾**，即客户端初始化完成 | 适合做"一次性"的客户端初始化（加载贴图、注册渲染器） | 无 |
| `STOP` | `Minecraft.shutdown()` 的**开头**。此时实例仍然有效 | 适合保存配置、释放自己持有的资源；不要在这里等待后台任务太久 | 无 |
| `TICK_START` | `Minecraft.tick()` 的开头，**每个客户端 tick 一次** | 参数可为 null（源码直接传入当前实例字段，正常流程下非 null） | 无 |
| `TICK_END` | `Minecraft.tick()` 的末尾 | 同上；输入处理、世界 tick 都已完成 | 无 |

> 时序补充：`STOP` 触发后、`shutdown()` 返回时 OSL 会清空实例引用，因此 `STOP` 之后调用 `MinecraftInstance.get()` 会抛异常。

### `MinecraftInstance`

Reference: `net.ornithemc.osl.lifecycle.api.client.MinecraftInstance`

**作用**：拿到当前的 `Minecraft` 实例，避免依赖原版的静态访问器命名。

**需要**：只能在客户端、且只在 `START` 触发之后到 `shutdown()` 结束之前调用。

**返回**：`net.minecraft.client.Minecraft`。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `get()` | 取当前客户端实例 | 太早（`START` 之前）或太晚（`STOP` 之后）都会抛 `IllegalStateException`，消息为 `no Minecraft instance available right now` | `Minecraft` |

### `ClientWorldEvents`

Reference: `net.ornithemc.osl.lifecycle.api.client.ClientWorldEvents`

**作用**：客户端世界（`net.minecraft.client.world.ClientWorld`）的每 tick 回调。用于"世界已存在时才做"的客户端逻辑：粒子、音效、HUD 上的世界信息等。

**需要**：监听器在入口点注册；回调参数是该 tick 的世界实例，切换世界后参数会变成新实例（事件本身**不通知**世界切换，见文末说明）。

**返回**：无（事件不返回值）。

| 成员 | 触发时机 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `TICK_START` | `ClientWorld.tick()` 开头，每个客户端世界每 tick 一次 | 世界玩家实体可能还没初始化（进入世界的第一 tick），访问玩家前先判空 | 无 |
| `TICK_END` | `ClientWorld.tick()` 末尾 | 同上 | 无 |

## 服务端

### `MinecraftServerEvents`

Reference: `net.ornithemc.osl.lifecycle.api.server.MinecraftServerEvents`

**作用**：服务端主生命周期：启动、初始化完成、tick、世界存档加载的三个阶段、关闭。**单人游戏的集成服务器同样触发这些事件**，所以写"服务端逻辑"时不需要区分单人/专用。

**需要**：监听器在入口点注册（专用服务器用 `server-init`，单人也要生效就同时挂在 `init` 上）；参数是 `net.minecraft.server.MinecraftServer` 实例，单人游戏每次进入/切换世界都会有**新的**服务端实例。

**返回**：无（事件不返回值）。

| 成员 | 触发时机（1.12.2 注入点） | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `START` | `MinecraftServer.run()` 的开头；实例已创建并被 OSL 记为当前实例 | 此时世界/配置尚未加载 | 无 |
| `READY` | `run()` 中 `init()` 返回之后（服务器初始化完成，即将进入主循环） | 适合做一次性的服务端初始化；此时世界加载流程通常已经跑完（见下一行注） | 无 |
| `STOP` | `MinecraftServer.shutdown()` 的开头 | 只会在**最外层** `shutdown()` 调用时触发一次：内部用嵌套深度计数，避免递归关闭时重复触发；`shutdown()` 全部返回后实例引用被清空 | 无 |
| `TICK_START` | `MinecraftServer.tick()` 开头，每个服务端 tick 一次 | — | 无 |
| `TICK_END` | `MinecraftServer.tick()` 末尾 | 世界 tick 已完成，适合做"每 tick 收尾"（同步数据、发网络包） | 无 |
| `LOAD_WORLD` | `MinecraftServer.convertWorld()` 的开头，即**读取世界存档数据之前** | 适合在此之前修改存档目录/世界类型/难度等会影响读档的东西 | 无 |
| `PREPARE_WORLD` | `MinecraftServer.prepareWorlds()` 的开头，即**存档已读入、出生区块还没加载** | 适合调整出生点、维度列表等 | 无 |
| `READY_WORLD` | `MinecraftServer.prepareWorlds()` 的末尾，即**出生区块已加载** | 适合做"世界已可用"的初始化（放置结构、生成初始实体） | 无 |

> 关于 `READY` 与三个世界事件的先后：`convertWorld`/`prepareWorlds` 属于世界加载流程，按 1.12.2 原版流程它们在 `run()` 调用 `init()` 期间执行，因此**通常早于** `READY`。源码本身没有把这条顺序写成契约，若顺序对你的逻辑很关键，建议在两个事件里各打一条日志实测。

### `MinecraftServerInstance`

Reference: `net.ornithemc.osl.lifecycle.api.server.MinecraftServerInstance`

**作用**：拿到当前的 `MinecraftServer` 实例。

**需要**：只能在 `START` 之后、`shutdown()` 结束之前调用。客户端（单人）与服务端都可用。

**返回**：`net.minecraft.server.MinecraftServer`。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `get()` | 取当前服务端实例 | 无实例时抛 `IllegalStateException`，消息为 `no MinecraftServer instance available right now` | `MinecraftServer` |

### `ServerWorldEvents`

Reference: `net.ornithemc.osl.lifecycle.api.server.ServerWorldEvents`

**作用**：服务端每个维度世界的每 tick 回调。

**需要**：注意**一个 tick 会触发多次**（主世界、下界、末地各一次），必须按回调参数区分维度，不要假设只有一个世界。

**返回**：无（事件不返回值）。

| 成员 | 触发时机 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `TICK_START` | `ServerWorld.tick()` 开头，每个维度每 tick 一次 | 参数是该维度的 `net.minecraft.server.world.ServerWorld` | 无 |
| `TICK_END` | `ServerWorld.tick()` 末尾 | 同上 | 无 |

## 1.12.2 触发顺序总览

| 顺序 | 客户端 | 服务端（含单人） |
|---|---|---|
| 1 | 入口点（`init` / `client-init`） | 入口点（`init` / `server-init`） |
| 2 | `LifecycleEvents.BOOTSTRAP_START` | `LifecycleEvents.BOOTSTRAP_START` |
| 3 | `LifecycleEvents.BOOTSTRAP_END` | `LifecycleEvents.BOOTSTRAP_END` |
| 4 | `MinecraftClientEvents.START` | `MinecraftServerEvents.START`（`run()` 开头） |
| 5 | `MinecraftClientEvents.READY` | `LOAD_WORLD` → `PREPARE_WORLD` → `READY_WORLD` |
| 6 | 每 tick：`TICK_START` → 世界/界面逻辑 → `TICK_END` | `MinecraftServerEvents.READY`（`init()` 之后） |
| 7 | `ClientWorldEvents.TICK_START` / `TICK_END`（世界存在时，嵌在 6 里） | 每 tick：`TICK_START` → `ServerWorldEvents.TICK_*`（每个维度）→ `TICK_END` |
| 8 | `MinecraftClientEvents.STOP` → 实例被清空 | `MinecraftServerEvents.STOP` → 实例被清空 |

> 顺序表里 `BOOTSTRAP_*` 与入口点的关系取决于原版何时调用 `Bootstrap.init()`（1.12.2 在客户端启动较早阶段、服务端初始化阶段）；源码未固定这一点，请以实测为准。

## 本模块**不**提供的事件（避免浪费时间找）

- **没有**"世界卸载/离开世界"事件（客户端与服务端都没有）。服务端只有存档加载的三个阶段（`LOAD_WORLD` / `PREPARE_WORLD` / `READY_WORLD`），客户端则完全没有世界加载事件，`ClientWorldEvents` / `ServerWorldEvents` 只有 tick。要检测"进入/离开世界"，只能靠跟踪 tick 回调里世界实例的引用变化，或自己写 mixin。
- **没有**玩家登录/断线、连接建立/断开事件。
- **没有**资源包重载、语言切换、窗口尺寸变化事件。
- 以上均以源码为准：这些事件的字段在本模块中不存在，1.12.2 上也没有对应的替代 API。
