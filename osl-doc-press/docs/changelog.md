---
title: 变更历史
---

# 变更历史

记录 OSL 在 **Minecraft 1.12.2** 上的 API 与行为变化。表里的版本号是 OSL 的发布版本（也就是 `ploceus.dependOsl(...)` 的参数），模块版本则是各模块自己的 `library_version`。

## 0.24.0 → 0.26.0（当前）

这一轮发布包含 0.25.0 / 0.25.1 / 0.26.0 三次版本号提交。22 个模块里，**5 个在 1.12.2 上有实质变化**，其余只是版本号与依赖元数据同步。

| 模块 | 版本 | 1.12.2 影响 |
|---|---|---|
| resource-loader | 0.10.0 → 0.12.0 | ★ 新增服务端数据包（data pack）与 5 个 API 类型 |
| commands | 0.1.0 → 0.2.0 | 客户端 HelpCommand 移出 API |
| lifecycle-events | 0.6.1 → 0.7.0 | `LifecycleEvents` 整体废弃；子工程合并 |
| networking | 0.12.0 → 0.12.1 | `networking-impl` 并入本模块（API 不变） |
| registries | 0.4.0 → 0.4.1 | 实现重构（API 不变） |

### resource-loader 0.10.0 → 0.12.0

**最大的一项：1.3–1.12 现在支持服务端数据包（data pack）。** 资源包里的 `data/<namespace>/` 目录会被当作数据包读取，服务端会据此重载配方、战利品表、函数、进度与结构。

新增 API：

| 类型 | 说明 |
|---|---|
| `DataReloaders`（`api.server.resource.reload`） | 服务端重载器 id 常量：`CRAFTING_MANAGER`、`LOOT_TABLE_MANAGER`、`FUNCTION_MANAGER`、`ADVANCEMENT_MANAGER`、`STRUCTURE_MANAGER`，以及排序锚点 `BEFORE_VANILLA` / `AFTER_VANILLA` |
| `SimpleJsonResourceReloader`（`api.resource.reload`） | 把某个目录下所有 `.json` 解析成 `Map<NamespacedIdentifier, JsonObject>` 的抽象重载器，直接继承即可 |
| `PackSourcePosition`（`api.resource.repository`） | 枚举 `FIRST` / `LAST`，用于给资源包来源指定默认排序 |
| `MinecraftServerExtension`（`api.server`） | `getLootTables()`、`reloadResources()`，服务端侧重载入口 |
| `WorldDataExtension`（`api.world`） | `getEnabledDataPacks()` / `getDisabledDataPacks()`，读取存档里数据包的启用状态 |

新增方法：`ResourcePackRepository.addSource(Source source, PackSourcePosition position)`。原来的 `addSource(Source)` 保留，语义等价于 `PackSourcePosition.LAST`；`FIRST` 的来源会排在原版来源之前，适合"提供类原版内容、希望被其他 mod 覆盖"的场景。

同时修复（均落在 1.12.2 可用的代码里）：

- 重载纹理包时的 NPE（b1.8-pre1 以下同样受益）
- `13w48a` 以前语言列表不随重载刷新
- 无法禁用 mod 提供的默认数据包
- 崩溃报告补充数据包信息

> 迁移：`addSource(Source)` 的调用点不用改；想让自己的包优先被其他 mod 覆盖，改用两参重载并传 `PackSourcePosition.FIRST`。

### commands 0.1.0 → 0.2.0

- `net.ornithemc.osl.commands.api.client.command.HelpCommand` **已从 API 移除**，实现移到 `impl.client.command`，客户端 help 命令与服务端分开。
- 其余命令 API（`Commands`、`ClientCommands`、`ClientCommandSource`、47 个参数类型、参数序列化等）无变化。

> 迁移：不要直接引用 `HelpCommand`。客户端命令仍通过 `ClientCommandEvents` 注册，`ClientCommands` 负责分发。

### lifecycle-events 0.6.1 → 0.7.0

- `net.ornithemc.osl.lifecycle.api.LifecycleEvents` 整个类标记 **`@Deprecated`**，javadoc 指向 `net.ornithemc.osl.registries.api.RegistryEvents.BOOTSTRAP_REGISTRIES`。
- `BOOTSTRAP_START` / `BOOTSTRAP_END` 字段仍在、行为不变，但建议改用注册表侧的引导事件。
- 子工程合并：原来的 `lifecycle-events-mc13w36a-mc19w07a`、`-mc19w08a-mc1.14.4`、`-mc12w21a-mc1.6.4` 等合并为 `lifecycle-events-mc12w18a-mc1.14.4`。
- `MinecraftClientEvents`、`ClientWorldEvents`、`MinecraftServerEvents`、`ServerWorldEvents`、`MinecraftInstance` / `MinecraftServerInstance` 无变化。

> 迁移：1.12.2 上构件坐标后缀变为 `+mc12w18a-mc1.14.4`；用了 `ploceus.dependOsl(...)` 的话不需要改坐标。

### networking 0.12.0 → 0.12.1

- `networking-impl` 模块**并入 `networking`**：不再有独立的 `osl-networking-impl` 构件，`registries`、`items`、`entities`、`blocks`、`blockentities`、`biomes`、`commands`、`blockstates`、`datagen` 也都去掉了对它的依赖。
- 实现改用 Conditional Mixin 组织，合并了原先多个子工程。
- **API 无变化**：`ChannelIdentifiers`、`PacketBuffer`、`ClientPlayNetworking`、`ServerPlayNetworking` 等签名与行为不变。

### registries 0.4.0 → 0.4.1

- 注册表映射的加载/保存从 mixin 里移出到独立实现类（"move registry mapping loading/saving out of mixins"）。
- **API 无变化**：`Registry`、`WritableRegistry`、`ResourceKey`、`RegistryEvents`、`registry.sync.*` 均未改。

### 只有版本号变化的模块

以下模块的 1.12.2 源码逐字节未变，只是 `library_version` / `fabric.mod.json` 里的依赖版本同步：

| 模块 | 版本 | 说明 |
|---|---|---|
| blockstates | 0.3.0 → 0.4.0 | 修复只影响 b1.6 及以前的服务端 |
| biomes | 0.1.1 → 0.1.2 | 只合并了 18w32a–1.14.4 的子工程 |
| blocks | 0.3.1 → 0.3.2 | — |
| blockentities | 0.1.1 → 0.1.2 | — |
| entities | 0.1.3 → 0.1.4 | — |
| items | 0.3.2 → 0.3.3 | — |
| core / config / entrypoints / executors / keybinds / localization / branding / text-components / crash-reports / *-rendering | 不变 | — |

### 全量版本对照

| 模块 | 0.24.0 | 0.26.0 | 1.12.2 代码是否有改动 |
|---|---|---|---|
| core | 0.13.0 | 0.13.0 | 否 |
| biomes | 0.1.1 | 0.1.2 | 否 |
| blocks | 0.3.1 | 0.3.2 | 否 |
| blockstates | 0.3.0 | 0.4.0 | 否 |
| blockentities | 0.1.1 | 0.1.2 | 否 |
| blockentities-rendering | 0.1.0 | 0.1.0 | 否 |
| branding | 0.4.4 | 0.4.4 | 否 |
| commands | 0.1.0 | 0.2.0 | 是（移除 HelpCommand） |
| config | 0.6.3 | 0.6.3 | 否 |
| crash-reports | 0.1.0 | 0.1.0 | 否 |
| entities | 0.1.3 | 0.1.4 | 否 |
| entities-rendering | 0.1.0 | 0.1.0 | 否 |
| entrypoints | 0.6.1 | 0.6.1 | 否 |
| executors | 0.1.1 | 0.1.1 | 否 |
| items | 0.3.2 | 0.3.3 | 否 |
| keybinds | 0.3.0 | 0.3.0 | 否 |
| lifecycle-events | 0.6.1 | 0.7.0 | 是（废弃 LifecycleEvents） |
| localization | 0.2.1 | 0.2.1 | 否 |
| networking | 0.12.0 | 0.12.1 | 仅实现（合并 networking-impl） |
| registries | 0.4.0 | 0.4.1 | 仅实现 |
| resource-loader | 0.10.0 | 0.12.0 | 是（data pack + 5 个新 API） |
| text-components | 0.2.0 | 0.2.0 | 否 |

## 升级到 0.26.0 的检查清单

1. `ploceus.dependOsl('0.24.0')` 改成 `ploceus.dependOsl('0.26.0')`。
2. 搜索 `commands.api.client.command.HelpCommand`，改用 `ClientCommands` / `ClientCommandEvents`。
3. 搜索 `LifecycleEvents`，改用 `RegistryEvents.BOOTSTRAP_REGISTRIES`（仅注册表引导场景）。
4. 如果手动写过 `osl-networking-impl` 依赖，删掉它（已并入 `networking`）。
5. 需要服务端数据包时，改用 `resource-loader` 的 `DataReloaders` + `SimpleJsonResourceReloader`。

## 与 1.12.2 无关的变更

同一批提交里还有大量只影响其他 MC 版本的工作，1.12.2 不受影响：

- 各模块的子工程合并（registries 18w43a–1.14.4、biomes 18w32a–1.14.4、lifecycle-events 3 段），并用 Conditional Mixin 替代部分 mixin 配置
- 更早版本（b1.x / 1.3–1.6）的资源包与数据包支持
- datagen 0.1.1：仍然只有 1.13+ 的子工程，1.12.2 无法使用

## 参考

- 上游仓库：`acf984c3`（0.24.0）→ `9f486c8d`（0.26.0），共 47 次提交
- 关键提交：`7295100e`（data packs in 1.3-1.12）、`6dd7f2e3`（two-phase ordering of pack sources）、`cbf94145`（client help command）、`a59151b8`（deprecate bootstrap events）、`165eb2a0`（merge networking-impl）、`93e9d0c4`（registry mapping loading/saving）
