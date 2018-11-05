# Prepare
## install `python3`/`pip3`
### python libraries `flatbuffers`,`protobuf`, `xlrd`
### install command line tools `flatc`,`protoc`

# Serialize 

> FOO_CONF

| | | | | | | | | | | | | | | | | | | | | | | | | | | | | | |
|:--|:--|:--|:--|:--|:--|:--|:--|:--|:--|:--|:--|:--|:--|:--|:--|:--|:--|:--|:--|:--|:--|:--|:--|:--|:--|:--|:--|:--|:--|
| FIELD_RULE | required | optional | repeated | optional | optional | optional | optional | optional | optional | optional | optional | optional | repeated | optional | optional | repeated | optional | optional | optional | optional | optional | optional | optional | optional | optional | optional | optional | optional | optional |
| FIELD_TYPE | uint32 | string | uint32 | string | string | 4 | string | uint32 | float | 2 | string | uint32 | float | float | uint32 | 2 | 4 | string | uint32 | float | 2 | string | uint32 | string | uint32 | float | 2 | string | uint32 |
| FIELD_NAME | id | name | maps | description | description_recommend | base_stat=StatInfo | name | type | value | nest_object | name | value | float_attrs | ratio | price | stat_list | StatInfo | name | type | value | nest_object | name | value | name | type | value | nest_object | name | value |
| FIELD_ACES |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| FIELD_DESC | 装备ID | 装备名称 | 装备生效地图列表 | 描述 | 推荐界面描述 | 基础属性 | 属性名 | 属性类型 | 属性加成 | 嵌套测试 |  |  | 浮点列表 | 浮点数 | 装备价格 | 属性加成 | 加成列表 | 属性名称 | 属性类型 | 属性值 | 嵌套测试 |  |  | 属性名称 | 属性类型 | 属性值 | 嵌套测试 |  |  |
| FIELD_DATA | 2001 | 自爆 | 0;100;105;108;204;205;206;207 | 自爆 | 自爆 |  | damage | 1 | 0.8 |  | name_2001 | 123 | 0.642;0.911;0.151;0.164 | 0.69 | 350 | 1 |  | attack_damage_percent | 3 | 2 |  | name1 | 100 |  |  |  |  |  |  |
| FIELD_DATA | 2002 | 子弹 | 0;100;105;108;204;205;206;207;210 | +75%全额护甲穿透。 |  |  | damage | 2 | 0.5 |  | name_2002 | 321 | 0.223;0.543;0.628;0.155 | 0.964 | 600 | 2 |  | armor_penetration_percent | 4 | 0.75 |  | name2 | 200 | armor_penetration_percent_1 | 3 | 0.85 |  | Name21 | 401 |

> FlatBuffers

```
python3 ./flatcfg.py -f demo/foo.xlsx
```

```fbs
namespace dataconfig;

table FOO_CONF
{
    id:uint32(key); // '装备ID'
    name:string; // '装备名称'
    maps:[uint32]; // '装备生效地图列表\n参见arena_mode表'
    description:string; // '描述'
    description_recommend:string; // '推荐界面描述\n描述最多有二十四个字，一行十二个也就是最多两行。'
    base_stat:FooConfStatInfo; // '基础属性'
    float_attrs:[float]; // '浮点列表'
    ratio:float = 0; // '浮点数'
    price:uint32 = 0; // '装备价格'
    stat_list:[FooConfStatInfo]; // '属性加成'
}

table FooConfStatInfo
{
    name:string; // '属性名'
    type:uint32 = 0; // '属性类型'
    value:float = 0; // '属性加成'
    nest_object:FooConfNestObject; // '嵌套测试'
}

table FooConfNestObject
{
    name:string;
    value:uint32 = 0;
}

table FOO_CONF_ARRAY
{
    items:[FOO_CONF];
}

root_type FOO_CONF_ARRAY;
```

```json
{
  "items": [
    {
      "id": 2001,
      "name": "\u81EA\u7206",
      "maps": [
        0,
        100,
        105,
        108,
        204,
        205,
        206,
        207
      ],
      "description": "\u81EA\u7206",
      "description_recommend": "\u81EA\u7206",
      "base_stat": {
        "name": "damage",
        "type": 1,
        "value": 0.8,
        "nest_object": {
          "name": "name_2001",
          "value": 123
        }
      },
      "float_attrs": [
        0.642,
        0.911,
        0.151,
        0.164
      ],
      "ratio": 0.69,
      "price": 350,
      "stat_list": [
        {
          "name": "attack_damage_percent",
          "type": 3,
          "value": 2.0,
          "nest_object": {
            "name": "name1",
            "value": 100
          }
        }
      ]
    },
    {
      "id": 2002,
      "name": "\u5B50\u5F39",
      "maps": [
        0,
        100,
        105,
        108,
        204,
        205,
        206,
        207,
        210
      ],
      "description": "+75%\u5168\u989D\u62A4\u7532\u7A7F\u900F\u3002\n\u552F\u4E00\u88AB\u52A8-\u65E0\u89C6\u95EA\u907F\uFF1A\u9632\u5FA1\u5854\u7684\u653B\u51FB\u4E0D\u4F1A\u88AB\u95EA\u907F\u3002\n\u552F\u4E00\u88AB\u52A8-\u9884\u70ED\uFF1A\u9632\u5FA1\u5854\u5728\u653B\u51FB\u4E00\u4E2A\u82F1\u96C4\u65F6\uFF0C\u6BCF\u6B21\u653B\u51FB\u7684\u4F24\u5BB3\u63D0\u534737.5%\uFF0C\u6700\u591A\u63D0\u534775%\u4F24\u5BB3\u3002\n\u552F\u4E00\u88AB\u52A8-\u5347\u6E29\uFF1A\u5728\u9632\u5FA1\u5854\u5B8C\u5168\u9884\u70ED\u540E\uFF0C\u5BF9\u76F8\u540C\u82F1\u96C4\u7684\u8FDE\u7EED\u653B\u51FB\u5C06\u9020\u621025%\u989D\u5916\u4F24\u5BB3\uFF0C\u6700\u591A\u9020\u621050%\u989D\u5916\u4F24\u5BB3\u3002",
      "description_recommend": "",
      "base_stat": {
        "name": "damage",
        "type": 2,
        "value": 0.5,
        "nest_object": {
          "name": "name_2002",
          "value": 321
        }
      },
      "float_attrs": [
        0.223,
        0.543,
        0.628,
        0.155
      ],
      "ratio": 0.964,
      "price": 600,
      "stat_list": [
        {
          "name": "armor_penetration_percent",
          "type": 4,
          "value": 0.75,
          "nest_object": {
            "name": "name2",
            "value": 200
          }
        },
        {
          "name": "armor_penetration_percent_1",
          "type": 3,
          "value": 0.85,
          "nest_object": {
            "name": "Name21",
            "value": 401
          }
        }
      ]
    }
  ]
}
```
> Protobuf

```
python3 ./flatcfg.py -f demo/foo.xlsx -u
```

```protobuf
syntax = "proto2";
package dataconfig;

message FOO_CONF
{
    required uint32 id = 1; // '装备ID'
    optional string name = 2; // '装备名称'
    repeated uint32 maps = 3; // '装备生效地图列表\n参见arena_mode表'
    optional string description = 4; // '描述'
    optional string description_recommend = 5; // '推荐界面描述\n描述最多有二十四个字，一行十二个也就是最多两行。'
    optional FooConfStatInfo base_stat = 6; // '基础属性'
    repeated float float_attrs = 7; // '浮点列表'
    optional float ratio = 8[default = 0]; // '浮点数'
    optional uint32 price = 9[default = 0]; // '装备价格'
    repeated FooConfStatInfo stat_list = 10; // '属性加成'
}

message FooConfStatInfo
{
    optional string name = 1; // '属性名'
    optional uint32 type = 2[default = 0]; // '属性类型'
    optional float value = 3[default = 0]; // '属性加成'
    optional FooConfNestObject nest_object = 4; // '嵌套测试'
}

message FooConfNestObject
{
    optional string name = 1;
    optional uint32 value = 2[default = 0];
}

message FOO_CONF_ARRAY
{
    repeated FOO_CONF items = 1;
}
```

```json
items {
  id: 2001
  name: "\350\207\252\347\210\206"
  maps: 0
  maps: 100
  maps: 105
  maps: 108
  maps: 204
  maps: 205
  maps: 206
  maps: 207
  description: "\350\207\252\347\210\206"
  description_recommend: "\350\207\252\347\210\206"
  base_stat {
    name: "damage"
    type: 1
    value: 0.8
    nest_object {
      name: "name_2001"
      value: 123
    }
  }
  float_attrs: 0.642
  float_attrs: 0.911
  float_attrs: 0.151
  float_attrs: 0.164
  ratio: 0.69
  price: 350
  stat_list {
    name: "attack_damage_percent"
    type: 3
    value: 2
    nest_object {
      name: "name1"
      value: 100
    }
  }
}
items {
  id: 2002
  name: "\345\255\220\345\274\271"
  maps: 0
  maps: 100
  maps: 105
  maps: 108
  maps: 204
  maps: 205
  maps: 206
  maps: 207
  maps: 210
  description: "+75%\345\205\250\351\242\235\346\212\244\347\224\262\347\251\277\351\200\217\343\200\202\n\345\224\257\344\270\200\350\242\253\345\212\250-\346\227\240\350\247\206\351\227\252\351\201\277\357\274\232\351\230\262\345\276\241\345\241\224\347\232\204\346\224\273\345\207\273\344\270\215\344\274\232\350\242\253\351\227\252\351\201\277\343\200\202\n\345\224\257\344\270\200\350\242\253\345\212\250-\351\242\204\347\203\255\357\274\232\351\230\262\345\276\241\345\241\224\345\234\250\346\224\273\345\207\273\344\270\200\344\270\252\350\213\261\351\233\204\346\227\266\357\274\214\346\257\217\346\254\241\346\224\273\345\207\273\347\232\204\344\274\244\345\256\263\346\217\220\345\215\20737.5%\357\274\214\346\234\200\345\244\232\346\217\220\345\215\20775%\344\274\244\345\256\263\343\200\202\n\345\224\257\344\270\200\350\242\253\345\212\250-\345\215\207\346\270\251\357\274\232\345\234\250\351\230\262\345\276\241\345\241\224\345\256\214\345\205\250\351\242\204\347\203\255\345\220\216\357\274\214\345\257\271\347\233\270\345\220\214\350\213\261\351\233\204\347\232\204\350\277\236\347\273\255\346\224\273\345\207\273\345\260\206\351\200\240\346\210\22025%\351\242\235\345\244\226\344\274\244\345\256\263\357\274\214\346\234\200\345\244\232\351\200\240\346\210\22050%\351\242\235\345\244\226\344\274\244\345\256\263\343\200\202"
  description_recommend: ""
  base_stat {
    name: "damage"
    type: 2
    value: 0.5
    nest_object {
      name: "name_2002"
      value: 321
    }
  }
  float_attrs: 0.223
  float_attrs: 0.543
  float_attrs: 0.628
  float_attrs: 0.155
  ratio: 0.964
  price: 600
  stat_list {
    name: "armor_penetration_percent"
    type: 4
    value: 0.75
    nest_object {
      name: "name2"
      value: 200
    }
  }
  stat_list {
    name: "armor_penetration_percent_1"
    type: 3
    value: 0.85
    nest_object {
      name: "Name21"
      value: 401
    }
  }
}
```

# Serialize with fixed float encoding
> FlatBuffers

```
python3 ./flatcfg.py -f demo/foo.xlsx -32
```

```
// + /Users/larryhou/Downloads/flatcfg/temp/shared_FixedFloat32.fbs
namespace dataconfig;

table FixedFloat32
{
    memory:int32 = 0; // 'representation of float32 value'
}


//# FOO_CONF
//+ /Users/larryhou/Downloads/flatcfg/temp/foo_conf.fbs
include "shared_FixedFloat32.fbs";

namespace dataconfig;

table FOO_CONF
{
    id:uint32(key); // '装备ID'
    name:string; // '装备名称'
    maps:[uint32]; // '装备生效地图列表\n参见arena_mode表'
    description:string; // '描述'
    description_recommend:string; // '推荐界面描述\n描述最多有二十四个字，一行十二个也就是最多两行。'
    base_stat:FooConfStatInfo; // '基础属性'
    float_attrs:[FixedFloat32];
    ratio:FixedFloat32;
    price:uint32 = 0; // '装备价格'
    stat_list:[FooConfStatInfo]; // '属性加成'
}

table FooConfStatInfo
{
    name:string; // '属性名'
    type:uint32 = 0; // '属性类型'
    value:FixedFloat32;
    nest_object:FooConfNestObject; // '嵌套测试'
}

table FooConfNestObject
{
    name:string;
    value:uint32 = 0;
}

table FOO_CONF_ARRAY
{
    items:[FOO_CONF];
}

root_type FOO_CONF_ARRAY;
```

```json
{
  "items": [
    {
      "id": 2001,
      "name": "\u81EA\u7206",
      "maps": [
        0,
        100,
        105,
        108,
        204,
        205,
        206,
        207
      ],
      "description": "\u81EA\u7206",
      "description_recommend": "\u81EA\u7206",
      "base_stat": {
        "name": "damage",
        "type": 1,
        "value": {
          "memory": 819
        },
        "nest_object": {
          "name": "name_2001",
          "value": 123
        }
      },
      "float_attrs": [
        {
          "memory": 657
        },
        {
          "memory": 932
        },
        {
          "memory": 154
        },
        {
          "memory": 167
        }
      ],
      "ratio": {
        "memory": 706
      },
      "price": 350,
      "stat_list": [
        {
          "name": "attack_damage_percent",
          "type": 3,
          "value": {
            "memory": 2048
          },
          "nest_object": {
            "name": "name1",
            "value": 100
          }
        }
      ]
    },
    {
      "id": 2002,
      "name": "\u5B50\u5F39",
      "maps": [
        0,
        100,
        105,
        108,
        204,
        205,
        206,
        207,
        210
      ],
      "description": "+75%\u5168\u989D\u62A4\u7532\u7A7F\u900F\u3002\n\u552F\u4E00\u88AB\u52A8-\u65E0\u89C6\u95EA\u907F\uFF1A\u9632\u5FA1\u5854\u7684\u653B\u51FB\u4E0D\u4F1A\u88AB\u95EA\u907F\u3002\n\u552F\u4E00\u88AB\u52A8-\u9884\u70ED\uFF1A\u9632\u5FA1\u5854\u5728\u653B\u51FB\u4E00\u4E2A\u82F1\u96C4\u65F6\uFF0C\u6BCF\u6B21\u653B\u51FB\u7684\u4F24\u5BB3\u63D0\u534737.5%\uFF0C\u6700\u591A\u63D0\u534775%\u4F24\u5BB3\u3002\n\u552F\u4E00\u88AB\u52A8-\u5347\u6E29\uFF1A\u5728\u9632\u5FA1\u5854\u5B8C\u5168\u9884\u70ED\u540E\uFF0C\u5BF9\u76F8\u540C\u82F1\u96C4\u7684\u8FDE\u7EED\u653B\u51FB\u5C06\u9020\u621025%\u989D\u5916\u4F24\u5BB3\uFF0C\u6700\u591A\u9020\u621050%\u989D\u5916\u4F24\u5BB3\u3002",
      "description_recommend": "",
      "base_stat": {
        "name": "damage",
        "type": 2,
        "value": {
          "memory": 512
        },
        "nest_object": {
          "name": "name_2002",
          "value": 321
        }
      },
      "float_attrs": [
        {
          "memory": 228
        },
        {
          "memory": 556
        },
        {
          "memory": 643
        },
        {
          "memory": 158
        }
      ],
      "ratio": {
        "memory": 987
      },
      "price": 600,
      "stat_list": [
        {
          "name": "armor_penetration_percent",
          "type": 4,
          "value": {
            "memory": 768
          },
          "nest_object": {
            "name": "name2",
            "value": 200
          }
        },
        {
          "name": "armor_penetration_percent_1",
          "type": 3,
          "value": {
            "memory": 870
          },
          "nest_object": {
            "name": "Name21",
            "value": 401
          }
        }
      ]
    }
  ]
}
```

> Protobuf
```
python3 ./flatcfg.py -f demo/foo.xlsx -32 -u
```

```protobuf
//+ /Users/larryhou/Downloads/flatcfg/temp/shared_FixedFloat32.proto
syntax = "proto2";
package dataconfig;

message FixedFloat32
{
    optional int32 memory = 1[default = 0]; // 'representation of float32 value'
}


//# FOO_CONF
//+ /Users/larryhou/Downloads/flatcfg/temp/foo_conf.proto
syntax = "proto2";
import "shared_FixedFloat32.proto";

package dataconfig;

message FOO_CONF
{
    required uint32 id = 1; // '装备ID'
    optional string name = 2; // '装备名称'
    repeated uint32 maps = 3; // '装备生效地图列表\n参见arena_mode表'
    optional string description = 4; // '描述'
    optional string description_recommend = 5; // '推荐界面描述\n描述最多有二十四个字，一行十二个也就是最多两行。'
    optional FooConfStatInfo base_stat = 6; // '基础属性'
    repeated FixedFloat32 float_attrs = 7;
    optional FixedFloat32 ratio = 8;
    optional uint32 price = 9[default = 0]; // '装备价格'
    repeated FooConfStatInfo stat_list = 10; // '属性加成'
}

message FooConfStatInfo
{
    optional string name = 1; // '属性名'
    optional uint32 type = 2[default = 0]; // '属性类型'
    optional FixedFloat32 value = 3;
    optional FooConfNestObject nest_object = 4; // '嵌套测试'
}

message FooConfNestObject
{
    optional string name = 1;
    optional uint32 value = 2[default = 0];
}

message FOO_CONF_ARRAY
{
    repeated FOO_CONF items = 1;
}
```

```json
items {
  id: 2001
  name: "\350\207\252\347\210\206"
  maps: 0
  maps: 100
  maps: 105
  maps: 108
  maps: 204
  maps: 205
  maps: 206
  maps: 207
  description: "\350\207\252\347\210\206"
  description_recommend: "\350\207\252\347\210\206"
  base_stat {
    name: "damage"
    type: 1
    value {
      memory: 819
    }
    nest_object {
      name: "name_2001"
      value: 123
    }
  }
  float_attrs {
    memory: 657
  }
  float_attrs {
    memory: 932
  }
  float_attrs {
    memory: 154
  }
  float_attrs {
    memory: 167
  }
  ratio {
    memory: 706
  }
  price: 350
  stat_list {
    name: "attack_damage_percent"
    type: 3
    value {
      memory: 2048
    }
    nest_object {
      name: "name1"
      value: 100
    }
  }
}
items {
  id: 2002
  name: "\345\255\220\345\274\271"
  maps: 0
  maps: 100
  maps: 105
  maps: 108
  maps: 204
  maps: 205
  maps: 206
  maps: 207
  maps: 210
  description: "+75%\345\205\250\351\242\235\346\212\244\347\224\262\347\251\277\351\200\217\343\200\202\n\345\224\257\344\270\200\350\242\253\345\212\250-\346\227\240\350\247\206\351\227\252\351\201\277\357\274\232\351\230\262\345\276\241\345\241\224\347\232\204\346\224\273\345\207\273\344\270\215\344\274\232\350\242\253\351\227\252\351\201\277\343\200\202\n\345\224\257\344\270\200\350\242\253\345\212\250-\351\242\204\347\203\255\357\274\232\351\230\262\345\276\241\345\241\224\345\234\250\346\224\273\345\207\273\344\270\200\344\270\252\350\213\261\351\233\204\346\227\266\357\274\214\346\257\217\346\254\241\346\224\273\345\207\273\347\232\204\344\274\244\345\256\263\346\217\220\345\215\20737.5%\357\274\214\346\234\200\345\244\232\346\217\220\345\215\20775%\344\274\244\345\256\263\343\200\202\n\345\224\257\344\270\200\350\242\253\345\212\250-\345\215\207\346\270\251\357\274\232\345\234\250\351\230\262\345\276\241\345\241\224\345\256\214\345\205\250\351\242\204\347\203\255\345\220\216\357\274\214\345\257\271\347\233\270\345\220\214\350\213\261\351\233\204\347\232\204\350\277\236\347\273\255\346\224\273\345\207\273\345\260\206\351\200\240\346\210\22025%\351\242\235\345\244\226\344\274\244\345\256\263\357\274\214\346\234\200\345\244\232\351\200\240\346\210\22050%\351\242\235\345\244\226\344\274\244\345\256\263\343\200\202"
  description_recommend: ""
  base_stat {
    name: "damage"
    type: 2
    value {
      memory: 512
    }
    nest_object {
      name: "name_2002"
      value: 321
    }
  }
  float_attrs {
    memory: 228
  }
  float_attrs {
    memory: 556
  }
  float_attrs {
    memory: 643
  }
  float_attrs {
    memory: 158
  }
  ratio {
    memory: 987
  }
  price: 600
  stat_list {
    name: "armor_penetration_percent"
    type: 4
    value {
      memory: 768
    }
    nest_object {
      name: "name2"
      value: 200
    }
  }
  stat_list {
    name: "armor_penetration_percent_1"
    type: 3
    value {
      memory: 870
    }
    nest_object {
      name: "Name21"
      value: 401
    }
  }
}
```