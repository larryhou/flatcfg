#!/usr/bin/env python3
import enum, xlrd, re, string, io, json, os
import os.path as p
from typing import Dict
import operator

ROW_RULE_INDEX, \
ROW_TYPE_INDEX, \
ROW_NAME_INDEX, \
ROW_ACES_INDEX, \
ROW_DESC_INDEX, \
ROW_DATA_INDEX = range(6)

SHARED_ENUM_NAME = 'shared_enum'

class FieldType(enum.Enum):
    float, float32, float64, double, \
    int16, uint16, int8 , uint8 , \
    int32, uint32, int64, uint64, \
    short, ushort, byte, ubyte, long, ulong, \
    bool, string, bytes = range(21) # standard protobuf scalar types
    date, duration, enum, table, array = tuple(x + 100 for x in range(5)) # extend field types

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
        self.default:str = None

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

    def import_cases(self, case_list): # type: (list[str])->None
        offset = 0
        if self.case_map:
            for index in self.case_map.values():
                if index > offset: offset = index
        else:
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

class BytesEncoder(object):
    def __init__(self, workspace:str):
        self.package_name: str = ''
        self.enum_filepath: str = None
        self.enum_filename: str = None
        self.syntax_filepath: str = None
        self.sheet: xlrd.sheet.Sheet = None
        self.table: TableFieldObject = None
        assert workspace
        if not p.exists(workspace): os.makedirs(workspace)
        self.workspace:str = workspace

    def set_package_name(self, package_name:str):
        self.package_name = package_name

    def opt(self, v:str)->str:
        return re.sub(r'\.0$', '', v) if self.is_int(v) else v

    def abc(self, index):
        label = ''
        num = len(string.ascii_uppercase)
        if index >= num:
            label += string.ascii_uppercase[int(index / num) - 1]
            label += string.ascii_uppercase[index % num]
        else:
            label += string.ascii_uppercase[index]
        return label

    def is_int(self, v:str)->bool:
        return re.match(r'^[+-]?\d+\.0$', v)

    def parse_int(self, v:str):
        return int(re.sub(r'\.0$', '', v)) if v else 0

    def parse_float(self, v:str)->float:
        return float(v) if v else 0.0

    def parse_bool(self, v:str)->bool:
        return self.parse_int(v) != 0 if v else False

    def parse_array(self, v:str):
        return [self.opt(x) for x in re.split(r'\s*[;\uff1b]\s*', v)] # split with ;|；

    def parse_value(self, v:str, t:FieldType):
        if t in (FieldType.array, FieldType.table): return v
        elif re.match(r'^u?int\d*$', t.name) or re.match(r'^u?(long|short|byte)$', t.name): return self.parse_int(v)
        elif t == FieldType.double or re.match(r'^float\d*$', t.name): return self.parse_float(v)
        elif t == FieldType.bool: return self.parse_bool(v)
        else: return v

    def get_indent(self, depth:int)->str:
        return ' '*depth*4

    def encode(self, sheet:xlrd.sheet.Sheet):
        pass

    def save_enums(self, enum_map: Dict[str, Dict[str, int]]):
        pass

    def save_syntax(self, table: TableFieldObject):
        pass

class ProtobufEncoder(BytesEncoder):
    def __init__(self, workspace:str):
        super(ProtobufEncoder, self).__init__(workspace)
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
            if member.type not in (FieldType.table, FieldType.array):
                if member.default: buffer.write('[default = {}]'.format(member.default))
            buffer.write(';')
            if member.description: buffer.write(' // {!r}'.format(member.description))
            buffer.write('\n')
        buffer.write('}\n\n')
        for nest_table in nest_table_list:
            self.__generate_syntax(nest_table, buffer)
        if table.member_count == 0:
            buffer.write('message {}_ARRAY\n{{\n'.format(table.type_name))
            buffer.write('{}{} {} items = 1;\n'.format(indent, FieldRule.repeated.name, table.type_name))
            buffer.write('}\n')

    def encode(self, sheet:xlrd.sheet.Sheet):
        self.sheet = sheet
        pass

    def save_enums(self, enum_map:Dict[str,Dict[str,int]]):
        self.enum_filepath = p.join(self.workspace, self.enum_filename)
        with open(self.enum_filepath, 'w+') as fp:
            if self.package_name:
                fp.write('package {};\n\n'.format(self.package_name))
            fp.write(self.__generate_enums(enum_map))
            fp.seek(0)
            print('+ {}'.format(self.enum_filepath))
            print(fp.read())

    def save_syntax(self, table:TableFieldObject):
        self.syntax_filepath = p.join(self.workspace, '{}.proto'.format(table.type_name.lower()))
        with open(self.syntax_filepath, 'w+') as fp:
            buffer = io.StringIO()
            self.__generate_syntax(table, buffer)
            buffer.seek(0)
            fp.write('import "{}";\n\n'.format(self.enum_filename))
            if self.package_name:
                fp.write('package {};\n\n'.format(self.package_name))
            fp.write(buffer.read())
            fp.seek(0)
            print('+ {}'.format(self.syntax_filepath))
            print(fp.read())

class FlatbufEncoder(BytesEncoder):
    def __init__(self, workspace:str):
        super(FlatbufEncoder, self).__init__(workspace)
        self.enum_filename = '{}.fbs'.format(SHARED_ENUM_NAME)

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
                buffer.write(member.enum)
            elif member.type == FieldType.date:
                buffer.write(FieldType.uint32.name)
            elif member.type == FieldType.duration:
                buffer.write(FieldType.uint32.name)
            else:
                assert member.type, member
                buffer.write(member.type.name)
                if member.name.lower() == 'id': buffer.write(' (key)')
            if member.type not in (FieldType.table, FieldType.array):
                if member.default: buffer.write(' = {}'.format(member.default))
            buffer.write(';')
            if member.description: buffer.write(' // {!r}'.format(member.description))
            buffer.write('\n')
        buffer.write('}\n\n')
        for nest_table in nest_table_list:
            self.__generate_syntax(nest_table, buffer)
        if table.member_count == 0:
            buffer.write('table {}_ARRAY\n{{\n'.format(table.type_name))
            buffer.write('{}items:[{}];\n'.format(indent, table.type_name))
            buffer.write('}\n')

    def encode(self, sheet:xlrd.sheet.Sheet):
        self.sheet = sheet
        pass

    def save_enums(self, enum_map:Dict[str,Dict[str,int]]):
        self.enum_filepath = p.join(self.workspace, self.enum_filename)
        with open(self.enum_filepath, 'w+') as fp:
            if self.package_name:
                fp.write('namespace {};\n\n'.format(self.package_name))
            fp.write(self.__generate_enums(enum_map))
            fp.seek(0)
            print('+ {}'.format(self.enum_filepath))
            print(fp.read())

    def save_syntax(self, table:TableFieldObject):
        self.syntax_filepath = p.join(self.workspace, '{}.fbs'.format(table.type_name.lower()))
        with open(self.syntax_filepath, 'w+') as fp:
            buffer = io.StringIO()
            self.__generate_syntax(table, buffer)
            buffer.seek(0)
            fp.write('include "{}";\n\n'.format(self.enum_filename))
            if self.package_name:
                fp.write('namespace {};\n\n'.format(self.package_name))
            fp.write(buffer.read())
            fp.seek(0)
            print('+ {}'.format(self.syntax_filepath))
            print(fp.read())

class SheetSerializer(object):
    def __init__(self, debug = True):
        self.__type_map:dict[str, any] = vars(FieldType)
        self.__rule_map:dict[str, any] = vars(FieldRule)
        self.__debug:bool = debug
        self.__root:TableFieldObject = None
        self.__sheet:xlrd.sheet.Sheet = None
        self.__field_map:dict[int, FieldObject] = {}
        # enum settings
        self.__enum_filepath = p.join(p.dirname(p.abspath(__file__)), '{}.json'.format(SHARED_ENUM_NAME))
        self.__enum_map: dict[str, dict[str, int]] = {}
        if p.exists(self.__enum_filepath):
            with open(self.__enum_filepath) as fp:
                self.__enum_map: dict[str, dict[str, int]] = json.load(fp)

    def __parse_int(self, v):
        return int(re.sub(r'\.0$', '', v))

    def __is_int(self, v:str):
        return re.match(r'^\d+\.0$', v) is not None

    def __parse_access(self, v:str)->FieldAccess:
        v = v.lower()
        if v in ('s', 'svr', 'server'): return FieldAccess.server
        if v in ('c', 'cli', 'client'): return FieldAccess.client
        return FieldAccess.default

    def log(self, indent=0, *kwargs):
        if not self.__debug: return
        print(*kwargs) if indent <= 0 else print(' '*(indent*4-1), *kwargs)

    def abc(self, index):
        label = ''
        num = len(string.ascii_uppercase)
        if index >= num:
            label += string.ascii_uppercase[int(index / num) - 1]
            label += string.ascii_uppercase[index % num]
        else:
            label += string.ascii_uppercase[index]
        return label

    def __get_table_name(self, field_name:str, prefix:str = None)->str:
        if field_name.find('_') > 0:
            table_name = ''.join([x.title() for x in field_name.split('_')])
        else:
            table_name = field_name
        if prefix and prefix.find('_'):
            prefix = ''.join([x.title() for x in prefix.split('_')])
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
        if self.__is_int(field_type):
            num = self.__parse_int(field_type)
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
            field_value = str(cell.value).strip()
            if field_value not in unique_values: unique_values.append(field_value)
        return unique_values

    def pack(self, encoder:BytesEncoder):
        visit_map:dict[str, bool] = {}
        for field in self.__field_map.values():
            if not isinstance(field, EnumFieldObject): continue
            field.hook_default()
            if field.enum in visit_map: continue
            field.import_cases(self.__get_unique_values(field.offset))
            visit_map[field.enum] = True
        encoder.encode(sheet=self.__sheet)
        encoder.save_enums(enum_map=self.__enum_map)
        encoder.save_syntax(table=self.__root)
        with open(self.__enum_filepath, 'w+') as fp:
            json.dump(self.__enum_map, fp, indent=4)
            # print('+ {}'.format(self.__enum_filepath))
            # fp.seek(0)
            # print(fp.read())

if __name__ == '__main__':
    import sys, argparse
    arguments = argparse.ArgumentParser()
    arguments.add_argument('--workspace', '-w', default='/Users/larryhou/Downloads/flatcfg')
    arguments.add_argument('--book-file', '-f', nargs='+', required=True)
    arguments.add_argument('--use-protobuf', '-u', action='store_true')
    options = arguments.parse_args(sys.argv[1:])
    for book_filepath in options.book_file:
        book = xlrd.open_workbook(book_filepath)
        for sheet_name in book.sheet_names(): # type: str
            if not sheet_name.isupper(): continue
            serializer = SheetSerializer()
            try:
                serializer.parse_syntax(book.sheet_by_name(sheet_name))
                if options.use_protobuf:
                    encoder = ProtobufEncoder(workspace=options.workspace)
                else:
                    encoder = FlatbufEncoder(workspace=options.workspace)
                encoder.set_package_name('dataconfig')
                serializer.pack(encoder)
            except Exception: pass
            break

