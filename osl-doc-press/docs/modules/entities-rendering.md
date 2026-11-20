---
title: 12 entities-rendering
---

# 12 entities-rendering

> 一句话定位：给自定义实体（以及想换掉渲染器的原版实体）登记渲染器——客户端启动时把渲染器塞进原版的实体渲染分派表。

| 项 | 值 |
|---|---|
| 模块 id | `entities-rendering` |
| Maven | `net.ornithemc.osl-gen2:entities-rendering:0.1.0+mc14w05a-mc1.14.4` |
| 端 | 仅客户端 |
| 依赖 | `ploceus.dependOslModule('entities-rendering', '0.24.0')`（另需 `core`、`entrypoints`） |

模块整体用途：1.12.2 的原版 `EntityRenderDispatcher` 把「实体类 → 渲染器」的表放在私有字段里，构造时硬编码登记全部原版渲染器，第三方实体没有正规登记途径。本模块在分派器构造、原版登记完成之后触发事件，把这个动作包装成 API：给出实体类和一个「拿到分派器再返回渲染器」的工厂，插入由 OSL 完成。因为涉及渲染，模块仅客户端。

**包名提醒**：本模块的 api 只有 `net.ornithemc.osl.entities.api.client` 这个子包。同前缀下的 `net.ornithemc.osl.entities.api`（非 `client`）属于**entities 模块**（实体类型注册等），不在本文档范围内。

**前置条件**：自定义实体自身的注册（实体类型 / 存档 id）由 entities 模块负责；本模块只决定「它长什么样」。

## 注册器（仅客户端）

### `EntityRendererRegistry`

Reference: `net.ornithemc.osl.entities.api.client.EntityRendererRegistry`

**作用**：原版实体渲染分派表的一层包装，只在 `REGISTER_ENTITY_RENDERERS` 事件里由 OSL 传入。它是函数式接口，但不是给你实现的——拿到实例后调用 `register` 即可。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `register(Class type, Function factory)` | 为指定实体类登记渲染器 | `type` 为实体类（原版按**精确类**查表，子类不会自动继承父类的渲染器）；`factory` 接收原版 `EntityRenderDispatcher` 并返回渲染器实例，常见写法 `CookieMonsterRenderer::new`，需要分派器时写 `disp -> new CookieMonsterRenderer(disp)` | 无（void） |
| `registerUnsafe(Class type, Function factory)` | **（已废弃，请改用 `register(Class, Function)`）** 不做泛型检查的同义重载 | 同 `register`；仅在编译期无法使用泛型（例如对泛型签名被裁剪的旧版 jar）时才需要 | 无（void），内部直接转调 `register` |

补充说明：

- 工厂参数为什么是分派器：原版不少渲染器（例如玩家渲染器）需要分派器来查其他实体的渲染器、共享模型或皮肤资源，所以这里的工厂签名是 `Function<EntityRenderDispatcher, EntityRenderer<? super T>>`，而不是方块实体渲染器那种无参 `Supplier`。
- 渲染器类型是原版的 `net.minecraft.client.render.entity.EntityRenderer`，泛型参数为 `? super T`，可以给父类登记通用渲染器供多个子类共用。
- 同一个实体类重复登记时，后写入者覆盖先写入者（实现就是往渲染器表里放一项）。
- 工厂在登记时被调用一次，实例由分派器持有；OSL 不缓存渲染器。

## 事件（仅客户端）

### `EntityRenderingEvents`

Reference: `net.ornithemc.osl.entities.api.client.EntityRenderingEvents`

**作用**：实体渲染生命周期的客户端事件容器。目前只有一个事件：实体渲染器的注册窗口。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `REGISTER_ENTITY_RENDERERS`（static final 字段） | 在客户端启动、原版实体渲染器登记完成之后触发一次 | 监听器应在 mod 的客户端入口点里注册；只有在监听器内部拿到注册器才能完成登记 | `Event<Consumer<EntityRendererRegistry>>`；无返回值（监听器是 `Consumer`） |

监听器类型是 `Consumer<EntityRendererRegistry>`：

```java
EntityRenderingEvents.REGISTER_ENTITY_RENDERERS.register(registry -> {
    registry.register(CookieMonsterEntity.class, CookieMonsterRenderer::new);
});
```

触发细节（来自注入点，供排查用）：

- 事件注入在原版 `net.minecraft.client.render.entity.EntityRenderDispatcher` 构造器的末尾，此时原版渲染器已全部登记；你的登记不会顶掉原版渲染器，除非你用同一个实体类。
- 每次构造分派器都会触发（正常游戏里客户端启动时构造一次），监听器里不要放与注册无关的昂贵逻辑，也不要指望它在资源重载时再次触发。
- 1.12.2 走「直接写渲染器表」的那条注入路径（较新版本改为调用分派器的登记方法，模块按 `18w50a` 分界自动选择）；对本版本而言效果一样：都是往「实体类 → 渲染器」的表里放一项。
- 该事件只在客户端存在；在专用服务端上注册监听器会因类缺失而失败。
- 想替换原版实体的渲染器，就用那个实体的**具体类**登记（例如给原版苦力怕类登记你自己的渲染器）。
