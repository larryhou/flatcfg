`flatcfg` is a python tool for serializing xls book row data into `FlatBuffers` or `protobuf` formats.

`flatcfg` support full types in `FlatBuffers` and some limited `protobuf` types (`double`, `float`, `string`, `bool`, `[u]int32`, `[u]int64`).

> FlatBuffers types

| | | | |
|:--|:--|:--|:--|
|8 bit| byte (int8)| ubyte (uint8)| bool|
|16 bit| short (int16)| ushort (uint16)||
|32 bit| int (int32)| uint (uint32)| float (float32)|
|64 bit| long (int64)| ulong (uint64)| double (float64)|

# Table
`Table` is a basic data structure in `flatcfg`, and it's derived from `FlatBuffers`. A table present a row data, no matter how complicated it is.

First we need know how define a `Table` in xls book. Suppose we have a sheet named `INFORMATION_CONFIG` as following.

### INFORMATION_CONFIG

| | | | |
|:--|:--|:--|:--|
| FIELD_RULE | optional | optional | optional |
| FIELD_TYPE | int32 | string | string |
| FIELD_NAME | id | title | content |
| FIELD_ACES |  |  |  |
| FIELD_DESC | id（请按照顺序添加） | 标题 | 内容 |

As you can see, we need first **5** rows to define a table structure, and there are FIELD_RULE, FIELD_TYPE, FIELD_NAME, FIELD_ACES, FIELD_DESC.

FIELD_RULE: field rule type (optional, required, repeated), same meanings with those in `protobuf`</br>
FIELD_TYPE: field type as above</br>
FIELD_NAME: field name used for generating table structure, if equal mark `=` comes after it, the second part will the default value for this field. And if the field is a `Table` or `Array` then the second part will be the nest type name.</br>
FIELD_ACES: this is used for special purpose, e.g. generating different sirialized data from same table</br>
FIELD_DESC: for field description/comments

Run the following command line
```sh
python3 flatcfg.py -f ~/Downloads/foo.xlsx
```
You will get `FlatBuffers` schema file

```fbs
namespace dataconfig;

table INFORMATION_CONFIG
{
    id:int32(key); // 'id（请按照顺序添加）'
    title:string; // '标题'
    content:string; // '内容'
}

table INFORMATION_CONFIG_ARRAY
{
    items:[INFORMATION_CONFIG];
}

root_type INFORMATION_CONFIG_ARRAY;
```

Run `python3 flatcfg.py -f ~/Downloads/foo.xlsx`, you'll get `protobuf` message file.

```protobuf
syntax = "proto2";
package dataconfig;

message INFORMATION_CONFIG
{
    optional int32 id = 1; // 'id（请按照顺序添加）'
    optional string title = 2; // '标题'
    optional string content = 3; // '内容'
}

message INFORMATION_CONFIG_ARRAY
{
    repeated INFORMATION_CONFIG items = 1;
}

```
When `schema`/`message` files are generated, `flatcfg` will use there files to serialize xls book data into binary formats, which you could deserialize into runtime objects with libraries from `FlatBuffers`/`protobuf`.

# Nest

### FOO_CONF
| | | | | | | | |
|:--|:--|:--|:--|:--|:--|:--|:--|
| FIELD_RULE | required | required | required | required | required | required | required |
| FIELD_TYPE | uint32 | 4 | string | uint32 | bool | string | string |
| FIELD_NAME | id | author | name | age | gender | mobile | article |
| FIELD_ACES | C | C | C | C | C | C | C |
| FIELD_DESC | 唯一ID | 作者 | 姓名 | 年龄 | 性别 | 手机号码 | 文章 |


```fbs
namespace dataconfig;

table FOO_CONF
{
    id:uint32(key); // '唯一ID'
    author:FooConfAuthor; // '作者'
    article:string; // '文章'
}

table FooConfAuthor
{
    name:string; // '姓名'
    age:uint32 = 0; // '年龄'
    gender:bool = false; // '性别'
    mobile:string; // '手机号码'
}

table FOO_CONF_ARRAY
{
    items:[FOO_CONF];
}

root_type FOO_CONF_ARRAY;
```

```protobuf
syntax = "proto2";
package dataconfig;

message FOO_CONF
{
    required uint32 id = 1; // '唯一ID'
    required FooConfAuthor author = 2; // '作者'
    required string article = 3; // '文章'
}

message FooConfAuthor
{
    required string name = 1; // '姓名'
    required uint32 age = 2[default = 0]; // '年龄'
    required bool gender = 3[default = false]; // '性别'
    required string mobile = 4; // '手机号码'
}

message FOO_CONF_ARRAY
{
    repeated FOO_CONF items = 1;
}
```

Here we get nest table type `FooConfAuthor`, which comes from `FOO_CONF` and field name `author` concating. The `author` field has integer value **4** in the type cell, and if the rule cell is not **repeated**, we'll define this pattern as a table declartion, and the integer **4** means there're 4 following field members in the nest table `FooConfAuthor`, and there're `name`, `age`, `gender`, `mobile`.

What happens if the rule cell value is **repeated**? This will be a situaion that table nest in array, we talk about this in next chapter.

# Array

### ITEM_CONF
| | | | | | | | | | | | | | | | | | | | | | | | | | | | | | | | | | | | | | | | | | | | | | | | | | | | | |
|:--|:--|:--|:--|:--|:--|:--|:--|:--|:--|:--|:--|:--|:--|:--|:--|:--|:--|:--|:--|:--|:--|:--|:--|:--|:--|:--|:--|:--|:--|:--|:--|:--|:--|:--|:--|:--|:--|:--|:--|:--|:--|:--|:--|:--|:--|:--|:--|:--|:--|:--|:--|:--|
| FIELD_RULE | required | optional | * | optional | repeated | * | optional | * | optional | optional | optional | optional | optional | repeated | optional | optional | optional | repeated | optional | repeated | optional | optional | optional | optional | optional | optional | optional | optional | optional | optional | optional | optional | optional | optional | optional | optional | optional | optional | optional | optional | optional | optional | optional | optional | optional | optional | optional | optional | optional | optional | optional | optional |
| FIELD_TYPE | uint32 | uint32 | * | string | uint32 | * | string | * | string | string | uint32 | string | string | uint32 | uint32 | string | uint32 | uint32 | uint32 | 5 | 5 | string | uint32 | float | string | string | string | uint32 | float | string | string | string | uint32 | float | string | string | string | uint32 | float | string | string | string | uint32 | float | string | string | uint32 | string | uint32 | uint32 | uint32 | uint32 |
| FIELD_NAME | id | not_in_shop | * | name | maps | * | description | * | description_recommend | icon | price | type | type_tab | recipe | active_ability | cooldown | active_ability_cooldown_type | passive_abilities | level | stat_list | StatInfo | stat_name | stat_type | stat_value | stat_tag | stat_giver | stat_name | stat_type | stat_value | stat_tag | stat_giver | stat_name | stat_type | stat_value | stat_tag | stat_giver | stat_name | stat_type | stat_value | stat_tag | stat_giver | stat_name | stat_type | stat_value | stat_tag | stat_giver | buyer_level | item_tag | stack_size | max | is_consume | vip_type |
| FIELD_ACES |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| FIELD_DESC | 装备ID | 不显示在商店里面（比如塔的一些装备） | 装备名称 | 装备名称 | 装备生效地图列表 | 描述 | 描述 | 推荐界面描述 | 推荐界面描述 | 装备图标 | 装备价格 | 装备类型 | 页签类型 | 合成材料 | 主动技能 | 主动技能的CoolDown名，默认使用主动技能本身的name | 主动技能Cooldown类型，0为默认，1为团队共享CD | 被动技能 | 装备等级（0-初级，1-中级，2-顶级） | 属性加成 | 加成列表 | 属性名称 | 属性类型 | 属性值 | 如果是唯一，就填唯一Tag | 属性只对指定施法对象类型生效 | 属性名称 | 属性类型 | 属性值 | 如果是唯一，就填唯一Tag | 属性只对指定施法对象类型生效 | 属性名称 | 属性类型 | 属性值 | 如果是唯一，就填唯一Tag | 属性只对指定施法对象类型生效 | 属性名称 | 属性类型 | 属性值 | 如果是唯一，就填唯一Tag | 属性只对指定施法对象类型生效 | 属性名称 | 属性类型 | 属性值 | 如果是唯一，就填唯一Tag | 属性只对指定施法对象类型生效 | 购买者等级 | 物品tag也可以理解为物品类型 | 可叠加数（默认是0，代表不可叠加） | 最多可买数量，0的话为无限 | 是否是消耗品 | 优先推荐 |

```fbs
namespace dataconfig;

table ITEM_CONF
{
    id:uint32(key); // '装备ID'
    not_in_shop:uint32 = 0; // '不显示在商店里面（比如塔的一些装备）'
    name:string; // '装备名称'
    maps:[uint32]; // '装备生效地图列表\n参见arena_mode表'
    description:string; // '描述'
    description_recommend:string; // '推荐界面描述\n描述最多有二十四个字，一行十二个也就是最多两行。'
    icon:string; // '装备图标'
    price:uint32 = 0; // '装备价格'
    type:string; // '装备类型'
    type_tab:string; // '页签类型'
    recipe:[uint32]; // '合成材料'
    active_ability:uint32 = 0; // '主动技能'
    cooldown:string; // '主动技能的CoolDown名，默认使用主动技能本身的name'
    active_ability_cooldown_type:uint32 = 0; // '主动技能Cooldown类型，0为默认，1为团队共享CD'
    passive_abilities:[uint32]; // '被动技能'
    level:uint32 = 0; // '装备等级（0-初级，1-中级，2-顶级）'
    stat_list:[ItemConfStatInfo]; // '属性加成'
    buyer_level:uint32 = 0; // '购买者等级'
    item_tag:string; // '物品tag也可以理解为物品类型'
    stack_size:uint32 = 0; // '可叠加数（默认是0，代表不可叠加）'
    max:uint32 = 0; // '最多可买数量，0的话为无限'
    is_consume:uint32 = 0; // '是否是消耗品'
    vip_type:uint32 = 0; // '优先推荐'
}

table ItemConfStatInfo
{
    stat_name:string; // '属性名称'
    stat_type:uint32 = 0; // '属性类型'
    stat_value:float = 0; // '属性值'
    stat_tag:string; // '如果是唯一，就填唯一Tag'
    stat_giver:string; // '属性只对指定施法对象类型生效'
}

table ITEM_CONF_ARRAY
{
    items:[ITEM_CONF];
}

root_type ITEM_CONF_ARRAY;
```

```protobuf
syntax = "proto2";
package dataconfig;

message ITEM_CONF
{
    required uint32 id = 1; // '装备ID'
    optional uint32 not_in_shop = 2[default = 0]; // '不显示在商店里面（比如塔的一些装备）'
    optional string name = 3; // '装备名称'
    repeated uint32 maps = 4; // '装备生效地图列表\n参见arena_mode表'
    optional string description = 5; // '描述'
    optional string description_recommend = 6; // '推荐界面描述\n描述最多有二十四个字，一行十二个也就是最多两行。'
    optional string icon = 7; // '装备图标'
    optional uint32 price = 8[default = 0]; // '装备价格'
    optional string type = 9; // '装备类型'
    optional string type_tab = 10; // '页签类型'
    repeated uint32 recipe = 11; // '合成材料'
    optional uint32 active_ability = 12[default = 0]; // '主动技能'
    optional string cooldown = 13; // '主动技能的CoolDown名，默认使用主动技能本身的name'
    optional uint32 active_ability_cooldown_type = 14[default = 0]; // '主动技能Cooldown类型，0为默认，1为团队共享CD'
    repeated uint32 passive_abilities = 15; // '被动技能'
    optional uint32 level = 16[default = 0]; // '装备等级（0-初级，1-中级，2-顶级）'
    repeated ItemConfStatInfo stat_list = 17; // '属性加成'
    optional uint32 buyer_level = 18[default = 0]; // '购买者等级'
    optional string item_tag = 19; // '物品tag也可以理解为物品类型'
    optional uint32 stack_size = 20[default = 0]; // '可叠加数（默认是0，代表不可叠加）'
    optional uint32 max = 21[default = 0]; // '最多可买数量，0的话为无限'
    optional uint32 is_consume = 22[default = 0]; // '是否是消耗品'
    optional uint32 vip_type = 23[default = 0]; // '优先推荐'
}

message ItemConfStatInfo
{
    optional string stat_name = 1; // '属性名称'
    optional uint32 stat_type = 2[default = 0]; // '属性类型'
    optional float stat_value = 3[default = 0]; // '属性值'
    optional string stat_tag = 4; // '如果是唯一，就填唯一Tag'
    optional string stat_giver = 5; // '属性只对指定施法对象类型生效'
}

message ITEM_CONF_ARRAY
{
    repeated ITEM_CONF items = 1;
}

```

In this exmaple, we generate nest type `ItemConfStatInfo`, which is repeated in `stat_list` field, and the integer **5** above the field name is max length of the array, and the following field `StatInfo` is a table definition same as the exampe above. Since we has repeated same `ItemConfStatInfo` objects, we just repeat field members, and ignore the table declarasion in the following `ItemConfStatInfo` objects after the first one.

Until now, we get table, nest table, array, and if you like, you can composite more complicated data structure by nesting array and table in any way you can imaging, e.g.

### MALL_CONF
| | | | | | | | | | | | | | | | | | | | | | | | | | | | | | | | | | | | | | | | | | | | | | | | | | | | | | | | | |
|:--|:--|:--|:--|:--|:--|:--|:--|:--|:--|:--|:--|:--|:--|:--|:--|:--|:--|:--|:--|:--|:--|:--|:--|:--|:--|:--|:--|:--|:--|:--|:--|:--|:--|:--|:--|:--|:--|:--|:--|:--|:--|:--|:--|:--|:--|:--|:--|:--|:--|:--|:--|:--|:--|:--|:--|:--|
| FIELD_RULE | optional | optional | optional | optional | optional | optional | optional | optional | optional | optional | optional | optional | repeated | optional | optional | optional | optional | optional | optional | optional | optional | optional | repeated | required_struct | optional | optional | optional | optional | repeated | required_struct | optional | optional | optional | optional | optional | optional | optional | optional | optional | optional | repeated | required_struct | optional | optional | optional | optional | optional | optional | optional | optional | optional | optional | optional | optional | repeated | optional |
| FIELD_TYPE | uint32 | string | string | enum.ItemRarity | bool | bool | DateTime | DateTime | enum.GoodsType | uint32 | enum.MallAchievingType | int32 | enum.MallItemTag | string | enum.MallSubscriptType | DateTime | DateTime | enum.GoodsType | uint32 | uint32 | uint32 | uint32 | 2 | 5 | enum.GoodsType | uint32 | uint32 | uint32 | 2 | 3 | DateTime | DateTime | uint32 | DateTime | DateTime | uint32 | enum.GoodsType | uint32 | uint32 | uint32 | 2 | 3 | DateTime | DateTime | uint32 | DateTime | DateTime | uint32 | uint32 | uint32 | uint32 | uint32 | uint32 | bool | uint32 | bool |
| FIELD_NAME | id | DisplayName | IconPath | Rarity | Enable | IsHide | EnableTime | DisableTime | GoodsType | MaxBuyCount | AchievingType | AchievingData | tags | Desc | SubscriptType | time_start | time_end | RewardGoodsType | RewardGoodsId | RewardGoodsNum | limitID | Discount | prices | SellPriceItem | Type | Id | Cost | OriginalCost | discounts | DiscountPriceItem | Discounttime_start | Discounttime_end | Discount | Discounttime_start | Discounttime_end | Discount | Type | Id | Cost | OriginalCost | discounts | DiscountPriceItem | Discounttime_start | Discounttime_end | Discount | Discounttime_start | Discounttime_end | Discount | Limit | LimitTime | FragmentCost | FragmentNum | ChildItemId | Isfree | IncludeGift | ShowGiftHint |
| FIELD_ACES |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| FIELD_DESC |  | 显示名称 | 图标 | 稀有度，用于外观显示 | 是否上架 | 是否隐藏显示 | 上架时间 | 下架时间 | 资产类型 | 最大购买数量 | 获取途径 | 获取途径的数据，比如，限时活动的id | 标签 | 描述 | 角标类型 | 限时促销开始时间 | 限时促销结束时间 | 获得的资产类型 | 获得的资产的id | 获得的资产的数量 | 限制id，详情查看limit表 | 折扣 | 奖励资源、货币 | 售价结构体 | 资产类型 | ID | 售价 | 原价 | 奖励资源、货币 | 售价结构体 | 折扣开始时间 | 折扣结束时间 | 折扣价 | 折扣开始时间 | 折扣结束时间 | 折扣价 | 资产类型 | ID | 售价 | 原价 | 奖励资源、货币 | 售价结构体 | 折扣开始时间 | 折扣结束时间 | 折扣价 | 折扣开始时间 | 折扣结束时间 | 折扣价 | 限购次数，为0表示不限制次数 | 限购周期(单位：天) | 碎片售价 | 获得的碎片的数量 | 子物品id | 是否免费 | 被包含在礼包的信息 | 是否显示礼包提醒 |


```fbs
include "shared_enum.fbs";

namespace dataconfig;

table MALL_CONF
{
    id:uint32(key);
    DisplayName:string; // '显示名称'
    IconPath:string; // '图标'
    Rarity:ItemRarity = IR_COMMON; // '稀有度，用于外观显示'
    Enable:bool = false; // '是否上架'
    IsHide:bool = false; // '是否隐藏显示'
    EnableTime:uint32; // '上架时间'
    DisableTime:uint32; // '下架时间'
    GoodsType:GoodsType = GT_BAGITEM; // '资产类型'
    MaxBuyCount:uint32 = 0; // '最大购买数量'
    AchievingType:MallAchievingType = MA_NORMAL_SALE; // '获取途径'
    AchievingData:int32 = 0; // '获取途径的数据，比如，限时活动的id'
    tags:[MallItemTag]; // '标签'
    Desc:string; // '描述'
    SubscriptType:MallSubscriptType = ST_NONE; // '角标类型'
    time_start:uint32; // '限时促销开始时间'
    time_end:uint32; // '限时促销结束时间'
    RewardGoodsType:GoodsType = GT_BAGITEM; // '获得的资产类型'
    RewardGoodsId:uint32 = 0; // '获得的资产的id'
    RewardGoodsNum:uint32 = 0; // '获得的资产的数量'
    limitID:uint32 = 0; // '限制id，详情查看limit表'
    Discount:uint32 = 0; // '折扣'
    prices:[MallConfSellPriceItem]; // '奖励资源、货币'
    Limit:uint32 = 0; // '限购次数，为0表示不限制次数'
    LimitTime:uint32 = 0; // '限购周期(单位：天)'
    FragmentCost:uint32 = 0; // '碎片售价'
    FragmentNum:uint32 = 0; // '获得的碎片的数量'
    ChildItemId:uint32 = 0; // '子物品id'
    Isfree:bool = false; // '是否免费'
    IncludeGift:[uint32]; // '被包含在礼包的信息'
    ShowGiftHint:bool = false; // '是否显示礼包提醒'
}

table MallConfSellPriceItem
{
    Type:GoodsType = GT_BAGITEM; // '资产类型'
    Id:uint32(key); // 'ID'
    Cost:uint32 = 0; // '售价'
    OriginalCost:uint32 = 0; // '原价'
    discounts:[MallConfDiscountPriceItem]; // '奖励资源、货币'
}

table MallConfDiscountPriceItem
{
    Discounttime_start:uint32; // '折扣开始时间'
    Discounttime_end:uint32; // '折扣结束时间'
    Discount:uint32 = 0; // '折扣价'
}

table MALL_CONF_ARRAY
{
    items:[MALL_CONF];
}

root_type MALL_CONF_ARRAY;

```

```protobuf
syntax = "proto2";
import "shared_enum.proto";

package dataconfig;

message MALL_CONF
{
    optional uint32 id = 1;
    optional string DisplayName = 2; // '显示名称'
    optional string IconPath = 3; // '图标'
    optional ItemRarity Rarity = 4[default = IR_COMMON]; // '稀有度，用于外观显示'
    optional bool Enable = 5[default = false]; // '是否上架'
    optional bool IsHide = 6[default = false]; // '是否隐藏显示'
    optional uint32 EnableTime = 7; // '上架时间'
    optional uint32 DisableTime = 8; // '下架时间'
    optional GoodsType GoodsType = 9[default = GT_BAGITEM]; // '资产类型'
    optional uint32 MaxBuyCount = 10[default = 0]; // '最大购买数量'
    optional MallAchievingType AchievingType = 11[default = MA_NORMAL_SALE]; // '获取途径'
    optional int32 AchievingData = 12[default = 0]; // '获取途径的数据，比如，限时活动的id'
    repeated MallItemTag tags = 13; // '标签'
    optional string Desc = 14; // '描述'
    optional MallSubscriptType SubscriptType = 15[default = ST_NONE]; // '角标类型'
    optional uint32 time_start = 16; // '限时促销开始时间'
    optional uint32 time_end = 17; // '限时促销结束时间'
    optional GoodsType RewardGoodsType = 18[default = GT_BAGITEM]; // '获得的资产类型'
    optional uint32 RewardGoodsId = 19[default = 0]; // '获得的资产的id'
    optional uint32 RewardGoodsNum = 20[default = 0]; // '获得的资产的数量'
    optional uint32 limitID = 21[default = 0]; // '限制id，详情查看limit表'
    optional uint32 Discount = 22[default = 0]; // '折扣'
    repeated MallConfSellPriceItem prices = 23; // '奖励资源、货币'
    optional uint32 Limit = 24[default = 0]; // '限购次数，为0表示不限制次数'
    optional uint32 LimitTime = 25[default = 0]; // '限购周期(单位：天)'
    optional uint32 FragmentCost = 26[default = 0]; // '碎片售价'
    optional uint32 FragmentNum = 27[default = 0]; // '获得的碎片的数量'
    optional uint32 ChildItemId = 28[default = 0]; // '子物品id'
    optional bool Isfree = 29[default = false]; // '是否免费'
    repeated uint32 IncludeGift = 30; // '被包含在礼包的信息'
    optional bool ShowGiftHint = 31[default = false]; // '是否显示礼包提醒'
}

message MallConfSellPriceItem
{
    optional GoodsType Type = 1[default = GT_BAGITEM]; // '资产类型'
    optional uint32 Id = 2; // 'ID'
    optional uint32 Cost = 3[default = 0]; // '售价'
    optional uint32 OriginalCost = 4[default = 0]; // '原价'
    repeated MallConfDiscountPriceItem discounts = 5; // '奖励资源、货币'
}

message MallConfDiscountPriceItem
{
    optional uint32 Discounttime_start = 1; // '折扣开始时间'
    optional uint32 Discounttime_end = 2; // '折扣结束时间'
    optional uint32 Discount = 3[default = 0]; // '折扣价'
}

message MALL_CONF_ARRAY
{
    repeated MALL_CONF items = 1;
}

```

More often, we just wanna generate simple array which contains scalar values, e.g. uint, bool. In this situation, we just declare a array same as `maps` field, in which the type cell value is scalar type, and the rule cell value is **repeated**, `flatcfg` will split each value by `;`, and generate array with related type declared in the type cell.

# Enum
Both `FlatBuffers` and `protobuf` support `enum` type, `flatcfg` also support `enum` declaration, e.g.

### MAIL_CONF
| | | | | | | | | | | | | | | | | | |
|:--|:--|:--|:--|:--|:--|:--|:--|:--|:--|:--|:--|:--|:--|:--|:--|:--|:--|
| FIELD_RULE | optional | optional | optional | optional | optional | optional | optional | optional | optional | optional | optional | optional | optional | optional | optional | optional | optional |
| FIELD_TYPE | uint32 | enum.MailConditionType | int32 | int32 | enum.CliLanguageType | int32 | string | string | int32 | string | enum.MailType | int32 | string | int32 | date | date | int32 |
| FIELD_NAME | id | condition_type | zone_id | version | language | is_copy_content | title | contents | enable | desc | type | client_sys_jump | client_web_jump | expire_time | time_start | time_end | reward_goods |
| FIELD_ACES |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| FIELD_DESC | id | 邮件目标条件类型 | zone_id | 版本号 | 语言（CLT_TYPE_ALL 全部发，CLT_TYPE_JP 发日本玩家，CLT_TYPE_CH 发中文 0CLT_TYPE_NONE， 发其他国家，其他值忽略） | 是否把邮件内容copy一封到db | 标题 | 内容 | 是否上架 | 描述 | 邮件类型 | 客户端跳转 | 跳转到web | 过期天数 | 开始时间 | 结束时间 | 礼包id |

Let's inspect `condition_type` field in this exmaple, there's `enum.MaillConditionType` in the type cell, the type is defined above, this is a extend type, you can custom enum type and prepend `enum.` before the enum type name, then `flatcfg` will parse all field values as a enum case, and also generate a enum class for you, e.g.

```csharp
enum MailConditionType:ubyte
{
    MCT_TYPE_EVENT = 0
}
```
And if you assign a default value to `condition_type` field like `condition_type=MCT_NONE`, then the enum definition will be as following, and will assign the defualt value to those empty cells.

```csharp
enum MailConditionType:ubyte
{
    MCT_NONE = 0
    MCT_TYPE_EVENT = 1
}
```


`MAIL_CONF` schema

```fbs
include "shared_enum.fbs";

namespace dataconfig;

table MAIL_CONF
{
    id:uint32(key); // 'id'
    condition_type:MailConditionType = MCT_TYPE_EVENT; // '邮件目标条件类型'
    zone_id:int32 = 0; // 'zone_id'
    version:int32 = 0; // '版本号'
    language:CliLanguageType = CLT_TYPE_ALL; // '语言（CLT_TYPE_ALL 全部发，CLT_TYPE_JP 发日本玩家，CLT_TYPE_CH 发中文 0CLT_TYPE_NONE， 发其他国家，其他值忽略）'
    is_copy_content:int32 = 0; // '是否把邮件内容copy一封到db'
    title:string; // '标题'
    contents:string; // '内容'
    enable:int32 = 0; // '是否上架'
    desc:string; // '描述'
    type:MailType = MT_TYPE_SYSTEM; // '邮件类型'
    client_sys_jump:int32 = 0; // '客户端跳转'
    client_web_jump:string; // '跳转到web'
    expire_time:int32 = 0; // '过期天数'
    time_start:uint32; // '开始时间'
    time_end:uint32; // '结束时间'
    reward_goods:int32 = 0; // '礼包id'
}

table MAIL_CONF_ARRAY
{
    items:[MAIL_CONF];
}

root_type MAIL_CONF_ARRAY;
```
`MAIL_CONF` messages
```protobuf
syntax = "proto2";
import "shared_enum.proto";

package dataconfig;

message MAIL_CONF
{
    optional uint32 id = 1; // 'id'
    optional MailConditionType condition_type = 2[default = MCT_TYPE_EVENT]; // '邮件目标条件类型'
    optional int32 zone_id = 3[default = 0]; // 'zone_id'
    optional int32 version = 4[default = 0]; // '版本号'
    optional CliLanguageType language = 5[default = CLT_TYPE_ALL]; // '语言（CLT_TYPE_ALL 全部发，CLT_TYPE_JP 发日本玩家，CLT_TYPE_CH 发中文 0CLT_TYPE_NONE， 发其他国家，其他值忽略）'
    optional int32 is_copy_content = 6[default = 0]; // '是否把邮件内容copy一封到db'
    optional string title = 7; // '标题'
    optional string contents = 8; // '内容'
    optional int32 enable = 9[default = 0]; // '是否上架'
    optional string desc = 10; // '描述'
    optional MailType type = 11[default = MT_TYPE_SYSTEM]; // '邮件类型'
    optional int32 client_sys_jump = 12[default = 0]; // '客户端跳转'
    optional string client_web_jump = 13; // '跳转到web'
    optional int32 expire_time = 14[default = 0]; // '过期天数'
    optional uint32 time_start = 15; // '开始时间'
    optional uint32 time_end = 16; // '结束时间'
    optional int32 reward_goods = 17[default = 0]; // '礼包id'
}

message MAIL_CONF_ARRAY
{
    repeated MAIL_CONF items = 1;
}
```

# DateTime
Setting `date` to the type cell, `flatcfg` will parse field values as date with format `%Y-%m-%d %H:%M:%S`, and if you set time zone parameter, `flatcfg` will parse date string into specific time-zone value, and the result will be an `uint` value.

# Duration
Setting `duration` to the type cell, `flatcfg` will parse field values as duration with format `DAY:HOUR:MINUTES:SECONDS`, the result will be an `uint` value.

# Key Sorting

Sometimes if we want a key-sorted data, we can add an `id` field name into table definition, `flatcfg` will perform sorting on `id` key, and this will be convenient for binary searching which is used in `FlatBuffers`.
