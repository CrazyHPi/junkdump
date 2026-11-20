---
title: 介绍与总览
---

# OSL API 参考（Minecraft 1.12.2）

> Ornithe Standard Libraries — 面向 Minecraft 1.12.2 的 API 手册。
> 对应源码：`ornithe-standard-libraries` 分支 `gen2`，版本 `0.24.0`（ploceus intermediary generation 2）。

## 关于本文档

- 收录对象：OSL 在 **MC 1.12.2** 下实际可用的全部公开 API 类型（`net.ornithemc.osl.<模块>.api.*`），共 22 个模块、约 300 个类型。
- 组织方式：按模块分章；每章内部按**功能**再分组（如「事件」「注册表」「序列化」）。
- 每个 API 都给出三件事：**作用**（它解决什么问题）、**需要**（参数、前置条件、调用时机）、**返回**（返回值 / 副作用 / 抛出的异常）。
- `impl`、`mixin`、`access` 包下的类属于内部实现，不逐一收录，但会影响语义的地方已在相应 API 中说明。
- 源码位置：本仓库是多版本构建，同一模块有多个"MC 版本区间"子工程。本文档描述的是 1.12.2 命中的那一个子工程 + 模块共享源码。

## 文档结构

- 第 01–22 章：按模块分章，每章内按功能分组。
- 附录 A：逐模块注意事项与已知缺陷（踩坑清单，建议先看）。
- 附录 B：公开类型索引（按包列全部类型，用于按名字反查）。
- [变更历史](/changelog)：0.24.0 → 0.26.0 在 1.12.2 上的变化。

## 依赖引入

用 Ploceus Gradle 插件引入（推荐）：

```groovy
dependencies {
    // 引入整套 OSL
    ploceus.dependOsl('0.24.0')

    // 或只引入需要的模块
    ploceus.dependOslModule('core', '0.24.0')
    ploceus.dependOslModule('registries', '0.24.0')
    ploceus.dependOslModule('lifecycle-events', '0.24.0')
}
```

也可以直接写 Maven 坐标。模块 group 为 `net.ornithemc.osl-gen2`，artifact 为模块 id，版本形如 `<模块版本>+mc<最低版本>-mc<最高版本>`：

```groovy
modImplementation 'net.ornithemc.osl-gen2:registries:0.4.0+mc14w27a-mc17w46a'
```

运行时，每个模块都是一个独立的 Fabric mod，id 为 `osl-<模块 id>`（例如 `osl-registries`）；整套 OSL 的 mod id 为 `osl`，要求 fabricloader `>=0.18.0`。

## 模块总览

| # | 模块 id | 名称 | 版本 | 端 | 用途 | 依赖的 OSL 模块 |
|---|---|---|---|---|---|---|
| 01 | `core` | Core | 0.13.0 | 双端 | 基础设施：事件总线、注册表、命名空间 ID、JSON/IO 工具、数学与排序工具 | — |
| 02 | `biomes` | Biomes | 0.1.1 | 双端 | 生物群系注册表与事件、自定义生物群系参数 | core, entrypoints, registries, localization |
| 03 | `blocks` | Blocks | 0.3.1 | 双端 | 方块注册表与方块事件 | core, entrypoints, blockstates, registries |
| 04 | `blockstates` | Block States | 0.3.0 | 双端 | 属性/状态/状态表的概念与类型（1.12.2 上需自行接到 metadata） | core, registries |
| 05 | `blockentities` | Block Entities | 0.1.1 | 双端 | 方块实体类型注册与事件 | core, entrypoints, registries |
| 06 | `blockentities-rendering` | Block Entities Rendering | 0.1.0 | 仅客户端 | 方块实体渲染器注册与渲染事件 | core, entrypoints |
| 07 | `branding` | Branding | 0.4.4 | 客户端 | 把标题界面版本串、F3 调试信息变成可插拔的文本链 | core, entrypoints, lifecycle-events |
| 08 | `commands` | Commands | 0.1.0 | 双端 | 把 Brigadier 命令框架反移植到 1.12.2 | core, entrypoints, lifecycle-events, blockstates, blocks, items, entities, networking, text-components |
| 09 | `config` | Config | 0.6.3 | 双端 | 配置系统：选项、选项组、JSON/NBT/网络序列化 | core, entrypoints, lifecycle-events |
| 10 | `crash-reports` | Crash Reports | 0.1.0 | 双端 | 崩溃报告分节与自定义崩溃信息 | core, entrypoints |
| 11 | `entities` | Entities | 0.1.3 | 双端 | 实体类型注册与实体事件 | core, entrypoints, registries |
| 12 | `entities-rendering` | Entities Rendering | 0.1.0 | 仅客户端 | 实体渲染器注册与渲染事件 | core, entrypoints |
| 13 | `entrypoints` | Entrypoints | 0.6.1 | 双端 | 游戏/客户端/服务端初始化入口点与启动事件 | core |
| 14 | `executors` | Executors | 0.1.1 | 双端 | 主线程执行器与后台执行器 | core |
| 15 | `items` | Items | 0.3.2 | 双端 | 物品注册表与物品事件 | core, entrypoints, registries, blocks |
| 16 | `keybinds` | Keybinds | 0.3.0 | 仅客户端 | 按键绑定注册与按键事件 | core |
| 17 | `lifecycle-events` | Lifecycle Events | 0.6.1 | 双端 | 游戏、世界、服务器生命周期事件（1.12.2 上最重要的事件入口） | core, entrypoints |
| 18 | `localization` | Localization | 0.2.1 | 双端 | 翻译查询与自定义语言 | core, entrypoints, resource-loader |
| 19 | `networking` | Networking | 0.12.0 | 双端 | 自定义数据包通道与收发 | core, executors, text-components |
| 20 | `registries` | Registries | 0.4.0 | 双端 | 通用注册表 API 与客户端/服务端数字 ID 同步 | core, entrypoints, lifecycle-events, executors, networking, networking-impl |
| 21 | `resource-loader` | Resource Loader | 0.10.0 | 双端（客户端为主） | 把 1.13+ 的资源包/资源重载系统反移植到 1.12.2 | core, lifecycle-events, executors, crash-reports, text-components |
| 22 | `text-components` | Text Components | 0.2.0 | 双端 | 富文本组件、样式、点击/悬停事件 | core, entrypoints |

> 另有两个非 API 模块：`networking-impl`（networking 的内部实现）、`datagen`（数据生成器，仅 MC 1.13+ 提供，1.12.2 不可用）。

## 依赖层次

```
core
 ├── entrypoints ── lifecycle-events ── executors
 │                                │
 ├── registries ── biomes / blocks / items / entities / blockentities
 ├── blockstates ── blocks ── items
 ├── networking ── commands / registries
 ├── text-components ── networking / commands
 ├── config（基于 core + entrypoints + lifecycle-events）
 ├── resource-loader ── localization
 └── keybinds / branding / crash-reports / *-rendering
```

## 推荐起步顺序

1. `entrypoints`：写一个 `ModInitializer`，在 `fabric.mod.json` 里挂上。
2. `lifecycle-events`：拿到 tick、世界加载、连接等时机。
3. `registries` + 具体内容模块（`blocks`/`items`/`entities`/`biomes`）：注册游戏内容。
4. `networking`：需要自定义同步时再引入。
5. `config`：需要持久化设置时再引入。

---

