---
title: 06 blockentities-rendering
---

# 06 blockentities-rendering

> 一句话定位：让自定义方块实体拥有自己的渲染器——把一个 `BlockEntityRenderer` 绑到你的方块实体类上，客户端启动时自动塞进原版的渲染分派表。

| 项 | 值 |
|---|---|
| 模块 id | `blockentities-rendering` |
| Maven | `net.ornithemc.osl-gen2:blockentities-rendering:0.1.0+mca1.0.1_01-mc1.14.4` |
| 端 | 仅客户端 |
| 依赖 | `ploceus.dependOslModule('blockentities-rendering', '0.24.0')`（另需 `core`、`entrypoints`） |

模块整体用途：1.12.2 的方块实体渲染器登记在原版 `BlockEntityRenderDispatcher` 内部的一张私有表里（方块实体类 → 渲染器实例），构造时硬编码登记全部原版渲染器，第三方方块实体没有正规的登记途径。本模块在分派器构造、原版渲染器全部登记完之后触发一个事件，把「往表里放渲染器」包装成安全的 API：你只要提供方块实体类和一个渲染器工厂，查找与插入由 OSL 完成。因为涉及渲染，模块仅客户端；专用服务端上这些类不存在，也不该被引用。

**包名提醒**：本模块的两个类型位于 `net.ornithemc.osl.blockentities.api.client` 包下（沿用 `blockentities` 模块的包名），但它们属于**本模块**，不在 `05 blockentities` 里。

**前置条件**：被渲染的方块实体必须先有一个注册过的类型（见 `05 blockentities` 的 `BlockEntityTypeRegistry`）——渲染器只是「怎么画」，类型注册才是「游戏怎么认出它」。

## 注册器（仅客户端）

### `BlockEntityRendererRegistry`

Reference: `net.ornithemc.osl.blockentities.api.client.BlockEntityRendererRegistry`

**作用**：原版渲染分派表的一层包装，只在 `REGISTER_BLOCK_ENTITY_RENDERERS` 事件里由 OSL 传入。它是函数式接口，但不是给你实现的——你拿到实例后调用 `register` 即可。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `register(Class type, Supplier factory)` | 为指定方块实体类登记渲染器 | `type` 是你的方块实体类（原版按**精确类**查表，子类不会继承父类的渲染器）；`factory` 每次调用返回一个新的渲染器实例，通常写 `CookieRenderer::new` | 无（void） |
| `registerUnsafe(Class type, Supplier factory)` | **（已废弃，请改用 `register(Class, Supplier)`）** 不做泛型检查的同义重载 | 同 `register`；仅在编译期无法使用泛型（例如对泛型签名被裁剪的旧版 jar）时才需要 | 无（void），内部直接转调 `register` |

补充说明：

- 渲染器类型是原版的 `net.minecraft.client.render.block.entity.BlockEntityRenderer`，泛型参数为 `? super T`，所以也可以给某个父类登记一个通用渲染器，再让多个子类共用。
- 同一个方块实体类重复登记时，后写入者覆盖先写入者（实现就是往渲染器表里 `put` 一项）。
- 工厂只在登记时被调用一次，生成的实例由分派器持有；OSL 不缓存、不复用工厂。

## 事件（仅客户端）

### `BlockEntityRenderingEvents`

Reference: `net.ornithemc.osl.blockentities.api.client.BlockEntityRenderingEvents`

**作用**：方块实体渲染生命周期的客户端事件容器。目前只有一个事件：方块实体渲染器的注册窗口。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `REGISTER_BLOCK_ENTITY_RENDERERS`（static final 字段） | 在客户端启动、原版方块实体渲染器登记完成之后触发一次 | 监听器应在 mod 的客户端入口点里注册；只有在监听器内部拿到注册器才能完成登记 | `Event<Consumer<BlockEntityRendererRegistry>>`；无返回值（监听器是 `Consumer`） |

监听器类型是 `Consumer<BlockEntityRendererRegistry>`：

```java
BlockEntityRenderingEvents.REGISTER_BLOCK_ENTITY_RENDERERS.register(registry -> {
    registry.register(CookieBlockEntity.class, CookieRenderer::new);
});
```

触发细节（来自注入点，供排查用）：

- 事件注入在原版 `net.minecraft.client.render.block.entity.BlockEntityRenderDispatcher` 构造器内部，位置在原版构造器遍历渲染器表（`Map.values()`）**之前**；从注入位置推断，这意味着随后那次遍历会覆盖到你新登记进来的渲染器（原版正是在这一遍遍历里做渲染器初始化）。
- 触发时原版表已经填满，你的登记不会顶掉原版渲染器，除非你故意用同一个方块实体类。
- 每次构造分派器都会触发一次（正常游戏里客户端启动时构造一次），所以监听器里不要放与渲染器无关的昂贵逻辑，也不要期望它随资源重载重新触发。
- 该事件只在客户端存在；在专用服务端上注册监听器会因类缺失而失败。
