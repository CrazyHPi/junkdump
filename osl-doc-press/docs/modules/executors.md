---
title: 14 executors
---

# 14 executors

> 一句话定位：一个共享的后台线程池 + 一个"主线程执行器"接口，用来安全地在后台线程和游戏主线程之间切换。

| 项 | 值 |
|---|---|
| 模块 id | `executors` |
| Maven | `net.ornithemc.osl-gen2:executors:0.1.1+mc14w21a-mc1.13.2` |
| 端 | 双端 |
| 依赖 | `ploceus.dependOslModule('executors', '0.24.0')` |

做 mod 时经常需要"后台算，主线程用"：读文件、解析数据、压缩区块都不该占用 tick 线程；而改世界、改渲染状态又只能在主线程做。本模块提供两半：`BackgroundExecutor.get()` 给出一个由 OSL 统一管理（随游戏关闭而关闭）的后台线程池；`MainThreadExecutor` 被注入到 `Minecraft` 与 `MinecraftServer`，让你能把任务排回主线程队列，并能判断"我现在是不是在主线程上"。

## 后台执行

### `BackgroundExecutor`

Reference: `net.ornithemc.osl.executors.api.BackgroundExecutor`

**作用**：访问 OSL 的**共享**后台线程池。全游戏只有这一个池（所有 mod 共用），所以不要在里面跑会长期阻塞的任务，否则会挤占别人的后台任务。

**需要**：任务必须在任意线程上都安全；**不要**在后台任务里改动世界、实体、渲染状态或客户端资源（源码注释明确警告会导致存档损坏与崩溃）。结果是"要回到主线程生效"的，通过 `MainThreadExecutor` 排回去。

**返回**：`Executor`（不是 `ExecutorService`，源码只暴露了 `execute`）。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `get()` | 取得共享后台执行器 | 可在任意线程、任意时刻调用（池是静态初始化的） | `java.util.concurrent.Executor` |

**池的特性（源自实现，写代码时需要知道）**：

- 底层是 `ForkJoinPool`，工作线程名形如 `Worker-OSL-<n>`。
- 线程数 = `min(可用处理器数 - 1, 上限)`；上限默认 255，可用系统属性 `max.bg.threads`（1~255）覆盖，非法值只打错误日志后回退默认。源码对单核机器（算出 0）没有特殊处理。
- 任务抛出的异常会被池捕获、解包 `CompletionException` 后记日志，**不会**打断你的调用方。
- 游戏关闭（`Minecraft.shutdown` / `MinecraftServer.shutdown` 结束时）会 `shutdown` 该池，等待 3 秒未终止则 `shutdownNow`。所以不要在游戏关闭之后再往里提交任务。

```java
BackgroundExecutor.get().execute(() -> {
    byte[] data = loadHeavyFile(); // 后台做 I/O
    ((MainThreadExecutor) MinecraftInstance.get()).execute(() -> applyToWorld(data)); // 回主线程
});
```

## 主线程执行

### `MainThreadExecutor`

Reference: `net.ornithemc.osl.executors.api.MainThreadExecutor`

**作用**：把任务投递到游戏主线程队列并延后执行；同时提供"当前线程是不是主线程"的判断。这个接口被**接口注入**到 `net.minecraft.client.Minecraft` 和 `net.minecraft.server.MinecraftServer` 上，因此实操写法是对这两个实例强转。

**需要**：mod 作者**不实现**它，只强转使用：

- 客户端：`(MainThreadExecutor) MinecraftInstance.get()`（lifecycle-events 提供实例访问器；`MinecraftClientEvents.START` 的参数就是同一个实例）
- 服务端：`(MainThreadExecutor) MinecraftServerInstance.get()`

**返回**：`execute` 为 `void`；`isRunningOnSameThread` 返回 `boolean`。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `execute(Runnable task)` | 把任务排进主线程队列，由主线程在后续 tick 中执行 | `task` 非 null；在后台线程调用时任务是异步生效的，不要假设"调用完就已经执行完" | 无（void） |
| `isRunningOnSameThread()` | 判断调用线程是否就是该执行器的主线程 | — | `boolean`：是则 `true` |

**注意（接口默认实现）**：这两个方法在接口上都有 default 实现，且默认体是 `throw new UnsupportedOperationException()` —— 这是为接口注入留下的占位实现。也就是说，如果你把某个**没有被注入**的对象强转成 `MainThreadExecutor`，调用会直接抛 `UnsupportedOperationException`，而不是编译错误。
