---
title: 13 entrypoints
---

# 13 entrypoints

> 一句话定位：Minecraft 还没有 `Minecraft` 实例时就能跑代码的三个 mod 入口点，以及解析启动参数的钩子。

| 项 | 值 |
|---|---|
| 模块 id | `entrypoints` |
| Maven | `net.ornithemc.osl-gen2:entrypoints:0.6.1+mc13w16a-mc1.14.4` |
| 端 | 双端（`environment: "*"`，三个入口点分别对应客户端/服务端） |
| 依赖 | `ploceus.dependOslModule('entrypoints', '0.24.0')` |

Fabric Loader 的 `entrypoints` 在 OSL 里被重新定义为三个固定的键：`init`、`client-init`、`server-init`。它们在 `Minecraft`/`MinecraftServer` 的 `main` 方法**最开始**被调用——此时游戏窗口、资源管理器、世界都还不存在，因此适合做注册表登记、事件监听器挂载、配置读取这类"越早越好"的工作。`LaunchEvents.PARSE_RUN_ARGS` 则在选项解析前后各插了一次，用来读取启动器传进来的自定义参数。

## 入口点

> **三个键名就是字面量**（源码常量）：`"init"`、`"client-init"`、`"server-init"`，**没有** `osl:` 之类的前缀。写在 `fabric.mod.json` 的 `entrypoints` 段里，值为实现对应接口的类名列表。OSL 用 `FabricLoader.invokeEntrypoints(key, Interface.class, ...)` 分派，所以**入口点类必须实现对应接口**，否则加载即报错。

### `ModInitializer`

Reference: `net.ornithemc.osl.entrypoints.api.ModInitializer`

**作用**：双端通用入口点。客户端与服务端都会在各自的 `main` 最开始调用一次。绝大多数的注册/事件挂载都应写在这里。

**需要**：实现 `init()`；在 `fabric.mod.json` 里登记：

```json
"entrypoints": { "init": ["com.example.mymod.MyMod"] }
```

**返回**：无（`void`）。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `ENTRYPOINT_KEY` | 常量字符串 `"init"`，即 `fabric.mod.json` 中的键名 | 只读常量 | `String` |
| `init()` | 入口点回调 | 客户端在 `Main.main` 的 HEAD 调用；服务端在 `MinecraftServer.main` 的 HEAD 调用。此时**没有** `Minecraft`/`MinecraftServer` 实例，不要访问 `MinecraftInstance.get()`（会抛 `IllegalStateException`） | 无（void） |

### `ClientModInitializer`

Reference: `net.ornithemc.osl.entrypoints.api.client.ClientModInitializer`

**作用**：仅客户端的入口点，调用时机与 `ModInitializer.init()` 相同（同一个注入点，`init` 先于 `client-init`）。把只在客户端存在的 API（渲染、按键、界面）挂在这里，可以避免服务端类加载问题。

**需要**：实现 `initClient()`；在 `fabric.mod.json` 里用键 `"client-init"` 登记。专用服务端上不会触发。

**返回**：无（`void`）。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `ENTRYPOINT_KEY` | 常量字符串 `"client-init"` | 只读常量 | `String` |
| `initClient()` | 客户端入口点回调 | 在 `net.minecraft.client.main.Main.main` 的 HEAD 调用；此时 OpenGL、资源管理器都还没初始化 | 无（void） |

### `ServerModInitializer`

Reference: `net.ornithemc.osl.entrypoints.api.server.ServerModInitializer`

**作用**：仅服务端的入口点，调用时机与 `ModInitializer.init()` 相同（`init` 先于 `server-init`）。

**需要**：实现 `initServer()`；在 `fabric.mod.json` 里用键 `"server-init"` 登记。客户端（含单人游戏的集成服务器）**不会**触发它，单人服务器端的逻辑请用 `ModInitializer` 或 lifecycle-events 的服务端事件。

**返回**：无（`void`）。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `ENTRYPOINT_KEY` | 常量字符串 `"server-init"` | 只读常量 | `String` |
| `initServer()` | 服务端入口点回调 | 在 `net.minecraft.server.MinecraftServer.main` 的 HEAD 调用 | 无（void） |

## 启动参数

### `LaunchEvents`

Reference: `net.ornithemc.osl.entrypoints.api.launch.LaunchEvents`

**作用**：暴露 `PARSE_RUN_ARGS` 事件，让你向 Minecraft 自己的 `joptsimple.OptionParser` 里添加自定义选项，并在解析完成后读取它们的值。

**需要**：在入口点（`init`/`client-init`/`server-init`）里 `register` 监听器，且必须早于选项解析——即只能在上述入口点里注册，不能等到 `MinecraftClientEvents.START` 之后。

**返回**：无（事件不返回值；你通过 `OptionSet` 自己取值）。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `PARSE_RUN_ARGS` | 静态字段，类型 `Event<OptionsConsumer>` | `defineOptions` 与 `acceptOptions` 会被分两趟、按监听器注册顺序分别调用 | 无（事件无返回值） |

**触发时机（1.12.2）**：

| 端 | 注入点 | 调用的方法 |
|---|---|---|
| 客户端 | `Main.main` 中、`OptionParser.parse(String[])` **之前** | 所有监听器的 `defineOptions(parser)` |
| 客户端 | `Main.main` 中、`parse` 返回之后 | 所有监听器的 `acceptOptions(options)` |
| 服务端 | `MinecraftServer.main` 的 HEAD（在 `init`/`server-init` 之后） | OSL 自己 new 一个允许未知选项的 `OptionParser`，依次调用 `defineOptions` 再 `acceptOptions` |

> 两端的差别值得注意：客户端是把选项挂进**游戏自己的** parser（因此你定义的选项不会被当成"无法识别"）；服务端是 OSL 用一份**独立的** parser 再解析一遍同样的 `String[] args`，所以选项能被读到，但不会影响服务端自己后续的解析。

### `OptionsConsumer`

Reference: `net.ornithemc.osl.entrypoints.api.launch.OptionsConsumer`

**作用**：`LaunchEvents.PARSE_RUN_ARGS` 的监听器接口。两个方法分别对应"声明选项"和"读取选项"两个阶段。

**需要**：实现两个方法（都不是 default）。`defineOptions` 里只做声明并保存 `ArgumentAcceptingOptionSpec`；`acceptOptions` 里用保存下来的 spec 去 `options.valueOf(spec)`。

**返回**：均为 `void`。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `defineOptions(OptionParser parser)` | 声明自定义选项（`parser.accepts(...)`） | 不要调用 `parser.parse(...)`；客户端上解析由游戏完成 | 无（void） |
| `acceptOptions(OptionSet options)` | 读取解析结果 | 只能读在 `defineOptions` 里声明过的（或游戏自带的）选项；未提供时 `valueOf` 返回 null | 无（void） |

```java
LaunchEvents.PARSE_RUN_ARGS.register(new OptionsConsumer() {
    private ArgumentAcceptingOptionSpec<String> cookie;

    @Override
    public void defineOptions(OptionParser parser) {
        cookie = parser.accepts("cookie").withRequiredArg();
    }

    @Override
    public void acceptOptions(OptionSet options) {
        String value = options.valueOf(cookie); // 未传入时为 null
        if (value != null) { /* ... */ }
    }
});
```

## 1.12.2 上的调用顺序（客户端）

1. `LaunchEvents` 模块所在类加载，`Main.main` 进入 → `init` 入口点 → `client-init` 入口点
2. 游戏构造 `OptionParser` → 你的 `defineOptions`
3. 游戏 `parse` 命令行 → 你的 `acceptOptions`
4. 一切照旧：`Minecraft` 实例创建（此时 lifecycle-events 的 `MinecraftClientEvents.START` 才触发）

服务端（`MinecraftServer.main`）的顺序是：`init` → `server-init` → `defineOptions` → `acceptOptions` → 服务端启动流程。
