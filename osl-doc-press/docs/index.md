---
layout: home

hero:
  name: OSL API 参考
  text: Minecraft 1.12.2
  tagline: Ornithe Standard Libraries 0.24.0 — 22 个模块、约 300 个公开 API 类型
  actions:
    - theme: brand
      text: 开始阅读
      link: /guide/intro
    - theme: alt
      text: 直接查模块
      link: /modules/core
    - theme: alt
      text: 踩坑清单
      link: /appendix/notes
    - theme: alt
      text: 变更历史
      link: /changelog

features:
  - title: 按模块分章
    details: core、registries、lifecycle-events、networking、config、commands 等 22 个模块，每章内部再按功能分组。
  - title: 三要素说明
    details: 每个 API 都写明「作用 / 需要什么 / 返回什么」，包括参数含义、前置条件与抛出的异常。
  - title: 源码级细节
    details: 事件触发点、注册时机、线程要求、已知缺陷，均依据 1.12.2 子工程源码整理。
  - title: 全量索引
    details: 附录 B 按包列出全部公开类型，便于按类名反查所属模块与包。
---

## 这份文档是什么

OSL（Ornithe Standard Libraries）是 Ornithe 工具链上的标准库集合，把 1.13+ 才有的各项系统（Brigadier 命令、BlockState、资源重载、注册表与 ID 同步等）反向移植到老版本。

本文档覆盖 **Minecraft 1.12.2** 下实际可用的全部公开 API，依据 `ornithe-standard-libraries` 仓库 `gen2` 分支（`acf984c3`，OSL 0.24.0）的源码整理。

## 怎么读

| 你的目的 | 去哪里 |
|---|---|
| 先搞清楚模块之间怎么依赖、怎么引入 | [介绍与总览](/guide/intro) |
| 我要注册方块 / 物品 / 实体 | [03 blocks](/modules/blocks)、[15 items](/modules/items)、[11 entities](/modules/entities) |
| 我要一个入口、要 tick 回调 | [13 entrypoints](/modules/entrypoints)、[17 lifecycle-events](/modules/lifecycle-events) |
| 我要写配置 | [09 config](/modules/config) |
| 我要自己发包同步数据 | [19 networking](/modules/networking) |
| 我要注册命令 | [08 commands](/modules/commands) |
| 我已经踩坑了 | [附录 A](/appendix/notes) |
| 我只记得类名 | [附录 B](/appendix/types) |
| 我想知道 0.25/0.26 改了什么 | [变更历史](/changelog) |
