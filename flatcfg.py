#!/usr/bin/env python3
import enum, xlrd, re, string, io

ROW_RULE_INDEX, \
ROW_TYPE_INDEX, \
ROW_NAME_INDEX, \
ROW_ACES_INDEX, \
ROW_DESC_INDEX, \
ROW_DATA_INDEX = range(6)

class FieldType(enum.Enum):
    float, \
    int32, int64, uint32, uint64, sint32, sint64, \
    fixed32, fixed64, sfixed32, sfixed64, \
    bool, string, bytes = range(14) # standard protobuf scalar types
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

class ArrayFieldObject(FieldObject):
    def __init__(self, count:int):
        super(ArrayFieldObject, self).__init__()
        self.table: TableFieldObject = None
        self.__count:int = count
        assert count > 0

    @property
    def count(self) -> int: return self.__count

class TableFieldObject(FieldObject):
    def __init__(self, member_count:int = 0):
        super(TableFieldObject, self).__init__()
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
        return '{} member_count:{}'.format(super(TableFieldObject, self).__repr__(), len(self.member_fields))

class SheetEncoder(object):
    def __init__(self):
        pass

    def encode(self, sheet:xlrd.sheet.Sheet, table:TableFieldObject):
        pass

class ProtobufEncoder(SheetEncoder):
    def __init__(self):
        super(ProtobufEncoder, self).__init__()

class FlatbufEncoder(SheetEncoder):
    def __init__(self):
        super(FlatbufEncoder, self).__init__()

class SheetSerializer(object):
    def __init__(self, debug = True):
        self.__type_map = vars(FieldType)
        self.__rule_map = vars(FieldRule)
        self.__debug = debug

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
        table_name = ''.join([x.title() for x in field_name.split('_')])
        prefix = ''.join([x.title() for x in prefix.split('_')])
        return prefix + table_name if prefix else table_name

    def __parse_array(self, array:ArrayFieldObject, sheet:xlrd.sheet.Sheet, column:int, depth:int = 0)->int:
        self.log(depth, '[ARRAY] col:{} count:{}'.format(self.abc(column-1), array.count))
        array.type = FieldType.array
        field, field_type = self.__parse_field(sheet, column, depth=depth + 1)
        c = column + 1
        assert self.__is_int(field_type)
        member_count = self.__parse_int(field_type)
        assert member_count > 0
        table = TableFieldObject(member_count)
        table.fill(field)
        table.name = self.__get_table_name(table.name, prefix=sheet.name)
        table.offset = c
        c = self.__parse_table(table, sheet, c, depth=depth + 1)
        array.table = table
        count = 1
        if array.count > count:
            while c < sheet.ncols:
                element = TableFieldObject(table.member_count)
                element.name = table.name
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

    def __parse_field(self, sheet:xlrd.sheet.Sheet, column:int, depth:int = 0)->(FieldObject, str):
        c = column
        type_map = self.__type_map
        rule_map = self.__rule_map
        cell_type = sheet.cell_type(ROW_RULE_INDEX, c)
        if cell_type != xlrd.XL_CELL_TEXT: return None, None
        field_rule = sheet.cell_value(ROW_RULE_INDEX, c).strip()  # type: str
        if field_rule == '*': return None, None
        field_type = str(sheet.cell_value(ROW_TYPE_INDEX, c)).strip()  # type: str
        field_name = str(sheet.cell_value(ROW_NAME_INDEX, c)).strip()  # type: str
        field_aces = str(sheet.cell_value(ROW_ACES_INDEX, c)).strip()  # type: str
        field_desc = str(sheet.cell_value(ROW_DESC_INDEX, c)).strip()  # type: str
        # fill field object
        field = FieldObject()
        field.type = type_map.get(field_type)
        field.name = field_name
        field.rule = rule_map.get(field_rule)
        field.access = self.__parse_access(field_aces)
        field.description = field_desc
        field.offset = c
        self.log(depth, '{:2d} {:2s} {}'.format(c, self.abc(c), field))
        return field, field_type

    def __parse_table(self, table:TableFieldObject, sheet:xlrd.sheet.Sheet, column:int, depth:int = 0)->int:
        member_fields = table.member_fields
        table.type = FieldType.table
        self.log(depth, '[TABLE] col:{} member_count:{} name:{}'.format(self.abc(column), table.member_count, table.name))
        c = column
        while c < sheet.ncols:
            field, field_type = self.__parse_field(sheet, column=c, depth=depth + 1) # type: FieldObject, str
            c += 1
            if not field: continue
            if self.__is_int(field_type):
                num = self.__parse_int(field_type)
                if field.rule == FieldRule.repeated: # array
                    nest_array = ArrayFieldObject(num)
                    nest_array.fill(field)
                    field = nest_array
                    c = self.__parse_array(nest_array, sheet, c, depth=depth + 1) # parse array
                else: # table
                    nest_table = TableFieldObject(num)
                    nest_table.fill(field)
                    nest_table.name = self.__get_table_name(nest_table.name, prefix=sheet.name)
                    field = nest_table
                    c = self.__parse_table(nest_table, sheet, c, depth=depth + 1)
            else: # simple
                field.size = 1
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
        root = TableFieldObject()
        root.name = sheet.name
        self.__parse_table(root, sheet, 0)
        return root

if __name__ == '__main__':
    import sys
    book = xlrd.open_workbook(sys.argv[1])
    for sheet_name in book.sheet_names(): # type: str
        if not sheet_name.isupper(): continue
        serializer = SheetSerializer()
        serializer.parse_syntax(book.sheet_by_name(sheet_name))
        print('+'*80)