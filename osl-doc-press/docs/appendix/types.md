---
title: 附录 B　公开类型索引
---

# 附录 B　公开类型索引（按包）

下表列出 MC 1.12.2 下各模块 `api` 包中的全部公开类型，便于按名字反查所属包。

## core

| 包 | 公开类型 |
|---|---|
| `net.ornithemc.osl.core.api.events` | `Event` |
| `net.ornithemc.osl.core.api.io` | `DataStream` |
| `net.ornithemc.osl.core.api.json` | `JsonFile` |
| `net.ornithemc.osl.core.api.registry` | `DefaultedIdRegistry`、`IdBiMap`、`Registries`、`Registry`、`RegistryKey`、`SimpleIdRegistry` |
| `net.ornithemc.osl.core.api.util` | `NamespacedIdentifier`、`NamespacedIdentifiers`、`Unit` |
| `net.ornithemc.osl.core.api.util.function` | `IOConsumer`、`IOSupplier`、`TriConsumer`、`TriFunction` |
| `net.ornithemc.osl.core.api.util.math` | `BlockPos`、`Direction` |
| `net.ornithemc.osl.core.api.util.sort` | `TopoSort` |

## biomes

| 包 | 公开类型 |
|---|---|
| `net.ornithemc.osl.biomes.api` | `BiomeEvents`、`BiomeRegistry` |
| `net.ornithemc.osl.biomes.api.biome` | `BiomeExtension`、`BiomeSettings` |

## blocks

| 包 | 公开类型 |
|---|---|
| `net.ornithemc.osl.blocks.api` | `BlockEvents`、`BlockRegistry` |

## blockstates

| 包 | 公开类型 |
|---|---|
| `net.ornithemc.osl.blockstates.api.block` | `BlockExtension` |
| `net.ornithemc.osl.blockstates.api.block.entity` | `BlockEntityExtension` |
| `net.ornithemc.osl.blockstates.api.block.state` | `BlockBehaviors`、`BlockProperties`、`BlockStateExtension` |
| `net.ornithemc.osl.blockstates.api.state` | `State`、`StateDefinition` |
| `net.ornithemc.osl.blockstates.api.state.property` | `AbstractProperty`、`BooleanProperty`、`DirectionProperty`、`EnumProperty`、`IntegerProperty`、`Property`、`StringSerializable` |

## blockentities

| 包 | 公开类型 |
|---|---|
| `net.ornithemc.osl.blockentities.api` | `BlockEntityEvents`、`BlockEntityTypeRegistry` |
| `net.ornithemc.osl.blockentities.api.blockentity` | `BlockEntityType`、`BlockEntityTypes` |

## blockentities-rendering

| 包 | 公开类型 |
|---|---|
| `net.ornithemc.osl.blockentities.api.client` | `BlockEntityRendererRegistry`、`BlockEntityRenderingEvents` |

## branding

| 包 | 公开类型 |
|---|---|
| `net.ornithemc.osl.branding.api` | `BrandingContext`、`BrandingModifierRegistry`、`BrandingPatch`、`BrandingPatchEvents`、`Operation` |

## commands

| 包 | 公开类型 |
|---|---|
| `net.ornithemc.osl.commands.api` | `Commands` |
| `net.ornithemc.osl.commands.api.client` | `ClientCommandEvents`、`ClientCommands` |
| `net.ornithemc.osl.commands.api.client.command` | `ClientCommandSource`、`HelpCommand` |
| `net.ornithemc.osl.commands.api.client.network.handler` | `ClientPlayNetworkHandlerExtension` |
| `net.ornithemc.osl.commands.api.command` | `CommandFailureConsumer`、`SharedSuggestionProvider`、`SuggestionProviders` |
| `net.ornithemc.osl.commands.api.command.argument` | `AnchorArgument`、`AxesArgument`、`BlockInput`、`BlockPosArgument`、`BlockPredicateArgument`、`BlockStateArgument`、`BlockStateParser`、`ColorArgument`、`ColumnPosArgument`、`Coordinate`、`Coordinates`、`EnchantmentArgument`、`EntityArgument`、`EntitySelector`、`EntitySelectorOptions`、`EntitySelectorParser`、`GameProfileArgument`、`GlobalCoordinates`、`IdentifierArgument`、`IdentifierParser`、`ItemArgument`、`ItemInput`、`ItemParser`、`ItemPredicateArgument`、`LegacyBlockPredicateArgument`、`LegacyBlockStateArgument`、`LocalCoordinates`、`MessageArgument`、`NbtCompoundArgument`、`NbtUtils`、`NumberRange`、`ObjectiveArgument`、`OperationArgument`、`RangeArgument`、`RotationArgument`、`ScoreHolderArgument`、`ScoreboardCriterionArgument`、`ScoreboardDisplaySlotArgument`、`SlotArgument`、`SnbtParser`、`StatusEffectArgument`、`TeamArgument`、`TextArgument`、`Vec2f`、`Vec2fArgument`、`Vec3dArgument`、`WrappedNumberRange` |
| `net.ornithemc.osl.commands.api.command.argument.serdes` | `ArgumentSerializer`、`ArgumentTypes`、`BrigadierArgumentSerializers`、`DoubleArgumentSerializer`、`EmptyArgumentSerializer`、`FloatArgumentSerializer`、`IntegerArgumentSerializer`、`StringArgumentSerializer` |
| `net.ornithemc.osl.commands.api.entity` | `EntityExtension` |
| `net.ornithemc.osl.commands.api.server` | `MinecraftServerExtension`、`PlayerManagerExtension`、`ServerCommandEvents`、`ServerCommands` |
| `net.ornithemc.osl.commands.api.server.command` | `CommandSourceBuilder`、`CommandSourceStack` |

## config

| 包 | 公开类型 |
|---|---|
| `net.ornithemc.osl.config.api` | `ConfigManager`、`ConfigRegistries`、`ConfigScope`、`LoadingPhase` |
| `net.ornithemc.osl.config.api.config` | `BaseConfig`、`Config` |
| `net.ornithemc.osl.config.api.config.option` | `BaseOption`、`BlockPosOption`、`BooleanOption`、`ByteOption`、`CharacterOption`、`DoubleOption`、`FloatOption`、`IdentifierOption`、`IntegerOption`、`ListOption`、`LongOption`、`MapOption`、`ModifiableOption`、`Option`、`PathOption`、`ShortOption`、`StringOption`、`UuidOption` |
| `net.ornithemc.osl.config.api.config.option.group` | `OptionGroup` |
| `net.ornithemc.osl.config.api.config.option.validator` | `IntegerValidators`、`OptionValidators`、`StringValidators` |
| `net.ornithemc.osl.config.api.serdes` | `FileSerializerType`、`JsonSerializer`、`JsonSerializers`、`MemorySerializerType`、`MinecraftSerializerTypes`、`NbtSerializer`、`NbtSerializers`、`NbtType`、`NetworkSerializer`、`NetworkSerializers`、`SerializationSettings`、`Serializer`、`SerializerType`、`SerializerTypes`、`Serializers` |
| `net.ornithemc.osl.config.api.serdes.config` | `ConfigSerializer`、`ConfigSerializers`、`JsonConfigSerializer`、`MinecraftConfigSerializers`、`NbtConfigSerializer`、`NetworkConfigSerializer` |
| `net.ornithemc.osl.config.api.serdes.config.option` | `JsonOptionSerializer`、`JsonOptionSerializers`、`MinecraftJsonOptionSerializers`、`NbtOptionSerializer`、`NbtOptionSerializers`、`NetworkOptionSerializer`、`NetworkOptionSerializers`、`OptionSerializer`、`OptionSerializers` |

## crash-reports

| 包 | 公开类型 |
|---|---|
| `net.ornithemc.osl.crashreports.api` | `CrashExceptions` |
| `net.ornithemc.osl.crashreports.api.crash` | `CrashException`、`CrashListener`、`CrashReport`、`CrashReportDetail`、`CrashReportPopulator`、`CrashReportSection` |

## entities

| 包 | 公开类型 |
|---|---|
| `net.ornithemc.osl.entities.api` | `EntityEvents`、`EntityTypeRegistry` |
| `net.ornithemc.osl.entities.api.entity` | `EntityType`、`EntityTypes` |

## entities-rendering

| 包 | 公开类型 |
|---|---|
| `net.ornithemc.osl.entities.api.client` | `EntityRendererRegistry`、`EntityRenderingEvents` |

## entrypoints

| 包 | 公开类型 |
|---|---|
| `net.ornithemc.osl.entrypoints.api` | `ModInitializer` |
| `net.ornithemc.osl.entrypoints.api.client` | `ClientModInitializer` |
| `net.ornithemc.osl.entrypoints.api.launch` | `LaunchEvents`、`OptionsConsumer` |
| `net.ornithemc.osl.entrypoints.api.server` | `ServerModInitializer` |

## executors

| 包 | 公开类型 |
|---|---|
| `net.ornithemc.osl.executors.api` | `BackgroundExecutor`、`MainThreadExecutor` |

## items

| 包 | 公开类型 |
|---|---|
| `net.ornithemc.osl.items.api` | `ItemEvents`、`ItemRegistry` |

## keybinds

| 包 | 公开类型 |
|---|---|
| `net.ornithemc.osl.keybinds.api` | `KeyBindingEvents`、`KeyBindingRegistry`、`KeybindEvents`、`KeybindRegistry` |

## lifecycle-events

| 包 | 公开类型 |
|---|---|
| `net.ornithemc.osl.lifecycle.api` | `LifecycleEvents` |
| `net.ornithemc.osl.lifecycle.api.client` | `ClientWorldEvents`、`MinecraftClientEvents`、`MinecraftInstance` |
| `net.ornithemc.osl.lifecycle.api.server` | `MinecraftServerEvents`、`MinecraftServerInstance`、`ServerWorldEvents` |

## localization

| 包 | 公开类型 |
|---|---|
| `net.ornithemc.osl.localization.api` | `L10n` |
| `net.ornithemc.osl.localization.api.language` | `Language`、`LanguageMetadata` |

## networking

| 包 | 公开类型 |
|---|---|
| `net.ornithemc.osl.networking.api` | `ChannelIdentifiers`、`ChannelRegistry`、`IdentifierChannelIdentifierParser`、`LegacyChannelIdentifier`、`PacketBuffer`、`PacketBuffers`、`PacketPayload`、`StringChannelIdentifierParser` |
| `net.ornithemc.osl.networking.api.client` | `ClientConnectionEvents`、`ClientPacketListener`、`ClientPlayNetworking` |
| `net.ornithemc.osl.networking.api.server` | `ServerConnectionEvents`、`ServerPacketListener`、`ServerPlayNetworking` |

## registries

| 包 | 公开类型 |
|---|---|
| `net.ornithemc.osl.registries.api` | `RegistryEvents` |
| `net.ornithemc.osl.registries.api.registry` | `DefaultedRegistry`、`IdMap`、`LegacyStringIds`、`Registries`、`Registry`、`RegistryKeys`、`ResourceKey`、`ResourceKeys`、`SyncedRegistries`、`WritableRegistry` |
| `net.ornithemc.osl.registries.api.registry.sync` | `ArrayMapper`、`BooleanArrayMapper`、`DynamicArray`、`DynamicBooleanArray`、`DynamicInt2ObjectMapMapper`、`DynamicIntArray`、`Id2ObjectBiMapMapper`、`IdFixer`、`IdMapper`、`Int2ObjectMapMapper`、`IntArrayMapper`、`IntegerMapMapper`、`ListMapper`、`RegistryMappings` |

## resource-loader

| 包 | 公开类型 |
|---|---|
| `net.ornithemc.osl.resource.loader.api.client` | `ClientResourceLoaderEvents` |
| `net.ornithemc.osl.resource.loader.api.client.resource.reload` | `AssetsReloaders` |
| `net.ornithemc.osl.resource.loader.api.resource` | `Resource`、`ResourceLocation`、`ResourceMetadata`、`ResourcePath`、`ResourceType` |
| `net.ornithemc.osl.resource.loader.api.resource.manager` | `ReloadableResourceManager`、`ResourceManager` |
| `net.ornithemc.osl.resource.loader.api.resource.pack` | `AbstractResourcePack`、`PackCompatibility`、`PackPosition`、`ResourceConsumer`、`ResourcePack`、`ResourcePackFileNotFoundException`、`ResourcePackMetadata` |
| `net.ornithemc.osl.resource.loader.api.resource.reload` | `ReloadStep`、`ResourceReload`、`ResourceReloadContext`、`ResourceReloadListener`、`ResourceReloader`、`SimpleResourceReloader` |
| `net.ornithemc.osl.resource.loader.api.resource.repository` | `ClientPackSource`、`ResourcePackRepository`、`ResourcePackSummary`、`ServerPackSource` |
| `net.ornithemc.osl.resource.loader.api.server` | `ServerResourceLoaderEvents` |

## text-components

| 包 | 公开类型 |
|---|---|
| `net.ornithemc.osl.text.api` | `ClickEvent`、`Formatting`、`HoverEvent`、`MessageConsumer`、`Style`、`StyledTextVisitor`、`TextColor`、`TextComponent`、`TextComponents`、`TextVisitResults`、`TextVisitor` |
