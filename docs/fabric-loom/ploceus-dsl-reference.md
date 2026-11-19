# Ploceus `ploceus { }` 选项速查

> 依据本地 checkout：`ploceus` @ `972a589`（版本 `1.19`）。插件 id `ploceus`，扩展名也叫 `ploceus`
> （实现 `PloceusGradleExtension`，公开接口 `PloceusGradleExtensionApi`）。
> 官方文档：<https://wiki.ornithemc.net/wiki/Ploceus>
>
> **定位**：ploceus 是 Loom 的补充扩展，不是替代品。它没有 `runs { }` / `mods { }` / `decompilers { }` 这类子 DSL——
> 那些依旧写在 `loom { }` 里。`ploceus { }` 提供的是 Ornithe 生态专用的映射来源、OSL/补丁数据依赖和几个开关。
>
> 由于 API 全是**方法**（返回 `Dependency`/`String` 或无返回值），所以常见写法不是在 `ploceus { }` 里配属性，
> 而是在 `dependencies { }` 里把它们当坐标用，例如 `mappings ploceus.featherMappings("3")`。
> 另外 ploceus 的 **major.minor 版本必须和 Loom 的 major.minor 一致**（Loom `1.19.x` ↔ ploceus `1.19.x`）。

---

## 1. 映射（返回 `Dependency`，写在 `dependencies { }` 里）

| 选项 | 说明 |
|---|---|
| `featherMappings(build)` | Feather 映射（推荐）。build 号按 intermediary 代数选坐标：gen1 → `net.ornithemc:feather:<mc><-side>+build.<n>:v2`；gen2+ → `net.ornithemc:feather-gen<N>:<mc>+build.<n>:v2` |
| `featherMappingsSpec(build)` | 同上但返回 `FileSpec`，用于在 `loom { }` 的 `layered { }` 里当一层 |
| `mcpMappings(channel, build)` | MCP 映射，MC 版本取当前 `minecraft` 依赖；`channel` 如 `stable`、`snapshot` |
| `mcpMappings(channel, mc, build)` | 显式指定 MC 版本 |
| `mcpForgeMappings(version)` | Forge 的 MCP 映射（`net.minecraftforge.mcp:forge:<mc>-<version>:src@zip`），MC 版本取当前依赖 |
| `mcpForgeMappings(mc, version)` | 显式指定 MC 版本 |
| `mappings(file)` | 任意本地/远程映射文件或目录 |
| `layeredMappings { }` | 包装 `loom.layered { }`，可自由用 `addLayer` / `officialMojangMappings` / `parchment` / `mappings` 等 |

**关键行为**：上面这些 `Dependency` 最终都走 `layeredMappings`，即在用户定义层之后**自动追加两层**：

1. `FillingMappingSpec` —— 用 MC jar + runtime 库自动补齐缺失映射（库方法覆盖等）
2. `NestsMappingSpec` —— 应用 `nests` 依赖里的内部类（nest）信息

因此有硬性顺序：**`nests` 必须在 `mappings` 之前声明**，否则抛
`IllegalStateException("Nests dependencies must be declared before the mappings dependency!")`。

## 2. 补丁数据依赖（返回 `Dependency`，各有约定配置名）

| 选项 | 加到哪个配置 | 数据内容 |
|---|---|---|
| `nests(build)` / `nests(build, side)` / `nests(build, GameSide)` | `nests` | 内部类（nest）补丁，`net.ornithemc:nests:<mc><suffix>+build.<n>` |
| `raven(build)` / `raven(build, side)` / `raven(build, GameSide)` | `exceptions` | throws 子句补丁，`net.ornithemc:raven:...` |
| `sparrow(build)` / `sparrow(build, side)` / `sparrow(build, GameSide)` | `signatures` | 泛型签名补丁，`net.ornithemc:sparrow:...` |

`side` 接受字符串 `"client"` / `"server"` / `"merged"` / `"*"`，或 `GameSide` 枚举（`CLIENT` / `SERVER` / `MERGED`）。
不传 side 时：generation 1 用版本自身的 side，generation 2+ 一律 `MERGED`。
ploceus 已注册 `exceptions` / `clientExceptions` / `serverExceptions`、`signatures` / `clientSignatures` / `serverSignatures`、
`nests` / `clientNests` / `serverNests` 这一整套配置，所以直接在对应配置里声明即可。

## 3. OSL（Ornithe Standard Libraries）

| 选项 | 说明 |
|---|---|
| `dependOsl(version)` / `dependOsl(version, side)` / `dependOsl(version, GameSide)` | 加全部模块到 `modImplementation`（当前 MC 没有的模块自动跳过） |
| `dependOsl(configuration, version, side)` | 加全部模块到指定配置 |
| `dependOslModule(version, module)` / `(version, side, module)` / `(version, GameSide, module)` | 只加单个模块（`dependOslModule(configuration, version, side, module)` 可指定配置） |
| `oslModule(module, version)` / `(module, version, side)` / `(module, version, GameSide)` | 只返回坐标字符串 `net.ornithemc.osl[-gen<N>]:<module>:<version>`，不加依赖 |

`dependOsl*` 的 `version` 是 **OSL 版本**（从 `meta.ornithemc.net` 的 `/v3/versions/gen<N>/osl/<version>` 解析），
`oslModule(...)` 的 `version` 是 **module base version**，两者语义不同，别混用。找不到模块会抛 `RuntimeException`。

## 4. 开关类

| 选项 | 默认 | 说明 |
|---|---|---|
| `disableLibraryUpgrades()` | 开启 | 关掉 LibraryUpgrader：它按 Ornithe meta（`/v3/versions/gen<N>/libraries/<mc>`）把老版本里过旧/坏掉的库（LWJGL 等）升级成可用版本 |
| `disableLvtPatch()` | 开启 | 关掉 LVT（LocalVariableTable）修补。只在 `0.32.0 < mc < 1.8.2-rc.5` 区间真正生效 |
| `setIntermediaryGeneration(int)` | `2` | 选 Calamus intermediary 代数：`1` = `calamus-intermediary`（分 client/server），`2+` = `calamus-intermediary-gen<N>`（merged）。切换时同时替换版本清单与 intermediary provider |
| `clientOnlyMappings()` | — | 已弃用，等价于把 `side` 设为 `CLIENT`；配合 `loom { clientOnlyMinecraftJar() }` |
| `serverOnlyMappings()` | — | 已弃用，等价于把 `side` 设为 `SERVER`；配合 `loom { serverOnlyMinecraftJar() }` |

> 1.3 之前的版本没有合并的 client/server 开发环境，必须按官方文档同时配置
> `loom { clientOnlyMinecraftJar() }` + `ploceus { clientOnlyMappings() }`（或 server 的那一对）。

## 5. 实现层可访问（不在 `PloceusGradleExtensionApi` 里）

| 成员 | 说明 |
|---|---|
| `side` (`Property<GameSide>`) | 当前映射 side，默认按版本元数据推断（只有 client → `CLIENT`，只有 server → `SERVER`，否则 `MERGED`） |
| `intermediaryGeneration` (`Property<Integer>`) | 与 `setIntermediaryGeneration` 共享状态 |
| `exceptionsProvider` / `signaturesProvider` / `nestsProvider` | 内部 provider，convention 自动解析，不建议手动 set |
| `getLibraryUpgrades()` / `getLibraries()` / `getMappingFiller(ctx)` | 内部访问器 |

`ploceus.intermediaryGeneration = 2` 会走 `setIntermediaryGeneration(int)`（有对应 setter）；
`ploceus.side.set(GameSide.CLIENT)` 直接操作 Property。

## 6. ploceus 自动做的事（不是选项，但会影响构建）

- 注册仓库：Ornithe、Quilt、Legacy Fabric（仅 `org.lwjgl.lwjgl` 组）、Forge（pom + artifact 元数据）
- 注册版本清单 `ornithe-gen<N>`：`https://ornithemc.net/mc-versions/gen<N>/version_manifest.json`，优先级 `-10`（高于 Mojang 清单）
- 把 loom 的 intermediate mappings provider 换成 Calamus（gen1 分侧 / gen2+ 合并）
- 注册 jar 处理器：LVT 修补、异常表修补（exceptor）、签名修补（signature-changer）、preen、nester
- 注册 library 处理器：LibraryUpgrader、RealmsRemover（去掉 Realms 相关库）
- 给**所有** run config 追加 `-Dfabric.gameVersion=<mc>`
- `remapJar` 目标命名空间为 `intermediary` 时，往 manifest 写 `Calamus-Generation: <N>`

## 7. 示例（与官方模板一致）

```groovy
plugins {
    id 'fabric-loom' version '1.19-SNAPSHOT'
    id 'ploceus' version '1.19-SNAPSHOT'   // major.minor 必须和 loom 一致
}

dependencies {
    minecraft "com.mojang:minecraft:${project.minecraft_version}"
    modImplementation "net.fabricmc:fabric-loader:${project.loader_version}"

    // 补丁数据：必须写在 mappings 之前
    exceptions ploceus.raven(project.raven_build)
    signatures ploceus.sparrow(project.sparrow_build)
    nests ploceus.nests(project.nests_build)

    mappings ploceus.featherMappings(project.feather_build)
    // 或者: mappings ploceus.mcpMappings("stable", "1.12", "39")

    ploceus.dependOsl(project.osl_version)          // 全量 OSL，加到 modImplementation
    // ploceus.dependOslModule("0.17.1", "core")    // 只要单个模块
    // ploceus.dependOsl("implementation", "0.17.1", GameSide.CLIENT)  // 指定配置 + side
    //   （用 GameSide 时记得 import net.ornithemc.ploceus.api.GameSide）
}

ploceus {
    setIntermediaryGeneration(2)   // 默认就是 2；用 b1.7.3 + biny 之类生态时需要显式声明
    disableLibraryUpgrades()
    disableLvtPatch()

    // 1.3 之前的版本：和 loom 的一侧 jar 配置成对使用
    clientOnlyMappings()           // + loom { clientOnlyMinecraftJar() }
}

loom {
    // loom 的选项照常可用
    runs { client { preferGradleTask = false } }
}
```
