---
title: 09 config
---

# 09 config

> 一句话定位：OSL 的配置框架 —— 用「选项 + 选项组」声明配置，交给 `ConfigManager` 按作用域（全局 / 存档）自动读写。

| 项 | 值 |
|---|---|
| 模块 id | `config` |
| Maven | `net.ornithemc.osl-gen2:config:0.6.3+mc15w40a-mc1.12.2` |
| 端 | 双端 |
| 依赖 | `ploceus.dependOslModule('config', '0.24.0')` |
| 适用版本 | 本仓库 1.12.2 子工程（`config-mc15w40a-mc1.12.2`，覆盖 15w40a ~ 1.12.2） |
| 前置模块 | `osl-core`、`osl-entrypoints`、`osl-lifecycle-events`（由 OSL 自带入口点自动初始化） |

本模块提供一套「声明式」配置系统：你把若干**选项**（`BooleanOption`、`IntegerOption` 等）按**选项组**登记进一个 `Config`，再把 `Config` 注册给 `ConfigManager`；之后配置的值会在作用域（`ConfigScope`）启动时自动从磁盘读入、在作用域关闭时自动写回。
模块同时提供三套序列化后端：**JSON 文件**（默认落盘格式）、**NBT**（嵌进 `NbtCompound`）、**网络**（`PacketByteBuf`），三者共用同一套 `Option` / 注册表基础设施，因此自定义选项类型时三种格式要分别注册序列化器。

模块的入口点已在 `fabric.mod.json` 中注册（`init` / `client-init` / `server-init`），你**不需要**手动调用任何初始化方法，只需在自己的入口点里 `ConfigManager.register(...)`。

## 1. 生命周期：作用域、加载阶段、注册

### `ConfigScope`

Reference: `net.ornithemc.osl.config.api.ConfigScope`

**作用**：声明「这份配置在什么范围内有效」。配置在其作用域被初始化时加载、在作用域关闭时保存并卸载；作用域不活跃时读取选项会抛异常，因此必须先确认作用域已激活。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `GLOBAL` | 全局配置：对整个游戏生效，客户端与专用服务器都使用它。根目录是客户端 `gameDir` / 服务端 `runDir`；配置落在 `<根>/config/` 下 | 无 | 枚举常量 |
| `WORLD` | 存档配置：只对某个存档生效。根目录是该存档目录；配置落在 `<存档>/config/` 下 | 无 | 枚举常量 |

**时机（1.12.2 实际行为，来自模块自带初始化器）**：
- `GLOBAL`：客户端在 `MinecraftClientEvents.START` 建立并进入 `START` 阶段，`READY` 阶段在 `MinecraftClientEvents.READY`，`STOP` 时卸载；专用服务器对应 `MinecraftServerEvents.START` / `READY` / `STOP`。
- `WORLD`：由服务端事件驱动 —— `LOAD_WORLD` 建立并进入 `START`，`READY_WORLD` 进入 `READY`，`STOP` 时卸载并销毁。客户端单人游戏里的集成服务器同样会触发这些事件，所以单机打开存档时 `WORLD` 配置也会加载（客户端侧没有单独处理 `WORLD` 作用域 —— 源码中客户端初始化器只处理 `GLOBAL`）。

### `LoadingPhase`

Reference: `net.ornithemc.osl.config.api.LoadingPhase`

**作用**：声明「这份配置在作用域的哪个时刻被读入」。同一作用域里的配置会分两批加载，便于把「别人初始化前就要用的值」和「依赖其他系统已就绪的值」分开。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `START` | 在作用域启动时、作用域尚未完成初始化之前加载 | 无 | 枚举常量 |
| `READY` | 在作用域完全初始化之后加载 | 无 | 枚举常量 |

> 加载顺序（源码）：`Config.load()`（把配置与选项标记为已加载）→ `Config.resetAll()`（所有选项回到默认值）→ 读文件并覆盖。也就是说**文件里缺失的选项一定是默认值**，不会残留上一次运行的值。

### `ConfigManager`

Reference: `net.ornithemc.osl.config.api.ConfigManager`

**作用**：配置的注册与手动保存入口。整个模块只有这两个公开方法 —— 加载 / 卸载由作用域生命周期驱动，没有公开的 load/unload API。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `register(Config config)` | 把配置登记到其 `getScope()` 对应的作用域管理器，并立即调用该配置的 `init()`。若该作用域的管理器尚未建立，注册会被推迟到作用域建立的那一刻（通过内部就绪事件补做） | 配置不能为 `null`；同一作用域内 `namespace:name` 必须唯一，重复注册**另一个实例**会抛 `IllegalStateException`（同一实例重复注册是允许的、无副作用） | 无（void） |
| `save(Config config)` | 立即用 `config.getType()` 指定的文件序列化器 + `SerializationSettings.forFile()` 把配置写盘；目录不存在会自动创建 | 配置通常应已加载；写失败时异常被 `printStackTrace` 吞掉，不向外抛 | 无（void） |

**注意**：应在自己的入口点（`init` / `initClient` / `initServer`）里注册。注册晚于该作用域的 `START` 加载也能成功（`init()` 会被调用），但由于 `load` 只在作用域事件里被调用一次，之后再注册的配置不会收到加载，读值会抛 `IllegalStateException`。

### `ConfigRegistries`

Reference: `net.ornithemc.osl.config.api.ConfigRegistries`

**作用**：本模块四个内部注册表的 `RegistryKey` 常量。只有写「自定义序列化体系」时才需要直接引用它们；日常 `register` / `get` 已被封装在各 `Serializers` 类里。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `SERIALIZER_TYPE` | 序列化器**格式**注册表（`SerializerType`）的 key | 无 | `RegistryKey`（裸类型，源码中未带泛型参数） |
| `CONFIG_SERIALIZER` | 整份 `Config` 序列化器注册表的 key | 无 | 同上 |
| `OPTION_SERIALIZER` | `Option` 序列化器注册表的 key | 无 | 同上 |
| `OBJECT_SERIALIZER` | 普通对象序列化器注册表（按格式再分表）的 key | 无 | 同上 |

## 2. Config 与选项组

### `Config`

Reference: `net.ornithemc.osl.config.api.config.Config`

**作用**：一份配置的契约 —— 身份信息（命名空间、名称、文件名）、生命周期（作用域、加载阶段）、落盘格式（序列化器类型）以及选项组集合。**实现者**：直接实现本接口，或继承 `BaseConfig`（推荐）。这些属性被当作不可变值使用（序列化与目录布局都要用），实现时不要返回会变化的值。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `getNamespace()` | 配置命名空间。每个命名空间在作用域的 config 目录下拥有独立子目录，通常取 mod id | 可以为 `null`（此时不建子目录） | `String` |
| `getName()` | 显示名，可以是原始字符串或翻译键；也参与「同作用域唯一性」判定（与命名空间拼成 `namespace:name`） | 无 | `String` |
| `getSaveName()` | 落盘文件名（含扩展名），如 `example-config.json` | 无 | `String` |
| `getScope()` | 这份配置在哪个作用域生效 | 无 | `ConfigScope` |
| `getLoadingPhase()` | 在作用域的哪个阶段读入 | 无 | `LoadingPhase` |
| `getType()` | 落盘使用的**文件**序列化器类型 | 必须是 `FileSerializerType`；内置只有 `SerializerTypes.JSON` | `FileSerializerType<?>` |
| `getVersion()` | 配置版本号，会作为元数据写进文件 / 网络包 | 无 | `int` |
| `init()` | 注册成功后由框架调用；在这里登记选项、做其余初始化 | 注册时被调用一次；不要在此时读值（选项还没加载） | 无（void） |
| `load()` | 框架在作用域加载时调用，把配置及其选项标记为「已加载」 | 由框架调用，mod 一般不要调用 | 无（void） |
| `unload()` | 框架在作用域关闭时调用，把配置及选项标记为「未加载」 | 由框架调用 | 无（void） |
| `getGroups()` | 所有选项组（按登记顺序） | 无 | `Collection<OptionGroup>` |
| `getGroup(String name)` | 按名字取选项组 | `name` 为组名 | `OptionGroup`，不存在时返回 `null` |
| `resetAll()` | 把所有选项恢复为默认值 | 配置必须已加载，否则抛 `IllegalStateException` | 无（void） |

### `BaseConfig`

Reference: `net.ornithemc.osl.config.api.config.BaseConfig`

**作用**：`Config` 的骨架实现，替你管理选项组的登记、加载、重置与查询；你只需要实现 7 个属性 getter，并在 `init()` 里登记选项。**mod 作者要做的**：`extends BaseConfig`，在 `init()` 里调用 `registerOptions(...)`，并把选项实例放在静态字段里方便全局读取。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `BaseConfig()` | 建立空配置（内部用 `LinkedHashMap` 保持组顺序） | `protected`，只能被子类调用 | 无（构造） |
| `registerOptions(String group, Option... options)` | 把一批选项登记到名为 `group` 的组；组不存在会自动创建 | `protected final`；必须在 `init()`（即配置未加载）时调用；加载后调用抛 `IllegalStateException`；组内选项名重复抛 `IllegalStateException`；传入 0 个选项是空操作 | 无（void） |
| `getGroups()` / `getGroup(String name)` | 查询选项组（成组 getter） | 无 | `Collection<OptionGroup>` / `OptionGroup`（后者不存在时为 `null`） |
| `resetAll()` | 逐组重置为默认值 | 配置必须已加载 | 无（void） |
| `load()` / `unload()` | 级联到各组；`load` 先把配置标记为已加载，`unload` 结束后再标记为未加载 | 由框架调用 | 无（void） |
| `requireLoaded()` | 未加载时抛 `IllegalStateException("this config is not loaded!")` | 无 | 无（void） |
| `toString()` | 返回「类名[配置名]」 | 无 | `String` |

### `OptionGroup`

Reference: `net.ornithemc.osl.config.api.config.option.group.OptionGroup`

**作用**：选项的命名容器。组名既是显示名也是序列化用的键（JSON/NBT 里的对象名），因此**组名在配置内必须唯一**。一般由 `registerOptions` 隐式创建，很少手动 `new`。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `OptionGroup(String name)` | 建立空组 | `name` 在所属配置内唯一 | 无（构造） |
| `getName()` | 组名 | 无 | `String` |
| `getOptions()` | 组内所有选项（按登记顺序） | 无 | `Collection<Option>` |
| `getOption(String name)` | 按名字取选项 | `name` 为选项名 | `Option`，不存在时 `null` |
| `registerOptions(Option... options)` | 登记一批选项；同一实例重复登记无副作用 | 组不能处于已加载状态（否则 `IllegalStateException`）；同名但不同实例抛 `IllegalStateException("option name ... is not unique in group ...")` | 无（void） |
| `resetAll()` | 组内选项全部重置为默认值 | 组必须已加载 | 无（void） |
| `load()` / `unload()` | 级联加载 / 卸载组内选项 | 由配置调用 | 无（void） |
| `requireLoaded()` | 未加载时抛 `IllegalStateException("this option group is not loaded!")` | 无 | 无（void） |

## 3. 选项

### `Option`

Reference: `net.ornithemc.osl.config.api.config.option.Option`

**作用**：单个配置项的最小契约（名字、描述、默认值判定、重置、加载状态）。**实现者**：继承 `BaseOption`（不可变值类型）或 `ModifiableOption`（可变值类型）；内置选项已覆盖常用类型，通常不用直接实现本接口。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `getName()` | 选项显示名（也可作翻译键）；同时是序列化键，**组内唯一** | 无 | `String` |
| `getDescription()` | 选项说明，可为翻译键 | 无 | `String`，**可以为 `null`** |
| `isDefault()` | 当前值是否等于默认值（`Objects.equals` 比较） | 无 | `boolean` |
| `reset()` | 恢复默认值 | 选项须已加载（`BaseOption` 的实现里通过 `set` 完成） | 无（void） |
| `load()` / `unload()` | 切换加载状态；由选项组级联调用 | 由框架调用 | 无（void） |

### `BaseOption`

Reference: `net.ornithemc.osl.config.api.config.option.BaseOption`

**作用**：**不可变值类型**的选项基类。核心是三件事：保存默认值、用 `Predicate` 校验新值、在未加载时拒绝读写。自定义选项（例如 `CookieOption`）只要写一两个构造函数即可。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `BaseOption(String name, String description, T defaultValue)` | 用默认校验器 `OptionValidators.nonnull()` 构造 | `protected`；`defaultValue` 必须通过校验（默认校验器下即不能为 `null`），否则抛 `IllegalArgumentException("invalid default value given!")` | 无（构造） |
| `BaseOption(String name, String description, T defaultValue, Predicate<T> validator)` | 用自定义校验器构造 | 同上；校验器对默认值必须返回 `true` | 无（构造） |
| `getName()` / `getDescription()` | 名字 / 描述（成组 getter） | 无 | `String` |
| `getDefault()` | 默认值 | 无 | `T` |
| `get()` | 当前值 | 选项必须已加载，否则抛 `IllegalStateException("this option is not loaded!")` | `T` |
| `set(T newValue)` | 设置当前值 | 选项必须已加载；**新值与旧值相等、或未通过校验时静默忽略（不抛异常、不改值）** | 无（void） |
| `isDefault()` / `reset()` | 默认值判定 / 恢复默认值（`reset` 走 `set(getDefault())`） | `reset` 需要已加载 | `boolean` / 无（void） |
| `load()` / `unload()` | 切换加载状态 | 由框架调用 | 无（void） |
| `requireLoaded()` | 未加载时抛 `IllegalStateException` | 无 | 无（void） |
| `toString()` | 返回「类名[选项名]」 | 无 | `String` |

### `ModifiableOption`

Reference: `net.ornithemc.osl.config.api.config.option.ModifiableOption`

**作用**：**可变值类型**（`List`、`Map`、`NbtCompound`、OSL 的 `Event` 等）的选项基类。它在 `get` 时返回**不可修改视图**、在 `set` 时保存**可变副本**，从而保证任何改动都经过校验；要就地改值请用 `modify` / `modifyIO`，要整体换值请用 `set`。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `ModifiableOption(String name, String description, T defaultValue)` | 无自定义校验器构造 | `protected`；构造末尾会调用内部校验，检查 `modifiable` / `unmodifiable` 契约，不满足抛 `IllegalStateException` | 无（构造） |
| `ModifiableOption(String name, String description, T defaultValue, Predicate<T> validator)` | 带校验器构造 | 同上 | 无（构造） |
| `getDefault()` / `get()` | 返回默认值 / 当前值的**不可修改视图**（`Collections.unmodifiableList` / `unmodifiableMap` 等） | `get()` 需已加载 | `T` |
| `set(T value)` | 存为 `modifiable(value)` 得到的可变副本 | 选项必须已加载；仍需通过校验 | 无（void） |
| `modifiable(T value)` | （抽象，子类实现）返回传入值的可变视图 | 返回值必须**不等于同一对象**但 `equals` 相等，否则构造期抛 `IllegalStateException` | `T` |
| `unmodifiable(T value)` | （抽象，子类实现）返回传入值的不可修改视图 | 同上契约 | `T` |
| `modify(Consumer<T> modifier)` | 就地修改当前值：先把当前值存回去、再提交修改后的副本，以便校验失败时回退 | 选项必须已加载 | 无（void） |
| `modifyIO(IOConsumer<T> modifier)` | 同 `modify`，但修改器可以抛 `IOException`（反序列化时使用） | 同上；可能抛 `IOException` | 无（void） |

### 内置标量选项

**作用**：常用不可变类型的现成选项类，全部继承 `BaseOption`，都提供「无校验器」和「带 `Predicate` 校验器」两个构造函数。用法统一：`new XxxOption(name, description, defaultValue[, validator])`。

| 成员（类型 + 构造签名） | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `BooleanOption(String name, String description, boolean defaultValue[, Predicate<Boolean> validator])` | 布尔选项 | 默认值非 `null`（自动装箱） | 选项实例（`Option`） |
| `ByteOption(String name, String description, Byte defaultValue[, Predicate<Byte> validator])` | 字节选项 | 默认值非 `null`；校验器可选 | 同上 |
| `CharacterOption(String name, String description, Character defaultValue[, Predicate<Character> validator])` | 字符选项 | 同上；JSON/NBT/网络里按字符串存储 | 同上 |
| `DoubleOption(String name, String description, Double defaultValue[, Predicate<Double> validator])` | 双精度选项 | 默认值非 `null` | 同上 |
| `FloatOption(String name, String description, Float defaultValue[, Predicate<Float> validator])` | 单精度选项 | 同上 | 同上 |
| `IntegerOption(String name, String description, Integer defaultValue[, Predicate<Integer> validator])` | 整数选项（配合 `IntegerValidators` 做范围限制） | 同上 | 同上 |
| `LongOption(String name, String description, Long defaultValue[, Predicate<Long> validator])` | 长整型选项 | 同上 | 同上 |
| `ShortOption(String name, String description, Short defaultValue[, Predicate<Short> validator])` | 短整型选项 | 同上 | 同上 |
| `StringOption(String name, String description, String defaultValue[, Predicate<String> validator])` | 字符串选项 | 默认值非 `null`；可用 `StringValidators` | 同上 |
| `PathOption(String name, String description, Path defaultValue[, Predicate<Path> validator])` | 路径选项。序列化时写入**绝对路径字符串**（`toAbsolutePath`） | 同上 | 同上 |
| `UuidOption(String name, String description, UUID defaultValue[, Predicate<UUID> validator])` | `java.util.UUID` 选项，按字符串存储 | 同上 | 同上 |

### `ListOption`

Reference: `net.ornithemc.osl.config.api.config.option.ListOption`

**作用**：`List` 类型的选项，基于 `ModifiableOption`，并且**自身实现 `List` 接口**，因此可以直接 `option.add(x)`。必须提供元素类型（序列化时需要）。泛型选项需要你为**元素类型**注册对象序列化器。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `ListOption(Class<T> elementType, String name, String description)` | 默认值为空列表 | `elementType` 不能为 `null`（反序列化时使用） | 无（构造） |
| `ListOption(Class<T> elementType, String name, String description, List<T> defaultValue)` | 指定默认值；元素默认须非 `null` | 同上 | 无（构造） |
| `ListOption(Class<T> elementType, String name, String description, List<T> defaultValue, Predicate<T> elementValidator)` | 指定元素校验器（内部包装为对整表的校验） | 同上；默认值整体必须通过校验 | 无（构造） |
| `getElementType()` | 元素类型（序列化器据此找对象序列化器） | 无 | `Class<T>` |
| `get()` / `getDefault()` | 当前值 / 默认值的**只读视图**（`Collections.unmodifiableList`） | `get()` 需已加载 | `List<T>` |
| `add` / `addAll` / `remove` / `removeAll` / `retainAll` / `clear` / `set` / `add(int)` / `remove(int)` | 通过 `modify` 就地改表；`add` 等返回「长度是否变化」 | 选项必须已加载；改动后的表必须仍通过元素校验，否则改动被丢弃 | `boolean` / `T`（视方法而定） |
| `size` / `isEmpty` / `contains` / `iterator` / `toArray` / `containsAll` / `indexOf` / `lastIndexOf` / `listIterator` / `subList` | 纯查询，委托给当前值（成组 getter） | 同上（需已加载） | 各自对应类型 |
| `modify(Consumer)` / `modifyIO(IOConsumer)` | 继承自 `ModifiableOption`，批量改表时更方便 | 需已加载 | 无（void） |

### `MapOption`

Reference: `net.ornithemc.osl.config.api.config.option.MapOption`

**作用**：`Map` 类型的选项，基于 `ModifiableOption` 并实现 `Map` 接口。必须提供 key 与 value 的类型；序列化时按「keys 列表 + values 列表」成对存储（两侧长度不一致会抛 `IOException`）。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `MapOption(Class<K> keyType, Class<V> valueType, String name, String description)` | 默认值为空表 | 两个类型都不能为 `null` | 无（构造） |
| `MapOption(Class<K> keyType, Class<V> valueType, String name, String description, Map<K, V> defaultValue)` | 指定默认值；默认要求 key/value 都非 `null` | 同上 | 无（构造） |
| `MapOption(Class<K> keyType, Class<V> valueType, String name, String description, Map<K, V> defaultValue, BiPredicate<K, V> entryValidator)` | 指定条目校验器 | 默认表整体须通过校验 | 无（构造） |
| `getKeyType()` / `getValueType()` | 查询 key / value 类型（序列化用） | 无 | `Class<K>` / `Class<V>` |
| `get()` / `getDefault()` | 只读视图（`Collections.unmodifiableMap`） | `get()` 需已加载 | `Map<K, V>` |
| `put` / `putAll` / `remove` / `clear` | 通过 `modify` 就地改表；`put` / `remove` 返回被替换 / 删除的旧值 | 需已加载；改动后仍须通过条目校验 | `V` / 无（void） |
| `size` / `isEmpty` / `containsKey` / `containsValue` / `get(Object key)` / `keySet` / `values` / `entrySet` | 查询委托（注意 `get(Object)` 是 `Map` 的重载，与 `BaseOption.get()` 不同） | 需已加载 | 各自对应类型 |

> `ListOption` / `MapOption` 的**选项序列化器**本模块已内置（JSON/NBT/网络三套都有），但泛型参数对应的**对象序列化器**需要自己注册，否则 `JsonSerializers.get(...)` 等处拿不到序列化器。

### `IdentifierOption` / `BlockPosOption`

Reference: `net.ornithemc.osl.config.api.config.option.IdentifierOption` / `net.ornithemc.osl.config.api.config.option.BlockPosOption`

**作用**：Minecraft 类型的选项（仅 1.12.2 子工程提供）。`IdentifierOption` 存 `net.minecraft.resource.Identifier`；`BlockPosOption` 存 `net.minecraft.util.math.BlockPos`。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `IdentifierOption(String name, String description, Identifier defaultValue[, Predicate<Identifier> validator])` | 资源标识符选项，按字符串存储 | 默认值非 `null`（默认校验器） | 选项实例 |
| `BlockPosOption(String name, String description, BlockPos defaultValue[, Predicate<BlockPos> validator])` | 方块坐标选项。NBT 存为带 `x`/`y`/`z` 的 compound，网络存为 `BlockPos.toLong()` | 同上；`BlockPos` 自身可变，改值请整体 `set` 新实例 | 选项实例 |

### 校验器

#### `OptionValidators`

Reference: `net.ornithemc.osl.config.api.config.option.validator.OptionValidators`

**作用**：通用校验器工厂，产出 `Predicate` 供 `BaseOption` / `ModifiableOption` 的构造函数使用；默认校验器就是 `nonnull()`。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `always()` | 永远通过（等价于不校验） | 无 | `Predicate<T>` |
| `never()` | 永远不通过（注意：用它做默认校验器会导致构造期 `IllegalArgumentException`） | 无 | `Predicate<T>` |
| `nonnull()` | 值非 `null` | 无 | `Predicate<T>` |
| `list(Predicate<T> elementValidator)` | 逐元素校验整表 | 无 | `Predicate<List<T>>` |
| `map(BiPredicate<K, V> entryValidator)` | 逐条目校验整表 | 无 | `Predicate<Map<K, V>>` |

#### `IntegerValidators`

Reference: `net.ornithemc.osl.config.api.config.option.validator.IntegerValidators`

**作用**：整数范围校验器，常配合 `IntegerOption` 使用。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `min(int min)` | 值 `>= min` | `min` 为下界 | `Predicate<Integer>` |
| `max(int max)` | 值 `<= max` | `max` 为上界 | `Predicate<Integer>` |
| `minmax(int min, int max)` | 值落在闭区间 [min, max] | `min`、`max` 为端点（源码不做 `min <= max` 检查） | `Predicate<Integer>` |

#### `StringValidators`

Reference: `net.ornithemc.osl.config.api.config.option.validator.StringValidators`

**作用**：字符串模式校验器，配合 `StringOption` 使用。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `startsWith(String prefix)` | 以 `prefix` 开头 | 无 | `Predicate<String>` |
| `endsWith(String suffix)` | 以 `suffix` 结尾 | 无 | `Predicate<String>` |
| `regex(String regex)` | 整体匹配正则（`String.matches`，即**全串匹配**而非查找） | `regex` 必须是合法正则；非法正则在调用时抛 `PatternSyntaxException`（源码未捕获） | `Predicate<String>` |

## 4. 序列化基础设施

### `Serializer`

Reference: `net.ornithemc.osl.config.api.serdes.Serializer`

**作用**：所有序列化器（对象 / 选项 / 配置）的共同契约：在「值」与某种「介质 `M`」（`JsonFile`、`NbtElement`、`PacketByteBuf`）之间转换。**实现者**：一般实现三个子接口之一（`JsonSerializer` / `NbtSerializer` / `NetworkSerializer`），它们把其中一个方法设为默认抛 `UnsupportedOperationException`。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `serialize(T value, M medium)` | 把值写入已有介质 | `value`、`medium` 非 `null`；可能抛 `IOException` | 无（void） |
| `serialize(T value)` | 把值写成新建的介质 | 同上 | `M` |
| `deserialize(M medium)` | 从介质读回值 | 介质格式正确，否则通常抛 `IOException`（NBT 侧多用 `ClassCastException`，见 `NbtType.cast`） | `T` |

### `SerializerType`

Reference: `net.ornithemc.osl.config.api.serdes.SerializerType`

**作用**：序列化**格式**的标记接口，只用来区分「JSON / NBT / 网络」这类介质，具体能力交给两个子接口。**实现者**：实现 `FileSerializerType`（落盘）或 `MemorySerializerType`（内存），再注册进 `SerializerTypes`。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| （无成员） | 纯标记接口 | 泛型参数 `M` 为介质类型 | 无 |

### `FileSerializerType`

Reference: `net.ornithemc.osl.config.api.serdes.FileSerializerType`

**作用**：可落盘的格式。`Config.getType()` 要求返回它。内置实现只有 `SerializerTypes.JSON`。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `open(Path path)` | 打开 / 创建该路径对应的介质对象 | `path` 为最终文件路径（父目录由调用方保证已存在）；JSON 实现直接 `new JsonFile(path)` | `M` |

### `MemorySerializerType`

Reference: `net.ornithemc.osl.config.api.serdes.MemorySerializerType`

**作用**：只在内存中存在的格式（NBT 树、网络缓冲）。本模块用它们做「非文件」序列化。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `start()` | 创建一个新的空介质对象 | 无 | `M`（NBT 返回 `null` —— 由调用方自己建 `NbtCompound`；网络返回 `new PacketByteBuf(Unpooled.buffer())`） |

### `SerializerTypes`

Reference: `net.ornithemc.osl.config.api.serdes.SerializerTypes`

**作用**：格式注册表（`ConfigRegistries.SERIALIZER_TYPE`）的访问门面，并提供内置的 `JSON`。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `JSON` | 内置的 JSON 文件格式，`open(path)` 返回新的 `net.ornithemc.osl.core.api.json.JsonFile` | 无 | `FileSerializerType<JsonFile>` |
| `register(String name, T type)` | 以 `name` 注册一个格式（键为 `serializer_type:name`） | `name` 在格式注册表内唯一，重名会抛异常（由 OSL Core 注册表实现） | 传入的 `type` 本身 |
| `get(String name)` / `get(RegistryKey key)` | 按名字 / 键查格式 | 不存在时返回 `null`（源码未做空值检查） | `T`（`SerializerType` 子类型） |
| `getKey(SerializerType<?> type)` | 反查格式对应的键 | `type` 应已注册 | `RegistryKey` |

### `Serializers`

Reference: `net.ornithemc.osl.config.api.serdes.Serializers`

**作用**：为某个格式建立 / 取得「对象序列化器表」（`Class → Serializer`）。各 `XxxSerializers` 类在静态初始化时调用它。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `register(SerializerType<M> type, String name)` | 在 `type` 下取（或创建）名为 `name` 的对象序列化器表 | `type` 通常是已注册的格式；同一格式重复调用返回同一张表 | `Registry<Class<?>, S>` |

### `SerializationSettings`

Reference: `net.ornithemc.osl.config.api.serdes.SerializationSettings`

**作用**：控制一次序列化写什么：是否写配置 / 组 / 选项元数据、是否跳过默认值选项。`forFile()` 用于落盘（全写），`forNetwork()` 用于网络（省元数据、只发非默认值）。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `forFile()` | 落盘预设：不跳过任何内容 | 无 | `SerializationSettings` |
| `forNetwork()` | 网络预设：等价于 `skipMetadata()` + `skipDefaultOptions()` | 无 | `SerializationSettings` |
| `skipConfigMetadata` / `skipOptionGroupMetadata` / `skipOptionMetadata` / `skipDefaultOptions` | 四个 `public final boolean` 字段，供序列化器读取（成组字段） | 只读，构造时确定 | `boolean` |
| `Builder.skipConfigMetadata()` / `skipOptionGroupMetadata()` / `skipOptionMetadata()` / `skipMetadata()` / `skipDefaultOptions()` | 逐个打开跳过开关，链式调用；`skipMetadata()` 一次打开前三个 | 无 | `Builder` |
| `Builder.build()` | 生成不可变设置对象 | 无 | `SerializationSettings` |

> **实测注意**：内置的三个 `ConfigSerializer` 只读取 `skipConfigMetadata` 与 `skipDefaultOptions`；`skipOptionGroupMetadata` / `skipOptionMetadata` 目前没有被任何内置序列化器使用（仅为自定义序列化器预留）。另外 `forNetwork()` 在本模块内部**没有任何调用点**（见第 8 节）。

### `NbtType`

Reference: `net.ornithemc.osl.config.api.serdes.NbtType`

**作用**：NBT 标签类型的安全铸造器，把 `NbtElement` 收窄成具体子类型，类型不符时给出可读的错误信息。仅在 1.12.2 子工程提供。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `NULL` / `BYTE` / `SHORT` / `INT` / `LONG` / `FLOAT` / `DOUBLE` / `BYTE_ARRAY` / `STRING` / `LIST` / `COMPOUND` / `INT_ARRAY` / `LONG_ARRAY` | 13 个标签类型常量，分别对应 `NbtEnd`、`NbtByte`、`NbtShort`、`NbtInt`、`NbtLong`、`NbtFloat`、`NbtDouble`、`NbtByteArray`、`NbtString`、`NbtList`、`NbtCompound`、`NbtIntArray`、`NbtLongArray` | 无 | `NbtType<T>` |
| `cast(NbtElement nbt)` | 把标签转成该常量的具体类型 | `nbt` 非 `null` 且类型必须一致，否则抛 `ClassCastException("expected nbt type ... but found ...")`（构造器私有，只能通过常量使用） | `T` |

### `MinecraftSerializerTypes`

Reference: `net.ornithemc.osl.config.api.serdes.MinecraftSerializerTypes`

**作用**：Minecraft 相关的两种格式：NBT 与网络缓冲。二者都是 `MemorySerializerType`，**不能**作为 `Config.getType()` 的返回值（那里要 `FileSerializerType`）。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `NBT` | NBT 格式（注册名 `nbt`） | 无 | `MemorySerializerType<NbtElement>`，`start()` 返回 `null` |
| `NETWORK` | 网络格式（注册名 `network`） | 无 | `MemorySerializerType<PacketByteBuf>`，`start()` 返回空缓冲 |

## 5. 对象序列化器（Class → 值）

### `JsonSerializer`

Reference: `net.ornithemc.osl.config.api.serdes.JsonSerializer`

**作用**：把某个**不可变值类型**写进 / 读出 `JsonFile`。选项序列化器普遍复用它（例如 `UUID` 复用 `STRING`）。**实现者**：为自定义类型写一个匿名或具名实现并注册进 `JsonSerializers`。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `serialize(T value, JsonFile json)` | 把值写进当前 JSON 位置 | 调用前应已 `writeName(...)` 或处于对象 / 数组内 | 无（void） |
| `deserialize(JsonFile json)` | 从当前 JSON 位置读值 | 结构须与写入时一致 | `T` |
| `serialize(T value)` | 默认抛 `UnsupportedOperationException`（JSON 无法脱离文件创建介质） | 不要调用 | `JsonFile`（不会正常返回） |

### `NbtSerializer`

Reference: `net.ornithemc.osl.config.api.serdes.NbtSerializer`

**作用**：在值类型与 `NbtElement` 之间转换。与 `JsonSerializer` 相反：它要求实现「值 → 新标签」的 `serialize(T)`。仅在 1.12.2 子工程提供。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `serialize(T value)` | 生成表示该值的新 `NbtElement` | `value` 非 `null` | `NbtElement` |
| `deserialize(NbtElement nbt)` | 从标签读值 | 标签类型须匹配，否则 `NbtType.cast` 抛 `ClassCastException` | `T` |
| `serialize(T value, NbtElement nbt)` | 默认抛 `UnsupportedOperationException` | 不要调用 | 无（void） |

### `NetworkSerializer`

Reference: `net.ornithemc.osl.config.api.serdes.NetworkSerializer`

**作用**：在值类型与 `PacketByteBuf` 之间转换（`writeXxx` / `readXxx` 成对实现）。仅在 1.12.2 子工程提供。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `serialize(T value, PacketByteBuf buffer)` | 写入缓冲 | 缓冲的读写顺序必须与对端一致 | 无（void） |
| `deserialize(PacketByteBuf buffer)` | 从缓冲读出 | 同上 | `T` |
| `serialize(T value)` | 默认抛 `UnsupportedOperationException` | 不要调用（要新缓冲请用 `MinecraftSerializerTypes.NETWORK.start()`） | `PacketByteBuf`（不会正常返回） |

### `JsonSerializers`

Reference: `net.ornithemc.osl.config.api.serdes.JsonSerializers`

**作用**：JSON 对象序列化器注册表 + 内置实现（数值、布尔、字符、字符串、路径、UUID），以及 `Lists` / `Maps` 两个容器辅助类。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `BOOLEAN` / `BYTE` / `DOUBLE` / `FLOAT` / `INTEGER` / `LONG` / `SHORT` / `CHARACTER` / `STRING` / `PATH` / `UUID` | 内置 JSON 对象序列化器（`Character` 存为字符串；`Path` 存为绝对路径字符串；`UUID` 存为字符串） | 无 | `JsonSerializer<T>` |
| `register(Class<O> type, S serializer)` | 为类型注册 JSON 对象序列化器 | `type` 在表内唯一 | 传入的 `serializer` |
| `get(Class<O> type)` | 取类型对应的序列化器 | 未注册时返回 `null`（**源码未做空值检查**，随后调用会 NPE） | `JsonSerializer<O>` |
| `Lists.serialize(ListOption<T> option, JsonFile json)` / `Lists.serialize(List<T> list, Class<T> type, JsonFile json)` | 把列表写成 JSON 数组（逐元素用 `get(type)`） | 元素类型的序列化器必须已注册 | 无（void） |
| `Lists.deserialize(ListOption<T> option, JsonFile json)` / `Lists.deserialize(List<T> list, Class<T> type, JsonFile json)` | 读 JSON 数组；`ListOption` 版本走 `modifyIO` 以保留校验 | 同上 | 无（void） |
| `Maps.serialize(MapOption<K, V> option, JsonFile json)` / `Maps.serialize(Map<K, V> map, Class<K> keyType, Class<V> valueType, JsonFile json)` | 写成 `{"keys": [...], "values": [...]}` 对象 | 两个类型的序列化器都已注册 | 无（void） |
| `Maps.deserialize(MapOption<K, V> option, JsonFile json)` / `Maps.deserialize(Map<K, V> map, Class<K> keyType, Class<V> valueType, JsonFile json)` | 读回并重建表 | keys / values 长度不等时抛 `IOException` | 无（void） |

> **缺口注意**：共享源码的 `JsonSerializers` **没有**为 `Identifier` 与 `BlockPos` 注册对象序列化器（NBT / 网络侧有）。因此用 JSON 落盘 `IdentifierOption` / `BlockPosOption` 时，需要自己先 `JsonSerializers.register(Identifier.class, ...)` / `register(BlockPos.class, ...)`，否则 `get` 返回 `null` 并在序列化时抛 `NullPointerException`。

### `NbtSerializers`

Reference: `net.ornithemc.osl.config.api.serdes.NbtSerializers`

**作用**：NBT 对象序列化器注册表 + 内置实现（含 `Identifier`、`BlockPos`），以及 `Lists` / `Maps` 辅助类。仅在 1.12.2 子工程提供。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `BOOLEAN` … `UUID` | 与 JSON 侧同名的一组内置序列化器；`BOOLEAN` 实际存为 `NbtByte`（1/0），`CHARACTER` / `PATH` / `UUID` 存为 `NbtString` | 无 | `NbtSerializer<T>` |
| `IDENTIFIER` | `Identifier` ↔ `NbtString` | 无 | `NbtSerializer<Identifier>` |
| `BLOCK_POS` | `BlockPos` ↔ 带 `x`/`y`/`z` 的 `NbtCompound` | 无 | `NbtSerializer<BlockPos>` |
| `register(Class<O> type, S serializer)` / `get(Class<O> type)` | 注册 / 查询 | 未注册时 `get` 返回 `null` | `S` / `NbtSerializer<O>` |
| `Lists.serialize(ListOption<T>)` / `Lists.serialize(List<T>, Class<T>)` | 生成 `NbtList` | 元素序列化器已注册 | `NbtElement` |
| `Lists.deserialize(ListOption<T>, NbtElement)` / `Lists.deserialize(List<T>, Class<T>, NbtElement)` | 读回列表（先清空再填充） | 标签须是 `NbtList` | 无（void） |
| `Maps.serialize(MapOption<K, V>)` / `Maps.serialize(Map<K, V>, Class<K>, Class<V>)` | 生成含 `keys` / `values` 两个列表的 `NbtCompound` | 同上 | `NbtElement` |
| `Maps.deserialize(MapOption<K, V>, NbtElement)` / `Maps.deserialize(Map<K, V>, Class<K>, Class<V>, NbtElement)` | 读回并重建表 | 长度不等抛 `IOException` | 无（void） |

### `NetworkSerializers`

Reference: `net.ornithemc.osl.config.api.serdes.NetworkSerializers`

**作用**：网络对象序列化器注册表 + 内置实现（含 `Identifier`、`BlockPos`），以及 `Lists` / `Maps` 辅助类。仅在 1.12.2 子工程提供。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `BOOLEAN` … `UUID` | 内置实现，直接用 `PacketByteBuf` 的 `writeXxx` / `readXxx`；`STRING` 读取上限为 `Short.MAX_VALUE` 字符 | 无 | `NetworkSerializer<T>` |
| `IDENTIFIER` | 走 `writeIdentifier` / `readIdentifier` | 无 | `NetworkSerializer<Identifier>` |
| `BLOCK_POS` | 走 `BlockPos.toLong()` / `BlockPos.fromLong`（即按 `long` 传输） | 无 | `NetworkSerializer<BlockPos>` |
| `register(Class<O> type, S serializer)` / `get(Class<O> type)` | 注册 / 查询 | 未注册时返回 `null` | `S` / `NetworkSerializer<O>` |
| `Lists.serialize(ListOption<T>, PacketByteBuf)` / `Lists.serialize(List<T>, Class<T>, PacketByteBuf)` | 先写 `int` 长度再逐元素写 | 元素序列化器已注册 | 无（void） |
| `Lists.deserialize(...)` | 先读长度再逐元素读 | 顺序须与写入一致 | 无（void） |
| `Maps.serialize(...)` / `Maps.deserialize(...)` | 连写两个列表（keys、values） | 同上 | 无（void） |

## 6. Config 序列化器（整份配置 → 介质）

### `ConfigSerializer`

Reference: `net.ornithemc.osl.config.api.serdes.config.ConfigSerializer`

**作用**：整份配置的读写契约：遍历 `Config.getGroups()` / `OptionGroup.getOptions()`，再委托给对应 `Option` 的选项序列化器。**实现者**：内置已有 JSON/NBT/网络三份实现；只有想加新落盘格式时才需要实现它并注册进 `ConfigSerializers`。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `serialize(Config config, SerializationSettings settings, M medium)` | 把整份配置写入介质 | 配置的每个选项类都必须在对应格式下注册过选项序列化器，否则抛 `IOException("don't know how to serialize option ...")` | 无（void） |
| `deserialize(Config config, SerializationSettings settings, M medium)` | 从介质读回配置 | 选项须已加载（先 `config.load()`），否则 `option.set` 会抛 `IllegalStateException` | 无（void） |

### `ConfigSerializers`

Reference: `net.ornithemc.osl.config.api.serdes.config.ConfigSerializers`

**作用**：格式 → 配置序列化器的注册表，并提供 `JSON` 常量。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `JSON` | 内置 `JsonConfigSerializer`，挂在 `SerializerTypes.JSON` 上 | 无 | `JsonConfigSerializer` |
| `register(SerializerType<M> type, C serializer)` | 为格式注册配置序列化器 | 一个格式只应有一份实现 | `C`（传入的序列化器） |
| `get(SerializerType<M> type)` | 取格式对应的配置序列化器 | 未注册时返回 `null`；`ConfigManager.save` 遇到 `null` 会打印 `IOException` | `C` |
| `getType(C serializer)` | 反查某序列化器所属的格式 | 序列化器应已注册 | `SerializerType<M>` |

### `JsonConfigSerializer`

Reference: `net.ornithemc.osl.config.api.serdes.config.JsonConfigSerializer`

**作用**：默认落盘格式（`SerializerTypes.JSON` + `ConfigSerializers.JSON`）。文件结构固定为：

```json
{
  "config": "Example Config",
  "version": 0,
  "options": {
    "Example Group": {
      "Example Option 1": false,
      "Example Option 2": 2
    }
  }
}
```

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `serialize(Config config, SerializationSettings settings, JsonFile json)` | 写 `config` / `version`（`skipConfigMetadata` 时省略）与 `options` 对象；`skipDefaultOptions` 时跳过处于默认值的选项。方法内部负责 `write` 与 `close` | 序列化器须已注册；选项类型须有 JSON 选项序列化器 | 无（void） |
| `deserialize(Config config, SerializationSettings settings, JsonFile json)` | 读回；**文件里多出来的组 / 选项会被安静跳过**（`skipValue`，不报错），便于读取旧版本文件 | 配置须已加载且选项已登记 | 无（void） |

> `version` 读出来后**只被读入局部变量、未参与任何迁移逻辑**（源码中留有 `TODO: versioning`），因此不要指望框架帮你升级旧配置。

### `NbtConfigSerializer`

Reference: `net.ornithemc.osl.config.api.serdes.config.NbtConfigSerializer`

**作用**：把整份配置写进一个 `NbtCompound`（键名与 JSON 版一致：`config`、`version`、`options`）。适合把配置嵌进存档数据 / 物品 NBT 之类的场景。仅在 1.12.2 子工程提供。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `serialize(Config config, SerializationSettings settings, NbtElement nbt)` | 写入传入的 compound（`NbtType.COMPOUND.cast`，类型不符抛 `ClassCastException`） | 传入的必须是 `NbtCompound`；选项类型须有 NBT 选项序列化器 | 无（void） |
| `deserialize(Config config, SerializationSettings settings, NbtElement nbt)` | 读回；**遇到未知组 / 未知选项抛 `IOException`**（与 JSON 版不同，不会静默跳过） | 同上 | 无（void） |

### `NetworkConfigSerializer`

Reference: `net.ornithemc.osl.config.api.serdes.config.NetworkConfigSerializer`

**作用**：把整份配置写进 `PacketByteBuf`，布局为「配置名、版本、组数，然后每组：组名、选项数、每个选项的『名字 + 值』」。仅在 1.12.2 子工程提供。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `serialize(Config config, SerializationSettings settings, PacketByteBuf buffer)` | 按上述布局写入；`skipConfigMetadata` 时不写名字 / 版本，`skipDefaultOptions` 时不写默认值选项 | 选项类型须有网络选项序列化器 | 无（void） |
| `deserialize(Config config, SerializationSettings settings, PacketByteBuf buffer)` | 按同一布局读回；**未知组 / 未知选项抛 `IOException`** | 两端 `SerializationSettings` 必须一致，否则读串位 | 无（void） |

> 字符串读写上限为 `Short.MAX_VALUE` 字符（与 `NetworkSerializers.STRING` 一致）。

### `MinecraftConfigSerializers`

Reference: `net.ornithemc.osl.config.api.serdes.config.MinecraftConfigSerializers`

**作用**：把 NBT / 网络两份配置序列化器挂到对应格式上。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `NBT` | `NbtConfigSerializer`（挂在 `MinecraftSerializerTypes.NBT`） | 无 | `NbtConfigSerializer` |
| `NETWORK` | `NetworkConfigSerializer`（挂在 `MinecraftSerializerTypes.NETWORK`） | 无 | `NetworkConfigSerializer` |

## 7. Option 序列化器（单个选项 → 介质）

### `OptionSerializer`

Reference: `net.ornithemc.osl.config.api.serdes.config.option.OptionSerializer`

**作用**：单个选项的读写契约。与对象序列化器的区别是：它直接操作 `Option` 实例（要能判断默认值、能 `set`），并接收 `SerializationSettings`。**实现者**：一般用各 `XxxOptionSerializers.register(optionType, valueType)` 现成生成，或自己实现后注册。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `serialize(O option, SerializationSettings settings)` | 生成表示该选项的新介质 | 选项须已加载（内部会 `option.get()`） | `M` |
| `serialize(O option, SerializationSettings settings, M medium)` | 写入已有介质 | 同上 | 无（void） |
| `deserialize(O option, SerializationSettings settings, M medium)` | 从介质读入并写回选项（通常经 `option.set` / `modifyIO`） | 选项须已加载 | 无（void） |

### `OptionSerializers`

Reference: `net.ornithemc.osl.config.api.serdes.config.option.OptionSerializers`

**作用**：按格式建立 / 取得「选项类 → 选项序列化器」的表。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `register(SerializerType<M> type, String name)` | 在 `type` 下取 / 建名为 `name` 的选项序列化器表 | 同一格式重复调用返回同一张表 | `Registry<Class<? extends Option>, S>` |

### `JsonOptionSerializer`

Reference: `net.ornithemc.osl.config.api.serdes.config.option.JsonOptionSerializer`

**作用**：JSON 侧选项序列化器接口（`JsonOptionSerializer<O extends Option>`）。**实现者**：自定义选项且不想走对象序列化器时使用。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `serialize(O option, SerializationSettings settings, JsonFile json)` | 把选项值写到当前 JSON 位置 | 调用前调用方已 `writeName(option.getName())` | 无（void） |
| `deserialize(O option, SerializationSettings settings, JsonFile json)` | 从当前 JSON 位置读回 | 结构须与写入一致 | 无（void） |
| `serialize(O option, SerializationSettings settings)` | 默认抛 `UnsupportedOperationException` | 不要调用 | `JsonFile`（不会正常返回） |

### `NbtOptionSerializer`

Reference: `net.ornithemc.osl.config.api.serdes.config.option.NbtOptionSerializer`

**作用**：NBT 侧选项序列化器接口（`NbtOptionSerializer<O extends Option>`）。仅在 1.12.2 子工程提供。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `serialize(O option, SerializationSettings settings)` | 生成表示该选项值的 `NbtElement` | 选项须已加载 | `NbtElement` |
| `deserialize(O option, SerializationSettings settings, NbtElement nbt)` | 从标签读回 | 标签类型须匹配 | 无（void） |
| `serialize(O option, SerializationSettings settings, NbtElement nbt)` | 默认抛 `UnsupportedOperationException` | 不要调用 | 无（void） |

### `NetworkOptionSerializer`

Reference: `net.ornithemc.osl.config.api.serdes.config.option.NetworkOptionSerializer`

**作用**：网络侧选项序列化器接口（`NetworkOptionSerializer<O extends Option>`）。仅在 1.12.2 子工程提供。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `serialize(O option, SerializationSettings settings, PacketByteBuf buffer)` | 写入缓冲 | 选项须已加载 | 无（void） |
| `deserialize(O option, SerializationSettings settings, PacketByteBuf buffer)` | 从缓冲读回 | 读写顺序须一致 | 无（void） |
| `serialize(O option, SerializationSettings settings)` | 默认抛 `UnsupportedOperationException` | 不要调用 | `PacketByteBuf`（不会正常返回） |

### `JsonOptionSerializers`

Reference: `net.ornithemc.osl.config.api.serdes.config.option.JsonOptionSerializers`

**作用**：JSON 选项序列化器注册表 + 全套内置实现（标量 11 个 + `LIST` / `MAP`）。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `BOOLEAN` / `BYTE` / `DOUBLE` / `FLOAT` / `INTEGER` / `LONG` / `SHORT` / `CHARACTER` / `STRING` / `PATH` / `UUID` | 内置标量选项的 JSON 序列化器（内部委托 `JsonSerializers` 的对应对象序列化器） | 对应对象序列化器存在 | `JsonOptionSerializer<XxxOption>` |
| `LIST` / `MAP` | `ListOption` / `MapOption` 的 JSON 序列化器（委托 `JsonSerializers.Lists` / `Maps`，因此**元素类型**的对象序列化器必须已注册） | 同上，且元素 / 键值类型已注册 | `JsonOptionSerializer<ListOption>` / `JsonOptionSerializer<MapOption>`（裸类型） |
| `register(Class<O> optionType, Class<T> valueType)` | 一步生成选项序列化器：`serialize` 走 `JsonSerializers.get(valueType).serialize(option.get(), json)`，`deserialize` 走 `option.set(...)` | `optionType` 应继承 `BaseOption<T>`；`valueType` 的 JSON 对象序列化器必须已注册 | `JsonOptionSerializer<O>` |
| `register(Class<O> optionType, S serializer)` | 直接注册自定义选项序列化器 | `optionType` 唯一 | `S` |
| `get(Class<? extends Option> optionType)` | 查选项序列化器 | 未注册返回 `null`（配置序列化器会转成 `IOException`） | `JsonOptionSerializer<O>` |

### `NbtOptionSerializers`

Reference: `net.ornithemc.osl.config.api.serdes.config.option.NbtOptionSerializers`

**作用**：NBT 选项序列化器注册表 + 全套内置实现（标量 13 个，比 JSON 侧多出 `IDENTIFIER` / `BLOCK_POS`，另加 `LIST` / `MAP`）。仅在 1.12.2 子工程提供。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `BOOLEAN` … `UUID`、`IDENTIFIER`、`BLOCK_POS` | 内置选项序列化器 | 对应 NBT 对象序列化器已注册（内置已全部就绪） | `NbtOptionSerializer<XxxOption>` |
| `LIST` / `MAP` | 容器选项序列化器（委托 `NbtSerializers.Lists` / `Maps`） | 元素 / 键值类型的 NBT 序列化器已注册 | `NbtOptionSerializer<ListOption>` / `NbtOptionSerializer<MapOption>` |
| `register(Class<O> optionType, Class<T> valueType)` | 一步生成选项序列化器（`serialize` 返回 `NbtSerializers.get(valueType).serialize(option.get())`） | `optionType` 继承 `BaseOption<T>` | `NbtOptionSerializer<O>` |
| `register(Class<O> optionType, S serializer)` / `get(Class<? extends Option> optionType)` | 自定义注册 / 查询 | 未注册返回 `null` | `S` / `NbtOptionSerializer<O>` |

### `NetworkOptionSerializers`

Reference: `net.ornithemc.osl.config.api.serdes.config.option.NetworkOptionSerializers`

**作用**：网络选项序列化器注册表 + 全套内置实现（与 NBT 侧同名同集合）。仅在 1.12.2 子工程提供。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `BOOLEAN` … `UUID`、`IDENTIFIER`、`BLOCK_POS` | 内置选项序列化器 | 对应网络对象序列化器已注册（内置已就绪） | `NetworkOptionSerializer<XxxOption>` |
| `LIST` / `MAP` | 容器选项序列化器 | 元素 / 键值类型的网络序列化器已注册 | `NetworkOptionSerializer<ListOption>` / `NetworkOptionSerializer<MapOption>` |
| `register(Class<O> optionType, Class<T> valueType)` | 一步生成选项序列化器 | `optionType` 继承 `BaseOption<T>` | `NetworkOptionSerializer<O>` |
| `register(Class<O> optionType, S serializer)` / `get(Class<? extends Option> optionType)` | 自定义注册 / 查询 | 未注册返回 `null` | `S` / `NetworkOptionSerializer<O>` |

### `MinecraftJsonOptionSerializers`

Reference: `net.ornithemc.osl.config.api.serdes.config.option.MinecraftJsonOptionSerializers`

**作用**：把 Minecraft 类型的选项接进 JSON 体系（`JsonOptionSerializers` 本身只认共享源码里的选项类型）。仅在 1.12.2 子工程提供。

| 成员 | 作用 | 需要（参数 / 前置条件） | 返回 |
|---|---|---|---|
| `IDENTIFIER` | 为 `IdentifierOption` 注册 JSON 选项序列化器（委托 `Identifier` 的 JSON 对象序列化器） | 依赖 `JsonSerializers.get(Identifier.class)`，而共享源码**没有**注册它 —— 用前须自行 `JsonSerializers.register(Identifier.class, ...)` | `JsonOptionSerializer<IdentifierOption>` |
| `BLOCK_POS` | 为 `BlockPosOption` 注册 JSON 选项序列化器 | 同上，需自行注册 `BlockPos` 的 JSON 对象序列化器 | `JsonOptionSerializer<BlockPosOption>` |

## 8. 三种格式分别什么时候用

| 格式 | 相关注册点 | 介质类型 | 本模块是否自动使用 | 典型用途 |
|---|---|---|---|---|
| JSON 文件 | `SerializerTypes.JSON` + `ConfigSerializers.JSON` + `JsonOptionSerializers` | `net.ornithemc.osl.core.api.json.JsonFile` | **是** —— `ConfigManager` 读盘 / 写盘全部走 `config.getType()` + `SerializationSettings.forFile()` | 配置落盘（默认且唯一内置的落盘格式），人类可编辑 |
| NBT | `MinecraftSerializerTypes.NBT` + `MinecraftConfigSerializers.NBT` + `NbtOptionSerializers` | `net.minecraft.nbt.NbtElement`（自备 `NbtCompound`） | 否 | 把配置嵌进存档 / 物品 / 自定义数据；世界级数据共享 |
| 网络 | `MinecraftSerializerTypes.NETWORK` + `MinecraftConfigSerializers.NETWORK` + `NetworkOptionSerializers` | `net.minecraft.network.PacketByteBuf` | 否 | 服务端把配置同步给客户端（自己发包） |

**关于「网络同步」的实话**：本模块**只提供序列化能力，不提供传输通道**。源码中 `SerializationSettings.forNetwork()` 没有任何内部调用点，也没有任何包 / 通道注册代码；`MinecraftSerializerTypes.NETWORK` 的 `start()` 只是给你一个新缓冲。也就是说：同步需要你自己在 `osl-networking`（或原生 `PacketByteBuf` 通道）里发包，收端调用 `ConfigSerializers.get(MinecraftSerializerTypes.NETWORK)` 得到序列化器后 `deserialize(config, SerializationSettings.forNetwork(), buf)`。

**关于落盘路径**（由作用域根目录决定）：`<根>/config/<namespace>/<saveName>`；`getNamespace()` 返回 `null` 时退化为 `<根>/config/<saveName>`。客户端 `GLOBAL` 根目录是 `gameDir`，服务端 `GLOBAL` 根目录是运行目录，`WORLD` 根目录是存档目录。

## 9. 典型用法

### 9.1 定义选项 → 建 Config → 注册 → 读取

```java
public final class ExampleConfig extends BaseConfig {

    public static final BooleanOption ENABLED = new BooleanOption("example.enabled", "开关", true);
    public static final IntegerOption RADIUS = new IntegerOption("example.radius", "半径", 8, IntegerValidators.minmax(1, 32));
    public static final ListOption<String> NAMES = new ListOption<>(String.class, "example.names", "名单");

    @Override public String getNamespace() { return "example-mod"; }
    @Override public String getName() { return "Example Config"; }
    @Override public String getSaveName() { return "example.json"; }
    @Override public ConfigScope getScope() { return ConfigScope.GLOBAL; }
    @Override public LoadingPhase getLoadingPhase() { return LoadingPhase.START; }
    @Override public FileSerializerType<?> getType() { return SerializerTypes.JSON; }
    @Override public int getVersion() { return 0; }

    @Override
    public void init() {
        registerOptions("general", ENABLED, RADIUS);   // 组名 = 序列化键
        registerOptions("lists", NAMES);
    }
}

// 入口点（ModInitializer#init / ClientModInitializer#initClient / ServerModInitializer#initServer）
ConfigManager.register(new ExampleConfig());
```

```java
// 读取：必须在该作用域进入 START/READY 之后（否则 IllegalStateException）
if (ExampleConfig.ENABLED.get()) {
    int r = ExampleConfig.RADIUS.get();
}
ExampleConfig.NAMES.add("Steve");   // 就地修改，自动校验
ExampleConfig.RADIUS.set(64);       // 校验失败 → 静默保持原值（仍是 8）

// 立即落盘（否则等作用域关闭时自动保存）
ConfigManager.save(configInstance);
```

> **没有「变更监听」**：本模块源码里没有任何选项变更事件 / 回调。`set` / `modify` 之后想知道值变了，只能在自己的设置入口处自行通知（例如给设置写一层包装方法），或在需要的时机重新读取。不要指望 `Option` 提供监听器。

### 9.2 自定义 Option 类型 + 注册序列化器

```java
// 1) 不可变值类型 → 继承 BaseOption
public class CookieOption extends BaseOption<Cookie> {
    public CookieOption(String name, String description, Cookie defaultValue) {
        super(name, description, defaultValue);
    }
}

// 2) 入口点里为 Cookie 注册三个格式的对象序列化器
JsonSerializers.register(Cookie.class, myJsonCookieSerializer);
NbtSerializers.register(Cookie.class, myNbtCookieSerializer);
NetworkSerializers.register(Cookie.class, myNetworkCookieSerializer);

// 3) 选项序列化器只需一行（内部转调上面的对象序列化器）
JsonOptionSerializers.register(CookieOption.class, Cookie.class);
NbtOptionSerializers.register(CookieOption.class, Cookie.class);
NetworkOptionSerializers.register(CookieOption.class, Cookie.class);
```

自定义要点汇总：

- **不可变值类型** → `extends BaseOption<T>`，通常只需两个构造函数。
- **可变值类型** → `extends ModifiableOption<T>`，必须实现 `modifiable` / `unmodifiable`，且满足「不同对象但 `equals` 相等」；违反契约在**构造期**就抛 `IllegalStateException`。
- **序列化器**：每个实际用到的格式都要注册。要么写「对象序列化器 + 一行选项序列化器」，要么直接写完整的 `XxxOptionSerializer`（泛型选项只能走后者，参考内置 `LIST` / `MAP` 的做法）。
- **注册时机**：全部在 mod 入口点（`init`）里完成，早于任何作用域加载。

## 10. 易错点清单

| 现象 | 原因 | 处理 |
|---|---|---|
| `IllegalStateException: this option is not loaded!` | 在作用域 `START` / `READY` 之前（例如 mod `init` 里）读了选项 | 把读取推迟到该阶段之后，或把配置的 `getLoadingPhase()` 调成更早的阶段 |
| `IllegalStateException: this config is not loaded!` | 在未加载时调用 `resetAll()` | 同上 |
| `IllegalStateException: cannot register new options while this config is loaded!` | 在 `init()` 之外（配置已加载后）登记选项 | 选项登记只在 `init()` 里做 |
| `IllegalStateException: config ... is not unique` | 同一作用域注册了两份 `namespace:name` 相同的配置 | 改名或改命名空间；同一实例重复注册无害 |
| `IllegalArgumentException: invalid default value given!` | 默认值没过校验器（默认校验器是 `nonnull()`） | 给非 `null` 默认值，或显式传校验器 |
| `set(...)` 没生效却不报错 | 值相等，或未通过校验器 | 检查校验器；这是设计行为 |
| 文件里有值、读出来却是默认值 | 选项名 / 组名与文件里的键不一致（JSON 侧会静默跳过未知键） | 组名、选项名一经发布不要再改 |
| 换 NBT / 网络格式后反序列化失败 | 读到了旧版本数据，未知组 / 选项会抛 `IOException` | 保证两端版本一致，或自己处理兼容 |
| 把 `MinecraftSerializerTypes.NBT` 当 `getType()` 返回值 | `getType()` 要求 `FileSerializerType`，而 NBT / 网络是 `MemorySerializerType` | 落盘用 `SerializerTypes.JSON`；NBT 只用于自建 compound |
