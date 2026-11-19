# Fabric Loom `loom { }` DSL 选项速查

> 依据本地 checkout：`fabric-loom` @ `714fbeb9`（分支 `dev/1.19`，即 Loom 1.19.x / 1.20-alpha 时代的 API）。
> 入口类型是 `LoomGradleExtensionAPI`（`src/main/java/net/fabricmc/loom/api/LoomGradleExtensionAPI.java`），
> 运行时对象还会暴露实现层接口 `LoomGradleExtension` 的额外方法。
> 所有 `Property<T>` 在 Groovy DSL 里都可以写成 `foo = value`（等价于 `foo.set(value)`）。

---

## 1. `loom { }` 顶层选项

### 1.1 映射（mappings / namespace）

| 选项 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `officialMojangMappings()` | `Dependency` | — | 用 Mojang 官方映射；等价 `layered { it.officialMojangMappings() }`。未混淆环境会抛异常 |
| `layered { ... }` | `Action<LayeredMappingSpecBuilder>` → `Dependency` | — | 分层映射。层方法：`addLayer(MappingsSpec)`、`officialMojangMappings { }`、`parchment(notation) { removePrefix }`、`signatureFix(artifact)`、`mappings(fileOrDir) { }` |
| `productionNamespace` | `Property<String>` | `intermediary`（未混淆环境 `official`） | 生产运行时用的命名空间 |
| `useIntermediateMappings` | `Property<Boolean>` | 混淆环境 `true`，未混淆 `false` | 是否经过 intermediary 一层 |
| `noIntermediateMappings()` | 方法 | — | 快捷关闭 intermediary（= `useIntermediateMappings = false` 并 finalize） |
| `intermediateMappingsProvider` | `IntermediateMappingsProvider`（实验） | Loom 内置 | 自定义 intermediary 映射来源；也可用 `setIntermediateMappingsProvider(Class) { }` |
| `intermediaryUrl` | `Property<String>` | `https://maven.fabricmc.net/net/fabricmc/intermediary/%1$s/intermediary-%1$s-v2.jar` | `%1$s` 是 MC 版本占位符 |
| `defaultMixinRemapType` | `Property<String>` | 混淆环境 `MIXIN`，未混淆 `STATIC` | 生成 jar 时 mixin 引用的重映射方式 |
| `mappingsFile` | `File`（只读） | — | 生成的 tiny 映射文件 |

### 1.2 Minecraft jar 与运行环境

| 选项 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `minecraftJarConfiguration` | `Property<MinecraftJarConfiguration<?,?,?>>`（实验） | 按版本元数据自动推断 | 可选 `MERGED` / `LEGACY_MERGED` / `CLIENT_ONLY` / `SERVER_ONLY` / `SPLIT` |
| `splitMinecraftJar()` | 方法 | — | = 上面设成 `SPLIT`（client/server 两个 jar） |
| `serverOnlyMinecraftJar()` | 方法 | — | 只要服务端 jar，同时会移除 `client` 运行配置 |
| `clientOnlyMinecraftJar()` | 方法 | — | 只要客户端 jar，同时会移除 `server` 运行配置 |
| `splitEnvironmentSourceSets()` | 方法 | 关闭 | 创建 `client` source set，`main` 变成 common |
| `areEnvironmentSourceSetsSplit()` | `boolean`（只读） | — | 是否已拆分环境 source set |
| `customMinecraftMetadata` | `Property<String>` | 无 | 自定义 version manifest 的 URL |
| `versionsManifests { add(name, url[, priority]) }` | `ManifestLocations`（实验） | 已内置 `mojang`(-2)、`fabric_experimental`(-1) | 额外版本清单来源，priority 越小越优先 |
| `minecraftVersion` | `Provider<String>`（只读） | — | 当前解析出的 MC 版本 |
| `namedMinecraftJars` | `FileCollection`（只读） | — | named（映射后）MC jar 集合 |

### 1.3 运行时与打包行为

| 选项 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `accessWidenerPath` | `RegularFileProperty` | 无 | 项目的 access widener 文件 |
| `fabricModJsonPath` | `RegularFileProperty` | 自动探测 `src/main/resources` / `src/client/resources` | interface injection 等流程使用的 `fabric.mod.json` 位置 |
| `enableTransitiveAccessWideners` | `Property<Boolean>` | `true` | 自动应用编译依赖里带的 AW |
| `enableModProvidedJavadoc` | `Property<Boolean>` | `true` | 应用依赖 mod 提供的 javadoc |
| `runtimeOnlyLog4j` | `Property<Boolean>` | `false` | log4j 只出现在运行时 classpath（编译期不可见） |
| `runtimeOnlyLwjglGraphics` | `Property<Boolean>` | `false` | lwjgl opengl/vulkan 只做运行时依赖，避免编译绑死图形 API |
| `splitModDependencies` | `Property<Boolean>` | `true` | 多项目下按 mod 拆分配置 |
| `uncompressNestedJars` | `Property<Boolean>` | `false` | 嵌套 jar 内的条目用 STORED（减小体积，运行时解压变大） |
| `remapJsrAnnotationsToJetBrains` | `Property<Boolean>` | `true` | 把 JSR `@Nullable` 等换成 JetBrains 版本（仅非 JSpecify 版本生效） |
| `knownIndyBsms` | `SetProperty<String>` | `StringConcatFactory`、`ObjectMethods`、`groovy IndyInterface` | 允许通过的 indy BSM 白名单 |

### 1.4 依赖 / 配置 / 扩展点

| 选项 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `mods { <modid> { ... } }` | `NamedDomainObjectContainer<ModSettings>` | 空 | 为 `fabric.classPathGroups` 声明 mod 的 classpath 组，见 §2.5 |
| `addRemapConfiguration(name) { ... }` | `RemapConfigurationSettings` | — | 新增一个「代理配置」：源配置 → 重映射后的配置 |
| `createRemapConfigurations(sourceSet)` | 方法 | — | 为某个 source set 生成标准的一套 `modImplementation` 等配置 |
| `remapConfigurations` | `NamedDomainObjectList`（只读） | — | 已注册的重映射配置列表（未混淆环境抛异常） |
| `addRemapperExtension(Class, Class) { params }` | 方法 | — | 给 tiny-remapper 挂自定义扩展 |
| `addMinecraftJarProcessor(Class, Object... params)` | 方法 | — | 给 MC jar 加处理步骤（AW、接口注入等都走这套） |
| `minecraftJarProcessors` | `ListProperty<MinecraftJarProcessor<?>>` | 空 | 上面方法的属性形式 |
| `nestJars(task, files/config)` | 方法（实验） | — | 把已构建好的 mod jar / 配置里的依赖嵌进 `jar` 或 `remapJar` |
| `log4jConfigs` | `ConfigurableFileCollection` | Loom 内置 `log4j2.xml` | 想替换默认配置用 `log4jConfigs = files("...")` |
| `modVersion` | `String`（只读） | — | 从 `fabric.mod.json` 读 `version` |
| `disableDeprecatedPomGeneration(publication)` | 方法（实验） | — | 关闭旧式 POM 生成的告警 |

### 1.5 已弃用（顶层）

| 选项 | 替代 |
|---|---|
| `gameJarProcessors` / `addJarProcessor(...)` | `minecraftJarProcessors` / `addMinecraftJarProcessor(...)` |
| `customMinecraftManifest` | `customMinecraftMetadata` |

---

## 2. 子 DSL

### 2.1 `runs { <name> { ... } }` —— `RunConfiguration`

默认已存在 `client`、`server` 两个（`serverOnlyMinecraftJar()` / `clientOnlyMinecraftJar()` 会删掉不需要的那个）。

| 选项 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `displayName` | `Property<String>` | 由 source set + 名字推出，如 `Minecraft Client` | IDEA 里显示的名字 |
| `jvmArguments` | `ListProperty<String>` | Loom 自动补 `-Dfabric.dli.*` 等 | JVM 参数 |
| `programArguments` | `ListProperty<String>` | `server` 带 `nogui` | 游戏参数 |
| `environmentVars` | `MapProperty<String, Object>` | 空 | 环境变量 |
| `systemProperties` | `MapProperty<String, String>` | 空 | `-D` 系统属性 |
| `runtimeEnvironment` | `Property<String>` | `client` / `server` | 运行哪一侧；也可调 `client()` / `server()` 帮助方法 |
| `mainClass` | `Property<String>` | Knot client/server 或 installer 指定 | 真实主类 |
| `devLaunchMainClass` | `Property<String>`（实验） | dev-launch-injector | 一般不要改 |
| `sourceSet` | `Property<String>` | 按环境自动选 | 用哪个 source set 的 classpath |
| `runDirectory` | `DirectoryProperty` | `run/` | 工作目录 |
| `generateRunConfig` | `Property<Boolean>` | 根项目 `true`，子项目 `false` | 是否生成 IDE 运行配置 |
| `preferGradleTask` | `Property<Boolean>` | `true`（Loom 1.18.0-alpha.15 起） | `true` 生成 Gradle task 型配置，`false` 生成 Application 型 |
| `ideConfigFolder` | `Property<String>` | 无 | 在 IDEA 里归到某个文件夹 |
| `appendProjectPathToDisplayName` | `Property<Boolean>` | `true` | 子项目自动追加 `(:some:project)` |
| `task { ... }` | `Action<RunGameTask>` | — | 直接配置底层 `RunGameTask`（继承自 Gradle `JavaExec`，可改 `maxHeapSize`、`environment` 等） |
| `inherit(parent)` | 方法 | — | 从另一个 run config 继承所有 convention |
| `serverWithGui()` | 方法 | — | 去掉 server 默认的 `nogui` |

DSL 形态除了 `runs { client { ... } }`，还支持容器写法：`runs.named("client") { ... }`、`runs.configureEach { preferGradleTask = false }`、`runs.clear()`。

已弃用但仍可用（都是新 API 的 shim）：`name` / `configName` / `environment` / `runDir` / `source` / `vmArg(s)` / `programArg(s)` / `property` / `properties` / `environmentVariable` / `ideConfigGenerated` / `defaultMainClass` / `startFirstThread` / `makeRunDir`。

### 2.2 `mixin { ... }` —— `MixinExtensionAPI`

| 选项 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `useLegacyMixinAp` | `Property<Boolean>` | `false` | Mixin 注解处理器**默认不再启用**；`true` 才走老的 Mixin AP |
| `defaultRefmapName` | `Property<String>` | `<archivesName>-refmap.json`（按 source set 加前缀） | 默认 refmap 名 |
| `refmapTargetNamespace` | `Property<String>` | = `productionNamespace` | refmap 目标命名空间 |
| `messages` | `MapProperty<String, String>` | 空 | 传给 Mixin AP 的 `-A` 消息开关 |
| `showMessageTypes` | `Property<Boolean>` | `false` | 编译日志里显示 mixin 消息类型 |
| `add(sourceSet[, refmapName][, patternFilter])` | 方法（多重重载） | 过滤 `*.mixins.json` | 指定要跑 AP 的 source set 与 mixin 配置过滤 |
| `inlineDependencyRefmaps` | `Property<Boolean>` | `false` | 实现层（`MixinExtension`）属性，未在 API 接口里 |

### 2.3 `interfaceInjection { ... }`

| 选项 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `isEnabled` | `Property<Boolean>` | `true` | 总开关 |
| `enableDependencyInterfaceInjection` | `Property<Boolean>` | `true` | 把依赖 mod 声明的接口注入 MC jar |
| `interfaceInjectionSourceSets` | `ListProperty<SourceSet>` | — | 已弃用，改用 `mods { }` |

### 2.4 `decompilers { <name> { ... } }` —— `DecompilerOptions`

内置 `vineflower`（默认）/ `cfr`；也可以 `register("my", ...)` 自定义。

| 选项 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `decompilerClassName` | `Property<String>` | 内置实现 | 实现 `LoomDecompiler` 的类 |
| `classpath` | `ConfigurableFileCollection` | 内置依赖 | 反编译器自身的 classpath |
| `options` | `MapProperty<String, String>` | 空 | 传给反编译器的参数 |
| `memory` | `Property<Long>` | `4096` | fork JVM 内存（MB） |
| `maxThreads` | `Property<Integer>` | CPU 核数 | 最大线程数 |

### 2.5 `mods { <modid> { ... } }` —— `ModSettings`

| 成员 | 说明 |
|---|---|
| `sourceSet("main")` / `sourceSet(SourceSet)` | 把该 source set 的输出算进这个 mod 的 classpath 组 |
| `sourceSet(name, projectPath \| ProjectDependency)` | 跨项目（对方需 apply `net.fabricmc.fabric-loom-companion`） |
| `dependency(Dependency...)` | 把依赖（如 shade 进来的东西）算进该组 |
| `configuration(Configuration)` | 同上，配置形式 |
| `modFiles` | 直接给 `ConfigurableFileCollection` |

### 2.6 `addRemapConfiguration(name) { ... }` —— `RemapConfigurationSettings`

| 选项 | 默认值 | 说明 |
|---|---|---|
| `sourceSet` | 主 source set | 挂在哪个 source set 上 |
| `targetConfigurationName` | — | 产物最终进入哪个配置 |
| `clientSourceConfigurationName` | — | 拆分环境时 client-only 条目走哪个配置 |
| `onCompileClasspath` | — | 是否出现在编译 classpath |
| `onRuntimeClasspath` | — | 是否出现在运行时 classpath |
| `publishingMode` | `NONE` | `NONE` / `COMPILE_ONLY` / `RUNTIME_ONLY` / `COMPILE_AND_RUNTIME` |
| `applyDependencyTransforms` | 主/client source set 为 `true` | 是否对该配置的依赖做传递 AW / 接口注入处理 |

---

## 3. 不在 `loom { }` 里，但常一起用

`fabricApi` 是**独立的 project 扩展**（`project.extensions.create("fabricApi", ...)`），不能写在 `loom { }` 内部：

```groovy
fabricApi {
    module("fabric-api-base", "0.42.0+1.16")          // 取某个 FAPI 模块依赖
    moduleVersion("fabric-api-base", "0.42.0+1.16")   // 只取版本号
    configureDataGeneration {                          // DataGenerationSettings
        client = true; createRunConfiguration = true; modId = "mymod"
    }
    configureTests {                                   // GameTestSettings
        enableGameTests = true; eula = true; username = "Player0"
    }
}
```

## 4. `gradle.properties` 开关（不是 DSL，但同属配置面）

| 属性 | 作用 |
|---|---|
| `fabric.loom.dontRemap` | 不重映射输出 jar |
| `fabric.loom.disableObfuscation` | 完全关闭混淆/重映射流程（未混淆环境） |
| `fabric.loom.disableRemappedVariants` | 不发布重映射变体 |
| `fabric.loom.disableProjectDependentMods` | 关闭 project 依赖的 mod 处理 |
| `fabric.loom.libraryProcessors` | 选择 library processor |
| `fabric.loom.experimental.sandbox` | 实验性沙箱 |
| `fabric.loom.runtimeJavaCompatibilityVersion` | 假定游戏运行用的 Java 版本 |
| `fabric.loom.decompileCacheMaxFiles` / `MaxAge` | 反编译缓存上限 |
| `fabric.loom.enableMinecraftVerification` | MC jar 签名校验开关 |
| `fabric.loom.dropNonIntermediateRootMethods` | Mojang 层里丢掉非 root 方法名 |
| `fabric.loom.renderdoc.enabled` | RenderDoc 运行任务标记 |

---

## 5. 常用片段

```groovy
loom {
    accessWidenerPath = file("src/main/resources/mymod.accesswidener")

    // 老式 Application 运行配置（想回到 IDEA 里直接跑 main class）
    runs {
        client { preferGradleTask = false }
        server { preferGradleTask = false }
    }

    // 自定义运行配置
    runs {
        clientAutoLogin {
            client()
            programArgs "--username", "Player0"
            ideConfigFolder = "MyMod"
        }
    }

    mixin {
        useLegacyMixinAp = true                        // 1.17+ 默认关闭
        add sourceSets.main, "mymod-refmap.json"
    }

    interfaceInjection {
        enableDependencyInterfaceInjection = false
    }

    decompilers {
        vineflower { memory = 8192; maxThreads = 16 }
    }

    mods {
        mymod { sourceSet "main" }
    }

    nestJars(tasks.remapJar, configurations.myInclude)
}
```
