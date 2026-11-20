---
title: 04 blockstates
---

# 04 blockstates

> 一句话定位：把 1.13 的 BlockState / Property 概念搬回 1.12.2——用「属性」描述方块状态的取值范围，用「状态 / 状态表」枚举全部组合，并给 `Block` / `BlockState` / `BlockEntity` 补上一套 1.13 风格的扩展接口。

| 项 | 值 |
|---|---|
| 模块 id | `blockstates` |
| Maven | `net.ornithemc.osl-gen2:blockstates:0.3.0+mc16w39a-mc17w46a` |
| 端 | 双端 |
| 依赖 | `ploceus.dependOslModule('blockstates', '0.24.0')`（另需 `core`、`registries`） |

模块整体用途：1.12.2 的方块状态仍以「方块 + 4 bit metadata」表达，没有属性（property）概念。本模块提供三样东西：属性类（`Property` 及其实现），可以定义有名字、有固定取值集合、能按字符串序列化的属性；通用状态容器（`State` / `StateDefinition`），把一个「所有者」的全部属性组合展开成状态图，支持 `get` / `set` / `cycle` 跳转；以及方块侧扩展接口（`BlockExtension` / `BlockStateExtension` / `BlockEntityExtension`），由 OSL 通过混入注入到原版类型上，让 `Block`、`BlockState`、`BlockEntity` 的实例可以直接按 1.13 的方法名被调用。

**阅读顺序建议**：先看「属性」，再看「状态与状态表」，最后看「方块侧扩展接口」和「与 1.12.2 metadata 的关系」——前者是数据结构，后者决定这些数据结构在你的方块里怎么落地。

## 属性（property）

一个属性 = 一个名字 + 一组固定取值 + 值与字符串之间的双向映射。名字会成为状态序列化时的键，取值名会成为值，所以两者都必须是小写、数字和下划线组成的合法标识符。

### `Property`

Reference: `net.ornithemc.osl.blockstates.api.state.property.Property`

**作用**：属性的公共接口。凡是「有名字、取值有限且可比较」的量，都可以实现成属性，然后交给状态表展开。你通常不直接实现它，而是用下面几个现成实现（布尔 / 整数 / 枚举 / 方向），或者继承 `AbstractProperty`。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `getType()` | 取值的 Java 类型 | 无 | `Class<T>`，如 `Integer.class`、`Direction.class` |
| `getName()` | 属性名，序列化时作为键 | 无 | `String` |
| `values()` | 全部允许取值 | 无 | 不可变 `List<T>`；**顺序就是状态表里的下标顺序** |
| `getValue(String name)` | 按字符串名反查取值（反序列化用） | `name` 需匹配某个取值的字符串名 | `Optional<T>`；不匹配时为空 Optional，不抛异常 |
| `getName(T value)` | 取值的字符串名（序列化用） | `value` 应为合法取值 | `String` |
| `indexOf(T value)` | 取值在 `values()` 中的下标 | 同上 | `int`；非法取值返回 `-1` |
| `getName(Property property, Comparable value)`（static） | 类型不安全场景下（手上只有 `Property<?>`）取名字 | `value` 必须属于该属性 | `String` |
| `indexOf(Property property, Comparable value)`（static） | 同上，取下标 | 同上 | `int`；非法为 `-1` |

### `AbstractProperty`

Reference: `net.ornithemc.osl.blockstates.api.state.property.AbstractProperty`

**作用**：属性的基类，只做两件事：保存 `name` 与 `type`，并按「实现类 + 类型 + 名字」实现 `equals` / `hashCode` / `toString`。属性相等的语义是「同类属性且名字与类型相同」，因此**同一个属性对象应作为静态常量复用**，不要每次现场 new。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `AbstractProperty(String name, Class<T> type)`（protected） | 供子类调用的构造器 | `name` 为属性名，`type` 为值类型 | 无（构造器） |
| `equals(Object o)` / `hashCode()` | 按实现类、`type`、`name` 比较与散列 | `o` 可以是任意对象，非属性或异类实现返回 false | `boolean` / `int` |
| `toString()` | 调试用描述 | 无 | `String`，形如 `BooleanProperty[name: baked, type: class java.lang.Boolean, values: [true, false]]` |
| `getType()` / `getName()` | 见 `Property` | 无 | `Class<T>` / `String` |

### `BooleanProperty`

Reference: `net.ornithemc.osl.blockstates.api.state.property.BooleanProperty`

**作用**：只有 `true` / `false` 两个取值的属性，最常用的开关型属性（如「是否被点燃」「是否含水」）。构造器私有，只能通过 `of` 得到。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `of(String name)`（static） | 创建布尔属性 | `name` 为属性名 | 新的 `BooleanProperty` |
| `values()` | `[true, false]`（按下标 0、1） | 无 | `List<Boolean>`，只读 |
| `getValue(String name)` | `"true"` / `"false"` 解析为取值 | `name` 必须是这两个字符串之一 | `Optional<Boolean>`，其它输入为空 |
| `getName(Boolean value)` | 取值的字符串名 | `value` 非 null | `"true"` / `"false"` |
| `indexOf(Boolean value)` | 下标 | `value` 非 null；`true`→0、`false`→1 | `int` |

### `IntegerProperty`

Reference: `net.ornithemc.osl.blockstates.api.state.property.IntegerProperty`

**作用**：一段连续整数区间的属性（如「咬了几口 0..7」「功率 0..15」）。1.12.2 里非常适合直接对应 metadata 的某几位。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `of(String name, int min, int max)`（static） | 创建整数属性，取值 `min..max`（含两端） | `min >= 0` 且 `max > min`，否则抛 `IllegalArgumentException` | 新的 `IntegerProperty` |
| `values()` | 升序的全部取值 | 无 | `List<Integer>`，只读 |
| `getValue(String name)` | 十进制字符串解析为取值 | `name` 能解析为整数且落在区间内 | `Optional<Integer>`，否则为空 |
| `getName(Integer value)` | 取值的字符串名（十进制） | `value` 非 null | `String` |
| `indexOf(Integer value)` | 下标 = `value - min` | `value` 在区间内 | `int`，越界返回 `-1` |

注意：`min` 不允许为负，想表达负数请自己偏移；这条限制是构造时就检查的。

### `EnumProperty`

Reference: `net.ornithemc.osl.blockstates.api.state.property.EnumProperty`

**作用**：取值来自一个枚举的属性（如「朝向」「变种」「半砖位置」）。取值名默认取枚举的序列化名，可过滤、可只取子集、可自定义序列化函数。

泛型约束：用 `of(...)` 系列工厂时，枚举必须同时实现 `StringSerializable`（提供 `serializeName()`），因为取值名来自它而不是 `toString()`。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `of(String name, Class type)`（static） | 取该枚举的全部常量 | `type` 为枚举类 | 新的 `EnumProperty` |
| `of(String name, Class type, Predicate filter)`（static） | 取通过 `filter` 的常量 | `filter` 对每个常量求值 | 新的 `EnumProperty` |
| `of(String name, Class type, T... values)`（static） | 显式指定取值（可只取一部分） | 传入的常量非 null | 新的 `EnumProperty` |
| `of(String name, Class type, Collection values)`（static） | 同上，集合形式 | 集合非空 | 新的 `EnumProperty` |
| `EnumProperty(String name, Class type, Collection values)`（protected） | 供子类使用，取值名取 `T::toString` | 集合内取值名不得重复 | 无（构造器） |
| `EnumProperty(String name, Class type, Function serializer, Collection values)`（protected） | 同上，自定义取值名函数 | 序列化后名字不得重复，否则抛 `IllegalArgumentException` | 无（构造器） |
| `values()` | 取值列表 | 无 | 只读 `List<T>` |
| `getValue(String name)` | 按取值名反查 | `name` 为某个取值的名字 | `Optional<T>` |
| `getName(T value)` | 取值的名字 | `value` 为合法取值 | `String` |
| `indexOf(T value)` | 取值下标（按枚举序数查表） | `value` 为合法取值 | `int` |

### `DirectionProperty`

Reference: `net.ornithemc.osl.blockstates.api.state.property.DirectionProperty`

**作用**：专门表示「六个方向之一」的属性，是 `EnumProperty<Direction>` 的子类。注意这里的 `Direction` 是 OSL 自己的 `net.ornithemc.osl.core.api.util.math.Direction`（`core` 模块），不是原版的方向类型。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `of(String name)`（static） | 六方向全取 | 无 | 新的 `DirectionProperty` |
| `of(String name, Predicate filter)`（static） | 只取通过 `filter` 的方向 | 无 | 新的 `DirectionProperty` |
| `of(String name, Direction... directions)`（static） | 显式指定方向 | 至少一个方向 | 新的 `DirectionProperty` |
| `of(String name, Collection directions)`（static） | 同上，集合形式 | 集合非空 | 新的 `DirectionProperty` |

取值名来自 `Direction.toString()`，即 `down` / `up` / `north` / `south` / `west` / `east`；下标顺序就是传入顺序（用无参 `of` 时是枚举声明顺序）。

### `StringSerializable`

Reference: `net.ornithemc.osl.blockstates.api.state.property.StringSerializable`

**作用**：给枚举提供「状态里显示的取值名」。`EnumProperty.of(...)` 系列工厂要求枚举实现它，这样属性就有稳定的、与 `toString()` 解耦的序列化名。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `serializeName()` | 返回该枚举常量在状态里的名字 | 实现方保证名字合法且在同一枚举内唯一 | `String` |

## 状态与状态表

`Property` 只描述「有哪些取值」，`State` 描述「一个具体组合」，`StateDefinition` 描述「一个所有者的全部组合」。三者的关系：给定所有者（如某个方块）和一组属性，状态表把所有笛卡尔积组合都实例化出来，并预先算好「某个属性改成某个值后跳到哪个状态」的邻接表，所以 `set` / `cycle` 是 O(1) 查表。

### `State`

Reference: `net.ornithemc.osl.blockstates.api.state.State`

**作用**：一个不可变的具体状态，即「所有者 + 每个属性各取一个值」。判等、取值、切换属性都在这里；它只依赖泛型 `O`（所有者类型），因此既可以用在方块上，也可以用在别的东西上。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `is(O o)` | 判断该状态是否属于给定所有者 | `o` 通常为 `owner()` 返回的对象 | `boolean`；由具体实现定义（本模块未给默认实现） |
| `properties()` | 该状态携带的属性集合 | 无 | `Collection<Property<?>>`，顺序与状态表构建时一致 |
| `has(Property property)` | 该状态是否含某属性 | `property` 为任意属性 | `boolean`（按对象同一性查找） |
| `get(Property property)` | 取某属性的当前值 | 状态必须含该属性 | 属性值；**不含该属性时抛 `IllegalArgumentException`** |
| `set(Property property, V value)` | 换一个属性值，得到相邻状态 | 状态必须含该属性，且 `value` 在该属性的 `values()` 内 | 目标 `S`；属性不存在或值非法时抛 `IllegalArgumentException` |
| `cycle(Property property)` | 把属性切到下一个取值（到末尾回到第一个） | 状态必须含该属性 | 目标 `S`；属性不存在时抛 `IllegalArgumentException` |

内部接口 `State.Factory<O, S>`：

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `buildState(O owner, Property[] properties, Comparable[] values, State[][] neighbors)` | 由状态表实现调用，造出一个状态实例 | `properties` / `values` 一一对应；`neighbors[属性下标][取值下标]` 是该状态在对应切换后的目标（同一张表共享，构建期间可能还是 `null`，建完后填满） | 新建的 `S` |

实现 `State` 时通常直接继承实现包里的 `AbstractState`（它已实现 `get` / `set` / `cycle` 与 `toString`，只把 `is` 留给子类），但该基类不在 api 包内，属于实现细节。

### `StateDefinition`

Reference: `net.ornithemc.osl.blockstates.api.state.StateDefinition`

**作用**：一个所有者的状态表：属性清单 + 全部状态实例。遍历、按属性名查属性、取默认状态都通过它。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `owner()` | 状态表的所有者 | 无 | `O`，构建时传入 |
| `all()` | 全部状态 | 无 | 只读 `List<S>`，顺序固定（默认实现按属性取值的笛卡尔积生成） |
| `any()` | 任取一个状态，作为默认状态 | 无 | `S`；默认实现返回 `all().get(0)`，即各属性都取第一个值 |
| `properties()` | 全部属性 | 无 | `Collection<Property<?>>`；默认实现按属性**名**排序 |
| `getProperty(String name)` | 按名字取属性 | `name` 为属性名 | `Property<?>`，不存在时返回 `null`（默认实现直接查表） |

内部接口 `StateDefinition.Builder<O, S>`：

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `add(Property... properties)` | 追加属性 | 属性名须匹配 `^[a-z0-9_]+$`、至少 2 个取值、取值名也须匹配同一格式、同一状态表内不得重名，否则抛 `IllegalArgumentException` | `this`（可链式） |
| `build(State.Factory factory)` | 展开全部组合，生成状态表 | `factory` 负责实例化状态 | `StateDefinition<O, S>` |

构建规则（来自本模块默认实现，1.12.2 下同样适用）：

- 0 个属性 → 1 个状态；1 个属性 → 状态数 = 取值数；n 个属性 → 全部取值的笛卡尔积。
- 状态表与状态实例都是不可变的，建完就不能再加属性。
- 1.12.2 的 api 包里**没有**提供获取 `StateDefinition.Builder` 的工厂方法（本版本模块也没有把它接到 `Block` 上，见下一节）。要自己搭状态表，需要用到实现包里的 `Builder` 实现——它不属于 API，版本间可能变化；只声明属性、不做状态表的话，仅用 `Property` 就够了。

## 方块侧扩展接口

以下接口全部由 OSL 混入注入到原版类型上，**不需要你实现**，拿到 `Block` / `BlockState` / `BlockEntity` 实例后直接调用或强转即可。真正的「默认行为」在方块侧的同名方法里（状态只是转发并补上自己这个 `BlockState` 参数），所以想改行为请覆写方块的方法，而不是实现这些接口。

### `BlockExtension`

Reference: `net.ornithemc.osl.blockstates.api.block.BlockExtension`

**作用**：给 `net.minecraft.block.Block` 补一个「是不是空气」的判断。1.13 里 `Block#isAir()` 是常用判断，1.12.2 没有，OSL 把它补上：所有方块的默认实现返回 `false`，`net.minecraft.block.AirBlock` 被覆写为 `true`。写空气相关逻辑（例如「这个位置能不能放东西」）时可以放心调用。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `isAir()` | 该方块是否为空气 | 由 `Block` 实现，直接调用即可 | `boolean`；普通方块 `false`，`AirBlock` 为 `true` |

### `BlockStateExtension`

Reference: `net.ornithemc.osl.blockstates.api.block.state.BlockStateExtension`

**作用**：`net.minecraft.block.state.BlockState` 的 1.13 风格视图，聚合了「状态自身的属性查询」（`BlockProperties`）与「状态触发的行为」（`BlockBehaviors`），再加一个「这个状态是不是某个方块的状态」的判断。每个 `BlockState` 实例都实现了它，所以 `world.getBlockState(pos)` 的返回值可以直接当 `BlockStateExtension` 用。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `is(Block block)` | 该状态是否属于给定方块 | `block` 非 null；默认实现转发给所属方块（`getBlock().is(block)`），不是简单引用比较 | `boolean` |

其余成员见下面两个父接口。

### `BlockProperties`

Reference: `net.ornithemc.osl.blockstates.api.block.state.BlockProperties`

**作用**：状态的「静态属性」查询：形状、能否穿过、能否被替换、能否放置、是否随机刻。这些方法都把「世界 + 坐标」作为上下文传入，因为同一个状态在不同位置答案可能不同。该接口由 `BlockStateExtension` 继承，最终实现在 `BlockState` 上（混入），mod 作者只需要调用。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `isAir()` | 该状态是否为空气 | 无 | `boolean`，转发给所属方块 |
| `ticksRandomly()` | 该状态是否参与随机刻 | 无 | `boolean`，转发给所属方块 |
| `getShape(WorldView world, BlockPos pos)` | 该状态在该位置的碰撞/选择形状 | `world`、`pos` 非 null | `Box`（`net.minecraft.util.math.Box`） |
| `canWalkThrough(WorldView world, BlockPos pos)` | 实体能否穿过（无碰撞） | 同上 | `boolean` |
| `canBeReplaced(WorldView world, BlockPos pos)` | 该位置的状态能否被新方块替换（放置判定用） | 同上 | `boolean` |
| `canBePlaced(World world, BlockPos pos)` | 该状态能否被放置在该位置 | 同上 | `boolean` |

### `BlockBehaviors`

Reference: `net.ornithemc.osl.blockstates.api.block.state.BlockBehaviors`

**作用**：状态触发的「动态行为」回调，对应 1.13 的那一套事件方法名；同样由 `BlockStateExtension` 继承、由 `BlockState` 实现（混入），不需要 mod 作者实现。全部转发到方块侧（并自动补上当前 `BlockState` 参数），因此 mod 作者一般只覆写方块方法；这里的价值是：在只知道 `BlockState` 的地方（例如你自己写的遍历/判定代码）也能触发同一套行为。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `onAdded(World world, BlockPos pos)` | 该状态被放进世界时 | `world`、`pos` 非 null | 无（void） |
| `onRemoved(World world, BlockPos pos)` | 该状态被移出世界时 | 同上 | 无（void） |
| `tick(World world, BlockPos pos, Random random)` | 计划刻 | 同上，`random` 非 null | 无（void） |
| `randomTick(World world, BlockPos pos, Random random)` | 随机刻 | 同上 | 无（void） |
| `onEntityCollision(World world, BlockPos pos, Entity entity)` | 实体与该状态碰撞 | `entity` 非 null | 无（void） |
| `dropItems(World world, BlockPos pos, int fortuneLevel)` | 破坏时掉落物品 | `fortuneLevel` 为时运等级 | 无（void） |
| `dropItems(World world, BlockPos pos, float luck, int fortuneLevel)` | 同上，带运气值 | `luck` 为玩家运气 | 无（void） |
| `use(World world, BlockPos pos, PlayerEntity player, InteractionHand hand, Direction face, float faceX, float faceY, float faceZ)` | 玩家右键使用 | `face` 为点击的面，`faceX/Y/Z` 为命中点在方块内的相对坐标（0~1） | `boolean`，`true` 表示已处理（与 1.13 的 `ActionResult` 语义对应） |
| `startMining(World world, BlockPos pos, PlayerEntity player)` | 玩家开始破坏 | 无 | 无（void） |

### `BlockEntityExtension`

Reference: `net.ornithemc.osl.blockstates.api.block.entity.BlockEntityExtension`

**作用**：让 `net.minecraft.block.entity.BlockEntity` 能直接告诉你「我所在位置是哪个方块状态」。1.12.2 的方块实体只存「方块 + metadata」，这个方法内部用方块的 metadata→状态转换（`Block#getStateFromMetadata(int)`）补出 `BlockState`，省掉你自己查世界或自己算 metadata 的麻烦。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `getBlockState()` | 该方块实体所在位置的状态 | 方块实体必须已随世界加载（能取到所属方块与 metadata） | `BlockState`（`net.minecraft.block.state.BlockState`） |

## 与 1.12.2 metadata 的关系

这是使用本模块时最容易误解的一点，务必看清：

1. **1.12.2 没有 1.13 的属性体系。** 原版的 `BlockState` 本质上是「方块 + 0..15 的 metadata」的包装，没有 `get/set(Property)`；原版也没有 `Block#getStateManager()` 之类的入口给出属性表。
2. **本模块不接管原版状态。** 在 1.12.2 这一版源码里，`BlockExtension` 只增加了 `isAir()`，**没有** `buildStateDefinition(...)` 之类的钩子（本仓库只为更早的 MC 版本子工程保留了那套钩子）；也就是说 OSL 不会替你生成方块属性，也不会改变原版 `BlockState` 的行为。
3. **`Property` / `State` / `StateDefinition` 是给你自建状态表用的通用工具。** 它们不认识 metadata，只知道「属性 → 取值 → 下标」。要不要把它映射到 metadata、怎么映射（哪几位、哪些值），完全由你决定。
4. **双向转换在方块侧。** 状态 ↔ metadata 的换算由方块自己提供（`Block#getStateFromMetadata(int)` 等）；`BlockEntityExtension#getBlockState()` 就是走这条路把方块实体的 metadata 变成 `BlockState`。

因此 1.12.2 下推荐的写法是：**用 `Property` 明确声明属性的取值范围与序列化名，用 metadata 作为真正的存储，自己在方块的 `getStateFromMetadata` / `getMetadataFromState` 里做位运算**。属性在这里的用处是把「魔法位运算」变成「有名字、有合法取值范围」的量。示例（只用到 api 包里的 `Property`）：

```java
public static final IntegerProperty BITES = IntegerProperty.of("bites", 0, 7);
public static final BooleanProperty BAKED = BooleanProperty.of("baked");

// metadata 低 3 位存 bites，0x8 位存 baked
int raw = metadata & 0x7;
int bites = BITES.getValue(Integer.toString(raw)).orElse(0); // 越界则落回 0
boolean baked = (metadata & 0x8) != 0;

int meta = (BITES.indexOf(bites) & 0x7) | (baked ? 0x8 : 0);
```

想把「属性组合 → 状态对象」也交给 OSL，就需要自建 `StateDefinition`：这会用到 `State` / `State.Factory` 的实现和一个 `StateDefinition.Builder` 实例，而 1.12.2 的 api 包没有给出获取 Builder 的工厂方法（见上文「状态与状态表」末尾的说明）。仅做属性声明 + metadata 映射的话，用不到 `State` / `StateDefinition`。

另需注意：本模块的 `Property` 名字与取值名都参与序列化，改动它们等于改动存档/网络格式的键；上线后不要随意改名。
