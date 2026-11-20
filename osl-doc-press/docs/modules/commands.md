---
title: 08 commands
---

# 08 commands

::: warning 0.26.0 变更
本章按 **0.24.0** 的 API 整理。0.26.0 中 `api.client.command.HelpCommand` 已移出 API（改为客户端内部实现），详见[变更历史](/changelog#commands-0-1-0-0-2-0)。
:::

> 一句话定位：把 1.13+ 才有的 Brigadier 命令框架整套搬到 1.12.2 —— 事件里注册命令树、47 种参数类型、命令树网络同步与补全。

| 项 | 值 |
|---|---|
| 模块 id | `commands` |
| Maven | `net.ornithemc.osl-gen2:commands:0.1.0+mc14w28a-mc1.12.2` |
| 端 | 双端（`api.client` 下的类型仅客户端存在） |
| 版本 | `0.1.0`（1.12.2 构件为 `0.1.0+mc14w28a-mc1.12.2`） |
| 依赖 | `ploceus.dependOslModule('commands', '0.1.0')` |
| 传递依赖 | core, entrypoints, lifecycle-events, blockstates, blocks, items, entities, networking, text-components |

1.12.2 的原版命令系统是 `CommandRegistry` + `AbstractCommand`（用 `String[] args` 手工解析），没有 `ArgumentType`、没有补全树、没有 `CommandSourceStack`。本模块把 Brigadier（`com.mojang.brigadier`）完整移植过来：用 `CommandDispatcher` 组命令树，用参数类型自动解析与补全，并把整棵命令树按玩家权限裁剪后同步给客户端。

模块本身分成三层：**注册入口**（`ServerCommandEvents` / `ClientCommandEvents`）、**执行上下文**（`CommandSourceStack` / `ClientCommandSource`）与 **参数类型库**（`api.command.argument` 下 47 个类型，覆盖 1.13 的全部原版参数）。原版那一套命令仍然可用，两者可以并存。

## 1.12.2 上的运行方式

理解下面四点，后面的 API 就不会用错：

1. **注册时机（服务端）**：服务端 `CommandManager` 构造完成（即原版命令全部注册完之后）时创建 dispatcher，并立刻触发 `ServerCommandEvents.REGISTER_COMMANDS` 与 `REGISTER_LEGACY_COMMANDS`。也就是说事件是在"服务器/世界启动"阶段触发的，监听器必须在 mod 初始化（entrypoint）时就注册好。
2. **注册时机（客户端）**：客户端收到 `handleLogin`（连上服务器、进入世界）后创建客户端 dispatcher 并触发 `ClientCommandEvents.REGISTER_COMMANDS`；若你注册了至少一条客户端命令，框架会自动补上 `/help`。
3. **执行优先级**：服务端 `CommandRegistry.run(CommandSource, String)` 会先拿 Brigadier dispatcher 试一次；只有命令源是 `CommandSourceBuilder`（任何实体都实现了）且 dispatcher 认识该命令时才拦截，否则原样回落到原版命令。**因此 `/give`、`/tp` 之类原版命令不在 Brigadier 树里，只有你自己注册的命令在。** 客户端同理：以 `/` 开头的聊天会先由客户端 dispatcher 执行，认识就吃掉，不认识才发给服务端。
4. **同步与补全**：服务端在 `PlayerManager.updatePermissions` 之后把"该玩家看得见的命令树"序列化成自定义包发给客户端；原版补全包的结果会与 Brigadier 补全合并；需要服务端算的补全（`SuggestionProviders.ASK_SERVER`）走单独的自定义通道往返。

## 命令注册（服务端）

### `ServerCommands`

Reference: `net.ornithemc.osl.commands.api.server.ServerCommands`

**作用**：服务端命令注册的工具类。真正的注册动作在 `REGISTER_COMMANDS` 监听器里做，这里只提供拿 dispatcher 与造节点 builder 的静态方法。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `dispatcher()` | 取当前服务端命令调度器 | 在 `REGISTER_COMMANDS` 监听器内调用；服务端尚未启动（`CommandManager` 未构造）时内部字段还是 `null` | `CommandDispatcher<CommandSourceStack>`，未初始化时为 `null` |
| `literal(String name)` | 造一个字面量节点 builder（命令名 / 子命令名本身） | `name` 不能含空格；返回的 builder 还要 `.executes(...)` 或 `.then(...)` 才算完整 | `LiteralArgumentBuilder<CommandSourceStack>` |
| `argument(String name, ArgumentType<T> type)` | 造一个必选参数节点 builder | `name` 是参数名（后面 `ctx.getArgument(name, …)` 要用同名）；`type` 用本模块参数类型或 Brigadier 自带的 | `RequiredArgumentBuilder<CommandSourceStack, T>` |
| `ServerCommands.Selection`（枚举） | 告诉监听器当前跑在什么服务端环境 | — | 见下 |
| `ServerCommands.BuildContext`（接口） | 预留的构建上下文，目前是空接口 | — | 事件回调里传给你的实例永远非 `null`，但没有可调用成员 |

`Selection` 的取值与含义：

| 常量 | `includesIntegrated()` | `includesDedicated()` | 说明 |
|---|---|---|---|
| `ALL` | `true` | `true` | 表示"两种环境都算"。框架自身**不会**传这个值，只在你自己的判断逻辑里用得到 |
| `INTEGRATED` | `true` | `false` | 单人游戏的内置服务器；框架在 `server.isDedicated() == false` 时传入 |
| `DEDICATED` | `false` | `true` | 专用服务器；框架在 `server.isDedicated() == true` 时传入 |

典型用法（在 mod 的 `init` entrypoint 里挂监听器）：

```java
ServerCommandEvents.REGISTER_COMMANDS.register((commands, selection, context) -> {
    commands.register(ServerCommands.literal("example")
        .executes(ctx -> {
            ctx.getSource().sendSuccess(TextComponents.literal("ok"), false);
            return 1;
        }));
});
```

### `ServerCommandEvents`

Reference: `net.ornithemc.osl.commands.api.server.ServerCommandEvents`

**作用**：服务端命令生命周期的唯一入口。两个事件分别在"原版命令注册完成之后"触发，是注册自定义命令的正确位置。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `REGISTER_COMMANDS` | Brigadier 命令注册事件，类型 `Event<RegisterCommandsListener>` | 在 mod 初始化阶段调用 `.register(listener)`；触发时 dispatcher 是新建的空树（原版命令不在里面） | 无（事件对象，注册后由框架调用） |
| `REGISTER_LEGACY_COMMANDS` | 原版 `AbstractCommand` 注册事件，类型 `Event<RegisterLegacyCommandsListener>` | 同上；回调拿到的 `Consumer<Command>` 就是原版 `CommandRegistry::register` | 无 |
| `ServerCommandEvents.RegisterCommandsListener`（接口） | 前者要实现的回调 | 实现 `registerCommands(CommandDispatcher<CommandSourceStack> commands, ServerCommands.Selection selection, ServerCommands.BuildContext context)` | 无（void） |
| `ServerCommandEvents.RegisterLegacyCommandsListener`（接口） | 后者要实现的回调 | 实现 `registerLegacyCommands(Consumer<Command> commands, ServerCommands.Selection selection, ServerCommands.BuildContext context)` | 无（void） |

## 命令注册（客户端，仅客户端）

### `ClientCommands`

Reference: `net.ornithemc.osl.commands.api.client.ClientCommands`

**作用**：客户端命令注册的工具类。客户端命令**只在客户端执行**，框架在 `LocalClientPlayerEntity.sendChat` 里拦截以 `/` 开头的消息，客户端 dispatcher 认识就以客户端结果为准、不发给服务端。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `dispatcher()` | 取客户端命令调度器 | 在 `REGISTER_COMMANDS` 监听器内或之后调用；未进入世界时为 `null` | `CommandDispatcher<ClientCommandSource>`，未初始化时为 `null` |
| `literal(String name)` | 造字面量节点 builder | 同服务端 | `LiteralArgumentBuilder<ClientCommandSource>` |
| `argument(String name, ArgumentType<T> type)` | 造必选参数节点 builder | 同服务端 | `RequiredArgumentBuilder<ClientCommandSource, T>` |
| `ClientCommands.Selection`（枚举） | 当前客户端处于什么环境 | — | 见下 |
| `ClientCommands.BuildContext`（接口） | 预留的构建上下文，空接口 | — | 事件回调里传入，非 `null` |

`Selection` 的取值：

| 常量 | `includesSingleplayer()` | `includesMultiplayer()` | 说明 |
|---|---|---|---|
| `ALL` | `true` | `true` | 两者都算。框架自身不会传这个值 |
| `SINGLEPLAYER` | `true` | `false` | 内置服务器在跑（单人）时传入 |
| `MULTIPLAYER` | `false` | `true` | 连的是远程服务器时传入 |

注意：客户端 dispatch 的**返回值语义**与 Brigadier 一致（`1` 表示成功执行）；框架用"dispatcher 是否认识这条命令"来决定是否把消息继续发给服务端，所以你没法用"返回 0"来放弃执行、让服务端处理。

### `ClientCommandEvents`

Reference: `net.ornithemc.osl.commands.api.client.ClientCommandEvents`

**作用**：客户端命令注册事件。触发时机是客户端完成登录（`handleLogin` 末尾），每次进入一个世界都会重新触发一次。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `REGISTER_COMMANDS` | 客户端命令注册事件，类型 `Event<RegisterCommandsListener>` | 在 `ClientModInitializer` 里 `.register(listener)` | 无 |
| `ClientCommandEvents.RegisterCommandsListener`（接口） | 回调接口 | 实现 `registerCommands(CommandDispatcher<ClientCommandSource> commands, ClientCommands.Selection selection, ClientCommands.BuildContext context)` | 无（void） |

### `HelpCommand`

Reference: `net.ornithemc.osl.commands.api.client.command.HelpCommand`

**作用**：`/help [<命令>]` 命令的实现。框架在客户端注册了至少一条命令后会自动调用 `register`，一般不需要你手动调用；这里公开出来是为了让你能在自己的 dispatcher 上复用它。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `register(CommandDispatcher<ClientCommandSource> dispatcher)` | 往给定 dispatcher 注册 `help` 字面量命令 | dispatcher 非 `null`；重复注册同名命令会抛 Brigadier 的 `IllegalArgumentException` | 无（void） |

行为：不带参数时列出根节点的可用命令（调用 `dispatcher.getSmartUsage`）；带 `<命令>` 时先解析该命令，取最后一个节点再列它的用法；解析不出任何节点时抛 `SimpleCommandExceptionType`（语言键 `commands.help.failed`）。每条结果通过 `ClientCommandSource.sendSuccess` 以 `/<用法>` 形式输出，返回值是输出的条数。

## 命令源与执行上下文

### `CommandSourceStack`

Reference: `net.ornithemc.osl.commands.api.server.command.CommandSourceStack`

**作用**：服务端的"命令执行上下文"，对应 1.13 的 `ServerCommandSource`：把命令源、服务器、维度、实体、位置、朝向、锚点、权限等级、静默标志、结果回调打包在一起。所有 `with…` 方法都是**不可变**的，返回新实例（值没变时返回 `this`）。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `new CommandSourceStack(CommandSource source, MinecraftServer server, ServerWorld world, Entity entity, Vec3d pos, Vec2f rotation, String name, Text displayName, int permissions)` | 公开构造：`displayName` 传原版 `Text` 版本 | 各参数非 `null`（`entity` 可以为 `null`，表示"非实体源"如命令方块/控制台）；`displayName` 会被 `TextComponents.resolve` 转成 `TextComponent` | 新实例，锚点默认 `Anchor.FEET`、非静默、回调为空 |
| `new CommandSourceStack(…, TextComponent displayName, int permissions)` | 同上，但 `displayName` 直接给 `TextComponent` | 同上 | 同上 |
| `withEntity(Entity entity)` | 换成另一个实体，同时把 `name`/`displayName` 换成该实体的名字与显示名 | `entity` 非 `null` | 新 `CommandSourceStack`（相同则返回 `this`） |
| `withPos(Vec3d pos)` / `withRotation(Vec2f rotation)` | 改位置 / 改朝向 | 非 `null` | 新实例 |
| `withAnchor(Anchor anchor)` | 改锚点（脚 / 眼） | 非 `null` | 新实例 |
| `withWorld(ServerWorld world)` | 换维度 | 非 `null` | 新实例 |
| `withPermissions(int permissions)` | 直接设置权限等级 | 0~4 有意义（见 `hasPermissions`） | 新实例 |
| `withMaxPermissions(int maxPermissions)` | 只升不降：新值 ≤ 当前值时返回 `this` | — | 新实例或 `this` |
| `silent()` | 标记为静默：后续 `sendSuccess`/`sendFailure` 不再真正发消息 | — | 新实例或 `this` |
| `withCallback(ResultConsumer<CommandSourceStack> callback)` | 设置命令执行结果回调 | 非 `null` | 新实例 |
| `withCallback(ResultConsumer<CommandSourceStack> callback, BinaryOperator<ResultConsumer<CommandSourceStack>> chooser)` | 用 `chooser` 把新回调和旧回调合并 | 两者非 `null` | 新实例 |
| `withFacing(Entity entity, Anchor anchor)` | 让上下文朝向"从当前锚点看向该实体锚点" | `entity` 非 `null` | 新实例；计算不合法时抛 `CommandSyntaxException` |
| `withFacing(Vec3d rotation)` | 让上下文朝向"从当前锚点看向该坐标" | 非 `null` | 新实例；同上可能抛异常 |
| `getServer()` / `getWorld()` / `getEntity()` / `getPos()` / `getRotation()` / `getAnchor()` / `getName()` / `getDisplayName()` | 读取对应字段 | — | `MinecraftServer` / `ServerWorld` / `Entity`（可能 `null`）/ `Vec3d` / `Vec2f` / `Anchor` / `String` / `TextComponent` |
| `getEntityOrThrow()` | 取实体，没有就报错 | 上下文中必须有实体 | `Entity`；否则抛 `NOT_ENTITY_EXCEPTION`（`permissions.requires.entity`） |
| `getPlayerOrThrow()` | 取玩家，不是玩家就报错 | 上下文实体必须是 `ServerPlayerEntity` | `ServerPlayerEntity`；否则抛 `NOT_PLAYER_EXCEPTION`（`permissions.requires.player`） |
| `hasPermissions(int permissions)` | 权限判定：`this.permissions >= permissions` | `permissions` 为 0~4 | `boolean` |
| `sendSuccess(TextComponent message, boolean broadcastToOps)` | 给命令源回成功消息；`broadcastToOps` 为真且命令源允许时还会广播给 OP 并写管理员日志 | `message` 非 `null`；静默上下文不发送任何东西 | 无（void） |
| `sendFailure(TextComponent message)` | 给命令源回失败消息（自动染红） | 同上 | 无（void） |
| `onCommandComplete(CommandContext<CommandSourceStack> ctx, boolean success, int result)` | 转发给回调；框架把它挂在 dispatcher 的 consumer 上，所以每条命令执行完都会调用 | 一般不手动调用 | 无（void） |
| `getPlayerNames()` / `getTeams()` | 补全用：在线玩家名 / 记分板队伍名 | — | `Collection<String>` |
| `requestSuggestions(CommandContext<SharedSuggestionProvider> ctx, SuggestionsBuilder builder)` | 请求服务端计算补全 | — | **源码直接返回 `null`**，因此服务端源上的 `ASK_SERVER` 拿不到可用 future（源码未说明原因）；参数类型若走这条路要自己返回建议 |
| `getRelevantCoordinates(boolean absolute)` | 补全用：可作为坐标建议的候选 | — | 常量集合，仅含 `TextCoordinates.DEFAULT_GLOBAL`（`"~ ~ ~"`） |
| `NOT_PLAYER_EXCEPTION` / `NOT_ENTITY_EXCEPTION` | 两个预置异常类型 | — | `SimpleCommandExceptionType` |

### `ClientCommandSource`

Reference: `net.ornithemc.osl.commands.api.client.command.ClientCommandSource`

**作用**：客户端命令的执行上下文。框架的实现是 `ClientSuggestionProvider`（impl 包），客户端命令回调里的 `ctx.getSource()` 就是它。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `getMinecraft()` | 取 `Minecraft` 实例 | — | `Minecraft` |
| `getWorld()` | 取当前客户端世界 | 已在世界中 | `ClientWorld`（可能 `null`） |
| `getPlayer()` | 取本地玩家 | 已在世界中 | `LocalClientPlayerEntity`（可能 `null`） |
| `getPosition()` | 玩家坐标 | 玩家非 `null` | `Vec3d` |
| `getRotation()` | 玩家朝向（`x`=pitch，`y`=yaw） | 玩家非 `null` | `Vec2f` |
| `sendSuccess(TextComponent message)` | 往聊天栏输出成功消息 | 非 `null` | 无（void） |
| `sendFailure(TextComponent message)`（继承 `CommandFailureConsumer`） | 往聊天栏输出失败消息（实现里会先染红） | 非 `null` | 无（void） |

该接口同时继承 `SharedSuggestionProvider`，所以也有 `getPlayerNames()`、`getTeams()`、`hasPermissions(int)`、`requestSuggestions(…)`、`getRelevantCoordinates(boolean)` 这几个成员——由实现类提供，`requestSuggestions` 会真的向服务端发请求并等待回包。

### `CommandSourceBuilder`

Reference: `net.ornithemc.osl.commands.api.server.command.CommandSourceBuilder`

**作用**：能把自己转成 `CommandSourceStack` 的类型。框架用 `Entity` 混入实现了它，这也是"原版命令执行路径会先问一遍 Brigadier"的判据（见"运行方式"第 3 点）。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `createCommandSourceStack()` | 按当前实体状态（世界、位置、朝向、名字、权限）构造上下文 | 实体必须在 `ServerWorld` 里（实现会对 `world` 做强转） | 新的 `CommandSourceStack` |

### `CommandFailureConsumer`

Reference: `net.ornithemc.osl.commands.api.command.CommandFailureConsumer`

**作用**：只要能收失败消息就算命令源。服务端 `CommandSourceStack` 与客户端 `ClientCommandSource` 都实现它，框架执行命令时用它把 `CommandSyntaxException` 转成聊天提示。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `sendFailure(TextComponent message)` | 把失败原因发给玩家 | `message` 非 `null`；由实现决定是否染色/静默 | 无（void） |

### `SharedSuggestionProvider`

Reference: `net.ornithemc.osl.commands.api.command.SharedSuggestionProvider`

**作用**：服务端与客户端命令源共用的"补全数据源"接口，并附一大堆静态补全工具方法。参数类型的 `listSuggestions` 基本都靠这些静态方法拼结果。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `getPlayerNames()` | 在线玩家名，用于实体/玩家名补全 | — | `Collection<String>` |
| `getSelectedEntities()` | 准星指着的实体（默认空集合，客户端实现会返回该实体的 UUID 字符串） | — | `Collection<String>` |
| `getTeams()` | 记分板队伍名 | — | `Collection<String>` |
| `requestSuggestions(CommandContext<SharedSuggestionProvider> ctx, SuggestionsBuilder builder)` | 让命令源去算补全（客户端实现会请求服务端） | `ctx` / `builder` 非 `null` | `CompletableFuture<Suggestions>`；服务端 `CommandSourceStack` 的实现返回 `null` |
| `getRelevantCoordinates(boolean absolute)` | 可作为坐标建议的候选坐标 | — | `Collection<TextCoordinates>` |
| `hasPermissions(int permissions)` | 权限判定 | — | `boolean` |
| `filterResources(Iterable<T> values, String target, Function<T, ? extends NamespacedIdentifier> converter, Consumer<T> consumer)` | 按输入前缀过滤"带命名空间的 ID"：`target` 含 `:` 时全串前缀匹配，否则命名空间或路径任一前缀匹配都能命中 | — | 无（void，命中项交给 `consumer`） |
| `filterResources(Iterable<T> values, String target, String prefix, Function<T, ? extends NamespacedIdentifier> converter, Consumer<T> consumer)` | 同上，但额外提供一个 `prefix`（如 `"#"`）参与公共前缀裁剪；`target` 为空时全部命中 | — | 无（void） |
| `suggestResource(Iterable<? extends NamespacedIdentifier> keys, SuggestionsBuilder builder)` | 直接把 ID 列表作为建议（小写前缀匹配） | — | `CompletableFuture<Suggestions>`（已完成） |
| `suggestResource(Iterable<? extends NamespacedIdentifier> keys, SuggestionsBuilder builder, String prefix)` | 同上，但建议文本前面加 `prefix` | — | 同上 |
| `suggestResource(Iterable<T> values, SuggestionsBuilder builder, Function<T, ? extends NamespacedIdentifier> key, Function<T, Message> tooltip)` | 同上，且每项带悬浮提示 | — | 同上 |
| `suggestResource(Stream<NamespacedIdentifier> keys, SuggestionsBuilder builder)` / `suggestResource(Stream<T> values, SuggestionsBuilder builder, Function<T, ? extends NamespacedIdentifier> key, Function<T, Message> tooltip)` | Stream 重载 | — | 同上 |
| `suggestCoordinates(String s, Collection<TextCoordinates> coordinates, SuggestionsBuilder builder, Predicate<String> validator)` | 三维坐标补全：按已输入的空格数补 `x` / `x y` / `x y z`，每一项都要过 `validator`（通常传 `Commands.validator(arg::parse)`） | `coordinates` 非空 | `CompletableFuture<Suggestions>` |
| `suggestHorizontalCoordinates(String s, Collection<TextCoordinates> coordinates, SuggestionsBuilder builder, Predicate<String> validator)` | 二维（水平）坐标补全：补 `x` / `x z` | 同上 | 同上 |
| `suggestMatching(Iterable<String> suggestions, SuggestionsBuilder builder)` / `suggestMatching(Stream<String> …)` / `suggestMatching(String[] …)` | 按 `builder.getRemaining()` 的小写前缀过滤字符串列表并建议 | — | `CompletableFuture<Suggestions>` |
| `SharedSuggestionProvider.TextCoordinates`（嵌套类） | "可建议的坐标"三元组，`public final String x, y, z` | 构造 `TextCoordinates(String x, String y, String z)` | 实例；常量 `DEFAULT_LOCAL`（`"^ ^ ^"`）、`DEFAULT_GLOBAL`（`"~ ~ ~"`） |

### `MinecraftServerExtension`

Reference: `net.ornithemc.osl.commands.api.server.MinecraftServerExtension`

**作用**：给 `MinecraftServer` 加"按 GameProfile 查权限等级"的能力（mixin 实现，直接 `(MinecraftServerExtension) server` 强转即可用）。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `getPermissions(GameProfile profile)` | 计算该玩家的权限等级 | `profile` 非 `null` | `int`（0~4）。逻辑：OP 列表里有条目就用条目里的等级；单人下是自己或开了作弊就是 `4`；专用服务器下是 `op-permission-level`；非 OP 为 `0` |

### `PlayerManagerExtension`

Reference: `net.ornithemc.osl.commands.api.server.PlayerManagerExtension`

**作用**：给 `PlayerManager` 加"是否允许作弊"与"刷新玩家权限（并把新命令树重新同步给该玩家）"的能力。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `allowCommands()` | 该存档/服务器是否开启了作弊（`allow-commands`） | — | `boolean` |
| `updatePermissions(ServerPlayerEntity player)` | 重算权限并触发命令树重新下发 | `player` 非 `null` | 无（void）。1.12.2 走 `>=15w31a` 分支：命令树是在 `updatePermissions(player, permissions)` 的尾部发出的，所以这个方法等价于"刷新 + 重发"；只有 15w31a 之前的版本才走手工计算权限的那套实现 |

### `EntityExtension`

Reference: `net.ornithemc.osl.commands.api.entity.EntityExtension`

**作用**：给 `Entity` 加权限查询，并让它能当命令源用。任何实体都能 `(EntityExtension) entity`。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `createCommandSourceStack()`（继承 `CommandSourceBuilder`） | 用该实体构造上下文 | 实体在 `ServerWorld` 中 | `CommandSourceStack` |
| `getPermissions()` | 该实体的权限等级 | — | `int`。普通实体恒为 `0`；`ServerPlayerEntity` 覆写为 `server.getPermissions(gameProfile)` |
| `hasPermissions(int permissions)` | 权限判定 | `permissions` 为 0~4 | `boolean`，实现为「`permissions == 0` 或 `getPermissions() >= permissions`」 |

### `ClientPlayNetworkHandlerExtension`

Reference: `net.ornithemc.osl.commands.api.client.network.handler.ClientPlayNetworkHandlerExtension`

**作用**：客户端网络处理器上的命令状态：服务端下发来的命令树、补全用的命令源，以及两个收包入口。mod 一般只读 `getCommands()` / `getSuggestionProvider()`（例如给自己的 UI 做补全）。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `getCommands()` | 当前"服务端命令树 + 客户端命令"合并后的 dispatcher（未收到包时是空树） | 已登录 | `CommandDispatcher<SharedSuggestionProvider>` |
| `getSuggestionProvider()` | 补全用命令源 | 已登录 | `ClientSuggestionProvider`（impl 类型）；实际当 `ClientCommandSource` / `SharedSuggestionProvider` 用即可 |
| `handleCommands(CommandsPayload payload)` | 处理"命令树同步"包；会用它替换 `getCommands()` 的根节点并把客户端命令合并进去 | 由框架在收到包时调用 | 无（void） |
| `handleCommandSuggestions(CommandSuggestionsPayload payload)` | 处理"补全结果"包，按请求 id 完成对应的 future | 由框架调用 | 无（void） |

## 参数类型总览

`api.command.argument` 下的参数类型都是 Brigadier 的 `ArgumentType` 实现，用法统一：`ServerCommands.argument("名字", XxxArgument.xxx())`。每张表里的"命令里的样子"取自源码的 `getExamples()`，也就是玩家实际会敲的文本。

| 类型 | 工厂方法 | 命令里的样子 | `parse` 的返回 |
|---|---|---|---|
| `Vec3dArgument` | `vec3d()` / `vec3d(boolean centered)` | `0 0 0`、`~ ~ ~`、`^ ^ ^`、`^1 ^ ^-5` | `Coordinates`（全局或局部） |
| `Vec2fArgument` | `vec2f()` | `0 0`、`~ ~`、`0.1 -0.5` | `Coordinates`（只有 x/z） |
| `BlockPosArgument` | `blockPos()` | `0 0 0`、`~0.5 ~1 ~-5`、`^ ^ ^` | `Coordinates`（方块坐标） |
| `ColumnPosArgument` | `columnPos()` | `0 0`、`~1 ~-2`、`^-1 ^0` | `Coordinates`（列坐标 x/z） |
| `RotationArgument` | `rotation()` | `0 0`、`~-5 ~5` | `Coordinates`（pitch yaw） |
| `AnchorArgument` | `anchor()` | `eyes`、`feet` | `Anchor` |
| `AxesArgument` | `axes()` | `xyz`、`x` | `EnumSet<Axis>` |
| `BlockStateArgument` | `block()` | `stone`、`minecraft:stone`、`stone[foo=bar]`、`foo{bar=baz}` | `BlockInput` |
| `BlockPredicateArgument` | `blockPredicate()` | `stone`、`stone[foo=bar]` | `Result`（工厂，产出 `Predicate<BlockPointer>`） |
| `LegacyBlockStateArgument` | `block()` | `stone`、`stone foo=bar`、`stone 0` | `BlockInput` |
| `LegacyBlockPredicateArgument` | `blockPredicate()` | `stone`、`stone 0` | `Result` |
| `ItemArgument` | `item()` | `stick`、`minecraft:stick`、`stick{foo=bar}` | `ItemInput` |
| `ItemPredicateArgument` | `itemPredicate()` | `stick`、`minecraft:stick` | `Result` |
| `EntityArgument` | `entity()` / `entities()` / `player()` / `players()` | `Player`、`@e`、`@e[type=foo]`、`dd12be42-…` | `EntitySelector` |
| `GameProfileArgument` | `gameProfiles()` | `Player`、`0123`、`@e`、UUID | `Result` |
| `TextArgument` | `text()` | `"hello world"`、JSON 文本 | `TextComponent` |
| `MessageArgument` | `message()` | `Hello world!`、`Hello @p :)` | `MessageArgument.Message` |
| `NbtCompoundArgument` | `nbtCompound()` | `{}`、`{foo=bar}` | `NbtCompound` |
| `ObjectiveArgument` | `objective()` | `foo`、`*` | `String` |
| `ScoreHolderArgument` | `scoreHolder()` / `scoreHolders()` | `Player`、`*`、`@e` | `Result` |
| `ScoreboardCriterionArgument` | `criterion()` | `foo`、`minecraft:foo` | `ScoreboardCriterion` |
| `ScoreboardDisplaySlotArgument` | `displaySlot()` | `sidebar` | `Integer` |
| `OperationArgument` | `operation()` | `=`、`+=`、`><` | `Operation` |
| `TeamArgument` | `team()` | `foo`、`123` | `String` |
| `IdentifierArgument` | `identifier()` | `foo`、`foo:bar` | `NamespacedIdentifier` |
| `ColorArgument` | `color()` | `red`、`green` | `Formatting` |
| `EnchantmentArgument` | `enchantment()` | `unbreaking`、`silk_touch` | `Enchantment` |
| `StatusEffectArgument` | `effect()` | `spooky`、`effect` | `StatusEffect` |
| `SlotArgument` | `slot()` | `container.5`、`weapon` | `Integer` |
| `RangeArgument.Ints` | `RangeArgument.intRange()` | `0..5`、`0`、`-100..` | `NumberRange.Ints` |
| `RangeArgument.Floats` | `RangeArgument.floatRange()` | `0..5.2`、`-100.76..` | `NumberRange.Floats` |

> 1.12.2 上所有 `#标签` 语法都不可用：`BlockStateParser` 与 `ItemParser` 在构造时把 `allowTag` 强制改成了 `false`（源码里留着 `// TODO`），所以 `#minecraft:logs` 这类输入会直接抛"不允许标签"的异常。

## 参数类型：坐标与朝向

### `Vec3dArgument`

Reference: `net.ornithemc.osl.commands.api.command.argument.Vec3dArgument`

**作用**：三维坐标参数，世界坐标（`1 2 3`）、相对坐标（`~1 ~ ~-2`）、局部坐标（`^1 ^ ^-5`）三种写法都支持，是 1.13 的 `vec3` 参数。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `vec3d()` | 工厂：整数写法会自动补 `.5`（居中修正开启） | — | `Vec3dArgument` |
| `vec3d(boolean centered)` | 工厂：自己决定是否做居中修正 | — | `Vec3dArgument` |
| `parse(StringReader reader)` | 解析：首字符是 `^` 走局部坐标，否则走全局坐标 | reader 当前位置必须是坐标开头 | `Coordinates`（`LocalCoordinates` 或 `GlobalCoordinates`）；缺分量抛 `INCOMPLETE_EXCEPTION`（`argument.pos3d.incomplete`），混写抛 `MIXED_TYPE_EXCEPTION`（`argument.pos.mixed`） |
| `getVec3d(CommandContext<CommandSourceStack> ctx, String arg)` | 取值：解析成绝对坐标 | `arg` 与注册时的参数名一致 | `Vec3d`；解析结果报错时抛 `CommandSyntaxException` |
| `getCoordinates(CommandContext<CommandSourceStack> ctx, String arg)` | 取值：保留 `Coordinates` 对象（可再判相对/绝对） | 同上 | `Coordinates` |
| `listSuggestions(CommandContext<S> ctx, SuggestionsBuilder builder)` | 补全：用 `SharedSuggestionProvider.suggestHorizontalCoordinates` + `getRelevantCoordinates` 给候选 | 命令源需实现 `SharedSuggestionProvider`，否则返回 `Suggestions.empty()` | `CompletableFuture<Suggestions>` |
| `getExamples()` | 示例（也用于错误提示） | — | `Collection<String>` |

### `Vec2fArgument`

Reference: `net.ornithemc.osl.commands.api.command.argument.Vec2fArgument`

**作用**：水平二维坐标（x/z）参数，对应 1.13 的 `vec2`。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `vec2f()` | 工厂（居中修正开启） | — | `Vec2fArgument` |
| `new Vec2fArgument(boolean centerCorrect)` | 直接构造，指定居中修正 | — | 实例 |
| `parse(StringReader reader)` | 解析两个分量（x、z），中间必须有一个空格 | — | `Coordinates`（内部是 `GlobalCoordinates`，y 恒为相对 0）；分量不足抛 `INCOMPLETE_EXCEPTION`（`argument.pos2d.incomplete`） |
| `getVec2f(CommandContext<CommandSourceStack> ctx, String arg)` | 取 (x, z) 为 `Vec2f` | 命令源非 `null` | `Vec2f` |
| `listSuggestions(…)` | 补全：水平坐标建议 | 需 `SharedSuggestionProvider` | `CompletableFuture<Suggestions>` |
| `getExamples()` | 示例 | — | `Collection<String>` |

### `BlockPosArgument`

Reference: `net.ornithemc.osl.commands.api.command.argument.BlockPosArgument`

**作用**：方块坐标参数（`block_pos`），支持全局/相对/局部三种写法，并提供"取已加载方块坐标"的便利方法。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `blockPos()` | 工厂 | — | `BlockPosArgument` |
| `parse(StringReader reader)` | `^` 开头走局部坐标，否则按整数全局坐标解析 | — | `Coordinates` |
| `getBlockPos(CommandContext<CommandSourceStack> ctx, String arg)` | 解析成方块坐标 | — | `BlockPos` |
| `getLoadedBlockPos(CommandContext<CommandSourceStack> ctx, String arg)` | 解析并检查区块已加载、坐标在世界内 | 命令源必须有世界 | `BlockPos`；区块未加载抛 `UNLOADED_EXCEPTION`（`argument.pos.unloaded`），出界抛 `OUT_OF_WORLD_EXCEPTION`（`argument.pos.outofworld`） |
| `listSuggestions(…)` | 补全：局部前缀（`^`）只给 `^ ^ ^`，否则用命令源的坐标候选 | 需 `SharedSuggestionProvider` | `CompletableFuture<Suggestions>` |
| `getExamples()` | 示例 | — | `Collection<String>` |

### `ColumnPosArgument`

Reference: `net.ornithemc.osl.commands.api.command.argument.ColumnPosArgument`

**作用**：列坐标参数（只有 x/z，无 y），对应 1.13 的 `column_pos`，适合"按区块列操作"的命令。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `columnPos()` | 工厂 | — | `ColumnPosArgument` |
| `parse(StringReader reader)` | 解析两个整数分量（`^` 也接受，但只取数值） | — | `Coordinates`（y 固定相对 0）；格式不完整抛 `INCOMPLETE_EXCEPTION`（`argument.pos2d.incomplete`） |
| `getColumnPos(CommandContext<CommandSourceStack> ctx, String arg)` | 取列坐标 | — | `ColumnPosArgument.ColumnPos` |
| `listSuggestions(…)` | 补全：水平坐标建议 | 需 `SharedSuggestionProvider` | `CompletableFuture<Suggestions>` |
| `getExamples()` | 示例 | — | `Collection<String>` |
| `ColumnPosArgument.ColumnPos`（嵌套类） | 结果类型，`public final int x, z`，`toString()` 形如 `[x, z]` | 构造 `ColumnPos(int x, int z)` | 实例 |

### `RotationArgument`

Reference: `net.ornithemc.osl.commands.api.command.argument.RotationArgument`

**作用**：朝向参数（pitch / yaw 两个浮点），对应 1.13 的 `rotation`。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `rotation()` | 工厂 | — | `RotationArgument` |
| `parse(StringReader reader)` | 解析两个分量：`<pitch> <yaw>` | 两个分量都要有，缺一个抛 `INCOMPLETE_EXCEPTION`（`argument.rotation.incomplete`） | `Coordinates`，内部是 `GlobalCoordinates(yaw, pitch, ~0)`，用 `Coordinates#getRotation(source)` 取出 `Vec2f(x=pitch, y=yaw)` |
| `getRotation(CommandContext<?> ctx, String arg)` | 取值 | — | `Coordinates` |
| `getExamples()` | 示例 | — | `Collection<String>` |

注意：该类型**没有实现** `listSuggestions`（走 Brigadier 默认的空建议）。

### `AnchorArgument`

Reference: `net.ornithemc.osl.commands.api.command.argument.AnchorArgument`

**作用**：锚点参数（`feet` / `eyes`），决定"实体坐标取脚底还是眼睛"，配合 `CommandSourceStack.withAnchor` 使用。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `anchor()` | 工厂 | — | `AnchorArgument` |
| `parse(StringReader reader)` | 读一个非引号字符串并查表 | — | `Anchor`；未知名字抛 `DynamicCommandExceptionType`（`argument.anchor.invalid`），并把游标回退 |
| `getAnchor(CommandContext<?> ctx, String arg)` | 取值 | — | `Anchor` |
| `listSuggestions(…)` | 补全：`feet` / `eyes` | — | `CompletableFuture<Suggestions>` |
| `getExamples()` | 示例 | — | `Collection<String>` |
| `AnchorArgument.Anchor`（枚举） | 锚点：`FEET`（原坐标）、`EYES`（y 加 `entity.getEyeHeight()`） | — | 见下 |
| `Anchor.byName(String name)` | 按名字查（`"feet"` / `"eyes"`） | — | `Anchor`，查不到返回 `null` |
| `Anchor.apply(Entity entity)` | 把锚点应用到实体的绝对坐标 | `entity` 非 `null` | `Vec3d` |
| `Anchor.apply(CommandSourceStack source)` | 把锚点应用到命令源：有实体就按实体变换，没实体直接用 `source.getPos()` | `source` 非 `null` | `Vec3d` |

### `AxesArgument`

Reference: `net.ornithemc.osl.commands.api.command.argument.AxesArgument`

**作用**：坐标轴集合参数（`xyz`、`xz` 之类），对应 1.13 的 `swizzle`，用于 `/clone`、`/fill` 那种"哪些轴参与"的语义。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `axes()` | 工厂 | — | `AxesArgument` |
| `parse(StringReader reader)` | 逐字符读到空格为止，`x`/`y`/`z` 各算一个轴 | 字符必须是 `x`/`y`/`z`；重复或非法字符抛 `INVALID_EXCEPTION`（`arguments.swizzle.invalid`） | `EnumSet<Axis>` |
| `getAxes(CommandContext<CommandSourceStack> ctx, String arg)` | 取值 | — | `EnumSet<Axis>`（`Direction.Axis`） |
| `getExamples()` | 示例 | — | `Collection<String>`（无自定义补全） |

### `Coordinate`

Reference: `net.ornithemc.osl.commands.api.command.argument.Coordinate`

**作用**：单个坐标分量的模型：一个 `double` 值 + "是否相对"。三个坐标参数最终都靠它解析。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `new Coordinate(boolean relative, double coordinate)` | 直接构造 | — | 实例 |
| `isRelative()` | 是否为 `~` 相对值 | — | `boolean` |
| `get(double offset)` | 求绝对值：相对则 `coordinate + offset`，绝对则原样 | `offset` 通常是命令源对应轴的坐标 | `double` |
| `parseDouble(StringReader reader, boolean centered)` | 解析一个浮点分量；`centered` 为真且写法是整数时自动 `+0.5` | 不能以 `^` 开头（否则抛 `MIXED_TYPE_EXCEPTION`）；无输入抛 `NOT_DOUBLE_EXCEPTION`（`argument.pos.missing.double`） | `Coordinate` |
| `parseInt(StringReader reader)` | 解析一个整数分量（相对写法允许小数） | 同上，无输入抛 `NOT_INT_EXCEPTION`（`argument.pos.missing.int`） | `Coordinate` |
| `equals(Object)` / `hashCode()` | 值比较 | — | `boolean` / `int` |

### `Coordinates`

Reference: `net.ornithemc.osl.commands.api.command.argument.Coordinates`

**作用**：坐标参数的公共接口，两种实现：`GlobalCoordinates`（世界/相对坐标）与 `LocalCoordinates`（`^` 局部坐标）。它就是你从坐标参数里拿到的东西。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `getPosition(CommandSourceStack source)` | 解析成绝对坐标 | `source` 提供基准位置与朝向 | `Vec3d` |
| `getRotation(CommandSourceStack source)` | 解析成朝向（供 `RotationArgument` / `Vec2fArgument` 使用） | 同上 | `Vec2f` |
| `getBlockPos(CommandSourceStack source)` | 默认实现：`new BlockPos(getPosition(source))` | 同上 | `BlockPos` |
| `isXRelative()` / `isYRelative()` / `isZRelative()` | 各轴是否相对 | — | `boolean`（`LocalCoordinates` 恒为 `true`） |

### `GlobalCoordinates`

Reference: `net.ornithemc.osl.commands.api.command.argument.GlobalCoordinates`

**作用**：世界坐标 / `~` 相对坐标的实现。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `new GlobalCoordinates(Coordinate x, Coordinate y, Coordinate z)` | 直接构造 | 三个分量非 `null` | 实例 |
| `getPosition(CommandSourceStack source)` | 用命令源坐标作为相对基准 | 同上 | `Vec3d` |
| `getRotation(CommandSourceStack source)` | 用命令源朝向作为相对基准，x/y 两个分量转成 `Vec2f` | 同上 | `Vec2f` |
| `isXRelative()` / `isYRelative()` / `isZRelative()` | 转调对应分量 | — | `boolean` |
| `parseInt(StringReader reader)` | 解析三个整数分量 | 缺分量会回退游标并抛 `Vec3dArgument.INCOMPLETE_EXCEPTION` | `GlobalCoordinates` |
| `parseDouble(StringReader reader, boolean centered)` | 解析三个浮点分量（第一、三分量参与居中修正，中间分量不修正） | 同上 | `GlobalCoordinates` |
| `self()` | 造一个 `~ ~ ~`（相对 0） | — | `GlobalCoordinates` |
| `equals(Object)` / `hashCode()` | 值比较 | — | `boolean` / `int` |

### `LocalCoordinates`

Reference: `net.ornithemc.osl.commands.api.command.argument.LocalCoordinates`

**作用**：`^` 局部坐标的实现（左 / 上 / 前三个分量，相对命令源朝向）。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `new LocalCoordinates(double left, double upwards, double forwards)` | 直接构造 | — | 实例 |
| `getPosition(CommandSourceStack source)` | 用命令源的锚点、朝向换算出绝对坐标 | `source` 的 rotation 非 `null` | `Vec3d` |
| `getRotation(CommandSourceStack source)` | 局部坐标没有朝向语义 | — | 恒为 `Vec2f.ZERO` |
| `isXRelative()` / `isYRelative()` / `isZRelative()` | 局部坐标永远相对 | — | 恒为 `true` |
| `parse(StringReader reader)` | 解析三个必须带 `^` 前缀的分量 | 缺 `^` 抛 `Vec3dArgument.MIXED_TYPE_EXCEPTION`，缺分量抛 `Vec3dArgument.INCOMPLETE_EXCEPTION` | `LocalCoordinates` |
| `equals(Object)` / `hashCode()` | 值比较 | — | `boolean` / `int` |

### `Vec2f`

Reference: `net.ornithemc.osl.commands.api.command.argument.Vec2f`

**作用**：OSL 自己的二维浮点向量（1.12.2 没有 `net.minecraft.util.math.Vec2f`），用来表示朝向 `(pitch, yaw)`。`CommandSourceStack#getRotation` 和 `ClientCommandSource#getRotation` 都返回它。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `new Vec2f(float x, float y)` | 构造 | — | 实例 |
| `x` / `y`（`public final float`） | 两个分量 | — | — |
| `equals(Vec2f other)` | 值比较。注意这是**重载**，不是 `equals(Object)`，不要指望放进 `HashMap` 里能按值命中 | `other` 非 `null` | `boolean` |
| `ZERO` / `ONE` / `POS_X` / `NEG_X` / `POS_Y` / `NEG_Y` / `MAX` / `MIN` | 预置常量 | — | `Vec2f` |

## 参数类型：方块

### `BlockStateArgument`

Reference: `net.ornithemc.osl.commands.api.command.argument.BlockStateArgument`

**作用**：方块状态参数（`block_state`），1.13 的 `stone[foo=bar]{nbt}` 写法的移植：给方块 ID，可选方括号里的属性表，可选大括号里的方块实体 NBT。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `block()` | 工厂 | — | `BlockStateArgument` |
| `parse(StringReader reader)` | 用 `new BlockStateParser(reader, false, false).parse()` 解析，包成 `BlockInput` | — | `BlockInput`；未知方块 ID 抛 `BlockStateParser.INVALID_ID_EXCEPTION`，属性错误抛对应异常（见 `BlockStateParser`） |
| `getBlock(CommandContext<?> ctx, String arg)` | 取值 | — | `BlockInput` |
| `listSuggestions(…)` | 补全：把已输入部分重新交给 `BlockStateParser` 解析后取它的建议（方块 ID、属性名、属性值、`[`/`{`/`]`/`,`） | — | `CompletableFuture<Suggestions>` |
| `getExamples()` | 示例：`stone`、`minecraft:stone`、`stone[foo=bar]`、`foo{bar=baz}` | — | `Collection<String>` |

### `BlockPredicateArgument`

Reference: `net.ornithemc.osl.commands.api.command.argument.BlockPredicateArgument`

**作用**：方块**谓词**参数（`block_predicate`）：解析出的不是某一块的具体状态，而是一个能对世界里任意方块做匹配的 `Predicate<BlockPointer>`，适合"匹配区域内所有符合条件的方块"这类命令。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `blockPredicate()` | 工厂 | — | `BlockPredicateArgument` |
| `parse(StringReader reader)` | `new BlockStateParser(reader, false, true).parse()`，把状态 + 属性 + NBT 包成谓词 | — | `BlockPredicateArgument.Result`。**注意**：方块 ID 不存在时解析阶段不报错，返回的 `Result` 在 `create()` 时才抛 `arguments.block.unknown` |
| `getBlockPredicate(CommandContext<CommandSourceStack> ctx, String arg)` | 取值：直接拿到谓词 | — | `Predicate<BlockPointer>`；方块不存在时抛 `CommandSyntaxException` |
| `listSuggestions(…)` | 同 `BlockStateArgument` | — | `CompletableFuture<Suggestions>` |
| `getExamples()` | 示例：`stone`、`minecraft:stone`、`stone[foo=bar]` | — | `Collection<String>` |
| `BlockPredicateArgument.Result`（函数式接口） | 延迟构造谓词 | `create()` 可能抛 `CommandSyntaxException` | `Predicate<BlockPointer>` |

谓词语义：方块类型相同 → 指定的每个属性值相同 → 有 NBT 时要求方块实体存在且 `NbtUtils.matches(expected, actual, true)`。

### `LegacyBlockStateArgument`

Reference: `net.ornithemc.osl.commands.api.command.argument.LegacyBlockStateArgument`

**作用**：**旧写法**的方块状态参数：属性表用空格分隔、支持元数据数字（1.8~1.12 的命令风格），例如 `stone`、`stone foo=bar`、`stone 0`。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `block()` | 工厂 | — | `LegacyBlockStateArgument` |
| `parse(StringReader reader)` | `new BlockStateParser(reader, true, false).parse()`（`legacyFormat = true`） | — | `BlockInput` |
| `getBlock(CommandContext<?> ctx, String arg)` | 取值 | — | `BlockInput` |
| `listSuggestions(…)` | 补全 | — | `CompletableFuture<Suggestions>` |
| `getExamples()` | 示例：`stone`、`minecraft:stone`、`stone foo=bar`、`stone 0` | — | `Collection<String>` |

旧写法的两点差别（读自 `BlockStateParser`）：元数据写法会校验 `0..15`（否则 `INVALID_DATA_EXCEPTION`）；属性表里有"既不属于该方块、也不像任何待填属性前缀"的名字时，解析会**退化成"只匹配方块本身"**而不是报错（1.8 起方块 ID + 元数据的写法允许后面跟任意文本）。

### `LegacyBlockPredicateArgument`

Reference: `net.ornithemc.osl.commands.api.command.argument.LegacyBlockPredicateArgument`

**作用**：旧写法的方块谓词参数（`stone`、`stone 0`、`stone foo=bar`），语义与 `BlockPredicateArgument` 相同但不解析 NBT。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `blockPredicate()` | 工厂 | — | `LegacyBlockPredicateArgument` |
| `parse(StringReader reader)` | `new BlockStateParser(reader, true, true).parse()`，只用状态 + 属性构造谓词 | — | `LegacyBlockPredicateArgument.Result`；未知方块同样延迟到 `create()` 才抛 |
| `getBlockPredicate(CommandContext<CommandSourceStack> ctx, String arg)` | 取值 | — | `Predicate<BlockPointer>` |
| `listSuggestions(…)` | 补全 | — | `CompletableFuture<Suggestions>` |
| `getExamples()` | 示例：`stone`、`minecraft:stone`、`stone foo=bar`、`stone 0` | — | `Collection<String>` |
| `LegacyBlockPredicateArgument.Result`（函数式接口） | 延迟构造谓词 | `create()` 可能抛 `CommandSyntaxException` | `Predicate<BlockPointer>` |

### `BlockInput`

Reference: `net.ornithemc.osl.commands.api.command.argument.BlockInput`

**作用**：`BlockStateArgument` / `LegacyBlockStateArgument` 的解析结果：方块状态 + 需要匹配的属性集合 + 可选方块实体 NBT。它自己也是 `Predicate<BlockPointer>`，并且能直接把方块放到世界里。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `new BlockInput(BlockState state, Set<Property<?>> properties, NbtCompound nbt)` | 构造 | `state` 非 `null`；`nbt` 可为 `null` | 实例 |
| `getState()` | 取方块状态 | — | `BlockState` |
| `test(BlockPointer ptr)` | 判断某处方块是否匹配：方块类型、属性值、NBT 都要对上 | `ptr` 非 `null` | `boolean` |
| `set(World world, BlockPos pos, int flags)` | 把方块写进世界；有 NBT 时还会写入方块实体（并补上 `x`/`y`/`z`） | `world` / `pos` 非 `null`；`flags` 是原版 `setBlockState` 的标志位 | `boolean`：`false` 表示方块没被设置成功 |

### `BlockStateParser`

Reference: `net.ornithemc.osl.commands.api.command.argument.BlockStateParser`

**作用**：方块状态字符串的底层解析器，`BlockStateArgument` 与两个方块谓词参数共用。你也可以直接用它在自己的命令里解析 `stone[foo=bar]{…}`。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `new BlockStateParser(StringReader reader, boolean legacyFormat, boolean allowTag)` | 构造 | `allowTag` 目前**无意义**：构造里被强制改成 `false`（源码 `// TODO`），所以 `#标签` 一律不支持 | 实例 |
| `parse()` | 完整解析（方块 ID → 属性 → NBT） | reader 停在起点 | `BlockStateParser`（`this`，方便链式） |
| `parseBlock()` | 只解析方块 ID | 同上 | 无（void），结果进 `getId()` / `getState()`；未知 ID 抛 `INVALID_ID_EXCEPTION`（`argument.block.id.invalid`） |
| `parseProperties()` | 解析属性表：新写法 `[a=b,c=d]`，旧写法 ` a=b` 或元数据数字 | 必须已经解析过方块 | 无（void）；错误见下表 |
| `parseVagueProperties()` | 解析"模糊属性"（标签时代的产物，`[a=b]` 允许多种方块） | 仅新写法 + 标签场景用到；1.12.2 上标签不可用，实际走不到 | 无（void） |
| `parseTag()` | 解析 `#标签` | `allowTag` 为 `true` 才允许 | 无（void）；1.12.2 上必然抛 `NO_TAGS_ALLOWED_EXCEPTION`（`argument.block.tag.disallowed`） |
| `parseNbt()` | 解析 `{…}` 方块实体 NBT | 只在非旧写法下由 `parse()` 调用 | 无（void） |
| `getId()` / `getProperties()` / `getState()` / `getNbt()` / `getTag()` | 读解析结果 | 解析过才有值；`getState()` 在方块不存在时是 `null` | `NamespacedIdentifier` / `Map<Property<?>, Comparable<?>>` / `BlockState` / `NbtCompound` / `NamespacedIdentifier` |
| `addSuggestions(SuggestionsBuilder builder)` | 把当前解析状态对应的建议塞进 builder | — | `CompletableFuture<Suggestions>` |
| `serializeProperties(BlockState state)` | 反向序列化成命令字符串 | `state` 非 `null` | `String`，形如 `minecraft:stone[a=b]`（无属性时只有 ID） |

公开的异常常量（都是 Brigadier 的异常类型，可直接 `throw X.createWithContext(reader, …)`）：

| 常量 | 语言键 | 触发条件 |
|---|---|---|
| `NO_TAGS_ALLOWED_EXCEPTION` | `argument.block.tag.disallowed` | 用了 `#标签` 但 `allowTag` 为假 |
| `INVALID_ID_EXCEPTION` | `argument.block.id.invalid` | 方块 ID 查不到 |
| `INVALID_DATA_EXCEPTION` | `argument.block.data.invalid` | 旧写法元数据不在 `0..15` |
| `UNKNOWN_PROPERTY_EXCEPTION` | `argument.block.property.unknown` | 属性名不属于该方块 |
| `DUPLICATE_PROPERTY_EXCEPTION` | `argument.block.property.duplicate` | 同一属性写了两遍 |
| `INVALID_PROPERTY_EXCEPTION` | `argument.block.property.invalid` | 属性值不合法 |
| `NO_VALUE_EXCEPTION` | `argument.block.property.novalue` | 属性后面没有 `=值` |
| `UNCLOSED_PROPERTY_EXCEPTION` | `argument.block.property.unclosed` | 属性表没有闭合的 `]` |

## 参数类型：物品

### `ItemArgument`

Reference: `net.ornithemc.osl.commands.api.command.argument.ItemArgument`

**作用**：物品参数（`item_stack`）：物品 ID + 可选 NBT，例如 `stick`、`minecraft:stick`、`stick{foo=bar}`。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `item()` | 工厂 | — | `ItemArgument` |
| `parse(StringReader reader)` | 用 `new ItemParser(reader, false).parse()` 解析 | — | `ItemInput`；未知物品 ID 抛 `ItemParser.INVALID_ID_EXCEPTION` |
| `getItem(CommandContext<S> ctx, String arg)` | 取值 | — | `ItemInput` |
| `listSuggestions(…)` | 补全：物品 ID 前缀匹配，解析完成后会给 `{` 建议 | — | `CompletableFuture<Suggestions>` |
| `getExamples()` | 示例 | — | `Collection<String>` |

### `ItemPredicateArgument`

Reference: `net.ornithemc.osl.commands.api.command.argument.ItemPredicateArgument`

**作用**：物品**谓词**参数（`item_predicate`）：解析成 `Predicate<ItemStack>`，用于"背包里所有符合…的物品"。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `itemPredicate()` | 工厂 | — | `ItemPredicateArgument` |
| `parse(StringReader reader)` | `new ItemParser(reader, true).parse()` | — | `ItemPredicateArgument.Result`；物品 ID 不存在时不立刻报错，`create(ctx)` 时才抛 `arguments.item.unknown` |
| `getItemPredicate(CommandContext<CommandSourceStack> ctx, String arg)` | 取值 | — | `Predicate<ItemStack>` |
| `listSuggestions(…)` | 补全 | — | `CompletableFuture<Suggestions>` |
| `getExamples()` | 示例里含 `#stick`，但 **1.12.2 上标签不可用**，实际只能写物品 ID | — | `Collection<String>` |
| `ItemPredicateArgument.Result`（函数式接口） | 延迟构造谓词 | `create(CommandContext<CommandSourceStack> ctx)` 可能抛 `CommandSyntaxException` | `Predicate<ItemStack>` |

### `ItemInput`

Reference: `net.ornithemc.osl.commands.api.command.argument.ItemInput`

**作用**：`ItemArgument` 的解析结果：物品 + 可选 NBT。既是 `Predicate<ItemStack>`，也能造出真正的 `ItemStack`。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `new ItemInput(Item item, NbtCompound nbt)` | 构造 | `item` 非 `null`；`nbt` 可为 `null` | 实例 |
| `getItem()` | 取物品 | — | `Item` |
| `test(ItemStack item)` | 判断物品堆是否匹配（物品相同 + NBT 部分匹配） | `item` 非 `null` | `boolean` |
| `createItem(int size, boolean validateStackSize)` | 造一个物品堆，并可选地校验堆叠上限 | `size` ≥ 0；`validateStackSize` 为真且超上限时抛 `arguments.item.overstacked` | `ItemStack` |
| `serialize()` | 反向序列化为命令字符串 | — | `String`：`物品ID` + NBT 的 `toString()` |

### `ItemParser`

Reference: `net.ornithemc.osl.commands.api.command.argument.ItemParser`

**作用**：物品字符串的底层解析器（`ItemArgument` 与 `ItemPredicateArgument` 共用）。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `new ItemParser(StringReader reader, boolean allowTag)` | 构造 | `allowTag` 目前**无意义**：构造里被强制改成 `false`（源码 `// TODO`） | 实例 |
| `parse()` | 完整解析（`#标签` 或物品 ID → 可选 `{…}` NBT） | reader 停在起点 | `ItemParser`（`this`） |
| `parseItem()` | 只解析物品 ID | — | 无（void），结果进 `getId()` / `getItem()`；未知 ID 抛 `INVALID_ID_EXCEPTION`（`argument.item.id.invalid`） |
| `parseTag()` | 解析 `#标签` | `allowTag` 为真 | 无（void）；1.12.2 上必然抛 `NO_TAGS_ALLOWED_EXCEPTION`（`argument.item.tag.disallowed`） |
| `parseNbt()` | 解析 `{…}` | — | 无（void） |
| `getId()` / `getItem()` / `getNbt()` / `getTag()` | 读解析结果 | — | `NamespacedIdentifier` / `Item`（可能 `null`）/ `NbtCompound` / `NamespacedIdentifier` |
| `addSuggestions(SuggestionsBuilder builder)` | 把建议塞进 builder | — | `CompletableFuture<Suggestions>` |
| `NO_TAGS_ALLOWED_EXCEPTION` / `INVALID_ID_EXCEPTION` | 公开异常常量 | — | `SimpleCommandExceptionType` / `DynamicCommandExceptionType` |

## 参数类型：实体与玩家

### `EntityArgument`

Reference: `net.ornithemc.osl.commands.api.command.argument.EntityArgument`

**作用**：实体/玩家参数（`entity`、`entities`、`player`、`players` 四种变体）：既能写具体名字、UUID，也能写 `@e` / `@e[type=foo]` 这类选择器。四个工厂方法的区别只在于"允许多个"和"只允许玩家"。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `entity()` | 工厂：单个实体（`@e` 也接受，但只能选中 1 个） | — | `EntityArgument`（`single = true, players = false`） |
| `entities()` | 工厂：多个实体 | — | `EntityArgument`（`single = false, players = false`） |
| `player()` | 工厂：单个玩家 | — | `EntityArgument`（`single = true, players = true`） |
| `players()` | 工厂：多个玩家 | — | `EntityArgument`（`single = false, players = true`） |
| `parse(StringReader reader)` | 交给 `EntitySelectorParser` 解析，再按变体校验数量与玩家限制 | — | `EntitySelector`；选择器选中多个而参数是"单个"时抛 `TOO_MANY_ENTITIES_EXCEPTION`（`argument.entity.toomany`）或 `TOO_MANY_PLAYERS_EXCEPTION`（`argument.player.toomany`）；只允许玩家却选了非玩家时抛 `NOT_PLAYER_EXCEPTION`（`argument.player.entities`） |
| `getEntity(CommandContext<CommandSourceStack> ctx, String arg)` | 取单个实体 | — | `Entity`；找不到抛 `ENTITY_NOT_FOUND_EXCEPTION`（`argument.entity.notfound.entity`），多于一个抛 `TOO_MANY_ENTITIES_EXCEPTION` |
| `getEntities(CommandContext<CommandSourceStack> ctx, String arg)` | 取实体集合（至少 1 个） | — | `Collection<? extends Entity>`；空则抛 `ENTITY_NOT_FOUND_EXCEPTION` |
| `getOptionalEntities(CommandContext<CommandSourceStack> ctx, String arg)` | 取实体集合，允许为空 | — | `Collection<? extends Entity>` |
| `getPlayer(CommandContext<CommandSourceStack> ctx, String arg)` | 取单个玩家 | — | `ServerPlayerEntity`；不是恰好 1 个时抛 `PLAYER_NOT_FOUND_EXCEPTION`（`argument.entity.notfound.player`） |
| `getPlayers(CommandContext<CommandSourceStack> ctx, String arg)` | 取玩家集合（至少 1 个） | — | `Collection<ServerPlayerEntity>`；空则抛 `PLAYER_NOT_FOUND_EXCEPTION` |
| `getOptionalPlayers(CommandContext<CommandSourceStack> ctx, String arg)` | 取玩家集合，允许为空 | — | `Collection<ServerPlayerEntity>` |
| `listSuggestions(…)` | 补全：先重解析一遍再给出选择器名（`@p`/`@a`/`@r`/`@s`/`@e`）、选项名、玩家名 | 命令源不是 `SharedSuggestionProvider` 时返回 `Suggestions.empty()` | `CompletableFuture<Suggestions>` |
| `getExamples()` | 示例：`Player`、`0123`、`@e`、`@e[type=foo]`、UUID | — | `Collection<String>` |
| `TOO_MANY_ENTITIES_EXCEPTION` / `TOO_MANY_PLAYERS_EXCEPTION` / `NOT_PLAYER_EXCEPTION` / `ENTITY_NOT_FOUND_EXCEPTION` / `PLAYER_NOT_FOUND_EXCEPTION` / `SELECTOR_NOT_ALLOWED_EXCEPTION` | 公开异常常量 | — | 各自的 Brigadier 异常类型 |
| `EntityArgument.Serializer`（嵌套类） | 网络序列化：用 1 字节标志位（`1`=single，`2`=players） | 见"参数序列化" | `ArgumentSerializer<EntityArgument>` |

### `EntitySelector`

Reference: `net.ornithemc.osl.commands.api.command.argument.EntitySelector`

**作用**：`EntityArgument` 的解析结果，也就是"怎么选实体"的完整描述：数量上限、是否允许非玩家、是否限制在本维度、谓词、距离区间、位置变换、包围盒、排序方式、限定名字/UUID/类型、是否是 `@` 选择器。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `new EntitySelector(int max, boolean allowNonPlayers, boolean restrictOtherWorlds, Predicate<Entity> predicate, NumberRange.Floats range, Function<Vec3d, Vec3d> position, Box bounds, BiConsumer<Vec3d, List<? extends Entity>> order, boolean allowSelf, String name, UUID uuid, Class<? extends Entity> type, boolean selector)` | 全部字段的构造器（一般由 `EntitySelectorParser` 造） | `predicate`/`range`/`position`/`order` 非 `null`；`name`/`uuid` 可空 | 实例 |
| `getMax()` | 最多选几个 | — | `int` |
| `hasNonPlayers()` | 是否允许非玩家实体（`@e`/`@s` 为真，`@a`/`@p`/`@r` 为假） | — | `boolean` |
| `hasSelf()` | 是否是"自己"（`@s`） | — | `boolean` |
| `isRestrictOtherWorlds()` | 是否只在本维度找 | — | `boolean` |
| `findSingleEntity(CommandSourceStack source)` | 找唯一实体 | 命令源权限 ≥ 2（用了 `@` 选择器时），否则抛 `SELECTOR_NOT_ALLOWED_EXCEPTION`（`argument.entity.selector.not_allowed`） | `Entity`；空抛 `ENTITY_NOT_FOUND_EXCEPTION`，多个抛 `TOO_MANY_ENTITIES_EXCEPTION` |
| `findEntities(CommandSourceStack source)` | 找实体列表：有名字查 `PlayerManager`，有 UUID 遍历所有维度，否则按包围盒/距离/谓词在对应维度里收集，再排序并截断到 `max` | 同上权限要求 | `List<? extends Entity>`（可能为空） |
| `findSinglePlayer(CommandSourceStack source)` | 找唯一玩家 | 同上 | `ServerPlayerEntity`；不是恰好 1 个时抛 `PLAYER_NOT_FOUND_EXCEPTION` |
| `findPlayers(CommandSourceStack source)` | 找玩家列表 | 同上 | `List<ServerPlayerEntity>` |
| `joinNames(List<? extends Entity> entities)`（静态） | 把实体列表拼成"名字、名字、…"的文本（多于 1 个时用灰色逗号分隔） | `entities` 非 `null` | `TextComponent`（空列表返回空文本） |

### `EntitySelectorParser`

Reference: `net.ornithemc.osl.commands.api.command.argument.EntitySelectorParser`

**作用**：`@e[type=foo,sort=nearest]` 这类选择器字符串的解析器。通常不用直接 new，但如果你想在自己的参数类型里复用选择器语法（`MessageArgument`、`ScoreHolderArgument` 就是这么做的），就把 reader 交给它。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `new EntitySelectorParser(StringReader reader)` | 构造（允许选择器） | — | 实例 |
| `new EntitySelectorParser(StringReader reader, boolean allowSelectors)` | 构造：`allowSelectors` 为假时遇到 `@` 抛异常 | 权限不足（< 2）时应传 `false` | 实例 |
| `parse()` | 完整解析：`@` 开头走选择器，否则按"名字或 UUID"解析 | reader 停在起点 | `EntitySelector`；缺选择器字符抛 `SELECTOR_MISSING_EXCEPTION`，未知选择器抛 `UNKNOWN_SELECTOR_EXCEPTION`，名字非法抛 `INVALID_EXCEPTION` |
| `getSelector()` | 把当前状态打包成 `EntitySelector`（`parse()` 内部会调用） | 已解析过 | `EntitySelector` |
| `getReader()` | 取内部的 `StringReader` | — | `StringReader` |
| `addSuggestions(SuggestionsBuilder builder, Consumer<SuggestionsBuilder> names)` | 按当前解析阶段给建议；`names` 用来补"名字"这一类候选 | `names` 非 `null` | `CompletableFuture<Suggestions>` |
| `setSuggestions(BiFunction<SuggestionsBuilder, Consumer<SuggestionsBuilder>, CompletableFuture<Suggestions>> suggestions)` | 替换建议策略（选项处理器里用） | — | 无（void） |
| `shouldInvertValue()` | 读可选的 `!` 取反前缀 | reader 已跳过空白 | `boolean` |
| `addPredicate(Predicate<Entity> predicate)` | 追加实体过滤条件（多个条件取"与"） | — | 无（void） |
| `setRestrictOtherWorlds()` | 标记"只在本维度找" | — | 无（void） |
| `getDistance()` / `setDistance(NumberRange.Floats)` | `distance` 选项 | — | `NumberRange.Floats` |
| `getXp()` / `setXp(NumberRange.Ints)` | `level` 选项 | — | `NumberRange.Ints` |
| `getPitch()` / `setPitch(WrappedNumberRange)` | `x_rotation` 选项 | — | `WrappedNumberRange` |
| `getYaw()` / `setYaw(WrappedNumberRange)` | `y_rotation` 选项 | — | `WrappedNumberRange` |
| `getX()` / `getY()` / `getZ()` / `setX(double)` / `setY(double)` / `setZ(double)` | 基准坐标选项 | — | `Double` / 无（void） |
| `getDx()` / `getDy()` / `getDz()` / `setDx(double)` / `setDy(double)` / `setDz(double)` | 体积（包围盒）选项 | — | `Double` / 无（void） |
| `setMax(int max)` / `setAllowNonPlayers(boolean)` / `setOrder(BiConsumer<Vec3d, List<? extends Entity>>)` | 数量上限 / 是否允许非玩家 / 排序方式 | — | 无（void） |
| `setType(Class<? extends Entity> type)` | 限定实体类型 | — | 无（void） |
| `hasSelf()` / `hasName()` / `hasNotName()` / `hasLimit()` / `hasOrder()` / `hasGameMode()` / `hasNotGameMode()` / `hasTeam()` / `hasNotTeam()` / `hasType()` / `hasNotType()` / `hasScores()` / `hasAdvancements()` | 选项"是否已用过"的标记（用来阻止重复或互斥的选项） | — | `boolean` |
| `setHasName(boolean)` / `setHasNotName(boolean)` / `setHasLimit(boolean)` / `setHasOrder(boolean)` / `setHasGameMode(boolean)` / `setHasNotGameMode(boolean)` / `setHasTeam(boolean)` / `setHasNotTeam(boolean)` / `setHasNotType()` / `setHasScores(boolean)` / `setHasAdvancements(boolean)` | 设置上面的标记 | — | 无（void） |
| `parseSelector()` / `parseNameOrUuid()` / `parseOptions()`（`protected`） | 分段解析，供子类在自定义语法里复用 | 由 `parse()` 调用 | 无（void） |
| `ORDER_NEAREST` / `ORDER_FURTHEST` / `ORDER_RANDOM` / `ORDER_ARBITRARY` | 四种排序方式（`sort=` 的取值） | — | `BiConsumer<Vec3d, List<? extends Entity>>` |
| `NO_SUGGESTIONS` / `SORT_ORDER_SUGGESTIONS` | 预置建议策略 | — | `BiFunction<…>` |
| `INVALID_EXCEPTION` / `UNKNOWN_SELECTOR_EXCEPTION` / `SELECTOR_NOT_ALLOWED_EXCEPTION` / `SELECTOR_MISSING_EXCEPTION` / `UNTERMINATED_OPTIONS_EXCEPTION` / `OPTION_WITHOUT_VALUE_EXCEPTION` | 公开异常常量 | — | 各自的 Brigadier 异常类型 |

各选择器的默认值（读自 `parseSelector()`）：

| 选择器 | `max` | 允许非玩家 | 排序 | 类型限制 | 附加 |
|---|---|---|---|---|---|
| `@p` | 1 | 否 | 最近 | `ServerPlayerEntity` | — |
| `@a` | `Integer.MAX_VALUE` | 否 | 无 | `ServerPlayerEntity` | — |
| `@r` | 1 | 否 | 随机 | `ServerPlayerEntity` | — |
| `@s` | 1 | 是 | 无 | 不限 | `allowSelf = true` |
| `@e` | `Integer.MAX_VALUE` | 是 | 无 | 不限 | 谓词要求 `Entity::isAlive` |

### `EntitySelectorOptions`

Reference: `net.ornithemc.osl.commands.api.command.argument.EntitySelectorOptions`

**作用**：选择器方括号里那些选项（`name`、`type`、`sort`、`scores` …）的注册表与实现。解析由 `EntitySelectorParser.parseOptions()` 驱动，这里只提供"按名字取处理器"和"给建议"。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `init()` | 注册全部内置选项。**幂等**（表非空就直接返回） | 见下方警告 | 无（void） |
| `get(EntitySelectorParser parser, String name, int cursor)` | 取某选项的处理器 | `name` 必须已注册，否则回退游标并抛 `UNKNOWN_EXCEPTION`（`argument.entity.options.unknown`） | `Modifier`；该选项在当前状态下不适用时抛 `NOT_APPLICABLE_EXCEPTION`（`argument.entity.options.inapplicable`） |
| `suggest(EntitySelectorParser parser, SuggestionsBuilder builder)` | 建议当前可用的选项名（带 `=` 和说明文本） | — | 无（void） |
| `EntitySelectorOptions.Modifier`（函数式接口） | 选项处理器 | 实现 `apply(EntitySelectorParser parser)`，可能抛 `CommandSyntaxException` | 无（void） |
| `UNKNOWN_EXCEPTION` / `NOT_APPLICABLE_EXCEPTION` / `NEGATIVE_DISTANCE_EXCEPTION` / `NEGATIVE_XP_EXCEPTION` / `LIMIT_TOO_SMALL_EXCEPTION` / `UNKNOWN_ORDER_EXCEPTION` / `INVALID_GAME_MODE_EXCEPTION` / `INVALID_ENTITY_TYPE_EXCEPTION` | 公开异常常量 | — | 各自的 Brigadier 异常类型 |

内置选项一览（方括号里的内容）：

| 选项 | 值写法 | 作用 |
|---|---|---|
| `name` | 名字，可加 `!` 取反 | 按实体名精确匹配 |
| `distance` | `5`、`1..5`、`..10`、`3..` | 与命令源的距离区间；负值报错；同时会把搜索限制在本维度 |
| `level` | 同上的整数区间 | 玩家经验等级；会把"允许非玩家"关掉 |
| `x` / `y` / `z` | 浮点 | 搜索基准坐标（覆盖命令源坐标），同时限制本维度 |
| `dx` / `dy` / `dz` | 浮点 | 以基准点为角的体积，负值自动纠正方向 |
| `x_rotation` | 角度区间，如 `-90..90` | pitch 区间，按 `MathHelper.wrapDegrees` 环绕 |
| `y_rotation` | 同上 | yaw 区间 |
| `limit` | 正整数 | 最多选几个；`@s` 上不允许 |
| `sort` | `nearest` / `furthest` / `random` / `arbitrary` | 结果排序；`@s` 上不允许 |
| `gamemode` | `survival` / `creative` / …，可加 `!` | 玩家游戏模式；会把"允许非玩家"关掉 |
| `team` | 队伍名，可加 `!`；空串表示"无队伍" | 队伍匹配（只对 `LivingEntity` 生效） |
| `type` | 实体类型 ID（`minecraft:zombie`），可加 `!` | 实体类型；写玩家类型会关掉"允许非玩家" |
| `tag` | 命令标签名，可加 `!`；空串表示"没有任何标签" | 匹配 `Entity#getCommandTags()` |
| `nbt` | SNBT 复合标签，可加 `!` | 匹配实体 NBT（玩家还会带上 `SelectedItem`） |
| `scores` | `{objective=区间, …}` | 记分板分数匹配；任一目标不存在/没分数即不匹配 |
| `advancements` | `{id=true, id={criterion=false}}` | 进度匹配（1.12 及以上才注册，1.12.2 可用）；会把"允许非玩家"关掉 |

> **重要提醒**：本子工程的 `fabric.mod.json` 入口只挂了 `BrigadierCommandsImpl::init` / `initClient`，在整个仓库里搜不到对 `EntitySelectorOptions.init()` 的调用。也就是说 1.12.2 上这张选项表默认是**空的**，`@e[name=…]` 之类会抛"未知选项"。需要选项时请在自己的 mod 初始化里先调用一次 `EntitySelectorOptions.init()`（幂等，重复调用无副作用）。

### `GameProfileArgument`

Reference: `net.ornithemc.osl.commands.api.command.argument.GameProfileArgument`

**作用**：玩家档案参数（`game_profile`）：名字、UUID 或玩家选择器，解析成 `GameProfile` 集合（用档案缓存，不需要实体在线）。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `gameProfiles()` | 工厂 | — | `GameProfileArgument` |
| `parse(StringReader reader)` | `@` 开头按选择器解析（不允许非玩家），否则读到空格为止当名字 | — | `GameProfileArgument.Result`；选择器含非玩家时抛 `EntityArgument.NOT_PLAYER_EXCEPTION` |
| `getGameProfiles(CommandContext<CommandSourceStack> ctx, String arg)` | 取值 | 名字不在档案缓存里时抛 `UNKNOWN_PLAYER_EXCEPTION`（`argument.player.unknown`）；选择器选不到玩家时抛 `argument.entity.notfound.player` | `Collection<GameProfile>` |
| `listSuggestions(…)` | 补全：选择器名 + 在线玩家名 | 需 `SharedSuggestionProvider` | `CompletableFuture<Suggestions>` |
| `getExamples()` | 示例：`Player`、`0123`、UUID、`@e` | — | `Collection<String>` |
| `GameProfileArgument.SelectorResult`（嵌套类） | 用 `EntitySelector` 实现的 `Result` | 构造时传选择器 | 实例 |
| `GameProfileArgument.Result`（函数式接口） | 延迟求值 | `create(CommandSourceStack source)` 可能抛 `CommandSyntaxException` | `Collection<GameProfile>` |

## 参数类型：文本

### `TextArgument`

Reference: `net.ornithemc.osl.commands.api.command.argument.TextArgument`

**作用**：JSON 文本组件参数（`component`）：`"hello"`、`{"text":"hi","color":"red"}` 这类写法，解析成 `TextComponent`。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `text()` | 工厂 | — | `TextArgument` |
| `parse(StringReader reader)` | 取 `reader.getRemaining()` 整体当 JSON 解析；**不推进游标**，所以这个参数实际上只能放在命令末尾（贪婪） | — | `TextComponent`；JSON 非法或解析结果为空时抛 `INVALID_TEXT_EXCEPTION`（`argument.component.invalid`），并把 JSON 解析错误的 cause 消息塞进参数 |
| `getText(CommandContext<?> ctx, String arg)` | 取值 | — | `TextComponent` |
| `getExamples()` | 示例：`"hello world"`、`""`、转义双引号包着的 JSON、`[""]` | — | `Collection<String>` |
| `INVALID_TEXT_EXCEPTION` | 公开异常常量 | — | `DynamicCommandExceptionType` |

### `MessageArgument`

Reference: `net.ornithemc.osl.commands.api.command.argument.MessageArgument`

**作用**：聊天消息参数（`message`）：取剩下所有文本，但保留其中的 `@p` / `@e` 选择器，等到真正取文本时再按命令源的权限展开成玩家名字。`/msg`、`/say` 这类命令需要它。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `message()` | 工厂 | — | `MessageArgument` |
| `parse(StringReader reader)` | 取剩下全部文本并扫描 `@` 选择器（转调 `Message.parseText`） | — | `MessageArgument.Message` |
| `getMessage(CommandContext<CommandSourceStack> ctx, String arg)` | 取值并展开成文本组件 | 命令源权限 ≥ 2 才展开选择器，否则整段当普通文本 | `TextComponent`；选择器解析失败时抛 `CommandSyntaxException` |
| `getExamples()` | 示例：`Hello world!`、`foo`、`@e`、`Hello @p :)` | — | `Collection<String>` |
| `MessageArgument.Message`（嵌套类） | 原始文本 + 选择器片段表 | 构造 `Message(String text, Part[] parts)` | 实例 |
| `Message.toText(CommandSourceStack source, boolean op)` | 展开成文本：`op` 为假或没有片段时直接返回整段字面量 | `source` 非 `null` | `TextComponent` |
| `Message.parseText(StringReader reader, boolean op)`（静态） | 扫描文本里的 `@` 选择器；`op` 为假时不扫描、直接吃掉剩余输入 | — | `Message`；选择器语法错误但不是"缺选择器/未知选择器"时原样外抛 |
| `MessageArgument.Part`（嵌套类） | 一个选择器片段：`getStart()` / `getEnd()`（相对整段文本的偏移）与 `getText(CommandSourceStack source)` | `source` 非 `null` | `int` / `int` / `TextComponent` |

## 参数类型：NBT

### `NbtCompoundArgument`

Reference: `net.ornithemc.osl.commands.api.command.argument.NbtCompoundArgument`

**作用**：SNBT 复合标签参数（`nbt`）：`{}`、`{foo:bar}`、`{a:[1,2],b:{c:"d"}}`，解析成 `NbtCompound`。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `nbtCompound()` | 工厂 | — | `NbtCompoundArgument` |
| `parse(StringReader reader)` | 交给 `new SnbtParser(reader).readCompound()` | reader 停在 `{` 上 | `NbtCompound`；语法错误抛 `SnbtParser` 的各类异常（见该类的表） |
| `getNbtCompound(CommandContext<S> ctx, String arg)` | 取值 | — | `NbtCompound` |
| `getExamples()` | 示例：`{}`、`{foo=bar}` | — | `Collection<String>` |
| `INVALID_NBT_EXCEPTION` | 公开异常常量（`argument.nbt.invalid`）；注意 `parse` 自己不抛它，实际抛的是 `SnbtParser` 的异常 | — | `DynamicCommandExceptionType` |

## 参数类型：记分板

### `ObjectiveArgument`

Reference: `net.ornithemc.osl.commands.api.command.argument.ObjectiveArgument`

**作用**：记分板目标名参数（`objective`），`getObjective` 会顺手帮你查表。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `objective()` | 工厂 | — | `ObjectiveArgument` |
| `parse(StringReader reader)` | 读一个非引号字符串当目标名 | 名字长度不得超过 16 | `String`；超长时回退游标并抛 `NAME_TOO_LONG_EXCEPTION`（`commands.scoreboard.objectives.add.longName`） |
| `getObjective(CommandContext<CommandSourceStack> ctx, String arg)` | 按名字查目标 | 命令源必须有世界 | `ScoreboardObjective`；查不到抛 `arguments.objective.notFound` |
| `getWritableObjective(CommandContext<CommandSourceStack> ctx, String arg)` | 查目标并检查可写（只读判据不可写） | 同上 | `ScoreboardObjective`；只读时抛 `arguments.objective.readonly` |
| `listSuggestions(…)` | 补全：当前记分板里的目标名；命令源是 `SharedSuggestionProvider` 时改为向它请求（即客户端会问服务端） | — | `CompletableFuture<Suggestions>` |
| `getExamples()` | 示例：`foo`、`*`、`012` | — | `Collection<String>` |
| `NAME_TOO_LONG_EXCEPTION` | 公开异常常量 | — | `DynamicCommandExceptionType` |

### `ScoreHolderArgument`

Reference: `net.ornithemc.osl.commands.api.command.argument.ScoreHolderArgument`

**作用**：记分项持有者参数（`score_holder`）：玩家名、`*`（全部）、或实体选择器，解析成"名字列表"。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `scoreHolder()` | 工厂：单个持有者 | — | `ScoreHolderArgument`（`multiple = false`） |
| `scoreHolders()` | 工厂：多个持有者 | — | `ScoreHolderArgument`（`multiple = true`） |
| `new ScoreHolderArgument(boolean multiple)` | 直接构造 | — | 实例 |
| `parse(StringReader reader)` | `@` 开头按选择器解析（单个模式下选择器上限 > 1 就报错），`*` 走"全部"分支，否则当名字 | — | `ScoreHolderArgument.Result`；单个模式选了多个时抛 `EntityArgument.TOO_MANY_ENTITIES_EXCEPTION` |
| `getScoreHolder(CommandContext<CommandSourceStack> ctx, String arg)` | 取第一个名字 | — | `String`；集合为空抛 `argument.entity.notfound.entity` |
| `getScoreHolders(CommandContext<CommandSourceStack> ctx, String arg)` | 取名字集合，`*` 视为空 | — | `Collection<String>`；为空抛 `argument.entity.notfound.entity` |
| `getScoreHoldersOrAll(CommandContext<CommandSourceStack> ctx, String arg)` | 同上的 `*` 版本：回退成"记分板里所有有分数的人" | — | `Collection<String>` |
| `getScoreHolders(CommandContext<CommandSourceStack> ctx, String arg, Supplier<Collection<String>> fallback)` | 自己给 `*` 的回退集合 | `fallback` 非 `null`；回退结果为空抛 `argument.scoreHolder.empty` | `Collection<String>`；结果为空抛 `argument.entity.notfound.entity` |
| `getExamples()` | 示例：`Player`、`0123`、`*`、`@e` | — | `Collection<String>` |
| `SCORE_HOLDER_SUGGESTIONS` | 现成的补全器（按选择器语法解析后补在线玩家名） | — | `SuggestionProvider<CommandSourceStack>` |
| `ScoreHolderArgument.Result`（函数式接口） | 延迟求值 | `create(CommandSourceStack source, Supplier<Collection<String>> fallback)` 可能抛异常 | `Collection<String>` |
| `ScoreHolderArgument.SelectorResult`（嵌套类） | 用 `EntitySelector` 实现的 `Result`：玩家取名字，其他实体取 UUID 字符串 | 构造时传选择器 | 实例 |
| `ScoreHolderArgument.Serializer`（嵌套类） | 网络序列化：1 字节标志位（`1`=multiple） | 见"参数序列化" | `ArgumentSerializer<ScoreHolderArgument>` |

### `ScoreboardCriterionArgument`

Reference: `net.ornithemc.osl.commands.api.command.argument.ScoreboardCriterionArgument`

**作用**：记分板判据参数（`objective_criteria`），比如 `dummy`、`health`、`minecraft:foo`。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `criterion()` | 工厂 | — | `ScoreboardCriterionArgument` |
| `parse(StringReader reader)` | 读到空格为止，再按名字查 `ScoreboardCriterion.BY_NAME` | — | `ScoreboardCriterion`；查不到回退游标并抛 `INVALID_CRITERION_EXCEPTION`（`argument.criteria.invalid`） |
| `getCriterion(CommandContext<CommandSourceStack> ctx, String arg)` | 取值 | — | `ScoreboardCriterion` |
| `listSuggestions(…)` | 补全：所有判据名 | — | `CompletableFuture<Suggestions>` |
| `getExamples()` | 示例：`foo`、`foo.bar.baz`、`minecraft:foo` | — | `Collection<String>` |
| `INVALID_CRITERION_EXCEPTION` | 公开异常常量 | — | `DynamicCommandExceptionType` |

### `ScoreboardDisplaySlotArgument`

Reference: `net.ornithemc.osl.commands.api.command.argument.ScoreboardDisplaySlotArgument`

**作用**：记分板显示位置参数（`scoreboard_slot`），例如 `sidebar`、`list`、`below_name`，解析成原版的槽位数字。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `displaySlot()` | 工厂 | — | `ScoreboardDisplaySlotArgument` |
| `parse(StringReader reader)` | 读一个非引号字符串，交给 `Scoreboard.getDisplaySlot(name)` | — | `Integer`；返回 `-1`（未知槽位）时回退游标并抛 `INVALID_DISPLAY_SLOT_EXCEPTION`（`argument.scoreboardDisplaySlot.invalid`） |
| `getDisplaySlot(CommandContext<?> ctx, String arg)` | 取值（返回原始 `int`） | — | `int` |
| `listSuggestions(…)` | 补全：`Scoreboard.getDisplayLocations()` | — | `CompletableFuture<Suggestions>` |
| `getExamples()` | 示例：`sidebar`、`foo.bar` | — | `Collection<String>` |
| `INVALID_DISPLAY_SLOT_EXCEPTION` | 公开异常常量 | — | `DynamicCommandExceptionType` |

### `OperationArgument`

Reference: `net.ornithemc.osl.commands.api.command.argument.OperationArgument`

**作用**：记分板运算参数（`operation`）：`=`、`+=`、`-=`、`*=`、`/=`、`%=`、`<`、`>`、`><`（交换）。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `operation()` | 工厂 | — | `OperationArgument` |
| `parse(StringReader reader)` | 读到空格为止再查表 | 输入为空抛 `arguments.operation.invalid`；符号不认识同样抛它 | `OperationArgument.Operation` |
| `getOperation(CommandContext<?> ctx, String arg)` | 取值 | — | `Operation` |
| `listSuggestions(…)` | 补全：九个运算符号 | — | `CompletableFuture<Suggestions>` |
| `getExamples()` | 示例：`=`、`>`、`<` | — | `Collection<String>` |
| `OperationArgument.Operation`（函数式接口） | 对两个 `ScoreboardScore` 执行运算（`apply(score1, score2)`） | `/=` 与 `%=` 在除数为 0 时抛 `arguments.operation.div0` | 无（void） |

`<` 取较小值、`>` 取较大值、`><` 交换两个分数；除法与取模用 `MathHelper.floorDiv` / `floorMod`（向下取整，与 Java 的 `/` 不同）。

### `TeamArgument`

Reference: `net.ornithemc.osl.commands.api.command.argument.TeamArgument`

**作用**：队伍名参数（`team`）。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `team()` | 工厂 | — | `TeamArgument` |
| `parse(StringReader reader)` | 读一个非引号字符串 | — | `String` |
| `getTeam(CommandContext<CommandSourceStack> ctx, String arg)` | 按名字查队伍 | 命令源必须有世界 | `Team`；查不到抛 `team.notFound` |
| `listSuggestions(…)` | 补全：命令源的 `getTeams()` | 需 `SharedSuggestionProvider`，否则空建议 | `CompletableFuture<Suggestions>` |
| `getExamples()` | 示例：`foo`、`123` | — | `Collection<String>` |

## 参数类型：杂项

### `IdentifierArgument`

Reference: `net.ornithemc.osl.commands.api.command.argument.IdentifierArgument`

**作用**：命名空间 ID 参数（`resource_location`），例如 `foo`、`minecraft:stone`。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `identifier()` | 工厂 | — | `IdentifierArgument` |
| `parse(StringReader reader)` | 交给 `IdentifierParser.parse` | — | `NamespacedIdentifier`（OSL 的 ID 类型）；非法时抛 `argument.id.invalid` |
| `getNamespacedIdentifier(CommandContext<?> ctx, String arg)` | 取 OSL 的 ID | — | `NamespacedIdentifier` |
| `getIdentifier(CommandContext<?> ctx, String arg)` | 取原版 `Identifier` | — | `Identifier`（内部 `new Identifier(id.toString())`） |
| `getExamples()` | 示例：`foo`、`foo:bar`、`012` | — | `Collection<String>` |
| `UNKNOWN_ID_EXCEPTION` | 公开异常常量（`argument.id.unknown`）；`parse` 不用它，供你自己在查表失败时使用 | — | `DynamicCommandExceptionType` |

### `IdentifierParser`

Reference: `net.ornithemc.osl.commands.api.command.argument.IdentifierParser`

**作用**：OSL 命名空间 ID 的解析工具，`IdentifierArgument`、`ItemParser`、`BlockStateParser`、`StatusEffectArgument` 等都靠它读 ID。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `parse(StringReader reader)` | 读尽可能长的合法 ID 字符，再交给 `NamespacedIdentifiers.parse` | — | `NamespacedIdentifier`；不合法时回退游标并抛 `argument.id.invalid` |
| `parseIdentifier(StringReader reader)` | 同上的原版类型版本 | 同上 | `Identifier` |

### `ColorArgument`

Reference: `net.ornithemc.osl.commands.api.command.argument.ColorArgument`

**作用**：颜色参数（`color`），取值是 `Formatting`（`red`、`gold`、`reset` …）。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `color()` | 工厂 | — | `ColorArgument` |
| `parse(StringReader reader)` | 读一个非引号字符串，按 `Formatting.byName` 查 | — | `Formatting`；查不到回退游标并抛 `INVALID_COLOR_EXCEPTION`（`argument.color.invalid`） |
| `getColor(CommandContext<?> ctx, String arg)` | 取值 | — | `Formatting` |
| `listSuggestions(…)` | 补全：`Formatting.getNames(true, false)`（只要颜色名，不含 `bold` 之类格式） | — | `CompletableFuture<Suggestions>` |
| `getExamples()` | 示例：`red`、`green` | — | `Collection<String>` |
| `INVALID_COLOR_EXCEPTION` | 公开异常常量 | — | `DynamicCommandExceptionType` |

### `EnchantmentArgument`

Reference: `net.ornithemc.osl.commands.api.command.argument.EnchantmentArgument`

**作用**：附魔参数（`item_enchantment`），例如 `unbreaking`、`silk_touch`。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `enchantment()` | 工厂 | — | `EnchantmentArgument` |
| `parse(StringReader reader)` | 读 ID 后查 `Enchantment.REGISTRY` | — | `Enchantment`；查不到回退游标并抛 `UNKNOWN_ENCHANTMENT_EXCEPTION`（`enchantment.unknown`） |
| `getEnchantment(CommandContext<?> ctx, String arg)` | 取值 | — | `Enchantment` |
| `listSuggestions(…)` | 补全：注册表里所有附魔 ID | — | `CompletableFuture<Suggestions>` |
| `getExamples()` | 示例：`unbreaking`、`silk_touch` | — | `Collection<String>` |
| `UNKNOWN_ENCHANTMENT_EXCEPTION` | 公开异常常量 | — | `DynamicCommandExceptionType` |

### `StatusEffectArgument`

Reference: `net.ornithemc.osl.commands.api.command.argument.StatusEffectArgument`

**作用**：状态效果参数（`mob_effect`），例如 `speed`、`minecraft:poison`。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `effect()` | 工厂 | — | `StatusEffectArgument` |
| `parse(StringReader reader)` | 读 ID 后查 `StatusEffect.REGISTRY` | — | `StatusEffect`；查不到回退游标并抛 `UNKNOWN_STATUS_EFFECT_EXCEPTION`（`effect.effectNotFound`） |
| `getEffect(CommandContext<?> ctx, String arg)` | 取值 | — | `StatusEffect` |
| `listSuggestions(…)` | 补全：注册表里所有效果 ID | — | `CompletableFuture<Suggestions>` |
| `getExamples()` | 示例：`spooky`、`effect` | — | `Collection<String>` |
| `UNKNOWN_STATUS_EFFECT_EXCEPTION` | 公开异常常量 | — | `DynamicCommandExceptionType` |

### `SlotArgument`

Reference: `net.ornithemc.osl.commands.api.command.argument.SlotArgument`

**作用**：物品槽位参数（`item_slot`）：只能用**具名**槽位，解析成原版槽位号。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `slot()` | 工厂 | — | `SlotArgument` |
| `parse(StringReader reader)` | 读一个非引号字符串查表 | 只接受下表里的名字 | `Integer`；不认识时抛 `slot.unknown`（源码的 `getExamples()` 里有 `"12"`，但表里没有纯数字键，写数字会报错） |
| `getSlot(CommandContext<CommandSourceStack> context, String arg)` | 取值 | — | `int` |
| `listSuggestions(…)` | 补全：全部具名槽位 | — | `CompletableFuture<Suggestions>` |
| `getExamples()` | 示例 | — | `Collection<String>` |

槽位名与编号（源码里的完整映射）：

| 名字 | 编号 | 名字 | 编号 |
|---|---|---|---|
| `container.0`…`container.53` | 0…53 | `weapon` / `weapon.mainhand` | 98 |
| `hotbar.0`…`hotbar.8` | 0…8 | `weapon.offhand` | 99 |
| `inventory.0`…`inventory.26` | 9…35 | `armor.feet` / `armor.legs` / `armor.chest` / `armor.head` | 100 / 101 / 102 / 103 |
| `enderchest.0`…`enderchest.26` | 200…226 | `horse.saddle` / `horse.armor` / `horse.chest` | 400 / 401 / 499 |
| `villager.0`…`villager.7` | 300…307 | — | — |
| `horse.0`…`horse.14` | 500…514 | — | — |

## 参数类型：数值区间

### `RangeArgument`

Reference: `net.ornithemc.osl.commands.api.command.argument.RangeArgument`

**作用**：数值区间参数（`int_range` / `float_range`）：`5`、`1..5`、`..10`、`3..` 四种写法。既是接口又是工厂，两个实现是嵌套的 `Ints` / `Floats`。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `intRange()`（静态） | 工厂：整数区间 | — | `RangeArgument.Ints` |
| `floatRange()`（静态） | 工厂：浮点区间 | — | `RangeArgument.Floats` |
| `getIntRange(CommandContext<CommandSourceStack> ctx, String arg)`（静态） | 取整数区间 | — | `NumberRange.Ints` |
| `getFloatRange(CommandContext<CommandSourceStack> ctx, String arg)`（静态） | 取浮点区间 | — | `NumberRange.Floats` |
| `RangeArgument.Ints.parse(StringReader reader)` | 转调 `NumberRange.Ints.fromString` | — | `NumberRange.Ints`；语法错误抛 `argument.range.empty` / 内置的 `readerInvalidInt` |
| `RangeArgument.Ints.getExamples()` | 示例：`0..5`、`0`、`-5`、`-100..`、`..100` | — | `Collection<String>` |
| `RangeArgument.Floats.parse(StringReader reader)` | 转调 `NumberRange.Floats.fromString` | — | `NumberRange.Floats` |
| `RangeArgument.Floats.getExamples()` | 示例：`0..5.2`、`0`、`-5.4`、`-100.76..`、`..100` | — | `Collection<String>` |
| `RangeArgument.Serializer`（抽象类）+ `Ints.Serializer` / `Floats.Serializer` | 网络序列化：这两个类型没有额外状态，序列化写空、反序列化直接 new | 见"参数序列化" | `ArgumentSerializer` |

### `NumberRange`

Reference: `net.ornithemc.osl.commands.api.command.argument.NumberRange`

**作用**：数值区间模型（抽象类，`Floats` / `Ints` 两个实现），支持区间匹配与"按平方值匹配"（比较距离时省一次开方）。`RangeArgument` 与 `EntitySelector` 的 `distance` / `level` 都用它。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `getMin()` / `getMax()` | 两端（可能为 `null`，表示无界） | — | `T`（`Float` / `Integer`） |
| `isAny()` | 两端都为空 = 不作限制 | — | `boolean` |
| `toJson()` | 序列化成 JSON（无限制 → `JsonNull`；上下界相同 → 单值；否则 `{min,max}`） | — | `JsonElement` |
| `NumberRange.Floats.ANY` / `NumberRange.Ints.ANY` | 无限制常量 | — | 对应实例 |
| `NumberRange.Floats.ofAtLeast(float min)` / `NumberRange.Ints.of(int v)` / `NumberRange.Ints.ofAtLeast(int min)` | 便捷构造 | — | 对应实例 |
| `NumberRange.Floats.matches(float value)` / `matchesSquare(double value)` | 判定 / 按平方值判定（用于距离比较） | — | `boolean` |
| `NumberRange.Ints.matches(int value)` / `matchesSquare(long value)` | 同上 | — | `boolean` |
| `fromString(StringReader reader)` / `fromString(StringReader reader, Function<T, T> processor)` | 从命令文本解析区间；`processor` 可先对数值做变换（如把角度规范化） | reader 非空，否则抛 `EMPTY_EXCEPTION`（`argument.range.empty`） | 对应实例；`min > max` 抛 `DECIMAL_NOT_ALLOWED_EXCEPTION`（`argument.range.swapped`） |
| `fromJson(JsonElement json)` | 从 JSON 解析 | — | 对应实例；`json` 为空时返回 `ANY` |
| `NumberRange.Factory<T, R>` / `NumberRange.FactoryFromReader<T, R>`（函数式接口） | 自定义子类时用 | — | 实例 |
| `EMPTY_EXCEPTION` / `DECIMAL_NOT_ALLOWED_EXCEPTION` | 公开异常常量 | — | `SimpleCommandExceptionType` |

### `WrappedNumberRange`

Reference: `net.ornithemc.osl.commands.api.command.argument.WrappedNumberRange`

**作用**：可以"环绕"（wrap）的浮点区间，用于 `x_rotation` / `y_rotation` 这种 `-180..180` 会绕圈的取值。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `new WrappedNumberRange(Float min, Float max)` | 构造（两端可空） | — | 实例 |
| `getMin()` / `getMax()` | 两端 | — | `Float`（可能 `null`） |
| `fromString(StringReader reader, boolean doublePrecision, Function<Float, Float> processor)`（静态） | 解析区间；`doublePrecision` 决定是否允许小数点；`processor` 通常传 `MathHelper::wrapDegrees` | reader 非空 | `WrappedNumberRange`；空输入抛 `NumberRange.EMPTY_EXCEPTION`；整数模式出现 `.` 抛 `ERROR_INTS_ONLY`（`argument.range.ints`）；数值非法抛内置的 `readerInvalidInt` / `readerInvalidDouble` |
| `ANY` | 无限制常量 | — | `WrappedNumberRange` |
| `ERROR_INTS_ONLY` | 公开异常常量 | — | `SimpleCommandExceptionType` |

注意：它**不是** `NumberRange` 的子类，只是一个轻量的"可空上下界 + 环绕变换"容器；环形匹配的判断在 `EntitySelectorParser` 里做（`min > max` 时按"跨 0 点"处理）。

## 参数序列化（网络同步）

服务端会把自己的命令树同步给客户端，客户端才能给服务端命令做补全。树里每个参数节点都要能"序列化类型 + 反序列化类型"，这套机制就是本节。

### `ArgumentSerializer`

Reference: `net.ornithemc.osl.commands.api.command.argument.serdes.ArgumentSerializer`

**作用**：参数类型的序列化器接口。自定义参数类型想在客户端补全里出现，就必须为它提供一个实现并注册进 `ArgumentTypes`。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `serialize(T arg, PacketBuffer buffer)` | 把参数类型的状态写进包 | 该类型已用 `ArgumentTypes.register` 注册 | 无（void） |
| `deserialize(PacketBuffer buffer)` | 从包里还原参数类型 | 客户端与服务端的注册必须完全一致（同样的 ID、同样的字段顺序） | `T` |

### `ArgumentTypes`

Reference: `net.ornithemc.osl.commands.api.command.argument.serdes.ArgumentTypes`

**作用**：参数类型 ↔ 序列化器的双向注册表，同时提供包的读写入口。内置的 31 个原版风格参数（`minecraft:entity`、`minecraft:block_pos` …）和 5 个 Brigadier 参数（`brigadier:integer` …）都由它登记。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `register(NamespacedIdentifier identifier, Class<T> type, ArgumentSerializer<T> serializer)` | 注册一个参数类型 | `type` 与 `identifier` 都不能重复，否则抛 `IllegalArgumentException` | 无（void） |
| `init()` | 注册全部内置类型（内部先调 `BrigadierArgumentSerializers.init()`） | 见下方警告 | 无（void） |
| `serialize(PacketBuffer buffer, T argument)` | 写"类型 ID + 类型状态" | 类型未注册时打一条 error 日志并写入空 ID | 无（void） |
| `deserialize(PacketBuffer buffer)` | 读回参数类型 | ID 不认识时打 error 日志 | `ArgumentType<?>`；失败时返回 **`null`**（随后该节点整棵被丢弃） |
| `ArgumentTypes.Entry<T>`（嵌套类） | 一条注册记录：`public final Class<T> type` / `NamespacedIdentifier identifier` / `ArgumentSerializer<T> serializer` | — | 实例 |

内置注册名（命名空间默认 `minecraft`）：`entity`、`game_profile`、`block_pos`、`column_pos`、`vec3`、`vec2`、`block_state`、`block_predicate`、`legacy_block_state`、`legacy_block_predicate`、`item_stack`、`item_predicate`、`color`、`component`、`message`、`nbt`、`objective`、`objective_criteria`、`operation`、`rotation`、`scoreboard_slot`、`score_holder`、`swizzle`、`team`、`item_slot`、`resource_location`、`mob_effect`、`entity_anchor`、`int_range`、`float_range`、`item_enchantment`。

> **重要提醒**：与 `EntitySelectorOptions.init()` 一样，本子工程里搜不到对 `ArgumentTypes.init()` 的调用（入口点只挂了 `BrigadierCommandsImpl::init`）。这意味着 1.12.2 上内置参数类型的序列化表默认是空的：服务端同步命令树时每个参数节点都会命中"未注册"分支（写空 ID），客户端读到后 `deserialize` 返回 `null`、该节点被丢弃。要让同步生效，请在自己的 mod 初始化里先调用一次 `ArgumentTypes.init()`。

### `BrigadierArgumentSerializers`

Reference: `net.ornithemc.osl.commands.api.command.argument.serdes.BrigadierArgumentSerializers`

**作用**：把 Brigadier 自带的 5 个参数类型（`bool`、`float`、`double`、`integer`、`string`）注册进 `ArgumentTypes`，命名空间为 `brigadier`；另外提供 "min/max 标志位" 的打包工具。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `init()` | 注册上面 5 个类型（被 `ArgumentTypes.init()` 调用） | 重复调用会因重复注册抛 `IllegalArgumentException` | 无（void） |
| `minMaxFlags(boolean min, boolean max)` | 把"有下界/有上界"打包成 1 字节 | — | `byte`（`1`=min，`2`=max） |
| `hasMin(byte flags)` / `hasMax(byte flags)` | 读标志位 | — | `boolean` |

### `EmptyArgumentSerializer`

Reference: `net.ornithemc.osl.commands.api.command.argument.serdes.EmptyArgumentSerializer`

**作用**：适用于"没有状态"的参数类型：序列化不写任何东西，反序列化直接调用你给的构造方法。绝大多数内置参数类型（方块、物品、坐标、玩家…）都用它。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `new EmptyArgumentSerializer(Supplier<T> constructor)` | 构造 | `constructor` 非 `null`，且必须返回**默认配置**的实例 | 实例 |
| `serialize(T arg, PacketBuffer buffer)` | 什么都不写 | — | 无（void） |
| `deserialize(PacketBuffer buffer)` | 调 `constructor.get()` | — | `T` |

### `FloatArgumentSerializer`

Reference: `net.ornithemc.osl.commands.api.command.argument.serdes.FloatArgumentSerializer`

**作用**：`FloatArgumentType` 的序列化器：写 1 字节 min/max 标志位 + 存在的边界值。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `serialize(FloatArgumentType arg, PacketBuffer buffer)` | 写标志与 `getMinimum()` / `getMaximum()`（等于 `±Float.MAX_VALUE` 视为"没有该界"） | — | 无（void） |
| `deserialize(PacketBuffer buffer)` | 按标志读回边界并 `FloatArgumentType.floatArg(min, max)` | — | `FloatArgumentType` |

### `DoubleArgumentSerializer`

Reference: `net.ornithemc.osl.commands.api.command.argument.serdes.DoubleArgumentSerializer`

**作用**：`DoubleArgumentType` 的序列化器，逻辑与浮点版相同（边界判定用 `±Double.MAX_VALUE`）。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `serialize(DoubleArgumentType arg, PacketBuffer buffer)` | 写标志与边界 | — | 无（void） |
| `deserialize(PacketBuffer buffer)` | 读回并 `DoubleArgumentType.doubleArg(min, max)` | — | `DoubleArgumentType` |

### `IntegerArgumentSerializer`

Reference: `net.ornithemc.osl.commands.api.command.argument.serdes.IntegerArgumentSerializer`

**作用**：`IntegerArgumentType` 的序列化器（边界判定用 `Integer.MIN_VALUE` / `MAX_VALUE`）。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `serialize(IntegerArgumentType arg, PacketBuffer buffer)` | 写标志与边界 | — | 无（void） |
| `deserialize(PacketBuffer buffer)` | 读回并 `IntegerArgumentType.integer(min, max)` | — | `IntegerArgumentType` |

### `StringArgumentSerializer`

Reference: `net.ornithemc.osl.commands.api.command.argument.serdes.StringArgumentSerializer`

**作用**：`StringArgumentType` 的序列化器：只写一个枚举值（`SINGLE_WORD` / `QUOTABLE_PHRASE` / `GREEDY_PHRASE`）。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `serialize(StringArgumentType arg, PacketBuffer buffer)` | 写 `arg.getType()` | — | 无（void） |
| `deserialize(PacketBuffer buffer)` | 按枚举还原成 `word()` / `string()` / `greedyString()` | 枚举值不认识时退化成 `greedyString()` | `StringArgumentType` |

## 建议补全

### `SuggestionProviders`

Reference: `net.ornithemc.osl.commands.api.command.SuggestionProviders`

**作用**：**具名**补全器注册表。Brigadier 的 `SuggestionProvider` 是匿名对象，没法过网络；这里的做法是给每个补全器一个 `NamespacedIdentifier`，同步时只发 ID，客户端查表拿到同一个实现。1.12.2 上"由服务端算补全"就是靠 `ASK_SERVER` 实现的。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `register(NamespacedIdentifier identifier, SuggestionProvider<SharedSuggestionProvider> provider)` | 注册一个具名补全器 | ID 不能重复，否则抛 `IllegalArgumentException` | 包装后的 `SuggestionProvider<S>`（`IdentifiableSuggestionProvider`） |
| `get(NamespacedIdentifier identifier)` | 按 ID 取补全器 | — | `SuggestionProvider<SharedSuggestionProvider>`；查不到时**回退为 `ASK_SERVER`** |
| `getIdentifier(SuggestionProvider<SharedSuggestionProvider> provider)` | 取补全器的 ID | — | `NamespacedIdentifier`；未包装过的补全器一律返回 `minecraft:ask_server` |
| `getIdentifiable(SuggestionProvider<SharedSuggestionProvider> provider)` | 保证返回一个可同步的补全器 | — | 已包装的原样返回，否则返回 `ASK_SERVER` |
| `ASK_SERVER` | 预置补全器：转调 `ctx.getSource().requestSuggestions(ctx, builder)`（客户端会向服务端发请求） | 命令源必须实现 `SharedSuggestionProvider` | `SuggestionProvider<SharedSuggestionProvider>` |
| `SuggestionProviders.IdentifiableSuggestionProvider`（嵌套类） | 带 ID 的包装器 | 构造 `IdentifiableSuggestionProvider(NamespacedIdentifier identifier, SuggestionProvider<SharedSuggestionProvider> provider)` | 实例；`getSuggestions(ctx, builder)` 转发给内部实现 |

用法：`ServerCommands.argument("目标", EntityArgument.players()).suggests(SuggestionProviders.ASK_SERVER)`。若你要自定义补全且希望它在客户端也生效，必须通过 `register` 拿到包装后的实例再用。

## 辅助工具

### `Commands`

Reference: `net.ornithemc.osl.commands.api.Commands`

**作用**：两个小工具：把"解析器"变成 Brigadier 的字符串校验 `Predicate`（补全时用来剔除非法候选），以及"只吃 reader 不回值"的解析器接口。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `validator(Commands.Parser parser)` | 造一个 `Predicate<String>`：能完整解析就 `true`，抛 `CommandSyntaxException` 就 `false` | `parser` 非 `null` | `Predicate<String>`；典型用法 `Commands.validator(this::parse)` |
| `Commands.Parser`（函数式接口） | 解析一段文本但不返回结果 | 实现 `parse(StringReader reader)`，可能抛 `CommandSyntaxException` | 无（void） |

### `SnbtParser`

Reference: `net.ornithemc.osl.commands.api.command.argument.SnbtParser`

**作用**：SNBT（`{a:1b,b:[1,2],c:"x"}`）解析器，`NbtCompoundArgument` 与实体选择器的 `nbt` 选项都用它。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `new SnbtParser(StringReader reader)` | 构造 | `reader` 非 `null` | 实例 |
| `parse(String rawNbt)`（静态） | 一次性解析整段 SNBT，且要求**没有多余字符** | `rawNbt` 是完整复合标签 | `NbtCompound`；尾部还有内容抛 `TRAILING_DATA_EXCEPTION`（`argument.nbt.trailing`） |
| `readCompound()` | 从当前位置读一个 `{…}` | reader 停在 `{` 上 | `NbtCompound`；键/值缺失抛 `KEY_EXPECTED_EXCEPTION` / `VALUE_EXPECTED_EXCEPTION` |
| `readKey()` / `readElement()` / `readValue()` / `readListOrArray()`（`protected`） | 子类可复用的分段读取 | — | `String` / `NbtElement` |
| `TRAILING_DATA_EXCEPTION` / `KEY_EXPECTED_EXCEPTION` / `VALUE_EXPECTED_EXCEPTION` / `MIXED_LIST_TYPE_EXCEPTION` / `MIXED_ARRAY_TYPE_EXCEPTION` / `INVALID_ARRAY_EXCEPTION` | 公开异常常量 | — | 各自的 Brigadier 异常类型 |

支持的写法：双引号字符串或不带引号的裸串、整数 `1`、带后缀的 `1b`/`1s`/`1l`/`1f`/`1d`、浮点 `1.5` / `1.5e3`、`true`/`false`（存成 `NbtByte`）、`[1,2]` 列表（元素类型必须一致，否则 `MIXED_LIST_TYPE_EXCEPTION`）、`[B;…]`/`[I;…]`/`[L;…]` 数组（`L` 型数组从 1.12 起才注册，1.12.2 可用）。

键值分隔符只接受 `:`（源码是 `expect(':')`），所以 `NbtCompoundArgument.getExamples()` 里的 `{foo=bar}` 实际会解析失败，写 `{foo:bar}` 才对。

### `NbtUtils`

Reference: `net.ornithemc.osl.commands.api.command.argument.NbtUtils`

**作用**：NBT 的"部分匹配"比较，方块谓词、物品谓词、实体选择器的 `nbt` 选项都靠它。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `matches(NbtElement expected, NbtElement actual, boolean partialListMatches)` | 判断 `actual` 是否包含 `expected`：复合标签只比较 `expected` 里出现的键；列表在 `partialListMatches` 为真时按"每个期望元素都能在实参列表里找到"匹配（不要求顺序、长度可多），为假时退化成 `equals`；类型必须一致；任一侧为 `null` 直接算匹配 | 两个参数都可为 `null` | `boolean` |

## 注意事项汇总

写代码前值得先扫一眼这几条，它们都是"读源码才能发现"的行为：

1. `ArgumentTypes.init()` 与 `EntitySelectorOptions.init()` 在本子工程里**没有**被框架调用，需要你自己在 mod 初始化阶段调一次（两者都幂等）。否则参数类型同步与 `@e[选项]` 都不工作。
2. `#标签` 语法在 1.12.2 上不可用（`allowTag` 被硬编码为 `false`）。
3. `CommandSourceStack.requestSuggestions` 返回 `null`，服务端命令源上不要指望 `ASK_SERVER` 能拿到补全 future。
4. `TextArgument` 不推进 `StringReader` 游标，只能当最后一个参数用。
5. `Vec2f.equals(Vec2f)` 是重载而非覆写；`SlotArgument.getExamples()` 里的 `"12"` 实际解析不了。
6. 原版命令（`/give` 等）不在 Brigadier 树里；给自定义命令起同名不会覆盖原版，执行顺序是"先 Brigadier，未命中再原版"。
7. 客户端命令每次进入世界都会重新触发 `REGISTER_COMMANDS`，监听器里不要做"只能做一次"的事。




