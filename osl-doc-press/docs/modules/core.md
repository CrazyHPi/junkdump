---
title: 01 core
---

# 01 core

> 一句话定位：OSL 的底座模块——事件容器、二进制/JSON 读写包装、注册表骨架、跨版本中立 ID 与一批工具类型（坐标、方向、拓扑排序、函数式接口）。

| 项 | 值 |
|---|---|
| 模块 id | `core` |
| Maven | `net.ornithemc.osl-gen2:core:0.13.0+mc14w27a-mc1.14.4` |
| 模块版本 | `0.13.0`（`libraries/core/gradle.properties`） |
| 端 | 双端（api 只有一套，客户端/服务端通用） |
| 依赖 | `ploceus.dependOslModule('core', '0.13.0')` |

core 本身不注册任何游戏内容、不做渲染、不碰网络，它只提供其它 OSL 模块和 mod 自己反复需要的基础设施：一个不依赖 Minecraft 的极小事件容器、把 `DataInputStream` / `DataOutputStream` 与 quilt-parsers 的 JSON 读写包成"一条流 / 一个文件"的助手、一组键值注册表类型，以及若干被重写成跨版本稳定形态的工具类（原版这些类型在不同 MC 版本里名字和行为都不一样）。

模块内的分工大致是：

- `core.api.events`：事件容器 `Event`，纯 Java，可以在任意版本、任意线程上用。
- `core.api.io` / `core.api.json`：序列化脚手架，OSL 的 config / resource-loader / datagen 等模块都建在它上面。
- `core.api.registry`：`RegistryKey` + `Registry` 的最小键值注册表；另外三个带数字 ID 的注册表已废弃。
- `core.api.util`：`NamespacedIdentifier`（跨版本中立的 `Identifier`）、`BlockPos`、`Direction`、`Unit`、三参数函数式接口、`TopoSort`。

> **MC 1.12.2 说明**：本文档描述的全部 api 都来自共享源码 `libraries/core/src/main/java`。1.12.2 使用的子工程 `core-mc14w27a-mc1.14.4` 里只有 impl/mixin（给原版 `Identifier` 注入扩展方法）和一个 impl 工具类，**没有额外的 api 类型**，所以 core 的 api 在 1.12.2 上是"全套可用、没有版本缺口"的状态。

## 事件：`core.api.events`

### `Event<T>`

Reference: `net.ornithemc.osl.core.api.events.Event<T>`

**作用**：一个极简的事件容器。它内部只有"一个监听器 `List<T>` 和一个调用器 `T`"，`T` 是任意函数式接口（`Runnable`、`Consumer`、`Function`、OSL 的 `TriConsumer` / `TriFunction` 等）。mod 的常见用法是：自己声明一个 `public static final Event<...>` 字段，把 `register(...)` 暴露给别的 mod，触发时调用 `invoker().xxx(...)`。因为它完全不引用 Minecraft 类型，所以不用担心版本差异，也可以在初始化早期使用。

**需要**：创建时用 `Event.of(...)` 或本节的静态工厂给出"怎么把监听器列表变成调用器"；注册的监听器必须与 `T` 一致（只有编译期保证）。**没有**取消注册 / 移除监听器的 API；内部 `ArrayList` 没有同步，注册与触发并发执行属于未定义行为。

**返回**：`invoker()` 返回调用器对象，它每次被调用时才现场遍历当前监听器列表——所以"先取调用器、后注册监听器"依然能触发到新监听器（虽然 `register` 会把缓存的调用器字段置空）。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `of(Function<List<T>, T> invokerFactory)` | 自定义"监听器列表 → 调用器"的构造方式 | `invokerFactory` 在第一次 `invoker()` 时被调用一次，参数是事件内部的**可变**监听器列表，不要把它长期保存 | 新的 `Event<T>` |
| `runnable()` | 广播型（无参、无返回） | 无 | `Event<Runnable>` |
| `consumer()` | 广播型（1 个参数） | 无 | `Event<Consumer<T>>` |
| `biConsumer()` | 广播型（2 个参数） | 无 | `Event<BiConsumer<T, U>>` |
| `triConsumer()` | 广播型（3 个参数，用 `core.api.util.function.TriConsumer`） | 无 | `Event<TriConsumer<T, U, V>>` |
| `functionFirst()` / `biFunctionFirst()` / `triFunctionFirst()` | 取值型：**按注册顺序**询问监听器，拿到第一个结果就停止 | 监听器返回值不能是 `null`（见"null 语义"） | 对应的 `Event<Function/BiFunction/TriFunction>` |
| `functionFirstNonNull()` / `biFunctionFirstNonNull()` | 取值型（名字带 NonNull） | 同上 | 同上——源码与不带 `NonNull` 的版本**实现完全相同** |
| `triFunctionFirstNonNull()` | 取值型：按顺序问，**跳过**返回 `null` 的监听器 | 无 | `Event<TriFunction<T, U, V, R>>` |
| `functionAny()` / `biFunctionAny()` / `triFunctionAny()` | 取值型：任意一个监听器的结果即可（`Stream#findAny()`） | 同 `...First`，不能返回 `null` | 对应的 `Event<Function/BiFunction/TriFunction>` |
| `functionAnyNonNull()` / `biFunctionAnyNonNull()` | 取值型（名字带 NonNull） | 同上 | 同上——同样与不带 `NonNull` 的版本实现相同 |
| `triFunctionAnyNonNull()` | 取值型：任意顺序，跳过 `null` | 无 | `Event<TriFunction<T, U, V, R>>` |
| `register(T listener)` | 追加一个监听器 | `listener` 非 null（不做检查） | 无（void） |
| `invoker()` | 取调用器；首次调用时用 `invokerFactory` 现场构造并缓存 | 无 | `T`（调用器） |

#### 触发语义速查（重点）

| 语义 | 工厂 | 说明 |
|---|---|---|
| 广播、不短路 | `runnable`、`consumer`、`biConsumer`、`triConsumer` | 触发一次就把**所有**监听器按注册顺序跑一遍，没有返回值、无法"打断"。监听器抛异常会直接冒到触发方，其后的监听器不再执行（源码没有 try/catch） |
| 顺序取第一个值（短路） | `functionFirst` 系 | 用 `listeners.stream().map(...).findFirst()`：按注册顺序询问，命中即停 |
| 任意取一个值（短路） | `functionAny` 系 | 用 `findAny()`。源码里的流是**顺序流**，实际结果与 `findFirst` 相同，但语义上不保证顺序，不要依赖"一定是先注册的那个" |
| 收集全部返回值 | — | **本类不提供**。需要"所有监听器的结果"时自己写 `Event.of(listeners -> (...) -> { ... })` |

#### null 语义（与名字不完全一致）

- 只有 `triFunctionFirstNonNull` 与 `triFunctionAnyNonNull` 会真正用 `filter(Objects::nonNull)` 跳过返回 `null` 的监听器。
- 其余所有 `...First` / `...Any` / `...FirstNonNull` / `...AnyNonNull` 都**不过滤 null**：它们把"第一个被问到的监听器的返回值"直接交给 `findFirst()` / `findAny()`，而这两个方法不接受 `null` 元素，因此**若被取到的那一次返回 `null`，会抛 `NullPointerException`**（哪怕后面的监听器能返回非 null）。
- 因此写"取值型"监听器时，要么永远返回非 null，要么改用 `triFunction*NonNull`（3 参），要么自己用 `Event.of` 实现过滤。
- 源码中若干 `*NonNull` 工厂的注释写的是 "Cancels after any listener returns non-null"，与实现不符；以实现为准（见上）。

#### 示例

```java
public final class MyModEvents {
    /** 广播型：给别处挂"每 tick 做点什么" */
    public static final Event<Runnable> TICK = Event.runnable();
    /** 取值型：第一个返回非 null 的监听器决定结果（用 3 参 NonNull 变体才安全） */
    public static final Event<TriFunction<World, Integer, Integer, String>> LOOKUP = Event.triFunctionFirstNonNull();
}

// 注册
MyModEvents.TICK.register(() -> counter++);

// 触发
MyModEvents.TICK.invoker().run();
String r = MyModEvents.LOOKUP.invoker().apply(world, x, z);
```

## 二进制读写：`core.api.io`

### `DataStream`

Reference: `net.ornithemc.osl.core.api.io.DataStream`

**作用**：把 `DataInputStream` / `DataOutputStream` 包成一个对象，同时实现 `DataInput` 与 `DataOutput`。这样"写包 / 读包"两侧的代码可以共用同一个类型，也能把"只读"或"只写"的意图显式表达出来。

**需要**：用静态工厂创建，构造函数是私有的。同一个实例要么只读、要么只写：对着只读实例调写方法抛 `IOException("not writing!")`，对着只写实例调读方法抛 `IOException("not reading!")`。

**返回**：写方法全部 `void`；读方法返回对应基本类型；所有方法都声明 `throws IOException`（透传底层流）。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `output(OutputStream)` | 新建只写 `DataStream`（内部 `new DataOutputStream(output)`） | `output` 非 null | `DataStream` |
| `input(InputStream)` | 新建只读 `DataStream`（内部 `new DataInputStream(input)`） | `input` 非 null | `DataStream` |
| `wrapOutput(DataOutputStream)` / `wrapInput(DataInputStream)` | 包装已有的数据流（不再多套一层） | 传入的流需要你自己关闭 | `DataStream` |
| `writeBoolean / writeByte / writeShort / writeChar / writeInt / writeLong / writeFloat / writeDouble` | 按 Java 的大端定长格式写基本类型 | 只写流 | 无（void） |
| `write(int) / write(byte[]) / write(byte[], int off, int len)` | 原样写字节 | 同上 | 无（void） |
| `writeBytes(String) / writeChars(String) / writeUTF(String)` | 写字符串：`writeBytes` 每字符取低 8 位、`writeChars` 写 UTF-16 单元、`writeUTF` 写 modified UTF-8（**最多 65535 字节**，超长抛 `UTFDataFormatException`） | 同上 | 无（void） |
| `readFully(byte[]) / readFully(byte[], int off, int len)` | 读满指定长度，读不满抛 `EOFException` | 只读流 | 无（void） |
| `skipBytes(int n)` | 跳过若干字节 | 同上 | 实际跳过的字节数 |
| `readBoolean / readByte / readUnsignedByte / readShort / readUnsignedShort / readChar / readInt / readLong / readFloat / readDouble` | 读基本类型，格式必须与写端一致 | 同上 | 对应类型（如 `readByte` 返回 `byte`、`readUnsignedByte` 返回 `int`） |
| `readLine()` | 读一行（旧的字节语义：逐字节读到换行/回车） | 同上 | `String`；流结束返回 `null` |
| `readUTF()` | 读 modified UTF-8 字符串（与 `writeUTF` 配对） | 同上 | `String` |

> `DataStream` 只是包装：不缓冲、不关闭底层流，生命周期由调用方负责。

## JSON 文件：`core.api.json`

### `JsonFile`

Reference: `net.ornithemc.osl.core.api.json.JsonFile`

**作用**：把 quilt-parsers 的 `JsonWriter` / `JsonReader` 包装成"一个文件对象 + 一串链式调用"。它固定把整个文件当成**一个 JSON 对象**：`write()` / `read()` 自动 `beginObject()`，`close()` 自动 `endObject()`，中间用 `writeName` / `writeString` / `readName` / `readString` 之类按顺序操作。

**需要**：构造时给 `Path`；先调用 `write()`（覆盖写）或 `read()` 之一；**必须** `close()`（实现 `Closeable`），否则文件没有收尾、JSON 不完整，流也不会关闭。两个打开方法不能在同一实例上重复调用（抛 `IOException("already writing!")` / `"already reading!"`），也不允许边读边写。

**返回**：写操作全部返回 `this`（便于链式），读操作返回读到的值；所有方法声明 `throws IOException`。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `JsonFile(Path path)` | 绑定文件路径（此时尚未打开） | 父目录需已存在（是否自动创建目录：源码未明确说明） | 新实例 |
| `write()` | 打开写入器并开始写顶层对象 | 尚未 `write()` / `read()` | 无（void） |
| `read()` | 打开读取器并开始读顶层对象 | 尚未 `write()` / `read()` | 无（void） |
| `close()` | 结束顶层对象并关闭流，之后不能再读写 | 已经 `write()` 或 `read()` | 无（void） |
| `writeName(String name)` | 写下一个属性名 | 正在写、且当前位于对象内 | `JsonFile` |
| `writeObject(JsonFileConsumer object)` / `writeObject(String name, JsonFileConsumer object)` | 写一个嵌套对象；带 `name` 的版本等价于 `writeName(name).writeObject(object)` | 同上 | `JsonFile` |
| `writeArray(JsonFileConsumer... elements)` / `writeArray(String name, JsonFileConsumer... elements)` | 写一个数组，每个回调负责写一个**元素** | 同上 | `JsonFile` |
| `writeString(String value)` / `writeString(String name, String value)` | 写字符串值 | 同上 | `JsonFile` |
| `writeBoolean(boolean)` / `writeBoolean(Boolean)`（各带 `name` 重载） | 写布尔值 | 同上 | `JsonFile` |
| `writeNumber(Number)` / `writeDouble(double)` / `writeLong(long)`（各带 `name` 重载） | 写数值 | 同上 | `JsonFile` |
| `writeNull()` / `writeNull(String name)` | 写 `null` | 同上 | `JsonFile` |
| `writeJson(String value)` / `writeJson(String name, String value)` | 把一段**已序列化好的 JSON 文本**原样写进去 | 同上；`value` 必须是合法 JSON | `JsonFile` |
| `hasNext()` | 当前对象/数组里是否还有下一个成员 | 正在读 | `boolean` |
| `peek()` | 预读下一个 token | 同上 | `JsonToken` |
| `readName()` | 读下一个属性名 | 同上 | `String` |
| `readName(String name)` | 读下一个属性名并与给定名字比较，不等就抛异常 | 名字必须与文件中的键完全一致 | `JsonFile`；不匹配抛 `IOException` |
| `readObject(JsonFileConsumer object)` / `readObject(String name, JsonFileConsumer object)` | 读一个嵌套对象 | 同上 | 无（void） |
| `readArray(JsonFileConsumer... elements)` / `readArray(String name, JsonFileConsumer... elements)` | 读一个数组，按回调个数逐个读元素 | 回调数量必须与元素数量一致 | 无（void） |
| `readString() / readString(String name)` | 读字符串 | 同上 | `String` |
| `readBoolean() / readBoolean(String name)` | 读布尔 | 同上 | `boolean` |
| `readNumber() / readNumber(String name)` | 读数字 | 同上 | `Number` |
| `readDouble() / readDouble(String name)` | 读双精度 | 同上 | `double` |
| `readLong() / readLong(String name)` | 读长整型 | 同上 | `long` |
| `readInt() / readInt(String name)` | 读整数 | 同上 | `int` |
| `readNull() / readNull(String name)` | 断言下一个值是 `null` | 同上 | 无（void） |
| `skipValue()` | 跳过下一个值（含整个对象/数组） | 同上 | 无（void） |

### `JsonFileConsumer`

Reference: `net.ornithemc.osl.core.api.json.JsonFile.JsonFileConsumer`

**作用**：`writeObject` / `readObject` / `writeArray` / `readArray` 用的回调；签名允许抛 `IOException`，所以回调里可以直接继续调用 `JsonFile` 的方法。

**需要**：自己给一个 lambda 即可，参数就是外层那个 `JsonFile`。

**返回**：无（void）。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `accept(JsonFile json)` | 在对象/数组内部执行读写 | `json` 是外层同一个实例 | 无（void）；可抛 `IOException` |

#### 示例

```java
try (JsonFile json = new JsonFile(path)) {
    json.write();
    json.writeString("name", "example");
    json.writeArray("values", j -> j.writeString("a"), j -> j.writeString("b"));
    json.writeBoolean("enabled", true);
}
```

## 注册表：`core.api.registry`

本包有两代东西：`RegistryKey` + `Registry` + `Registries` 是"键 → 值"的通用小注册表；`SimpleIdRegistry` / `DefaultedIdRegistry` / `IdBiMap` 是旧的"数字 ID"注册表，**全部已 `Deprecated`**。

### `Registries`

Reference: `net.ornithemc.osl.core.api.registry.Registries`

**作用**：`Registry` 的门面：提供"建一个具名注册表"和"在注册表里读写映射"的静态方法，避免调用方到处 `new` 注册表。

**需要**：所有 `Registry` 实例都由这里创建；同一个 `RegistryKey` 只能注册一次，重复会抛 `IllegalStateException`（消息形如 `cannot register duplicate key ... to registry osl:registries`）。

**返回**：见下表。注意注册表本身**没有**"按 key 反查已注册的 Registry"的公开方法（内部根注册表只写不读），所以请自己把拿到的 `Registry` 存进静态字段。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `register(RegistryKey name)` | 新建注册表并登记到内部根注册表 | `name` 未被使用过 | 新的 `Registry<K, V>`（泛型由调用方指定） |
| `registerMapping(Registry registry, K key, V value)` | 往某个注册表里放映射（等价于 `registry.register(key, value)`） | key、value 都不能重复 | 注册进去的 `value` |
| `getMapping(Registry registry, K key)` | 按 key 取值 | 无 | 值；未注册为 `null` |
| `getKey(Registry registry, V value)` | 按值反查 key | 无 | key；未注册为 `null` |

### `Registry<K, V>`

Reference: `net.ornithemc.osl.core.api.registry.Registry<K, V>`

**作用**：最小的双向映射注册表（key ⇄ value），用 `LinkedHashMap` 保存插入顺序。core 里它是 `RegistryKey` 的容器，mod 也可以拿它当"名字 → 对象"的自用注册表。

**需要**：实例只能由 `Registries.register(...)` 创建（构造函数是包私有的）。**没有**遍历、删除、`size` 之类的 API，也没有同步；注册一般只在初始化阶段做。

**返回**：`register` 返回注册进去的值，`get` / `getKey` 未命中返回 `null`。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `register(K key, T value)` | 建立 key ⇄ value 映射 | key 不能已存在、value 不能已注册过（任一重复抛 `IllegalStateException`）；value 用引用身份判重，请保证单例 | 注册进去的 `value` |
| `get(K key)` | 按 key 取值 | 无 | 值（泛型窄化为 `T extends V`）；未注册为 `null` |
| `getKey(V value)` | 按值取 key | 无 | key（泛型窄化为 `T extends K`）；未注册为 `null` |
| `equals / hashCode` | 按注册表的 `RegistryKey` 名字判等 | 无 | `boolean` / `int` |

### `RegistryKey`

Reference: `net.ornithemc.osl.core.api.registry.RegistryKey`

**作用**：注册表的名字（不可变、可比较、可作 Map 键），形式是"父名:子名"的字符串。

**需要**：用 `of(...)` 创建（构造函数私有）。`of(String)` 把名字挂到内部根键 `osl:registries` 下，`of(RegistryKey parent, String value)` 拼成 `parent:value`。

**返回**：见下表。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `of(String value)` | 在根命名空间下建键，结果为 `osl:registries:value` | `value` 非 null | `RegistryKey` |
| `of(RegistryKey parent, String value)` | 建子键，结果为 `parent.get() + ":" + value` | `value` 非 null | `RegistryKey` |
| `get()` | 取完整字符串 | 无 | `String` |
| `equals / hashCode` | 按字符串判等 | 无 | `boolean` / `int` |

### `SimpleIdRegistry<T>`

Reference: `net.ornithemc.osl.core.api.registry.SimpleIdRegistry<T>`

**作用**：（已废弃，请改用 registries 模块的注册表 API：`net.ornithemc.osl.registries.api.registry` 下的 `Registries` / `WritableRegistry` / `IdMap`。）一个把"数字 ID"和"带命名空间的字符串 key"都映射到同一个值的注册表：id ⇄ value、key ⇄ value、value ⇄ id/key，用来替代原版各种"按 id 或按名字查找"的静态表。实现 `Iterable<T>`，迭代顺序是 key 映射表的顺序。

**需要**：值必须是**引用唯一**的对象（内部用 `IdentityHashMap` 记 value → key，用 fastutil 的引用表记 value → id）。注册时 id 必须 `>= 0`，id、key、value 三者都不能重复，任一重复抛 `IllegalStateException`；不传 id 的 `register(key, value)` 使用自增 id（从 0 开始；注册显式 id 时会把自增游标推到 `id + 1`）。

**返回**：`register` 返回注册进去的值；查询未命中返回 `null`，`getId` 未命中返回 `-1`。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `SimpleIdRegistry()` | 建空注册表 | 无 | 新实例 |
| `register(NamespacedIdentifier key, T value)` | 用下一个自增 id 注册 | key、value 均未注册过 | `value` |
| `register(int id, NamespacedIdentifier key, T value)` | 用指定 id 注册 | `id >= 0` 且未占用；key、value 未注册过 | `value` |
| `get(int id)` | 按 id 查 | 无 | 值或 `null` |
| `get(NamespacedIdentifier key)` | 按 key 查 | 无 | 值或 `null` |
| `has(T value)` | 该值是否注册过 | 依赖引用身份 | `boolean` |
| `getId(T value)` | 反查 id | 同上 | `int`（未注册为 `-1`） |
| `getKey(T value)` | 反查 key | 同上 | `NamespacedIdentifier`（未注册为 `null`） |
| `keySet()` | 所有已注册的 key | 无 | `Set<NamespacedIdentifier>`（**可变视图**，不要直接改） |
| `iterator()` | 迭代所有值 | 无 | `Iterator<T>` |

### `DefaultedIdRegistry<T>`

Reference: `net.ornithemc.osl.core.api.registry.DefaultedIdRegistry<T>`

**作用**：（已废弃，请改用 registries 模块的 `net.ornithemc.osl.registries.api.registry.DefaultedRegistry`。）带"默认值"的 `SimpleIdRegistry`：查询未命中时不再返回 `null`，而是返回默认项。

**需要**：构造时给出默认项的 key（`String` 形式会被解析成 `NamespacedIdentifier`）；默认项必须用"key 等于默认 key"的那次 `register` 注册，否则默认值一直是 `null`。

**返回**：`get(...)` 未命中时返回默认值（默认项也没注册过则为 `null`）。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `DefaultedIdRegistry(String defaultKey)` | 用字符串指定默认 key | 字符串会被当作 **`minecraft` 命名空间下的 identifier**（内部走 `from`，不是 `parse`），因此**不能含冒号**；非法字符抛运行时异常 | 新实例 |
| `DefaultedIdRegistry(NamespacedIdentifier defaultKey)` | 用现成 ID 指定默认 key | 无 | 新实例 |
| `register(int id, NamespacedIdentifier key, T value)` | 注册；key 等于默认 key 时同时记为默认值 | 同父类 | `value` |
| `get(int id)` / `get(NamespacedIdentifier key)` | 查询，未命中回退到默认值 | 无 | 值 / 默认值 / `null` |

> 其余成员（`register(key, value)`、`has`、`getId`、`getKey`、`keySet`、`iterator`）与 `SimpleIdRegistry` 相同。

### `IdBiMap<T>`

Reference: `net.ornithemc.osl.core.api.registry.IdBiMap<T>`

**作用**：（已废弃，请改用 registries 模块的 `net.ornithemc.osl.registries.api.registry.IdMap`。）只有 id ⇄ value 的双向映射，没有字符串 key，是 `SimpleIdRegistry` 的轻量版。

**需要**：value 按引用身份判重；`id >= 0`；id 或 value 重复抛 `IllegalStateException`。

**返回**：`register` 返回值；`get` 未命中 `null`；`getId` 未命中 `-1`。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `IdBiMap()` | 建空映射 | 无 | 新实例 |
| `register(T value)` | 用下一个自增 id 注册 | value 未注册过 | `value` |
| `register(int id, T value)` | 用指定 id 注册 | `id >= 0` 且未被占用 | `value` |
| `get(int id)` | 按 id 查 | 无 | 值或 `null` |
| `has(T value)` | 是否注册过 | 无 | `boolean` |
| `getId(T value)` | 反查 id | 无 | `int`（未注册为 `-1`） |
| `iterator()` | 迭代所有值（按 id 映射表顺序） | 无 | `Iterator<T>` |

## 通用工具：`core.api.util`

### `NamespacedIdentifier`

Reference: `net.ornithemc.osl.core.api.util.NamespacedIdentifier`

**作用**：跨版本中立的"命名空间:标识符"ID，等价于原版的 `Identifier`，但**在所有 MC 版本上都存在、行为一致**（原版的 `Identifier` 直到 13w21a 才出现，14w27b 之前还只在客户端有，早期版本甚至完全不校验）。如果你的代码要跨版本、或者要在"原版 ID 类型还不存在 / 名字不一样"的版本上工作，就用它。

**需要**：一般**不要自己实现**这个接口，用 `NamespacedIdentifiers.from(...)` / `parse(...)` 拿实例（实现类是 impl 包里的不可变类）。它可以自由作为 `Map` 的键：实现类提供基于 namespace/identifier 的 `equals` / `hashCode`，`toString()` 为 `namespace:identifier`。

**返回**：`namespaced` / `prefixed` / `suffixed` / `subidentifier` 都返回**新副本**（类型本身不可变），不改动原对象。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `SEPARATOR` | 命名空间与标识符之间的分隔符常量（`':'`） | 无 | `char` |
| `separator()` | 分隔符（默认实现返回 `SEPARATOR`） | 无 | `char` |
| `namespace()` | 命名空间部分 | 无 | `String` |
| `identifier()` | 标识符部分 | 无 | `String` |
| `namespaced(String namespace)` | 换命名空间 | 不校验新命名空间（实现类直接替换） | 新的 `NamespacedIdentifier` |
| `prefixed(String prefix)` | 标识符前加前缀（命名空间不变） | 无 | 新副本 |
| `suffixed(String suffix)` | 标识符后加后缀 | 无 | 新副本 |
| `subidentifier(int beginIndex)` / `subidentifier(int beginIndex, int endIndex)` | 取标识符的子串（命名空间不变） | 索引越界抛 `StringIndexOutOfBoundsException` | 新副本 |

### `NamespacedIdentifiers`

Reference: `net.ornithemc.osl.core.api.util.NamespacedIdentifiers`

**作用**：`NamespacedIdentifier` 的工厂与校验器：负责字符集规则（命名空间只允许 `[a-z0-9-._]`，标识符另外允许 `/`）、长度上限常量和比较器。

**需要**：解析外部输入（配置文件、命令参数、资源路径）时用 `parse` 或 `isValid` 系，不要自己拼字符串。校验失败抛出的是运行时异常（具体类型在 impl 包里，不属于 api）。

**返回**：`from` / `parse` 返回 ID；`validate` 原样返回传入的 ID（便于链式）；`isValid` 系返回 `boolean`。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `MINECRAFT_NAMESPACE` / `DEFAULT_NAMESPACE` | 原版命名空间 `"minecraft"`；默认命名空间等于它 | 无 | `String` |
| `MAX_LENGTH_NAMESPACE` / `MAX_LENGTH_IDENTIFIER` | 长度上限常量（当前都是 `Integer.MAX_VALUE`，即不限制长度） | 无 | `int` |
| `COMPARATOR` | 比较器：先比 identifier，再比 namespace | 无 | `Comparator<NamespacedIdentifier>` |
| `from(String identifier)` | 用默认命名空间（`minecraft`）构造 | 标识符合法（非空、字符集合法） | `NamespacedIdentifier`；非法抛运行时异常 |
| `from(String namespace, String identifier)` | 用指定命名空间构造 | 两者都合法 | 同上 |
| `parse(String s)` | 解析 `namespace:identifier` 形式的字符串；**没有冒号时按默认命名空间处理**，冒号在开头（`":foo"`）或任一部分为空视为格式错误 | `s` 非 null | `NamespacedIdentifier`；失败抛解析异常（运行时） |
| `validate(NamespacedIdentifier id)` | 校验一个已有 ID | `id` 非 null | 原样返回 `id`；非法抛运行时异常 |
| `validateNamespace(String)` / `validateIdentifier(String)` | 只校验某一部分 | 非 null、非空、字符集合法、长度不超上限 | 原样返回该字符串；非法抛运行时异常 |
| `isValid(NamespacedIdentifier)` / `isValidNamespace(String)` / `isValidIdentifier(String)` | 只判断、不抛异常（null 视为非法；这组**不检查长度**，与 `validate` 系不完全对称） | 无 | `boolean` |
| `isCharAllowed(int chr)` | 某字符是否允许出现在 ID 中（含冒号、横线、点、下划线、斜杠、`a-z0-9`） | 无 | `boolean` |
| `equals(NamespacedIdentifier a, NamespacedIdentifier b)` | 语义相等（分隔符、命名空间、标识符都相同） | 两者非 null | `boolean` |

### `Unit`

Reference: `net.ornithemc.osl.core.api.util.Unit`

**作用**：只有一个常量的枚举，用来表达"没有值 / 已终止"这种占位。典型用途是配合 `Optional` 表示"访问到此结束"（见 text-components 模块的 `TextVisitResults`）。

**需要**：直接用 `Unit.INSTANCE`。

**返回**：无方法。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `INSTANCE` | 唯一实例 | 无 | `Unit` |

## 函数式接口：`core.api.util.function`

Java 8 自带的 `Consumer` / `BiConsumer` / `Function` / `BiFunction` 只到两参，也不允许抛受检异常，这里补齐。

### `IOConsumer<T>`

Reference: `net.ornithemc.osl.core.api.util.function.IOConsumer<T>`

**作用**：允许抛 `IOException` 的一参消费者，主要用于"读/写文件时对每个元素做点什么"的回调。

**需要**：作为 lambda 实现；调用方负责捕获或声明 `IOException`。

**返回**：无（void）。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `accept(T t)` | 处理一个元素 | 可抛 `IOException` | 无（void） |

### `IOSupplier<T>`

Reference: `net.ornithemc.osl.core.api.util.function.IOSupplier<T>`

**作用**：允许抛 `IOException` 的供应者，用于"惰性打开资源"。

**需要**：同 `IOConsumer`。

**返回**：`T`。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `get()` | 产出值 | 可抛 `IOException` | `T` |

### `TriConsumer<T, U, V>`

Reference: `net.ornithemc.osl.core.api.util.function.TriConsumer<T, U, V>`

**作用**：三参消费者（`BiConsumer` 的三参特化）。`Event.triConsumer()` 用的就是它。

**需要**：作为 lambda 实现；预期通过副作用工作。

**返回**：无（void）。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `accept(T t, U u, V v)` | 处理三个参数 | 无 | 无（void） |
| `andThen(TriConsumer after)` | 组合：先执行自己、再执行 `after` | `after` 非 null（null 抛 `NullPointerException`）；前半抛异常时 `after` 不执行 | 组合后的 `TriConsumer<T, U, V>` |

### `TriFunction<T, U, V, R>`

Reference: `net.ornithemc.osl.core.api.util.function.TriFunction<T, U, V, R>`

**作用**：三参函数（`BiFunction` 的三参特化），有返回值。`Event.triFunctionFirst()` 等工厂用的就是它。

**需要**：作为 lambda 实现。

**返回**：`R`。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `apply(T t, U u, V v)` | 计算结果 | 无 | `R` |
| `andThen(Function after)` | 先 `apply`，再把结果交给 `after` | `after` 非 null（null 抛 `NullPointerException`） | 组合后的 `TriFunction<T, U, V, W>` |

## 坐标与方向：`core.api.util.math`

### `BlockPos`

Reference: `net.ornithemc.osl.core.api.util.math.BlockPos`

**作用**：OSL 自己的整数方块坐标（不可变），提供打包成 `long`、距离、偏移、沿方向移动等原版在不同版本里叫法各异的功能。**它和 Minecraft 的 `BlockPos` 是两个不同的类**，不能互相赋值，需要自己转换（例如 `BlockPos.of(mcPos.getX(), mcPos.getY(), mcPos.getZ())`）。

**需要**：用 `of(x, y, z)` 或构造函数创建；`pack` / `unpack` 只做位运算、**不检查取值范围**，超范围坐标会被静默截断（见下方位布局）；要"临时可变坐标"用嵌套类 `Mutable`，要"高频复用、零分配"用 `PooledMutable`（配合 try-with-resources）。

**返回**：变换方法返回新对象（`Mutable` 系除外）；`add(0, 0, 0)` 会原样返回 `this`。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `of(int x, int y, int z)` | 新建不可变坐标 | 无 | `BlockPos` |
| `pooled(int x, int y, int z)` | 从对象池取一个可变坐标 | **必须** `close()` 归还（`PooledMutable` 实现 `AutoCloseable`），池上限 100，超出的不回收 | `BlockPos.PooledMutable` |
| `BlockPos(BlockPos pos)` / `BlockPos(int x, int y, int z)` | 拷贝 / 直接构造 | 无 | 新实例 |
| `pack(BlockPos)` / `pack(int x, int y, int z)` | 打包成 `long` | 坐标在下方表内范围内，否则截断 | `long` |
| `packX(int)` / `packY(int)` / `packZ(int)` | 只打包某一个分量（已移位，未做符号扩展） | 同上 | `long`（可直接按位或） |
| `unpack(long)` | 从 `long` 还原坐标 | `long` 必须来自 `pack` | `BlockPos` |
| `unpackX(long)` / `unpackY(long)` / `unpackZ(long)` | 只解出某一个分量（做符号扩展） | 同上 | `int` |
| `pack()` | 实例版打包（等价于 `pack(this)`） | 同 `pack` | `long` |
| `x()` / `y()` / `z()` | 三个分量 | 无 | `int` |
| `equals / hashCode` | 按当前 x/y/z 判等与求哈希（`hashCode` 为 `x + 31 * (y + 31 * z)`） | 无 | `boolean` / `int` |
| `compareTo(BlockPos)` | 排序：先 y，再 z，再 x | 无 | `int`（返回差值，不做归一化） |
| `toString()` | 形如 `BlockPos{x=1,y=2,z=3}` | 无 | `String` |
| `distanceSquared(BlockPos)` / `distanceSquared(BlockPos, boolean center)` / `distanceSquared(double x, double y, double z, boolean center)` | 平方距离；`center` 为 `true` 时按方块中心（+0.5）计算 | 无 | `double` |
| `distanceManhattan(BlockPos)` | 曼哈顿距离 | 无 | `int` |
| `add(int dx, int dy, int dz)` / `add(BlockPos)` | 平移（返回新对象） | 无 | `BlockPos` |
| `subtract(BlockPos)` | 反向平移 | 无 | `BlockPos` |
| `up() / down() / north() / south() / west() / east()`（各带 `int amount` 重载） | 沿某方向移动 1 格 / n 格 | 无 | `BlockPos` |
| `offset(Direction dir)` / `offset(Direction dir, int amount)` | 沿 `Direction` 移动 | `dir` 非 null | `BlockPos` |
| `immutable()` | 取不可变副本（基类返回 `this`，`Mutable` 返回新副本） | 无 | `BlockPos` |

#### `pack` 的位布局

`pack` 把三个 `int` 塞进一个 `long`（共 64 位），用于"把坐标当 `Map` 的键"或"只用一个 long 存档/发包"：

| 分量 | 位数 | 位偏移 | 有效取值范围（超范围会被掩码截断） |
|---|---|---|---|
| `y` | 12 | 0（最低 12 位） | -2048 ~ 2047 |
| `z` | 26 | 12 | -33554432 ~ 33554431 |
| `x` | 26 | 38（最高 26 位） | -33554432 ~ 33554431 |

- 打包：`(x & 0x3FFFFFF) << 38 | (z & 0x3FFFFFF) << 12 | (y & 0xFFF)`。
- 解包用算术右移做符号扩展，所以负数坐标能正确还原。
- **不要**把 `pack()` 的结果与原版 `BlockPos` 的长整型表示直接互换，除非你自己核对过位布局。
- **不要**把 `pack()` 的结果当成 `hashCode()`：后者是 `x + 31 * (y + 31 * z)`，两者不同。
- 因为超范围不报错，"打包再解包"可能拿回与原值不同的坐标——需要严格时请自行校验范围。

#### `BlockPos.Mutable`

**作用**：可变的坐标，避免在循环里反复创建对象。继承 `BlockPos`，重写 `x()` / `y()` / `z()`。

**需要**：不要把它当 `HashMap` 的键（`hashCode` 随内容变化）；`add(...)` 返回的是**不可变**新对象，原地移动请用 `move(...)`。

**返回**：`set` / `move` 返回 `this`（便于链式），`immutable()` 返回新副本。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `Mutable(BlockPos pos)` / `Mutable(int x, int y, int z)` | 构造 | 无 | 新实例 |
| `setX / setY / setZ(int)` | 改单个分量 | 无 | 无（void） |
| `set(int x, int y, int z)` / `set(BlockPos pos)` | 一次性设置 | 无 | `this` |
| `move(int dx, int dy, int dz)` / `move(BlockPos dpos)` / `move(Direction dir)` / `move(Direction dir, int amount)` | 相对移动 | `dir` 非 null | `this` |
| `immutable()` | 复制成不可变坐标 | 无 | 新的 `BlockPos` |

#### `BlockPos.PooledMutable`

**作用**：线程安全（内部对池加锁）的可变坐标对象池，专给"每 tick 大量临时坐标"的场景，减少 GC 压力。

**需要**：用 `acquire` 取、用 try-with-resources 归还；**归还后不能再使用**该实例（会被别的调用方复用）。

**返回**：`acquire` 返回一个已置为指定坐标的池化实例。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `acquire()` / `acquire(int x, int y, int z)` | 从池里取（池空则新建） | 无 | `PooledMutable` |
| `close()` | 归还到池（池未满 100 时才真正入池） | 只调用一次；`close()` 之后再使用属于错误 | 无（void） |

```java
try (BlockPos.PooledMutable p = BlockPos.pooled(x, y, z)) {
    p.move(Direction.UP);
    use(p.x(), p.y(), p.z());
}
```

### `Direction`

Reference: `net.ornithemc.osl.core.api.util.math.Direction`

**作用**：六个方向的枚举，自带两套"元数据编号"（2D 水平 0-3、3D 0-5）、轴信息、相反方向、绕各轴的顺/逆时针旋转，以及沿方向的单位偏移。原版不同版本里这些信息散落在多个类和 switch 中，这里集中成一份跨版本稳定的实现。

**需要**：`byName` 不认的字符串返回 `null`；`byData2d` / `byData3d` 对任意整数都取模，不抛异常；旋转方法**只对同一平面内的方向有效**，跨界会抛 `IllegalStateException`。

**返回**：见下表；全部是纯查表，无副作用。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `DOWN / UP / NORTH / SOUTH / WEST / EAST` | 六个方向（`toString()` 返回小写名） | 无 | 该常量 |
| `VALUES` | 所有方向组成的数组（公开字段，**不要修改**） | 无 | `Direction[]` |
| `byName(String)` | 按小写名查 | 名字为 `down` / `up` / `north` / `south` / `west` / `east`；`null` 返回 `null` | `Direction` 或 `null` |
| `byData2d(int)` | 按旧版水平元数据查（内部对 4 取模） | 无 | `Direction`（永远是水平方向） |
| `byData3d(int)` | 按旧版 3D 元数据查（内部对 6 取模） | 无 | `Direction` |
| `data2d()` / `data3d()` | 各自的元数据编号 | 无 | `int` |
| `axis()` | 所属轴 | 无 | `Direction.Axis` |
| `axisDirection()` | 沿轴的正负方向 | 无 | `Direction.AxisDirection` |
| `offsetX()` / `offsetY()` / `offsetZ()` | 单位偏移（不属于该轴的为 0） | 无 | `int` |
| `opposite()` | 相反方向 | 无 | `Direction` |
| `clockwise()` / `counterClockwise()` | 等价于绕 Y 轴顺/逆时针旋转 | 无 | `Direction` |
| `clockwiseX / counterClockwiseX / clockwiseY / counterClockwiseY / clockwiseZ / counterClockwiseZ` | 绕指定轴旋转 90° | 只接受该轴平面内的方向，否则抛 `IllegalStateException` | `Direction` |

> 编号速查：`byData2d` 的 0/1/2/3 依次是 `SOUTH / WEST / NORTH / EAST`；`byData3d` 的 0-5 依次是 `SOUTH / WEST / NORTH / EAST / DOWN / UP`。

#### `Direction.Axis`（枚举，实现 `Predicate<Direction>`）

**作用**：三个坐标轴，能"从坐标三元组里挑出属于自己的那个分量"，并告知自己所在平面。

**需要**：无。

**返回**：见下表。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `X / Y / Z` | 三个轴 | 无 | 该常量 |
| `plane()` | 所在平面（`X`、`Z` 为水平，`Y` 为垂直） | 无 | `Direction.Plane` |
| `isVertical()` / `isHorizontal()` | 平面判断 | 无 | `boolean` |
| `choose(int x, int y, int z)` / `choose(double x, double y, double z)` | 取出本轴对应的分量 | 无 | `int` / `double` |
| `test(Direction dir)` | 该方向是否沿本轴（`dir` 为 `null` 时返回 `false`） | 无 | `boolean` |

#### `Direction.AxisDirection`（枚举）

**作用**：表示"沿轴的哪一侧"。

**需要**：无。

**返回**：见下表。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `POSITIVE` / `NEGATIVE` | 沿轴正/负方向（`toString()` 为 `towards positive` / `towards negative`） | 无 | 该常量 |
| `offset()` | 偏移值 `+1` / `-1` | 无 | `int` |

#### `Direction.Plane`（枚举，实现 `Iterable<Direction>` 与 `Predicate<Direction>`）

**作用**：垂直平面（2 个方向）与水平平面（4 个方向），可遍历、可判断、可随机取一个。

**需要**：无。

**返回**：见下表。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `VERTICAL` / `HORIZONTAL` | 垂直（`DOWN`、`UP`）与水平（`NORTH`、`SOUTH`、`WEST`、`EAST`） | 无 | 该常量 |
| `iterator()` | 遍历本平面的方向 | 无 | `Iterator<Direction>` |
| `test(Direction dir)` | 该方向是否在本平面（`null` 返回 `false`） | 无 | `boolean` |
| `pickDirection(Random random)` | 随机取一个本平面方向 | `random` 非 null | `Direction` |

## 拓扑排序：`core.api.util.sort`

### `TopoSort`

Reference: `net.ornithemc.osl.core.api.util.sort.TopoSort`

**作用**：对"有依赖关系的对象集合"做拓扑排序，典型场景是"注册项之间有加载顺序"、"配方有前置"、"监听器要按依赖排序"。它直接作用在对象本身（`T`）上，不要求实现任何接口，也不要求可比较。

**需要**：同时给出"全部节点"和 `Map<T, Set<T>>` 依赖表（key 是节点，value 是**它的前置节点**集合）。依赖表里出现、但不在节点集合里的前置项会被**静默忽略**；节点集合里没出现在依赖表中的节点视为无前置。所有节点必须能作为 `HashMap` 的键（正确实现 `equals` / `hashCode`）。**源码没有环检测：一旦有环会死循环**（不抛异常），调用前请自己保证无环。

**返回**：排好序的 `List<T>`——前置节点总排在依赖它的节点之前；同一批"无前置"节点的相对顺序取决于传入集合的迭代顺序，**不保证稳定**。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `sort(Collection<T> unsortedNodes, Map<T, Set<T>> incomingEdges)` | 按依赖表排序 | 节点唯一、无环；`incomingEdges` 中 value 为 null 或空视为无前置 | `List<T>`（新列表；传入集合不被修改） |
| `sort(Collection<Node<T>> unsortedNodes)` | 接受内部节点包装的重载 | 参数类型是私有嵌套类，**mod 代码无法调用**（只有类内部能用） | `List<T>` |

```java
Map<String, Set<String>> deps = new HashMap<>();
deps.put("b", Set.of("a"));                                        // b 依赖 a
List<String> order = TopoSort.sort(List.of("a", "b"), deps);       // [a, b]
```
