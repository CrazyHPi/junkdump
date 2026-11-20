---
title: 19 networking
---

# 19 networking

> 一句话定位：给 mod 提供"命名通道 + 自定义负载"的点对点收发层，并在登录后自动交换双方通道表，让你能判断"对面到底会不会收"。

| 项 | 值 |
|---|---|
| 模块 id | `networking` |
| Maven | `net.ornithemc.osl-gen2:networking:0.12.0+mc13w41a-mc18w30b` |
| 版本 | `0.12.0+mc13w41a-mc18w30b`（1.12.2 命中该子工程） |
| 端 | 双端（客户端 / 服务端都有 API，包 `fabric.mod.json` 的 `environment` 为 `*`） |
| 依赖 | `ploceus.dependOslModule('networking', '0.24.0')`；传递依赖 `core`、`executors`、`text-components` |

OSL networking 在 Vanilla 的 `CustomPayload`（1.12.2 的 `CustomPayloadC2SPacket` / `CustomPayloadS2CPacket`）之上加了一层"通道注册表 + 监听器 + 握手"。通道是 `NamespacedIdentifier`（如 `example:cookie`）；收发时可以选择直接读写 `PacketBuffer`、自己实现 `PacketPayload`、或传 `byte[]`。模块在登录时会用一个内部保留通道（`osl:handshake`）交换双方的监听器列表，因此 `send` 默认只在"对面确实监听这个通道"时才真正发包，避免刷屏与无意义流量。

## 关键语义（线程 / 大小 / 握手）

| 主题 | 说明 |
|---|---|
| 监听器运行线程 | 监听器默认在**网络线程**上被调用（即 Vanilla 处理 `CustomPayload` 的线程），**不是**主线程。要改到主线程，请在回调第一行调用 `context.ensureOnMainThread()`；它检测到不在主线程时会抛异常，OSL 捕获后把同一个负载重新投递到主线程任务队列（`Minecraft#execute` / `MinecraftServer#execute`），监听器会被**再次调用一次**，第二次才在主线程上。因此 `ensureOnMainThread()` 必须放在回调最前面（在它之前做的读写会在网络线程上执行一遍）。如果不需要触碰世界 / 渲染状态，可以不调用，省一次调度。 |
| 负载大小 | OSL 只限制**通道名字符串**长度：命名空间与标识各最多 `Byte.MAX_VALUE`（127），完整 `namespace:identifier` 最多 255 字符（`StringChannelIdentifierParser.MAX_LENGTH`）。Vanilla 原本只允许 20 字符的通道名，OSL 通过 mixin 把读取上限放宽到 255。负载（payload）本身 OSL 不做长度检查，上限由 Minecraft 自己的 custom payload 包决定（源码未明确说明具体数值）。 |
| 握手时机 | 客户端在 `ClientPlayNetworkHandler#handleLogin` 结束时发一次 `osl:handshake`（内容是客户端已注册的监听器通道列表）；服务端收到后先回一份自己的列表、再登记"客户端监听哪些通道"，然后触发服务端 `PLAY_READY`；客户端收到回包后登记"服务端监听哪些通道"，再触发客户端 `PLAY_READY`。 |
| 通道表只交换一次 | 通道表来源是**已注册的监听器集合**（不是注册表）。登录之后再注册的监听器不会重新通告，`isPlayReady(channel)` 会一直是 `false`，直到重新连接。**请把监听器注册写在 mod 初始化器里。** |
| 对端没有 OSL | 如果对面是纯 Vanilla 客户端 / 服务端，握手不会发生，`isPlayReady(...)` 恒为 `false`，所有 `send`（带检查的）都会静默丢弃；只有 `sendNoCheck` 会真的发出去（由 Vanilla 自己忽略 / 处理）。 |
| 缓冲区生命周期 | 回调拿到的 `PacketBuffer` 是数据包内容的副本，回调返回后由 OSL 释放；不要在回调外保留引用（需要留存请 `copy()`）。自己传进 `send(channel, PacketBuffer)` 的缓冲区会被包对象直接引用（不再复制），发送后不要再写入或 `release()`。 |

## 通道标识符

### `ChannelIdentifiers`

Reference: `net.ornithemc.osl.networking.api.ChannelIdentifiers`

**作用**：创建 / 校验通道标识符的唯一推荐入口。通道名约定为 `<modid>:<snake_case 名>`。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `DEFAULT_NAMESPACE` | 默认命名空间常量，值为 `"minecraft"` | — | `String` |
| `MAX_LENGTH_NAMESPACE` / `MAX_LENGTH_IDENTIFIER` | 命名空间 / 标识的最大长度，均为 `Byte.MAX_VALUE`（127） | — | `int` |
| `register(String identifier)` | 用默认命名空间构造、校验并注册通道（双端可收发） | 标识合法；同通道重复注册且设置不同会抛 `IllegalArgumentException` | 注册后的 `NamespacedIdentifier` |
| `register(String namespace, String identifier)` | 同上，指定命名空间 | 命名空间 / 标识合法 | 同上 |
| `register(String identifier, boolean clientbound, boolean serverbound)` | 构造、校验并注册，同时指定可收发方向 | 同上 | 同上 |
| `register(String namespace, String identifier, boolean clientbound, boolean serverbound)` | 同上，指定命名空间 | 同上 | 同上 |
| `from(String identifier)` / `from(String namespace, String identifier)` | 只构造并校验，**不注册** | 命名空间 / 标识合法，否则抛运行时异常（`ChannelIdentifierException` / `NamespacedIdentifierException`，均在 impl 包） | `NamespacedIdentifier` |
| `legacy(String identifier)` / `legacy(String namespace, String identifier)` | 构造 1.13-pre2 及以下的旧式通道名（`namespace\|identifier`），**不做任何校验** | 无（允许大写、允许空命名空间） | `NamespacedIdentifier`（实际是 `LegacyChannelIdentifier`） |
| `validate(NamespacedIdentifier id)` | 校验并原样返回；不合法则抛异常 | 命名空间 / 标识合法 | 传入的 `NamespacedIdentifier` |
| `validateNamespace(String)` / `validateIdentifier(String)` | 单独校验长度与字符集 | 只允许 `[a-z0-9-._]`，标识额外允许 `/` | 校验通过的字符串 |

注意：`DEFAULT_NAMESPACE` 是 `minecraft`，所以 `register("foo")` 得到的是 `minecraft:foo`。**自己的通道务必显式给命名空间**，否则会和 Vanilla / 别的 mod 撞名。

```java
public static final NamespacedIdentifier COOKIE = ChannelIdentifiers.register("example", "cookie");
// -> example:cookie，双向通道
```

### `ChannelRegistry`

Reference: `net.ornithemc.osl.networking.api.ChannelRegistry`

**作用**：底层通道注册表。想在注册时直接给一个已构造好的 `NamespacedIdentifier` 时用它；一般用 `ChannelIdentifiers` 就够。

**需要**：通道必须先注册，才能在其上注册监听器；未注册的通道被视为 closed，收不到也发不出。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `register(NamespacedIdentifier channel)` | 以默认设置注册：`clientbound = true`、`serverbound = true` | 同一通道不得以不同设置重复注册，否则抛 `IllegalArgumentException`；相同设置重复注册是幂等的 | 注册后的通道（原样返回） |
| `register(NamespacedIdentifier channel, boolean clientbound, boolean serverbound)` | 以指定方向注册。`clientbound`：期望客户端收（服务端才能发往客户端）；`serverbound`：期望服务端收（客户端才能发往服务端） | 同上 | 同上 |

```java
// 只允许客户端 -> 服务端
ChannelRegistry.register(ChannelIdentifiers.from("example", "input"), false, true);
```

### `LegacyChannelIdentifier`

Reference: `net.ornithemc.osl.networking.api.LegacyChannelIdentifier`

**作用**：`NamespacedIdentifier` 的一个子类型，表示 1.13-pre2 及以下那种没有强格式约束的旧式通道名（约定用 `|` 分隔，例如 `MC|Brand`、`REGISTER`）。

**需要**：`namespace()` 允许为空字符串；此时 `toString()` 只输出标识本身（不带分隔符）。不需要实现它，用 `ChannelIdentifiers.legacy(...)` 构造即可。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `SEPARATOR` | 旧式分隔符 `'\|'`（仅约定，不做强制） | — | `char` |
| `separator()` | 返回 `SEPARATOR` | — | `char` |
| `namespaced(String)` / `prefixed(String)` / `suffixed(String)` | 复制出改命名空间 / 加前缀 / 加后缀的新标识 | 参数为 `null` 时的行为（源码未明确说明） | 新的 `LegacyChannelIdentifier` |
| `subidentifier(int beginIndex)` / `subidentifier(int beginIndex, int endIndex)` | 对标识部分取子串，复制出新标识 | 下标越界抛 `StringIndexOutOfBoundsException` | 新的 `LegacyChannelIdentifier` |

### `StringChannelIdentifierParser`

Reference: `net.ornithemc.osl.networking.api.StringChannelIdentifierParser`

**作用**：通道标识符与 `String` 的互转。协议里传的就是字符串，自己实现负载或调试时用得上。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `MAX_LENGTH` | 字符串形式的最大长度 = 127 + 1 + 127 = 255 | — | `int` |
| `fromString(String s)` | 解析字符串：先找 `\|`（有则视为旧式），否则找 `:`；都找不到则当作"空命名空间 + 该字符串"的旧式标识。**不做校验**，结果可能不合法 | 非 `null` | `NamespacedIdentifier`（可能不合法） |
| `fromStringOrThrow(String s)` | 同上，但新式标识会走 `ChannelIdentifiers.validate`；旧式分支仍不校验 | 非 `null` | 合法的 `NamespacedIdentifier`；解析失败抛运行时的 `ChannelIdentifierParseException`（impl 包） |
| `toString(NamespacedIdentifier id)` | 转成字符串（等价于 `id.toString()`） | 非 `null` | `String` |

### `IdentifierChannelIdentifierParser`

Reference: `net.ornithemc.osl.networking.api.IdentifierChannelIdentifierParser`

**作用**：通道标识符与 Minecraft 的 `net.minecraft.resource.Identifier` 互转（1.12.2 映射名；子工程专属类，仅在 1.12.2 这类有 `Identifier` 的版本存在）。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `fromIdentifier(Identifier id)` | 用 `id.getNamespace()` / `id.getPath()` 构造，**不校验** | 非 `null` | `NamespacedIdentifier`（可能不合法） |
| `fromIdentifierOrThrow(Identifier id)` | 同上但做校验 | 非 `null` | 合法的 `NamespacedIdentifier`；失败抛 `ChannelIdentifierParseException`（impl 包，运行时） |
| `toIdentifier(NamespacedIdentifier id)` | 转成 `new Identifier(namespace, identifier)` | 非 `null` | `net.minecraft.resource.Identifier` |

## 缓冲区与负载序列化

### `PacketBuffer`

Reference: `net.ornithemc.osl.networking.api.PacketBuffer`

**作用**：OSL 的读写缓冲，直接 `extends io.netty.buffer.ByteBuf`：既保留了 Netty 的全部字节操作（转发给内部的 `net.minecraft.network.PacketByteBuf`），又补上了 Minecraft 风格的 `VarInt` / 字符串 / NBT / 物品 / 文本 / 坐标等便携读写方法。

**需要**：监听器回调里由 OSL 提供；发送时用 `PacketBuffers.make()` 自己造，或直接传 `PacketBuffer` 给 `send`。写入顺序必须和读取顺序完全一致（自描述格式，没有字段名）。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `PacketBuffer(ByteBuf delegate)` / `PacketBuffer(PacketByteBuf delegate)` | 包装一个已有缓冲区（不复制） | 非 `null` | — |
| `readVarInt()` / `readVarLong()` | 读 7 bit/字节、最高位为续位的变长整数 | 数据完整 | `int` / `long`；超长（>5 / >10 字节）抛 `RuntimeException` |
| `writeVarInt(int)` / `writeVarLong(long)` | 写变长整数 | — | `this`（`ByteBuf`） |
| `readByteArray()` / `readByteArray(int maxLength)` | 先读 `VarInt` 长度，再读该数量的字节 | 无参时 `maxLength` = 剩余可读字节数 | `byte[]`；长度超限抛 `RuntimeException` |
| `writeByteArray(byte[])` | 写 `VarInt` 长度 + 原始字节 | 非 `null` | `ByteBuf` |
| `readIntArray()` / `readIntArray(int maxLength)` / `writeIntArray(int[])` | 长度前缀 + 每个元素 `VarInt` | 同上 | `int[]` / `ByteBuf` |
| `readLongArray()` / `readLongArray(int maxLength)` / `writeLongArray(long[])` | 长度前缀 + 每个元素 `VarLong` | 同上 | `long[]` / `ByteBuf`；长度超限时抛的是 `IllegalStateException`（与其它数组的 `RuntimeException` 不同，源码如此） |
| `readString()` / `readString(int maxLength)` | 读 `VarInt` 字节长度 + UTF-8 内容 | 无参上限 `Short.MAX_VALUE`（32767）；解码时字节层允许 `maxLength * 4` | `String`；超限 / 负数长度抛 `RuntimeException` |
| `writeString(String)` / `writeString(String, int maxLength)` | 写 `VarInt` 字节长度 + UTF-8 内容 | 无参上限 `Short.MAX_VALUE`；UTF-8 字节数超 `maxLength` 抛 `RuntimeException` | `ByteBuf` |
| `readEnum(Class<T> type)` / `writeEnum(Enum<?> value)` | 按序号 `VarInt` 读写枚举 | `type` 有常量 | `T` / `ByteBuf`；读到越界序号抛 `ArrayIndexOutOfBoundsException`（源码未做范围检查） |
| `readCollection(IntFunction<C> constructor, Function<PacketBuffer,T> reader)` / `readList(Function<PacketBuffer,T> reader)` | 先读 `VarInt` 元素个数，再逐个用回调读 | 读写顺序对称 | 集合 / `List` |
| `writeCollection(Collection<T>, BiConsumer<PacketBuffer,T> writer)` | 写元素个数 + 逐个写入 | — | `ByteBuf` |
| `readDate()` / `writeDate(Date)` | 按 `long`（毫秒）读写 | — | `Date` / `ByteBuf` |
| `readUuid()` / `writeUuid(UUID)` | 按两个 `long` 读写 | — | `UUID` / `ByteBuf` |
| `readBlockPos()` / `writeBlockPos(BlockPos)` | 按 `long` 打包读写坐标 | 仅当该 MC 版本的 `BlockPos` 支持 `toLong()` / `fromLong()`；1.12.2 的 `BlockPos` 继承 `Vec3i`，**支持** | `BlockPos` / `ByteBuf`；不支持时抛 `UnsupportedOperationException` |
| `readIdentifier()` / `writeIdentifier(Identifier)` | 以字符串形式读写 `net.minecraft.resource.Identifier` | 字符串合法 | `Identifier` / `ByteBuf` |
| `readNamespacedIdentifier()` / `writeNamespacedIdentifier(NamespacedIdentifier)` | 以 `namespace:path` 字符串形式读写 | 读取时会走 core 的解析（失败抛运行时异常） | `NamespacedIdentifier` / `ByteBuf` |
| `readText()` / `writeText(Text)` | 以 JSON 字符串读写 `net.minecraft.text.Text` | JSON 长度上限 `0x40000` | `Text` / `ByteBuf` |
| `readTextComponent()` / `writeTextComponent(TextComponent)` | 以 JSON 字符串读写 OSL 的 `TextComponent`（text-components 模块） | 同上 | `TextComponent` / `ByteBuf` |
| `readNbtCompound()` / `writeNbtCompound(NbtCompound)` | 读写 NBT 复合标签（转发给 `PacketByteBuf`） | — | `NbtCompound` / `ByteBuf` |
| `readItem()` / `writeItem(ItemStack)` | 读写物品堆（转发给 `PacketByteBuf`） | — | `ItemStack` / `ByteBuf` |
| 其余 `ByteBuf` 方法 | `capacity()`、`readerIndex()`、`readableBytes()`、`copy()`、`retain()`、`release()`、各定长读写等**全部**原样转发到内部缓冲区 | — | 与 Netty `ByteBuf` 一致 |

### `PacketBuffers`

Reference: `net.ornithemc.osl.networking.api.PacketBuffers`

**作用**：`PacketBuffer` 的工厂与转换工具。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `make()` | 新建一个空的堆缓冲区（`Unpooled.buffer()` 包装） | — | `PacketBuffer` |
| `make(IOConsumer<PacketBuffer> writer)` | 新建并立刻用 writer 写入 | writer 抛 `IOException` 会向外传播 | 已写入的 `PacketBuffer` |
| `wrap(byte[] bytes)` | 把字节数组包装成缓冲区（**不复制**，不加长度前缀） | 非 `null` | `PacketBuffer` |
| `unwrap(PacketBuffer buffer)` | 取出 `[0, writerIndex)` 的字节并**释放**该缓冲区 | 调用后 buffer 不可再用 | `byte[]` |
| `wrapped(ByteBuf buffer)` | 包装任意 Netty `ByteBuf` | 非 `null` | `PacketBuffer` |
| `unwrapped(PacketBuffer buffer)` | 取出内部的 `PacketByteBuf`（不复制、不释放） | 非 `null` | `net.minecraft.network.PacketByteBuf` |

### `PacketPayload`

Reference: `net.ornithemc.osl.networking.api.PacketPayload`

**作用**：把"一组字段"封装成可序列化负载的接口。实现它就能用 `send(channel, payload)` 发送、用 `registerListener(channel, initializer, listener)` 接收，不用手写缓冲区代码。

**需要**：实现 `read` / `write`，两者顺序必须严格对称；同时提供一个无参构造（或一个 `Supplier` 工厂）供接收端实例化。类不必是 public 的，但接收端要通过 `Supplier` 拿到实例。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `read(PacketBuffer buffer)` | 从缓冲区反序列化自身字段 | 与 `write` 的顺序严格一致 | 无（void），可抛 `IOException` |
| `write(PacketBuffer buffer)` | 把自身字段序列化进缓冲区 | 同上 | 无（void），可抛 `IOException` |

```java
public class CookiePayload implements PacketPayload {
    public int count;

    public CookiePayload() { }
    public CookiePayload(int count) { this.count = count; }

    @Override public void read(PacketBuffer buffer) throws IOException { this.count = buffer.readVarInt(); }
    @Override public void write(PacketBuffer buffer) throws IOException { buffer.writeVarInt(this.count); }
}
```

## 客户端收发（仅客户端可用的类）

### `ClientPlayNetworking`

Reference: `net.ornithemc.osl.networking.api.client.ClientPlayNetworking`

**作用**：客户端侧的收 / 发入口。监听器在 mod 初始化器里注册；发送时默认先检查"服务端是否在监听该通道"。

**需要**：通道必须已用 `ChannelIdentifiers` / `ChannelRegistry` 注册；服务端监听器对应的通道必须 `serverbound = true`，客户端监听器对应的通道必须 `clientbound = true`。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `registerListener(NamespacedIdentifier channel, Supplier<T> initializer, ClientPacketListener.Payload<T> listener)` | 以负载对象方式接收：先用 `initializer` 造实例，再 `payload.read(buffer)`，再回调 | 通道已注册且 `clientbound`；同一通道**只能有一个**监听器，重复注册抛 `IllegalArgumentException`；通道不是 clientbound 也抛 `IllegalArgumentException` | 无（void） |
| `registerListener(NamespacedIdentifier channel, ClientPacketListener.Buffer listener)` | 直接拿到 `PacketBuffer` 自己读 | 同上 | 无（void） |
| `registerLegacyListener(NamespacedIdentifier channel, ClientPacketListener.Bytes listener)` | 拿到 `byte[]`。实现是 `buffer.readByteArray()`，即按"VarInt 长度前缀 + 原始字节"解析 | 同上 | 无（void） |
| `unregisterListener(NamespacedIdentifier channel)` | 移除该通道的监听器 | 通道已注册 | 无（void） |
| `isPlayReady()` | 连接是否已就绪（已完成握手、可以安全发送） | — | `boolean`；未连接或握手未完成时为 `false` |
| `isPlayReady(NamespacedIdentifier channel)` | 该通道是否可发：连接就绪**且服务端有该通道的监听器** | 通道已注册 | `boolean` |
| `send(NamespacedIdentifier channel, PacketPayload payload)` | 发送负载对象 | 仅当 `isPlayReady(channel)` 为真才真正发送，否则静默丢弃（`payload.write` 不会被调用） | 无（void） |
| `send(NamespacedIdentifier channel, IOConsumer<PacketBuffer> writer)` | 用 writer 现场写入负载 | 同上 | 无（void） |
| `send(NamespacedIdentifier channel, PacketBuffer buffer)` | 直接发送缓冲区（包对象引用它，不复制） | 同上 | 无（void） |
| `send(NamespacedIdentifier channel, byte[] bytes)` | 直接发送原始字节（**不加**长度前缀） | 同上 | 无（void） |
| `sendNoCheck(...)`（4 个重载，参数同上） | 跳过通道检查直接发。**慎用**：对面没监听时会白发包、刷日志 | 通道仍需注册且方向匹配（`serverbound`） | 无（void）；写负载抛 `IOException` 时只记日志 |

> `send(channel, byte[])` 与 `registerLegacyListener` 的格式并不对称：前者发原始字节，后者按带 `VarInt` 长度前缀的格式读。要对接 `registerLegacyListener`，发送端应自己 `writeByteArray(bytes)`，或收端改用 `registerListener(channel, Buffer)` 自行读取（源码如此，未做额外说明）。

### `ClientPacketListener`

Reference: `net.ornithemc.osl.networking.api.client.ClientPacketListener`

**作用**：客户端收包回调的父接口，按收到的数据类型分成三个 `@FunctionalInterface` 子接口。

**需要**：不需要直接实现父接口，用 `ClientPacketListener.Buffer` / `.Bytes` / `.Payload<T>` 之一，或用 lambda；`handle` 抛出的 `IOException` 会被 OSL 记录为警告，不会中断连接。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `handle(Context ctx, T data)` | 收到数据时调用 | `ctx` 由 OSL 传入 | 无（void），可抛 `IOException` |
| `Payload<T extends PacketPayload>` | 声明 `T` 为负载对象 | `T` 有可用的 `Supplier` | — |
| `Buffer` | 声明 `T` = `PacketBuffer` | — | — |
| `Bytes` | 声明 `T` = `byte[]` | — | — |
| `Context#minecraft()` | 当前 `net.minecraft.client.Minecraft` 实例 | — | `Minecraft` |
| `Context#networkHandler()` | 收到该包的 `net.minecraft.client.network.handler.ClientPlayNetworkHandler` | — | `ClientPlayNetworkHandler` |
| `Context#ensureOnMainThread()` | 断言当前在主线程；不在则抛内部异常，OSL 捕获后把同一负载重新投递到主线程并**再调用一次**回调 | 应作为回调第一行调用 | 无（void） |

### `ClientConnectionEvents`

Reference: `net.ornithemc.osl.networking.api.client.ClientConnectionEvents`

**作用**：客户端连接生命周期事件（含连接整合服务器 / 单人世界）。

**需要**：在 mod 初始化器里 `XXX.register(listener)`；`Event` 类型来自 core 模块，重复注册会按注册顺序全部调用。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `LOGIN` | 登录成功时触发（`ClientPlayNetworkHandler#handleLogin` 末尾）。此时客户端刚发出通道表，**还不能安全发数据** | 回调类型 `Consumer<LoginContext>` | 无（void） |
| `PLAY_READY` | 收到服务端通道表、通道登记完成后触发。这是可以安全发数据的时刻 | `Consumer<PlayReadyContext>` | 无（void） |
| `DISCONNECT` | 客户端离开世界时触发：在 `Minecraft#setWorld(null, ...)` 之前（此时世界字段尚未清空）。断开原因取自此前收到的断开包 / `ClientPlayNetworkHandler#onDisconnect` 的文本 | `Consumer<DisconnectContext>` | 无（void） |
| `ConnectionContext#minecraft()` | 当前 `Minecraft` | — | `Minecraft` |
| `ConnectionContext#worldName()` | 单人世界名；连远程服务器时为 `null` | — | `String` |
| `ConnectionContext#serverAddress()` / `#serverPort()` | 服务器地址 / 端口；单人世界时分别为 `null` / `-1` | — | `String` / `int` |
| `ConnectionContext#isMultiplayer()` | 是否连的远程服务器（单人整合服务器为 `false`） | — | `boolean` |
| `ConnectionContext#isServerLocal()` | （已废弃，请改用 `isMultiplayer()`）等价于 `!isMultiplayer()` | — | `boolean` |
| `DisconnectContext#disconnectReason()` | 断开原因文本；自己退出 / 关游戏时为 `null` | — | `TextComponent`（text-components 模块） |

```java
ClientConnectionEvents.PLAY_READY.register(ctx -> {
    if (ClientPlayNetworking.isPlayReady(COOKIE)) {
        ClientPlayNetworking.send(COOKIE, new CookiePayload(3));
    }
});
```

## 服务端收发

### `ServerPlayNetworking`

Reference: `net.ornithemc.osl.networking.api.server.ServerPlayNetworking`

**作用**：服务端侧的收 / 发入口。除单播外还提供"发给一组玩家 / 某个维度 / 全员"的批量发送（即广播）重载。

**需要**：通道必须已注册；服务端监听器的通道需 `serverbound = true`，发往客户端的通道需 `clientbound = true`。所有 `send` 都按"该玩家是否在监听此通道"逐个过滤。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `registerListener(NamespacedIdentifier channel, Supplier<T> initializer, ServerPacketListener.Payload<T> listener)` | 以负载对象方式接收 | 通道已注册且 `serverbound`；同一通道只能一个监听器，重复注册或方向不对抛 `IllegalArgumentException` | 无（void） |
| `registerListener(NamespacedIdentifier channel, ServerPacketListener.Buffer listener)` | 直接拿 `PacketBuffer` | 同上 | 无（void） |
| `registerLegacyListener(NamespacedIdentifier channel, ServerPacketListener.Bytes listener)` | 拿 `byte[]`（按 `VarInt` 长度前缀解析） | 同上 | 无（void） |
| `unregisterListener(NamespacedIdentifier channel)` | 移除监听器 | 通道已注册 | 无（void） |
| `isPlayReady(ServerPlayerEntity player)` | 该玩家的连接是否已就绪 | `player` 非 `null` 且在线 | `boolean` |
| `isPlayReady(ServerPlayerEntity player, NamespacedIdentifier channel)` | 该玩家是否监听该通道 | 通道已注册 | `boolean` |
| `send(ServerPlayerEntity player, NamespacedIdentifier channel, PacketPayload \| IOConsumer<PacketBuffer> \| PacketBuffer \| byte[])` | 发给单个玩家（4 个重载） | 仅当 `isPlayReady(player, channel)` 为真才发 | 无（void） |
| `send(Iterable<ServerPlayerEntity> players, NamespacedIdentifier channel, ...)` | 发给指定玩家集合（4 个重载） | 逐个过滤：只发给在监听该通道的玩家；若一个都没有，负载不会被写入 | 无（void） |
| `send(int dimension, NamespacedIdentifier channel, ...)` | 发给某个维度的所有玩家（4 个重载） | 同上，额外按 `player.dimension == dimension` 过滤 | 无（void） |
| `send(NamespacedIdentifier channel, ...)` | 发给服务器上所有玩家（4 个重载）**——这就是"广播"** | 同上 | 无（void） |
| `sendNoCheck(...)` | 与上面四组一一对应的 16 个重载，跳过通道检查。**慎用** | 通道仍需注册且 `clientbound` | 无（void） |

**批量发送的返回值与副作用**：`PacketPayload` / `IOConsumer` 版本会为整批只构造**一个**包对象，再逐个 `sendPacket`；写负载抛 `IOException` 时只记日志，不抛给调用方。若目标是"所有玩家"，本方法在每个调用点都会遍历一次在线玩家（1.12.2 的 `PlayerManager` 列表）。

```java
// 广播给所有在监听 example:cookie 的玩家
ServerPlayNetworking.send(COOKIE, new CookiePayload(7));
// 只发给某个玩家
ServerPlayNetworking.send(player, COOKIE, buf -> buf.writeVarInt(42));
```

### `ServerPacketListener`

Reference: `net.ornithemc.osl.networking.api.server.ServerPacketListener`

**作用**：服务端收包回调的父接口，结构与客户端版对应，额外能拿到发包玩家。

**需要**：用三个 `@FunctionalInterface` 子接口之一实现；`handle` 抛的 `IOException` 会被记录为警告。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `handle(Context ctx, T data)` | 收到数据时调用 | — | 无（void），可抛 `IOException` |
| `Payload<T extends PacketPayload>` / `Buffer` / `Bytes` | 三种数据类型声明 | — | — |
| `Context#server()` | 当前 `net.minecraft.server.MinecraftServer` | — | `MinecraftServer` |
| `Context#networkHandler()` | 收到该包的 `net.minecraft.server.network.handler.ServerPlayNetworkHandler` | — | `ServerPlayNetworkHandler` |
| `Context#player()` | 发来该包的 `net.minecraft.server.entity.living.player.ServerPlayerEntity` | — | `ServerPlayerEntity` |
| `Context#ensureOnMainThread()` | 同客户端：非主线程时抛内部异常，OSL 会把负载重新投递到主线程并再调用一次回调 | 应作为回调第一行调用 | 无（void） |

### `ServerConnectionEvents`

Reference: `net.ornithemc.osl.networking.api.server.ServerConnectionEvents`

**作用**：服务端连接生命周期事件（含整合服务器）。

**需要**：在 mod 初始化器里注册；`LOGIN` 在 `PlayerManager#onLogin` 末尾触发，`DISCONNECT` 在 `PlayerManager#remove` 头部（以及服务器停机）触发。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `LOGIN` | 玩家登录成功时触发。此时尚未收到客户端通道表，**还不能安全发数据** | `Consumer<LoginContext>` | 无（void） |
| `PLAY_READY` | 收到客户端通道表、登记完成后触发。这是可以安全发数据的时刻 | `Consumer<PlayReadyContext>` | 无（void） |
| `DISCONNECT` | 玩家断开时触发（`PlayerManager#remove` 头部）。服务器停机时还会在 `MinecraftServer#stop` 末尾对所有在线玩家补发一次 | `Consumer<DisconnectContext>` | 无（void） |
| `ConnectionContext#server()` | 当前 `MinecraftServer` | — | `MinecraftServer` |
| `ConnectionContext#player()` | 本次连接对应的 `ServerPlayerEntity` | — | `ServerPlayerEntity` |
| `DisconnectContext#disconnectReason()` | 断开原因文本；自己退出时为 `null` | — | `TextComponent` |

```java
ServerConnectionEvents.PLAY_READY.register(ctx -> {
    // 此刻 ctx.player() 已确认在监听我们注册过的通道
    ServerPlayNetworking.send(ctx.player(), COOKIE, new CookiePayload(1));
});
```

## 典型组合：C→S 请求 / S→C 回应

```java
// 共享
public static final NamespacedIdentifier REQ = ChannelIdentifiers.register("example", "req");

// 客户端 initClient()
ClientPlayNetworking.registerListener(REQ, (ctx, buf) -> {
    ctx.ensureOnMainThread();              // 第一行，保证后续在主线程
    int answer = buf.readVarInt();
});

// 服务端 init()
ServerPlayNetworking.registerListener(REQ, (ctx, buf) -> {
    ctx.ensureOnMainThread();
    int n = buf.readVarInt();
    ServerPlayNetworking.send(ctx.player(), REQ, b -> b.writeVarInt(n * 2));
});
```
