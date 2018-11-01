#!/usr/bin/env python3
import enum, xlrd, re, io, json, os, hashlib, time, datetime
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

SHARED_ENUM_NAME = 'shared_enum'
ROOT_CLASS_TEMPLATE = '{}_ARRAY'

class FieldType(enum.Enum):
    float, float32, float64, double, \
    int16, uint16, int8 , uint8 , \
    int32, uint32, int64, uint64, \
    short, ushort, byte, ubyte, long, ulong, \
    bool, string = range(20) # standard protobuf scalar types
    date, duration, enum, table, array = tuple(x + 100 for x in range(5)) # extend field types

class type_presets(object):
    ints = (FieldType.byte, FieldType.int8, FieldType.short, FieldType.int16, FieldType.int32, FieldType.int64, FieldType.long)
    uints = (FieldType.ubyte, FieldType.uint8, FieldType.ushort, FieldType.uint16, FieldType.uint32, FieldType.uint64, FieldType.ulong)
    floats = (FieldType.float, FieldType.float32, FieldType.double, FieldType.float64)
    size_1 = (FieldType.byte, FieldType.ubyte, FieldType.bool, FieldType.int8, FieldType.uint8, FieldType.enum)
    size_2 = (FieldType.short, FieldType.int16, FieldType.ushort, FieldType.uint16)
    size_4 = (FieldType.int32, FieldType.uint32, FieldType.float, FieldType.float32, FieldType.date, FieldType.duration)
    size_8 = (FieldType.long, FieldType.int64, FieldType.ulong, FieldType.uint64, FieldType.double, FieldType.float64)
    nests = (FieldType.table, FieldType.array)

class FieldRule(enum.Enum):
    optional, required, repeated = range(3)

class FieldAccess(enum.Enum):
    default, client, server = range(3)

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

    def fill(self, f:'FieldObject'):
        for name, value in vars(f).items():
            if not name.startswith('_') and name.islower():
                self.__setattr__(name, value)

    def equal(self, f:'FieldObject')->bool:
        return self.name == f.name \
               and self.type == f.type \
               and self.size == f.size

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
        self.__count:int = count
        assert count > 0

    @property
    def count(self) -> int: return self.__count

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
        length = len(self.member_fields)
        for n in range(length):
            if not f.member_fields[n].equal(self.member_fields[n]): return False
        return True

    @property
    def member_count(self)->int: return self.__member_count

    def __repr__(self):
        return '{} type:{} member_count:{}'.format(super(TableFieldObject, self).__repr__(), self.type_name, len( self.member_fields))


class Codec(object):
    def __init__(self):
        self.time_zone = 8
        self.debug:bool = True

    def set_timezone(self, time_zone:int):
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
        return re.match(r'^[+-]?\d+\.0$', v)

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
        return [self.opt(x) for x in re.split(r'\s*[;\uff1b]\s*', v)] # split with ;|；

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

    def parse_value(self, v:str, t:FieldType)->(any, str):
        if t in (FieldType.array, FieldType.table): return v, ''
        elif re.match(r'^u?int\d*$', t.name) or re.match(r'^u?(long|short|byte)$', t.name): return self.parse_int(v), '0'
        elif t == FieldType.double or re.match(r'^float\d*$', t.name): return self.parse_float(v), '0'
        elif t == FieldType.bool: return self.parse_bool(v), 'false'
        else: return v, ''

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
            cell_value = str(sheet.cell(row_index, n)).strip()
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

    def set_package_name(self, package_name:str):
        self.package_name = package_name

    def get_indent(self, depth:int)->str:
        return ' '*depth*4

    def init(self, sheet:xlrd.sheet.Sheet):
        self.sheet = sheet

    def encode(self):
        pass

    def save_enums(self, enum_map: Dict[str, Dict[str, int]]):
        pass

    def save_syntax(self, table: TableFieldObject, include_enum:bool = True):
        pass

    def compile_schemas(self) -> str:
        pass

    def load_modules(self):
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
        self.module_map = module_map
        return module_map

class ProtobufEncoder(BookEncoder):
    def __init__(self, workspace:str, debug:bool):
        super(ProtobufEncoder, self).__init__(workspace, debug)
        self.enum_filename = '{}.proto'.format(SHARED_ENUM_NAME)

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

    def __generate_syntax(self, table:TableFieldObject, buffer:io.StringIO):
        nest_table_list:list[TableFieldObject] = []
        indent = self.get_indent(1)
        buffer.write('message {}\n'.format(table.type_name))
        buffer.write('{\n')
        for n in range(len(table.member_fields)):
            member = table.member_fields[n]
            assert member.rule, member
            buffer.write('{}{} '.format(indent, member.rule.name))
            if isinstance(member, TableFieldObject):
                nest_table_list.append(member)
                assert member.type_name
                buffer.write(member.type_name)
            elif isinstance(member, ArrayFieldObject):
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
            buffer.write(' {} = {}'.format(member.name, n + 1))
            if member.name.lower() == 'id': pass
            elif member.type not in (FieldType.table, FieldType.array) and member.rule != FieldRule.repeated:
                if member.default: buffer.write('[default = {}]'.format(member.default))
            buffer.write(';')
            if member.description: buffer.write(' // {!r}'.format(member.description))
            buffer.write('\n')
        buffer.write('}\n\n')
        for nest_table in nest_table_list:
            self.__generate_syntax(nest_table, buffer)
        if table.member_count == 0:
            root_message_name = ROOT_CLASS_TEMPLATE.format(table.type_name)
            buffer.write('message {}\n{{\n'.format(root_message_name))
            buffer.write('{}{} {} items = 1;\n'.format(indent, FieldRule.repeated.name, table.type_name))
            buffer.write('}\n')

    def compile_schemas(self)->str:
        python_out = p.abspath('{}/pp'.format(self.workspace))
        enum_schema = '{}/{}.proto'.format(self.workspace, SHARED_ENUM_NAME)
        data_schema = '{}/{}.proto'.format(self.workspace, self.sheet.name.lower())
        import shutil
        if p.exists(python_out): shutil.rmtree(python_out)
        os.makedirs(python_out)
        command = 'protoc --proto_path={} --python_out={} {} {}'.format(self.workspace, python_out, enum_schema, data_schema)
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
        table_size = len(field.table.member_fields)
        item_count = field.count
        cell = self.sheet.cell(self.cursor, field.offset)
        if not self.is_cell_empty(cell):
            count = self.parse_int(str(cell.value))
            if 0 < count < field.count: item_count = count
        for n in range(item_count):
            column_offset = n * table_size
            message = container.add() # type: object
            self.__encode_table(field.table, column_offset, message)

    def __encode_table(self, table:TableFieldObject, column_offset:int = 0, message:object = None):
        if not message: message = self.create_message_object(table.type_name)
        for field in table.member_fields:
            fv = str(self.sheet.cell(self.cursor, field.offset + column_offset).value).strip()
            nest_object = message.__getattribute__(field.name)
            if isinstance(field, TableFieldObject):
                self.__encode_table(field, message=nest_object)
                continue
            elif isinstance(field, ArrayFieldObject):
                self.__encode_array(container=nest_object, field=field)
                continue
            elif field.rule == FieldRule.repeated:
                items = self.parse_array(fv)
                if isinstance(field, EnumFieldObject):
                    items = [self.parse_enum(x, field.enum) for x in items]
                elif field.type != FieldType.string:
                    items = [self.parse_scalar(x, field.type) for x in items]
                container = nest_object # type: list
                for x in items: container.append(x)
                continue
            elif isinstance(field, EnumFieldObject):
                fv = self.parse_enum(fv, field.enum)
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
                fp.write('import "{}";\n\n'.format(self.enum_filename))
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

    def __generate_syntax(self, table:TableFieldObject, buffer:io.StringIO):
        nest_table_list:list[TableFieldObject] = []
        indent = self.get_indent(1)
        buffer.write('table {}\n'.format(table.type_name))
        buffer.write('{\n')
        for member in table.member_fields:
            buffer.write('{}{}:'.format(indent, member.name))
            type_format = '[{}]' if member.rule == FieldRule.repeated else '{}'
            if isinstance(member, TableFieldObject):
                nest_table_list.append(member)
                assert member.name
                buffer.write(member.type_name)
            elif isinstance(member, ArrayFieldObject):
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
            self.__generate_syntax(nest_table, buffer)
        if table.member_count == 0:
            array_type_name = ROOT_CLASS_TEMPLATE.format(table.type_name)
            buffer.write('table {}\n{{\n'.format(array_type_name))
            buffer.write('{}items:[{}];\n'.format(indent, table.type_name))
            buffer.write('}\n\n')
            buffer.write('root_type {};\n'.format(array_type_name))

    def __encode_array(self, module_name, field): # type: (str, ArrayFieldObject)->int
        table_size = len(field.table.member_fields)
        item_offsets:list[int] = []

        item_count = field.count
        cell = self.sheet.cell(self.cursor, field.offset)
        if not self.is_cell_empty(cell):
            count = self.parse_int(str(cell.value))
            if 0 < count < field.count: item_count = count
        for n in range(item_count):
            column_offset = table_size * n
            offset = self.__encode_table(field.table, column_offset)
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

    def __encode_table(self, table, column_offset = 0): # type: (TableFieldObject, int)->int
        offset_map:dict[str, int] = {}
        module_name = table.type_name
        row_items = self.sheet.row(self.cursor)
        member_count = len(table.member_fields)
        for n in range(member_count):
            field = table.member_fields[n]
            fv = str(row_items[field.offset + column_offset].value).strip()
            if isinstance(field, TableFieldObject):
                offset = self.__encode_table(field, column_offset)
            elif isinstance(field, ArrayFieldObject):
                offset = self.__encode_array(module_name, field)
            elif field.rule == FieldRule.repeated:
                items = self.parse_array(fv)
                if field.type == FieldType.string:
                    items = [self.__encode_string(x) for x in items]
                elif isinstance(field, EnumFieldObject):
                    items = [self.parse_enum(x, field.enum) for x in items]
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
            fv = str(row_items[field.offset + column_offset].value).strip()
            if field.name in offset_map:
                fv = offset_map.get(field.name)
            elif isinstance(field, EnumFieldObject):
                fv = self.parse_enum(fv, field.enum)
            else:
                fv = self.parse_scalar(fv, field.type)
            self.add_field(module_name, field.name, fv)
        return self.end_object(table.type_name)

    def compile_schemas(self)->str:
        python_out = p.abspath('{}/fp'.format(self.workspace))
        enum_schema = '{}/{}.fbs'.format(self.workspace, SHARED_ENUM_NAME)
        data_schema = '{}/{}.fbs'.format(self.workspace, self.sheet.name.lower())
        import shutil
        if p.exists(python_out): shutil.rmtree(python_out)
        command = 'flatc -p -o {} {} {}'.format(python_out, enum_schema, data_schema)
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
        v = str(self.sheet.cell(r, c)).strip()
        return self.parse_int(v) if self.is_int(v) else v

    def encode(self):
        self.load_modules()
        self.builder = flatbuffers.builder.Builder(1*1024*1024)
        item_offsets:list[int] = []
        column_indice = self.get_column_indice(self.sheet, 'id')
        sort_index = column_indice[0] if column_indice else 0
        sort_items = []
        for r in range(ROW_DATA_INDEX, self.sheet.nrows):
            if self.is_cell_empty(self.sheet.cell(r, 0)): continue
            self.cursor = r
            offset = self.__encode_table(self.table)
            sort_items.append([self.parse_sort_field(r, sort_index), offset])
            self.log(0, '{} {}'.format(self.table.type_name, self.ptr(offset)))
            item_offsets.append(offset)
        sort_items.sort(key=lambda x:x[0])
        self.log(0, '{-}', item_offsets)
        item_offsets = [x[1] for x in sort_items]
        self.log(0, '{+}', item_offsets)
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

    def save_syntax(self, table:TableFieldObject, include_enum:bool = True):
        self.table = table
        print('# {}'.format(self.sheet.name))
        self.syntax_filepath = p.join(self.workspace, '{}.fbs'.format(table.type_name.lower()))
        with open(self.syntax_filepath, 'w+') as fp:
            buffer = io.StringIO()
            self.__generate_syntax(table, buffer)
            buffer.seek(0)
            if include_enum:
                fp.write('include "{}";\n\n'.format(self.enum_filename))
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
        self.has_enum = False
        # enum settings
        self.__enum_filepath = p.join(p.dirname(p.abspath(__file__)), '{}.json'.format(SHARED_ENUM_NAME))
        self.__enum_map: dict[str, dict[str, int]] = {}
        if p.exists(self.__enum_filepath):
            with open(self.__enum_filepath) as fp:
                self.__enum_map: dict[str, dict[str, int]] = json.load(fp)

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

    def __parse_array(self, array:ArrayFieldObject, sheet:xlrd.sheet.Sheet, column:int, depth:int = 0)->int:
        self.log(depth, '[ARRAY] col:{} count:{}'.format(self.abc(column-1), array.count))
        table:TableFieldObject = self.__parse_field(sheet, column, depth=depth + 1)
        assert table.type == FieldType.table
        c = column + 1
        assert table.member_count > 0
        table.offset = c
        c = self.__parse_table(table, sheet, c, depth=depth + 1)
        array.table = table
        count = 1
        if array.count > count:
            while c < sheet.ncols:
                element = TableFieldObject(table.member_count)
                element.name = table.name
                element.type_name = table.type_name
                c = self.__parse_table(element, sheet, c, depth=depth + 1)
                assert element.equal(table), element
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
        field.rule = rule_map.get(field_rule)
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
                nest_table.type_name = self.__get_table_name(nest_table.name, prefix=sheet.name)
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
            _, field.default = self.parse_value('', field.type)
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
            assert not table.has_member(field.name), '{} {}'.format(field.name, self.abc(field.offset))
            member_fields.append(field)
            if 0 < table.member_count == len(member_fields):
                position = c
                table.size = position - column # exclude declaration field
                self.log(depth, table)
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
        encoder.init(sheet=self.__sheet)
        encoder.save_enums(enum_map=self.__enum_map)
        encoder.save_syntax(table=self.__root, include_enum=self.has_enum)
        encoder.encode()

if __name__ == '__main__':
    import sys, argparse
    arguments = argparse.ArgumentParser()
    arguments.add_argument('--workspace', '-w', default='/Users/larryhou/Downloads/flatcfg/temp', help='workspace path for outputs and temp files')
    arguments.add_argument('--book-file', '-f', nargs='+', required=True, help='xls book file path')
    arguments.add_argument('--use-protobuf', '-u', action='store_true', help='generate protobuf format binary output')
    arguments.add_argument('--debug', '-d', action='store_true', help='use debug mode to get more detial information')
    arguments.add_argument('--error', '-e', action='store_true', help='raise error to console')
    arguments.add_argument('--auto-default-case', '-c', action='store_true', help='auto generate a NONE default case for each enum')
    arguments.add_argument('--namespace', '-n', default='dataconfig', help='namespace for serialize class')
    options = arguments.parse_args(sys.argv[1:])
    for book_filepath in options.book_file:
        print('>>> {}'.format(book_filepath))
        book = xlrd.open_workbook(book_filepath)
        for sheet_name in book.sheet_names(): # type: str
            if not sheet_name.isupper(): continue
            serializer = SheetSerializer(debug=options.debug)
            try:
                serializer.parse_syntax(book.sheet_by_name(sheet_name))
                if options.use_protobuf:
                    encoder = ProtobufEncoder(workspace=options.workspace, debug=options.debug)
                else:
                    encoder = FlatbufEncoder(workspace=options.workspace, debug=options.debug)
                encoder.set_package_name(options.namespace)
                serializer.pack(encoder, auto_default_case=options.auto_default_case)
            except Exception as error:
                if options.error: raise error
                else: continue
        book.release_resources()



