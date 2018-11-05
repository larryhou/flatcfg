#!/usr/bin/env python3
import enum, xlrd, re, io, json, os, hashlib, datetime
import os.path as p
from typing import Dict
import operator
import flatbuffers
from google.protobuf.internal.enum_type_wrapper import EnumTypeWrapper

ROW_RULE_INDEX, \
ROW_TYPE_INDEX, \
ROW_NAME_INDEX, \
ROW_ACES_INDEX, \
ROW_DESC_INDEX, \
ROW_DATA_INDEX = range(6)

SHARED_PREFIX = 'shared_'
SHARED_ENUM_NAME = '{}enum'.format(SHARED_PREFIX)
ROOT_CLASS_TEMPLATE = '{}_ARRAY'
FIXED_MEMORY_NAME = 'memory'

class FieldType(enum.Enum):
    float, float32, float64, double, \
    int16, uint16, int8 , uint8 , \
    int, uint, int32, uint32, int64, uint64, \
    short, ushort, byte, ubyte, long, ulong, \
    bool, string = range(22) # standard protobuf scalar types
    date, duration, enum, table, array = tuple(x + 100 for x in range(5)) # extend field types

class type_presets(object):
    ints = (FieldType.byte, FieldType.int8, FieldType.short, FieldType.int16, FieldType.int, FieldType.int32, FieldType.int64, FieldType.long)
    uints = (FieldType.ubyte, FieldType.uint8, FieldType.ushort, FieldType.uint16, FieldType.uint, FieldType.uint32, FieldType.uint64, FieldType.ulong)
    floats = (FieldType.float, FieldType.float32, FieldType.double, FieldType.float64)
    size_1 = (FieldType.byte, FieldType.ubyte, FieldType.bool, FieldType.int8, FieldType.uint8, FieldType.enum)
    size_2 = (FieldType.short, FieldType.int16, FieldType.ushort, FieldType.uint16)
    size_4 = (FieldType.int, FieldType.uint, FieldType.int32, FieldType.uint32, FieldType.float, FieldType.float32, FieldType.date, FieldType.duration)
    size_8 = (FieldType.long, FieldType.int64, FieldType.ulong, FieldType.uint64, FieldType.double, FieldType.float64)
    nests = (FieldType.table, FieldType.array)

    @classmethod
    def alias(cls, t:FieldType)->FieldType:
        if t == FieldType.float32: return FieldType.float
        if t == FieldType.float64: return FieldType.double
        if t == FieldType.uint8: return FieldType.ubyte
        if t == FieldType.int8: return FieldType.byte
        if t == FieldType.uint16: return FieldType.ushort
        if t == FieldType.int16: return FieldType.short
        if t == FieldType.uint32: return FieldType.uint
        if t == FieldType.int32: return FieldType.int
        if t == FieldType.uint64: return FieldType.ulong
        if t == FieldType.int64: return FieldType.long
        return t

class FieldRule(enum.Enum):
    optional, required, repeated = range(3)

class FieldAccess(enum.Enum):
    default, client, server = range(3)

    @classmethod
    def get_option_choices(cls):
        return [name for name in cls.__members__]

    @classmethod
    def get_value(cls, name:str)->'FieldAccess':
        return cls.__members__.get(name) if name in cls.__members__ else FieldAccess.default

class FieldTag(enum.Enum):
    none, fixed_float32, fixed_float64 = range(3)

class FieldObject(object):
    def __init__(self):
        self.name:str = None
        self.type:FieldType = FieldType.string
        self.rule:FieldRule = FieldRule.optional
        self.offset:int = 0
        self.size:int = 1
        self.access:FieldAccess = FieldAccess.default
        self.description:str = ''
        self.default:str = ''
        self.tag:FieldTag = FieldTag.none

    def fill(self, f:'FieldObject'):
        for name, value in vars(f).items():
            if not name.startswith('_') and name.islower():
                self.__setattr__(name, value)

    def equal(self, f:'FieldObject')->bool:
        return self.name == f.name \
               and self.type == f.type \
               and self.size == f.size \
               and self.rule == f.rule if self.rule == FieldRule.repeated or f.rule == FieldRule.repeated else True

    def to_string(self, v:enum.Enum):
        return v.name if v else ''

    def __repr__(self):
        return 'name:{} type:{!r} rule:{!r} size:{} offset:{} access:{!r} desc:{!r}'\
            .format(self.name, self.to_string(self.type), self.to_string(self.rule), self.size, self.offset, self.to_string(self.access), self.description)

class EnumFieldObject(FieldObject):
    def __init__(self, name:str):
        super(EnumFieldObject, self).__init__()
        self.type = FieldType.enum
        self.enum:str = name
        self.case_map:dict[str, int] = {}

    def import_cases(self, case_list, auto_default_case = True): # type: (list[str], bool)->None
        offset = 0
        if self.case_map:
            for index in self.case_map.values():
                if index > offset: offset = index
            offset += 1
        elif auto_default_case:
            abbr = re.findall(r'[A-Z]', self.enum)[:2]
            default = self.default
            if not default: default = '{}_NONE'.format(''.join(abbr))
            self.default = default
            self.case_map[default] = offset
            offset += 1
        for case_name in case_list:
            if case_name not in self.case_map:
                self.case_map[case_name] = offset
                offset += 1

    def hook_default(self)->str:
        if not self.default:
            offset = 0xFFFF
            default = ''
            if self.case_map:
                for name, index in self.case_map.items():
                    if index < offset:
                        offset = index
                        default = name
            self.default = default
        return self.default


class ArrayFieldObject(FieldObject):
    def __init__(self, count:int):
        super(ArrayFieldObject, self).__init__()
        self.type = FieldType.array
        self.table: TableFieldObject = None
        self.elements: [TableFieldObject] = []
        self.__count:int = count
        assert count > 0

    @property
    def count(self) -> int: return self.__count

    def equal(self, f:'ArrayFieldObject'):
        assert isinstance(f, ArrayFieldObject)
        return f.table.equal(self.table)

class TableFieldObject(FieldObject):
    def __init__(self, member_count:int = 0):
        super(TableFieldObject, self).__init__()
        self.type = FieldType.table
        self.type_name = None
        self.member_fields:list[FieldObject] = []
        self.__member_count:int = member_count

    def has_member(self, name:str)->bool:
        for field in self.member_fields:
            if field.name == name: return True
        return False

    def get_member_names(self):
        return [x.name for x in self.member_fields]

    def equal(self, f:'TableFieldObject'):
        assert isinstance(f, TableFieldObject)
        length = len(self.member_fields)
        if f.type_name != self.type_name: return False
        if len(f.member_fields) != len(self.member_fields): return False
        for n in range(length):
            if not f.member_fields[n].equal(self.member_fields[n]): return False
        return True

    def field_names(self): return [x.name for x in self.member_fields]

    @property
    def member_count(self)->int: return self.__member_count

    def __repr__(self):
        return '{} type:{} member_count:{}'.format(super(TableFieldObject, self).__repr__(), self.type_name, len( self.member_fields))

class FixedCodec(object):
    def __init__(self, fraction_bits:int, type_size:int = 32):
        self.__fraction_bits = fraction_bits
        self.__integer_bits = type_size - fraction_bits
        self.__scaling = 1 << fraction_bits
        self.__max_integer_value = +((1 << (self.__integer_bits - 1)) - 1)
        self.__min_integer_value = -((1 << (self.__integer_bits - 1)) - 0)
        self.__max_memory = (1 << (type_size - 1)) - 1
        self.__min_memory = (1 << (type_size - 1))
        self.__type_mask = (1 << type_size) - 1
        self.__type_size = type_size
        self.__sign_mask = 1 << (self.__type_size - 1)
        self.__signed_min_memory = -(1 << (type_size - 1))
        self.__signed_max_memory = self.__max_memory

    @property
    def type_size(self): return self.__type_size

    @property
    def max_value(self)->float:
        return self.__max_integer_value + 1 - 1.0e-8
    @property
    def min_value(self)->float:
        return self.__min_integer_value + 0.0

    @property
    def min_memory(self)->int: return self.__min_memory
    @property
    def max_memory(self)->int: return self.__max_memory

    def encode(self, v:float, signed_encoding:bool = True)->int:
        if v >= self.max_value: return self.__max_memory
        if v <= self.min_value:
            return self.__signed_min_memory if signed_encoding else self.__min_memory
        if v >= 0:
            return min(int(v * self.__scaling), self.__max_memory)
        else:
            m = max(int(v * self.__scaling), self.__signed_min_memory)
            return m if signed_encoding else m & self.__type_mask

    def decode(self, v:int)->float:
        if v > 0 and (self.__sign_mask & v) > 0:
            v = -(~(v - 1) & self.__type_mask)
        return v / self.__scaling

class Codec(object):
    def __init__(self):
        self.time_zone:float = 8.0
        self.debug:bool = True

    def set_timezone(self, time_zone:float):
        self.time_zone = time_zone

    def log(self, indent=0, *kwargs):
        if not self.debug: return
        print(*kwargs) if indent <= 0 else print(' '*(indent*4-1), *kwargs)

    def opt(self, v:str)->str:
        return re.sub(r'\.0$', '', v) if self.is_int(v) else v

    def abc(self, index):
        label = ''
        import string
        num = len(string.ascii_uppercase)
        if index >= num:
            label += string.ascii_uppercase[int(index / num) - 1]
            label += string.ascii_uppercase[index % num]
        else:
            label += string.ascii_uppercase[index]
        return label

    def is_int(self, v:str)->bool:
        return re.match(r'^[+-]?\d+(\.0)?$', v)

    def is_cell_empty(self, cell:xlrd.sheet.Cell)->bool:
        return cell.ctype in (xlrd.XL_CELL_EMPTY, xlrd.XL_CELL_BLANK) or not str(cell.value).strip()

    def parse_int(self, v:str):
        return int(re.sub(r'\.\d+$', '', v)) if v else 0

    def parse_float(self, v:str)->float:
        return float(v) if v else 0.0

    def parse_bool(self, v:str)->bool:
        if self.is_int(v):
            return self.parse_int(v) != 0 if v else False
        else:
            return v.lower() == 'true'

    def parse_array(self, v:str):
        return [self.opt(x) for x in re.split(r'\s*[;\uff1b]\s*', v)] if v else [] # split with ;|；

    def parse_date(self, v:str)->int:
        if not v: return 0
        date_format = '%Y-%m-%d %H:%M:%S'
        offset = datetime.timedelta(seconds=-self.time_zone * 3600)
        assert re.match(r'^\d{4}(-\d{2})+ \d{2}(:\d{2})+$', v), '{!r} doesn\'t match with {!r}'.format(v, date_format)
        date = datetime.datetime.strptime(v, date_format) + offset
        seconds = (date - datetime.datetime(1970, 1, 1)).total_seconds()
        return min(int(seconds), (1<<32)-1)

    def parse_duration(self, v:str)->int:
        components = [self.parse_int(x) for x in re.split(r'\s*[:\uff1a]\s*', v)] # type: list[int]
        assert len(components) <= 4
        factor = (0, 60, 3600, 86400)
        count = len(components)
        total = 0
        for n in range(count):
            total += components[:-(n+1)]*factor[n]
        return min(total, (1<<32)-1)

    def get_default(self, t:FieldType)->str:
        if t in (FieldType.array, FieldType.table): return ''
        elif re.match(r'^u?int\d*$', t.name) or re.match(r'^u?(long|short|byte)$', t.name): return '0'
        elif t == FieldType.double or re.match(r'^float\d*$', t.name): return '0'
        elif t == FieldType.bool: return 'false'
        elif t == FieldType.date: return '0'
        elif t == FieldType.duration: return '0'
        else: return ''

    def parse_scalar(self, v:str, ftype:FieldType):
        if ftype in type_presets.ints or ftype in type_presets.uints:
            return self.parse_int(v)
        elif ftype in type_presets.floats:
            return self.parse_float(v)
        elif ftype == FieldType.bool:
            return self.parse_bool(v)
        elif ftype == FieldType.date:
            return self.parse_date(v)
        elif ftype == FieldType.duration:
            return self.parse_duration(v)
        else: raise SyntaxError('{!r} type:{!r}'.format(v, ftype))

    def make_camel(self, v:str, first:bool = True, force:bool = False)->str:
        name = ''
        need_uppercase = first
        if force and v.isupper(): v = v.lower()
        for char in v:
            if char == '_':
                need_uppercase = True
                continue
            if need_uppercase:
                name += char.upper()
                need_uppercase = False
            else:
                name += char
        return name

    def get_column_indice(self, sheet:xlrd.sheet.Sheet, name:str, row_index:int= ROW_NAME_INDEX):
        column_indice:list[str] = []
        for n in range(sheet.ncols):
            cell_value = str(sheet.cell(row_index, n).value).strip()
            if cell_value == name: column_indice.append(n)
        return column_indice

class BookEncoder(Codec):
    def __init__(self, workspace:str, debug:bool):
        super(BookEncoder, self).__init__()
        self.package_name: str = ''
        self.enum_filepath: str = None
        self.enum_filename: str = None
        self.syntax_filepath: str = None
        self.sheet: xlrd.sheet.Sheet = None
        self.table: TableFieldObject = None
        assert workspace
        if not p.exists(workspace): os.makedirs(workspace)
        self.workspace:str = workspace
        self.debug = debug
        self.sheet:xlrd.sheet.Sheet = None
        self.module_map = {}
        self.cursor:int = -1
        self.access:FieldAccess = FieldAccess.default
        self.fixed32_codec:FixedCodec = None
        self.fixed64_codec:FixedCodec = None
        self.signed_encoding:bool = True

    def set_package_name(self, package_name:str):
        self.package_name = package_name

    def get_indent(self, depth:int)->str:
        return ' '*depth*4

    def get_field_accessible(self, field:FieldObject)->bool:
        return self.access == FieldAccess.default \
               or field.access == FieldAccess.default \
               or field.access == self.access

    def get_table_accessible(self, table:TableFieldObject)->bool:
        if not self.get_field_accessible(table): return False
        access_count = 0
        for field in table.member_fields:
            if self.get_field_accessible(field): access_count += 1
        return access_count > 0

    def get_array_accessible(self, array:ArrayFieldObject):
        if not self.get_field_accessible(array): return False
        return self.get_table_accessible(array.table)

    def init(self, sheet:xlrd.sheet.Sheet):
        self.sheet = sheet

    def encode(self):
        pass

    def save_enums(self, enum_map: Dict[str, Dict[str, int]]):
        pass

    def save_syntax(self, table: TableFieldObject, include_enum:bool = True):
        pass

    def save_shared_syntax(self, tables): # type: (list[TableFieldObject])->None
        pass

    def compile_schemas(self) -> str:
        pass

    def load_modules(self):
        import importlib
        python_out = self.compile_schemas()
        module_list = []
        for base_path, _, file_name_list in os.walk(python_out):
            sys.path.append(base_path)
            for file_name in file_name_list:
                if not file_name.endswith('.py') or file_name.startswith('__'): continue
                module_name = re.sub(r'\.py$', '', file_name)
                exec('import {}'.format(module_name))
                module_list.append(module_name)
        module_map = {}
        scope_envs = locals()
        for module_name in module_list:
            module_map[module_name] = scope_envs.get(module_name)
            importlib.reload(scope_envs.get(module_name))
        self.module_map = module_map
        return module_map

class ProtobufEncoder(BookEncoder):
    def __init__(self, workspace:str, debug:bool):
        super(ProtobufEncoder, self).__init__(workspace, debug)
        self.enum_filename = '{}.proto'.format(SHARED_ENUM_NAME)
        self.include_protos = []

    def __generate_enums(self, enum_map:Dict[str, Dict[str, int]], buffer:io.StringIO = None)->str:
        if not buffer: buffer = io.StringIO()
        indent = self.get_indent(1)
        for name, field in enum_map.items():
            field_cases = [x for x in field.items()]
            field_cases.sort(key=operator.itemgetter(1))
            buffer.write('enum {}\n'.format(name))
            buffer.write('{\n')
            for case, index in field_cases:
                buffer.write('{}{} = {};\n'.format(indent, case, index))
            buffer.write('}\n\n')
        buffer.seek(0)
        return buffer.read()

    def __generate_syntax(self, table:TableFieldObject, buffer:io.StringIO, visit_map = None, ignore_tags:bool = True):
        if not visit_map: visit_map:dict[str, bool] = {}
        if visit_map.get(table.type_name): return
        if ignore_tags and table.tag != FieldTag.none: return
        visit_map[table.type_name] = True
        nest_table_list:list[TableFieldObject] = []
        indent = self.get_indent(1)
        buffer.write('message {}\n'.format(table.type_name))
        buffer.write('{\n')
        field_number = 0
        for n in range(len(table.member_fields)):
            member = table.member_fields[n]
            if not self.get_field_accessible(member): continue
            field_number += 1
            assert member.rule, member
            buffer.write('{}{} '.format(indent, member.rule.name))
            if isinstance(member, TableFieldObject):
                if not self.get_table_accessible(member): continue
                nest_table_list.append(member)
                assert member.type_name
                buffer.write(member.type_name)
            elif isinstance(member, ArrayFieldObject):
                if not self.get_array_accessible(member): continue
                assert member.table
                nest_table_list.append(member.table)
                buffer.write(member.table.type_name)
            elif isinstance(member, EnumFieldObject):
                assert member.enum
                buffer.write(member.enum)
            elif member.type == FieldType.date:
                buffer.write(FieldType.uint32.name)
            elif member.type == FieldType.duration:
                buffer.write(FieldType.uint32.name)
            else:
                assert member.type, member
                buffer.write(member.type.name)
            buffer.write(' {} = {}'.format(member.name, field_number))
            if member.name.lower() == 'id': pass
            elif member.type not in (FieldType.table, FieldType.array) and member.rule != FieldRule.repeated:
                if member.default: buffer.write('[default = {}]'.format(member.default))
            buffer.write(';')
            if member.description: buffer.write(' // {!r}'.format(member.description))
            buffer.write('\n')
        buffer.write('}\n\n')
        for nest_table in nest_table_list:
            self.__generate_syntax(nest_table, buffer, visit_map)
        if table.member_count == 0 and table.tag == FieldTag.none:
            root_message_name = ROOT_CLASS_TEMPLATE.format(table.type_name)
            buffer.write('message {}\n{{\n'.format(root_message_name))
            buffer.write('{}{} {} items = 1;\n'.format(indent, FieldRule.repeated.name, table.type_name))
            buffer.write('}\n')

    def compile_schemas(self)->str:
        python_out = p.abspath('{}/pp'.format(self.workspace))
        shared_schema = '{}/{}*.proto'.format(self.workspace, SHARED_PREFIX)
        data_schema = '{}/{}.proto'.format(self.workspace, self.sheet.name.lower())
        import shutil
        if p.exists(python_out): shutil.rmtree(python_out)
        os.makedirs(python_out)
        command = 'protoc --proto_path={} --python_out={} {} {}'.format(self.workspace, python_out, shared_schema, data_schema)
        assert os.system(command) == 0
        return python_out

    def get_module(self, module_name:str)->object:
        return self.module_map.get('{}_pb2'.format(module_name))

    def create_message_object(self, name:str)->object:
        module = self.get_module(self.sheet.name.lower())
        return getattr(module, name)()

    def parse_enum(self, case_name:str, type_name:str)->int:
        if not case_name: return 0
        module = self.get_module(SHARED_ENUM_NAME.lower())
        enum_type:EnumTypeWrapper = getattr(module, type_name)
        return enum_type.Value(case_name)

    def __encode_array(self, container, field:ArrayFieldObject):
        item_count = 0 # field.count
        cell = self.sheet.cell(self.cursor, field.offset)
        if not self.is_cell_empty(cell):
            count = self.parse_int(str(cell.value))
            if 0 < count <= field.count: item_count = count
        for n in range(item_count):
            message = container.add() # type: object
            self.__encode_table(field.elements[n], message)

    def __encode_fixed_floats(self, container, memories):
        for m in memories:
            f = container.add() # type: object
            f.__setattr__(FIXED_MEMORY_NAME, m)

    def __encode_table(self, table:TableFieldObject, message:object = None):
        if not message: message = self.create_message_object(table.type_name)
        for field in table.member_fields:
            fv = str(self.sheet.cell(self.cursor, field.offset).value).strip()
            nest_object = message.__getattribute__(field.name)
            if isinstance(field, TableFieldObject) and field.rule != FieldRule.repeated:
                self.__encode_table(field, message=nest_object)
                continue
            elif isinstance(field, ArrayFieldObject):
                self.__encode_array(container=nest_object, field=field)
                continue
            elif field.rule == FieldRule.repeated:
                items = self.parse_array(fv)
                if isinstance(field, EnumFieldObject):
                    items = [self.parse_enum(x, field.enum) for x in items]
                elif field.tag == FieldTag.fixed_float32:
                    items = [self.fixed32_codec.encode(self.parse_float(x), self.signed_encoding) for x in items]
                    self.__encode_fixed_floats(nest_object, items)
                    continue
                elif field.tag == FieldTag.fixed_float64:
                    items = [self.fixed64_codec.encode(self.parse_float(x), self.signed_encoding) for x in items]
                    self.__encode_fixed_floats(nest_object, items)
                    continue
                elif field.type != FieldType.string:
                    items = [self.parse_scalar(x, field.type) for x in items]
                container = nest_object # type: list
                for x in items: container.append(x)
                continue
            elif isinstance(field, EnumFieldObject):
                fv = self.parse_enum(fv, field.enum)
            elif field.tag == FieldTag.fixed_float32:
                fv = self.fixed32_codec.encode(self.parse_float(fv), self.signed_encoding)
            elif field.tag == FieldTag.fixed_float64:
                fv = self.fixed64_codec.encode(self.parse_float(fv), self.signed_encoding)
            elif field.type != FieldType.string:
                fv = self.parse_scalar(fv, field.type)
            message.__setattr__(field.name, fv)
        return message

    def encode(self):
        self.load_modules()
        root_message = self.create_message_object(ROOT_CLASS_TEMPLATE.format(self.sheet.name))
        items = root_message.__getattribute__('items')
        for r in range(ROW_DATA_INDEX, self.sheet.nrows):
            self.cursor = r
            if self.is_cell_empty(self.sheet.cell(r, 0)): continue
            self.__encode_table(self.table, message=items.add())
        output_filepath = p.join(self.workspace, '{}.ppb'.format(self.sheet.name.lower()))
        from operator import attrgetter
        if len(items) and hasattr(items[0], 'id'):
            items.sort(key=attrgetter('id'))
        with open(output_filepath, 'wb') as fp:
            fp.write(root_message.SerializeToString())
            print('[+] size:{:,} count:{} {!r}\n'.format(fp.tell(), len(items), output_filepath))

    def save_enums(self, enum_map:Dict[str,Dict[str,int]]):
        self.enum_filepath = p.join(self.workspace, self.enum_filename)
        with open(self.enum_filepath, 'w+') as fp:
            fp.write('syntax = "proto2";\n')
            if self.package_name:
                fp.write('package {};\n\n'.format(self.package_name))
            fp.write(self.__generate_enums(enum_map))
            if self.debug:
                fp.seek(0)
                print('+ {}'.format(self.enum_filepath))
                print(fp.read())

    def save_shared_syntax(self, tables): # type: (list[TableFieldObject])->None
        self.include_protos = []
        for x in tables:
            buffer = io.StringIO()
            self.include_protos.append('{}{}.proto'.format(SHARED_PREFIX, x.type_name))
            self.__generate_syntax(x, buffer, ignore_tags=False)
            syntax_filepath = p.join(self.workspace, '{}{}.proto'.format(SHARED_PREFIX, x.type_name))
            with open(syntax_filepath, 'w+') as fp:
                buffer.seek(0)
                fp.write('syntax = "proto2";\n')
                if self.package_name:
                    fp.write('package {};\n\n'.format(self.package_name))
                fp.write(buffer.read())
                fp.seek(0)
                print('+ {}'.format(syntax_filepath))
                print(fp.read())

    def save_syntax(self, table:TableFieldObject, include_enum:bool = True):
        print('# {}'.format(self.sheet.name))
        self.table = table
        self.syntax_filepath = p.join(self.workspace, '{}.proto'.format(table.type_name.lower()))
        with open(self.syntax_filepath, 'w+') as fp:
            buffer = io.StringIO()
            self.__generate_syntax(table, buffer)
            buffer.seek(0)
            fp.write('syntax = "proto2";\n')
            if include_enum:
                fp.write('import "{}.proto";\n\n'.format(SHARED_ENUM_NAME))
            if self.include_protos:
                for proto in self.include_protos:
                    fp.write('import "{}";\n\n'.format(proto))
            if self.package_name:
                fp.write('package {};\n\n'.format(self.package_name))
            fp.write(buffer.read())
            fp.seek(0)
            print('+ {}'.format(self.syntax_filepath))
            print(fp.read())

class FlatbufEncoder(BookEncoder):
    def __init__(self, workspace:str, debug:bool):
        super(FlatbufEncoder, self).__init__(workspace, debug)
        self.enum_filename = '{}.fbs'.format(SHARED_ENUM_NAME)
        self.builder = flatbuffers.builder.Builder(1*1024*1024)
        self.cursor = -1
        self.string_offsets:dict[str, int] = {}
        self.include_schemas = []

    def reset(self):
        self.__init__(self.workspace, self.debug)

    def __generate_enums(self, enum_map:Dict[str, Dict[str, int]], buffer:io.StringIO = None)->str:
        if not buffer: buffer = io.StringIO()
        indent = self.get_indent(1)
        for name, field in enum_map.items():
            field_cases = [x for x in field.items()]
            field_cases.sort(key=operator.itemgetter(1))
            size = len(field_cases)
            buffer.write('enum {}:{}\n'.format(name, 'ubyte' if size < 0xFF else 'ushort'))
            buffer.write('{\n')
            for case, index in field_cases:
                buffer.write('{}{} = {},\n'.format(indent, case, index))
            buffer.seek(buffer.tell() - 2)
            buffer.write('\n}\n\n')
        buffer.seek(0)
        return buffer.read()

    def __generate_syntax(self, table:TableFieldObject, buffer:io.StringIO, visit_map = None, ignore_tags:bool = True):
        if not visit_map: visit_map:dict[str, bool] = {}
        if visit_map.get(table.type_name): return
        if ignore_tags and table.tag != FieldTag.none: return
        visit_map[table.type_name] = True
        nest_table_list:list[TableFieldObject] = []
        indent = self.get_indent(1)
        buffer.write('table {}\n'.format(table.type_name))
        buffer.write('{\n')
        for member in table.member_fields:
            if not self.get_field_accessible(member): continue
            buffer.write('{}{}:'.format(indent, member.name))
            type_format = '[{}]' if member.rule == FieldRule.repeated else '{}'
            if isinstance(member, TableFieldObject):
                if not self.get_table_accessible(member): continue
                nest_table_list.append(member)
                assert member.name
                buffer.write(type_format.format(member.type_name))
            elif isinstance(member, ArrayFieldObject):
                if not self.get_array_accessible(member): continue
                assert member.table
                nest_table_list.append(member.table)
                buffer.write('[{}]'.format(member.table.type_name))
            elif isinstance(member, EnumFieldObject):
                assert member.enum
                buffer.write(type_format.format(member.enum))
            elif member.type == FieldType.date:
                buffer.write(type_format.format(FieldType.uint32.name))
            elif member.type == FieldType.duration:
                buffer.write(type_format.format(FieldType.uint32.name))
            else:
                assert member.type, member
                buffer.write(type_format.format(member.type.name))
            if member.name.lower() == 'id':
                buffer.write('(key)')
            elif member.type not in (FieldType.table, FieldType.array) and member.rule != FieldRule.repeated:
                if member.default: buffer.write(' = {}'.format(member.default))
            buffer.write(';')
            if member.description: buffer.write(' // {!r}'.format(member.description))
            buffer.write('\n')
        buffer.write('}\n\n')
        for nest_table in nest_table_list:
            self.__generate_syntax(nest_table, buffer, visit_map)
        if table.member_count == 0 and table.tag == FieldTag.none:
            array_type_name = ROOT_CLASS_TEMPLATE.format(table.type_name)
            buffer.write('table {}\n{{\n'.format(array_type_name))
            buffer.write('{}items:[{}];\n'.format(indent, table.type_name))
            buffer.write('}\n\n')
            buffer.write('root_type {};\n'.format(array_type_name))

    def __encode_array(self, module_name, field): # type: (str, ArrayFieldObject)->int
        item_offsets:list[int] = []
        item_count = 0 # field.count
        cell = self.sheet.cell(self.cursor, field.offset)
        if not self.is_cell_empty(cell):
            count = self.parse_int(str(cell.value))
            if 0 < count <= field.count: item_count = count
        for n in range(item_count):
            offset = self.__encode_table(field.elements[n])
            item_offsets.append(offset)
        return self.__encode_vector(module_name, item_offsets, field)

    def __encode_vector(self, module_name, items, field): # type: (str, list[str], FieldObject)->int
        assert field.rule == FieldRule.repeated
        item_count = len(items)
        self.start_vector(module_name, field.name, item_count)
        for n in range(len(items)):
            v = items[-(n+1)]
            self.__encode_scalar(v, field)
        return self.end_vector(item_count)

    def parse_enum(self, case_name:str, type_name:str)->int:
        module = self.module_map.get(type_name) # type: object
        return getattr(getattr(module, type_name), case_name) if case_name else 0

    def __encode_scalar(self, v:any, field:FieldObject):
        ftype = field.type
        builder = self.builder
        method_name = 'Prepend{}'.format(ftype.name.title())
        if ftype in (FieldType.table, FieldType.array, FieldType.string):
            builder.PrependUOffsetTRelative(v) # offset
        elif hasattr(builder, method_name):
            builder.__getattribute__(method_name)(v)
        elif ftype == FieldType.short:
            builder.PrependInt16(v)
        elif ftype == FieldType.ushort:
            builder.PrependUint16(v)
        elif ftype == FieldType.long:
            builder.PrependInt64(v)
        elif ftype == FieldType.ulong:
            builder.PrependUint64(v)
        elif ftype == FieldType.float:
            builder.PrependFloat32(v)
        elif ftype == FieldType.double:
            builder.PrependFloat64(v)
        elif ftype == FieldType.enum:
            builder.PrependUint8(v)
        elif ftype == FieldType.ubyte:
            builder.PrependUint8(v)
        elif ftype == FieldType.date:
            builder.PrependUint32(v)
        elif ftype == FieldType.duration:
            builder.PrependUint32(v)
        else:
            raise SyntaxError('{!r}:{} not a scalar value {}'.format(v, ftype.name, field))

    def __encode_string(self, v:str)->int:
        md5 = hashlib.md5()
        md5.update(v.encode('utf-8'))
        uuid = md5.hexdigest()
        if uuid in self.string_offsets:
            return self.string_offsets[uuid]
        else:
            offset = self.builder.CreateString(v)
            self.string_offsets[uuid] = offset
            return offset

    def __encode_fixed_floats(self, table, memories): # type: (TableFieldObject, list[int])->list[int]
        offset_list = []
        for m in memories:
            self.start_object(table.type_name)
            self.add_field(table.type_name, FIXED_MEMORY_NAME, m)
            offset = self.end_object(table.type_name)
            offset_list.append(offset)
        return offset_list

    def __encode_table(self, table): # type: (TableFieldObject)->int
        offset_map:dict[str, int] = {}
        module_name = table.type_name
        row_items = self.sheet.row(self.cursor)
        member_count = len(table.member_fields)
        for n in range(member_count):
            field = table.member_fields[n]
            fv = str(row_items[field.offset].value).strip()
            if isinstance(field, TableFieldObject) and field.rule != FieldRule.repeated:
                offset = self.__encode_table(field)
            elif isinstance(field, ArrayFieldObject):
                offset = self.__encode_array(module_name, field)
            elif field.rule == FieldRule.repeated:
                items = self.parse_array(fv)
                if field.type == FieldType.string:
                    items = [self.__encode_string(x) for x in items]
                elif isinstance(field, EnumFieldObject):
                    items = [self.parse_enum(x, field.enum) for x in items]
                elif field.tag == FieldTag.fixed_float32:
                    assert isinstance(field, TableFieldObject)
                    items = [self.fixed32_codec.encode(self.parse_float(x), self.signed_encoding) for x in items]
                    items = self.__encode_fixed_floats(field, items)
                elif field.tag == FieldTag.fixed_float64:
                    assert isinstance(field, TableFieldObject)
                    items = [self.fixed64_codec.encode(self.parse_float(x), self.signed_encoding) for x in items]
                    items = self.__encode_fixed_floats(field, items)
                else:
                    items = [self.parse_scalar(x, field.type) for x in items]
                offset = self.__encode_vector(module_name, items, field)
            elif field.type == FieldType.string:
                offset = self.__encode_string(fv)
            else:
                offset = -1
            if offset >= 0: offset_map[field.name] = offset
        # print(offset_map)
        self.start_object(module_name)
        for n in range(member_count):
            field = table.member_fields[n]
            fv = str(row_items[field.offset].value).strip()
            if field.name in offset_map:
                fv = offset_map.get(field.name)
            elif isinstance(field, EnumFieldObject):
                fv = self.parse_enum(fv, field.enum)
            elif field.tag == FieldTag.fixed_float32:
                fv = self.fixed32_codec.encode(self.parse_float(fv), self.signed_encoding)
            elif field.tag == FieldTag.fixed_float64:
                fv = self.fixed64_codec.encode(self.parse_float(fv), self.signed_encoding)
            else:
                fv = self.parse_scalar(fv, field.type)
            self.add_field(module_name, field.name, fv)
        return self.end_object(table.type_name)

    def compile_schemas(self)->str:
        python_out = p.abspath('{}/fp'.format(self.workspace))
        shared_schema = '{}/{}*.fbs'.format(self.workspace, SHARED_PREFIX)
        data_schema = '{}/{}.fbs'.format(self.workspace, self.sheet.name.lower())
        import shutil
        if p.exists(python_out): shutil.rmtree(python_out)
        command = 'flatc -p -o {} {} {}'.format(python_out, shared_schema, data_schema)
        assert os.system(command) == 0
        return python_out

    def ptr(self, v:int)->str:
        return '&{:08X}:{}'.format(v, v)

    def start_object(self, module_name:str):
        name = '{}Start'.format(module_name)
        self.log(0, '- {}'.format(name))
        module = self.module_map.get(module_name) # type: dict
        getattr(module, name)(self.builder)

    def start_vector(self, module_name:str, field_name:str, item_count:int):
        name = '{}Start{}Vector'.format(module_name, self.make_camel(field_name))
        self.log(0, '- {} #{}'.format(name, item_count))
        module = self.module_map.get(module_name)  # type: dict
        getattr(module, name)(self.builder, item_count)

    def end_object(self, module_name:str)->int:
        name = '{}End'.format(module_name)
        module = self.module_map.get(module_name) # type: dict
        offset = getattr(module, name)(self.builder)
        self.log(0, '- {} {}\n'.format(name, self.ptr(offset)))
        return offset

    def end_vector(self, item_count:int)->int:
        offset = self.builder.EndVector(item_count)
        self.log(0, '- EndVector {}\n'.format(self.ptr(offset)))
        return offset

    def add_field(self, module_name:str, field_name:str, v:any):
        name = '{}Add{}'.format(module_name, self.make_camel(field_name))
        self.log(0, '- {} = {!r}'.format(name, v))
        module = self.module_map.get(module_name)  # type: dict
        getattr(module, name)(self.builder, v)

    def parse_sort_field(self, r:int, c:int):
        v = str(self.sheet.cell(r, c).value).strip()
        return self.parse_int(v) if self.is_int(v) else v

    def encode(self):
        self.load_modules()
        self.builder = flatbuffers.builder.Builder(1*1024*1024)
        item_offsets:list[int] = []
        sort_column_indice = self.get_column_indice(self.sheet, 'id')
        sort_index = sort_column_indice[0] if sort_column_indice else 0
        sort_items = []
        for r in range(ROW_DATA_INDEX, self.sheet.nrows):
            if self.is_cell_empty(self.sheet.cell(r, 0)): continue
            self.cursor = r
            offset = self.__encode_table(self.table)
            sort_items.append([self.parse_sort_field(r, sort_index), offset])
            self.log(0, '{} {}'.format(self.table.type_name, self.ptr(offset)))
            item_offsets.append(offset)
        # sort items by `id` key or first field
        if sort_column_indice:
            sort_items.sort(key=lambda x:x[0])
            self.log(0, '{-}', item_offsets)
            item_offsets = [x[1] for x in sort_items]
            self.log(0, '{+}', item_offsets)
        # encode config items into root_type
        xsheet_name = self.sheet.name  # type: str
        module_name = ROOT_CLASS_TEMPLATE.format(xsheet_name)
        self.start_vector(module_name, 'items', len(item_offsets))
        item_count = len(item_offsets)
        for n in range(item_count):
            offset = item_offsets[-(n+1)]
            self.builder.PrependUOffsetTRelative(offset)
        item_vector = self.end_vector(len(item_offsets))
        self.start_object(module_name)
        self.add_field(module_name, 'items', item_vector)
        root_table = self.end_object(module_name)
        self.builder.Finish(root_table)
        # write flatbuffer into disk
        output_filepath = p.join(self.workspace, '{}.fpb'.format(xsheet_name.lower()))
        with open(output_filepath, 'wb') as fp:
            fp.write(self.builder.Output())
        # verify
        with open(output_filepath, 'rb') as fp:
            buffer = bytearray(fp.read())
            item_array_class = getattr(self.module_map.get(module_name), module_name) # type: object
            item_array = getattr(item_array_class, 'GetRootAs{}'.format(module_name))(buffer, 0) # type: object
            print('[+] size={:,} count={} {!r}\n'.format(fp.tell(), getattr(item_array, 'ItemsLength')(), output_filepath))

    def save_enums(self, enum_map:Dict[str,Dict[str,int]]):
        self.enum_filepath = p.join(self.workspace, self.enum_filename)
        with open(self.enum_filepath, 'w+') as fp:
            if self.package_name:
                fp.write('namespace {};\n\n'.format(self.package_name))
            fp.write(self.__generate_enums(enum_map))
            if self.debug:
                fp.seek(0)
                print('+ {}'.format(self.enum_filepath))
                print(fp.read())

    def save_shared_syntax(self, tables): # type: (list[TableFieldObject])->None
        self.include_schemas = []
        for x in tables:
            buffer = io.StringIO()
            self.include_schemas.append('{}{}.fbs'.format(SHARED_PREFIX, x.type_name))
            self.__generate_syntax(x, buffer, ignore_tags=False)
            syntax_filepath = p.join(self.workspace, '{}{}.fbs'.format(SHARED_PREFIX, x.type_name))
            with open(syntax_filepath, 'w+') as fp:
                buffer.seek(0)
                if self.package_name:
                    fp.write('namespace {};\n\n'.format(self.package_name))
                fp.write(buffer.read())
                fp.seek(0)
                print('+ {}'.format(syntax_filepath))
                print(fp.read())

    def save_syntax(self, table:TableFieldObject, include_enum:bool = True):
        self.table = table
        print('# {}'.format(self.sheet.name))
        self.syntax_filepath = p.join(self.workspace, '{}.fbs'.format(table.type_name.lower()))
        with open(self.syntax_filepath, 'w+') as fp:
            buffer = io.StringIO()
            self.__generate_syntax(table, buffer)
            buffer.seek(0)
            if include_enum:
                fp.write('include "{}.fbs";\n\n'.format(SHARED_ENUM_NAME))
            if self.include_schemas:
                for schema in self.include_schemas:
                    fp.write('include "{}";\n\n'.format(schema))
            if self.package_name:
                fp.write('namespace {};\n\n'.format(self.package_name))
            fp.write(buffer.read())
            fp.seek(0)
            print('+ {}'.format(self.syntax_filepath))
            print(fp.read())

class SheetSerializer(Codec):
    def __init__(self, debug = True):
        super(SheetSerializer, self).__init__()
        self.__type_map:dict[str, any] = vars(FieldType)
        self.__rule_map:dict[str, any] = vars(FieldRule)
        self.debug = debug
        self.__root:TableFieldObject = None
        self.__sheet:xlrd.sheet.Sheet = None
        self.__field_map:dict[int, FieldObject] = {}
        self.__table_map:dict[str, TableFieldObject] = {}
        self.has_enum = False
        # enum settings
        self.__enum_filepath = p.join(p.dirname(p.abspath(__file__)), '{}.json'.format(SHARED_ENUM_NAME))
        self.__enum_map: dict[str, dict[str, int]] = {}
        if p.exists(self.__enum_filepath):
            with open(self.__enum_filepath) as fp:
                self.__enum_map: dict[str, dict[str, int]] = json.load(fp)
        self.compatible_mode = False
        self.fixed32_codec:FixedCodec = None
        self.fixed64_codec:FixedCodec = None
        self.fixed_tables:list[TableFieldObject] = [None, None]
        self.signed_encoding:bool = True

    @property
    def root_table(self)->TableFieldObject:return self.__root

    def reset(self):
        self.__init__(self.debug)

    def __parse_access(self, v:str)->FieldAccess:
        v = v.lower()
        if v in ('s', 'svr', 'server'): return FieldAccess.server
        if v in ('c', 'cli', 'client'): return FieldAccess.client
        return FieldAccess.default

    def __get_table_name(self, field_name:str, prefix:str = None)->str:
        table_name = self.make_camel(field_name)
        if prefix and prefix.find('_'):
            prefix = self.make_camel(prefix, force=True)
        return prefix + table_name if prefix else table_name

    def __hook_fixed_float(self, field:FieldObject, codec:FixedCodec)->TableFieldObject:
        global FIXED_MEMORY_NAME
        table = TableFieldObject(member_count=1)
        table.name = field.name
        table.type_name = 'FixedFloat{}'.format(codec.type_size)
        table.rule = field.rule
        holder = FieldObject()
        holder.fill(field)
        holder.name = FIXED_MEMORY_NAME
        if self.signed_encoding:
            holder.type = FieldType.int32 if codec.type_size == 32 else FieldType.int64
        else:
            holder.type = FieldType.uint32 if codec.type_size == 32 else FieldType.uint64
        holder.rule = FieldRule.optional
        holder.default = '0'
        holder.tag = FieldTag.fixed_float32 if codec.type_size == 32 else FieldTag.fixed_float64
        holder.description = 'representation of float{} value'.format(codec.type_size)
        if self.compatible_mode:
            table.type_name = 'ProtoFScalar'
            holder.name = FIXED_MEMORY_NAME = 'rawValue'
            holder.type = FieldType.int32 if self.signed_encoding else FieldType.uint32
        table.member_fields.append(holder)
        table.tag = holder.tag
        table.offset = field.offset
        return table

    def __parse_array(self, array:ArrayFieldObject, sheet:xlrd.sheet.Sheet, column:int, depth:int = 0)->int:
        self.log(depth, '[ARRAY] col:{} count:{}'.format(self.abc(column-1), array.count))
        table:TableFieldObject = self.__parse_field(sheet, column, depth=depth + 1)
        assert table.type == FieldType.table
        c = column + 1
        assert table.member_count > 0
        table.offset = c
        if self.compatible_mode:
            table.type_name = 'InternalType_{}'.format(table.name)
            array.name = table.name
        c = self.__parse_table(table, sheet, c, depth=depth + 1)
        array.table = table
        array.elements.append(table)
        count = 1
        if array.count > count:
            while c < sheet.ncols:
                element = TableFieldObject(table.member_count)
                element.name = table.name
                element.type_name = table.type_name
                element.offset = c
                c = self.__parse_table(element, sheet, c, depth=depth + 1)
                assert element.equal(table), element
                array.elements.append(element)
                count += 1
                if count >= array.count:
                    position = c
                    array.size = position - column + 1 # include all fields in array definition
                    self.log(depth, array)
                    return position
            raise SyntaxError()
        else: return c

    def __parse_field(self, sheet:xlrd.sheet.Sheet, column:int, depth:int = 0)->FieldObject:
        c = column
        type_map = self.__type_map
        rule_map = self.__rule_map
        cell_type = sheet.cell_type(ROW_RULE_INDEX, c)
        if cell_type != xlrd.XL_CELL_TEXT: return None
        field_rule = sheet.cell_value(ROW_RULE_INDEX, c).strip()  # type: str
        field_type = str(sheet.cell_value(ROW_TYPE_INDEX, c)).strip()  # type: str
        field_name = str(sheet.cell_value(ROW_NAME_INDEX, c)).strip()  # type: str
        field_aces = str(sheet.cell_value(ROW_ACES_INDEX, c)).strip()  # type: str
        field_desc = str(sheet.cell_value(ROW_DESC_INDEX, c)).strip()  # type: str
        ignore_charset = '\uff0a* '
        if field_rule in ignore_charset or field_type in ignore_charset: return None
        # fill field object
        field = FieldObject()
        field.type = type_map.get(field_type.lower())
        sep = field_name.find('=')
        if sep > 0:
            field.name = field_name[:sep]
            field.default = field_name[sep+1:]
        else:
            field.name = field_name
        field.rule = rule_map.get(field_rule.lower())
        field.access = self.__parse_access(field_aces)
        field.description = field_desc
        field.offset = c
        if self.is_int(field_type):
            num = self.parse_int(field_type)
            if field.rule == FieldRule.repeated:
                nest_array = ArrayFieldObject(num)
                nest_array.fill(field)
                nest_array.type = FieldType.array
                field = nest_array
                assert field.name, '{}:{} Array field need a name'.format(ROW_NAME_INDEX + 1, self.abc(c))
            else:
                nest_table = TableFieldObject(num)
                nest_table.fill(field)
                nest_table.type = FieldType.table
                nest_table.type_name = self.__get_table_name(field.default if field.default else nest_table.name, prefix=self.__sheet.name)
                field = nest_table
        elif field_type.startswith('enum.'):
            self.has_enum = True
            enum_field = EnumFieldObject(re.sub(r'^enum\.', '', field_type))
            enum_field.fill(field)
            enum_field.type = FieldType.enum
            if enum_field.enum not in self.__enum_map:
                self.__enum_map[enum_field.enum] = {}
            enum_field.case_map = self.__enum_map.get(enum_field.enum)
            enum_field.hook_default()
            field = enum_field
        elif field_type == 'DateTime':
            field.type = FieldType.date
        assert field.name and field.type, field
        if not field.default:
            field.default = self.get_default(field.type)
        if field.rule == FieldRule.repeated: field.default = ''
        self.log(depth, '{:2d} {:2s} {}'.format(c, self.abc(c), field))
        self.__field_map[field.offset] = field
        return field

    def __parse_table(self, table:TableFieldObject, sheet:xlrd.sheet.Sheet, column:int, depth:int = 0)->int:
        member_fields = table.member_fields
        self.log(depth, '[TABLE] pos:{} member_count:{} type:{}'.format(self.abc(column), table.member_count, table.type_name))
        c = column
        while c < sheet.ncols:
            field = self.__parse_field(sheet, column=c, depth=depth + 1) # type: FieldObject
            c += 1
            if not field: continue
            if isinstance(field, ArrayFieldObject):
                assert field.type == FieldType.array
                c = self.__parse_array(field, sheet, c, depth=depth + 1)  # parse array
            elif isinstance(field, TableFieldObject):
                assert field.type == FieldType.table
                c = self.__parse_table(field, sheet, c, depth=depth + 1)
            if self.fixed32_codec and field.type in (FieldType.float, FieldType.float32):
                field = self.__hook_fixed_float(field, self.fixed32_codec)
                self.fixed_tables[0] = field
            elif self.fixed64_codec and field.type in (FieldType.double, FieldType.float64):
                field = self.__hook_fixed_float(field, self.fixed64_codec)
                self.fixed_tables[1] = field
            assert not table.has_member(field.name), '{} {}'.format(field.name, self.abc(field.offset))
            member_fields.append(field)
            if 0 < table.member_count == len(member_fields):
                position = c
                table.size = position - column # exclude declaration field
                self.log(depth, table)
                if table.type_name in self.__table_map: # make sure that same types with same definitions
                    assert self.__table_map.get(table.type_name).equal(table), 'expect:{!r} but:{!r} def:{{{}}} ref:{{{}}}'.format(self.__table_map.get(table.type_name).field_names(), table.field_names(), table, self.__table_map.get(table.type_name))
                else:
                    self.__table_map[table.type_name] = table
                return position
        self.log(depth, table)
        table.size = c - column
        return sheet.ncols

    def parse_syntax(self, sheet:xlrd.sheet.Sheet):
        self.__sheet = sheet
        self.__root = TableFieldObject()
        self.__root.type_name = sheet.name
        self.__parse_table(self.__root, sheet, 0)
        return self.__root

    def __get_unique_values(self, column:int):
        unique_values:list[str] = []
        for r in range(ROW_DATA_INDEX, self.__sheet.nrows):
            cell = self.__sheet.cell(r, column)
            if cell.ctype != xlrd.XL_CELL_TEXT: continue
            value_list = self.parse_array(str(cell.value).strip())
            for field_value in value_list:
                if field_value not in unique_values: unique_values.append(field_value)
        return unique_values

    def pack(self, encoder:BookEncoder, auto_default_case:bool):
        for field in self.__field_map.values():
            if not isinstance(field, EnumFieldObject): continue
            field.hook_default()
            field.import_cases(self.__get_unique_values(field.offset), auto_default_case)
        with open(self.__enum_filepath, 'w+') as fp:
            json.dump(self.__enum_map, fp, indent=4)
        if not encoder.get_table_accessible(self.__root): return
        encoder.signed_encoding = self.signed_encoding
        encoder.fixed32_codec = self.fixed32_codec
        encoder.fixed64_codec = self.fixed64_codec
        encoder.init(sheet=self.__sheet)
        encoder.save_enums(enum_map=self.__enum_map)
        shared_tables = []
        for x in self.fixed_tables:
            if x: shared_tables.append(x)
        if shared_tables: encoder.save_shared_syntax(tables=shared_tables)
        encoder.save_syntax(table=self.__root, include_enum=self.has_enum)
        encoder.encode()

if __name__ == '__main__':
    import sys, argparse
    arguments = argparse.ArgumentParser()
    arguments.add_argument('--workspace', '-w', default=p.expanduser('~/Downloads/flatcfg'), help='workspace path for outputs and temp files')
    arguments.add_argument('--excel-file', '-f', nargs='+', required=True, help='xls book file path')
    arguments.add_argument('--use-protobuf', '-u', action='store_true', help='generate protobuf format binary output')
    arguments.add_argument('--debug', '-d', action='store_true', help='use debug mode to get more detial information')
    arguments.add_argument('--error', '-e', action='store_true', help='raise error to console')
    arguments.add_argument('--auto-default-case', '-c', action='store_true', help='auto generate a NONE default case for each enum')
    arguments.add_argument('--namespace', '-n', default='dataconfig', help='namespace for serialize class')
    arguments.add_argument('--time-zone', '-z', default=8.0, type=float, help='time zone for parsing date time')
    arguments.add_argument('--compatible-mode', '-i', action='store_true', help='for private use')
    arguments.add_argument('--access', '-a', choices=FieldAccess.get_option_choices(), default='default')
    # arguments for fixed float encoding
    arguments.add_argument('--fixed32-fraction-bits', '-b32', default=10, type=int, help='use 2^exponent to present fractional part of a float32 value')
    arguments.add_argument('--fixed64-fraction-bits', '-b64', default=20, type=int, help='use 2^exponent to present fractional part of a float64 value')
    arguments.add_argument('--fixed64', '-64', action='store_true', help='encode double field values into FixedFloat64 type')
    arguments.add_argument('--fixed32', '-32', action='store_true', help='encode float field values into FixedFloat32 type')
    arguments.add_argument('--unsigned-encoding', '-0', action='store_true', help='encode fixed memory value into unsign integer type')
    options = arguments.parse_args(sys.argv[1:])
    for excel_filepath in options.excel_file:
        print('>>> {}'.format(excel_filepath))
        book = xlrd.open_workbook(excel_filepath)
        for sheet_name in book.sheet_names(): # type: str
            if not sheet_name.isupper(): continue
            serializer = SheetSerializer(debug=options.debug)
            serializer.compatible_mode = options.compatible_mode
            serializer.signed_encoding = not options.unsigned_encoding
            if options.fixed32:
                serializer.fixed32_codec = FixedCodec(fraction_bits=options.fixed32_fraction_bits, type_size=32)
            if options.fixed64:
                serializer.fixed64_codec = FixedCodec(fraction_bits=options.fixed64_fraction_bits, type_size=64)
            try:
                serializer.parse_syntax(book.sheet_by_name(sheet_name))
                if options.use_protobuf:
                    encoder = ProtobufEncoder(workspace=options.workspace, debug=options.debug)
                else:
                    encoder = FlatbufEncoder(workspace=options.workspace, debug=options.debug)
                encoder.access = FieldAccess.get_value(options.access)
                encoder.set_package_name(options.namespace)
                encoder.set_timezone(options.time_zone)
                serializer.pack(encoder, auto_default_case=options.auto_default_case)
            except Exception as error:
                if options.error: raise error
                else: continue
        book.release_resources()



