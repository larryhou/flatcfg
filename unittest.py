#!/usr/bin/env python3
from flatcfg import *
import os.path as p
import xlrd

class Suitcase(Codec):
    def __init__(self):
        super(Suitcase, self).__init__()
        self.sheet:xlrd.sheet.Sheet = None
        self.table:TableFieldObject = None
        self.python_out:str = None
        self.workspace:str = None
        self.cursor:int = -1
        self.module_map = {}
        self.row_layout:list[list[xlrd.sheet.Cell]] = None
        self.fixed32_codec: FixedCodec = None
        self.fixed64_codec: FixedCodec = None
        self.signed_encoding: bool = True

    def build_layout(self):
        self.row_layout = []
        column_indice = self.get_column_indice(self.sheet,'id')
        for n in range(ROW_DATA_INDEX, self.sheet.nrows):
            cell = self.sheet.cell(n, 0)
            if self.is_cell_empty(cell): continue
            row = self.sheet.row(n)
            self.row_layout.append(row)
        if column_indice:
            index = column_indice[0]
            field_type = str(self.sheet.cell(ROW_TYPE_INDEX, index).value).strip()
            field_type = vars(FieldType).get(field_type) # type: FieldType
            assert field_type
            if field_type == FieldType.string:
                self.row_layout.sort(key=lambda x: x[index].value)
            else:
                self.row_layout.sort(key=lambda x: float(x[index].value))

    def check(self, value, store):
        if isinstance(value, float):
            flag = abs(value - store) <= 1.0e-2
        elif isinstance(value, str):
            flag = True if not value and not store else value == store
        else:
            flag = value == store
        assert flag, 'expect={!r} but={!r}'.format(value, store)

    def compile_schemas(self) -> str:
        pass

    def load_modules(self):
        BookEncoder.load_modules(self)
        return self.module_map

    def run(self):
        pass

class ProtobufSuitcase(Suitcase):
    def __init__(self):
        super(ProtobufSuitcase, self).__init__()
        self.data:object = None

    def compile_schemas(self)->str:
        return ProtobufEncoder.compile_schemas(self)

    def create_root_object(self, buffer)->object:
        module_name = self.sheet.name # type: str
        module = self.module_map.get('{}_pb2'.format(module_name.lower()))
        cls = getattr(module, ROOT_CLASS_TEMPLATE.format(module_name))
        return getattr(cls, 'FromString')(buffer)

    def get_enum_number(self, type_name:str, case_name:str)->int:
        module = self.module_map.get('{}_pb2'.format(SHARED_ENUM_NAME.lower()))
        cls = getattr(module, type_name)
        return getattr(cls, 'Value')(case_name)

    def read_data(self):
        data_filepath = '{}/{}.ppb'.format(self.workspace, self.sheet.name.lower())
        with open(data_filepath, 'rb') as fp:
            self.data = self.create_root_object(fp.read()) # type: object
            print(self.data.__class__)

    def test_table(self, table:TableFieldObject, data:object):
        for field in table.member_fields:
            field_data = getattr(data, field.name)
            if isinstance(field, TableFieldObject) and field.tag == FieldTag.none:
                self.test_table(field, field_data)
            elif isinstance(field, ArrayFieldObject):
                self.test_array(field, field_data)
            elif isinstance(field, GroupFieldObject):
                self.test_group(field, field_data)
            elif field.rule == FieldRule.repeated:
                self.test_repeated_list(field, field_data)
            else:
                self.test_field(field, field_data)

    def test_array(self, array:ArrayFieldObject, data):
        assert len(data) <= len(array.elements)
        for n in range(len(data)):
            self.test_table(array.elements[n], data[n])

    def test_group(self, group:GroupFieldObject, data):
        assert len(data) <= len(group.items)
        for n in range(len(data)):
            self.test_field(group.items[n], data[n])

    def test_field(self, field:FieldObject, store:object, value:str = None):
        if value is None:
            value = str(self.row_layout[self.cursor][field.offset].value).strip()
        if field.type == FieldType.string:
            self.check(value, store)
        elif isinstance(field, EnumFieldObject):
            if not field.default: field.hook_default()
            case_name = value if value else field.default
            self.check(self.get_enum_number(field.enum, case_name), store)
        else:
            if self.fixed64_codec and field.tag == FieldTag.fixed_float64:
                value = self.parse_float(value)
                store = getattr(store, FIXED_MEMORY_NAME)
                store = self.fixed64_codec.decode(store)
            elif self.fixed32_codec and field.tag == FieldTag.fixed_float32:
                value = self.parse_float(value)
                store = getattr(store, FIXED_MEMORY_NAME)
                store = self.fixed32_codec.decode(store)
            else:
                value = self.parse_scalar(value, field.type)
            self.check(value, store)

    def test_repeated_list(self, field:FieldObject, data):
        value = str(self.row_layout[self.cursor][field.offset].value).strip()
        items = self.parse_array(value)
        assert len(items) == len(data)
        for n in range(len(data)):
            self.test_field(field, data[n], items[n])

    def run(self):
        self.read_data()
        for n in range(len(self.row_layout)):
            self.cursor = n
            self.test_table(self.table, getattr(self.data, 'items')[n])

class FlatbufSuitcase(Suitcase):
    def __init__(self):
        super(FlatbufSuitcase, self).__init__()
        self.data:object = None

    def compile_schemas(self):
        return FlatbufEncoder.compile_schemas(self)

    def read_data(self):
        data_filepath = '{}/{}.fpb'.format(self.workspace, self.sheet.name.lower())
        with open(data_filepath, 'rb') as fp:
            buffer = bytearray(fp.read())
            self.data = self.create_root_object(buffer)
            print(self.data)

    def create_root_object(self, buffer:bytearray)->object:
        module_name = ROOT_CLASS_TEMPLATE.format(self.sheet.name)
        module = self.module_map.get(module_name) # type: object
        cls = getattr(module, module_name)
        return getattr(cls, 'GetRootAs{}'.format(module_name))(buffer, 0)

    def get_enum_number(self, type_name:str, case_name:str):
        module = self.module_map.get(type_name)
        cls = getattr(module, type_name)
        return getattr(cls, case_name)

    def test_table(self, table:TableFieldObject, data:object):
        for field in table.member_fields:
            if isinstance(field, ArrayFieldObject):
                length = getattr(data, self.make_camel(field.name) + 'Length')()
                self.test_array(field, getattr(data, self.make_camel(field.name)), length)
            elif isinstance(field, TableFieldObject) and field.tag == FieldTag.none:
                self.test_table(field, getattr(data, self.make_camel(field.name))())
            elif isinstance(field, GroupFieldObject):
                length = getattr(data, self.make_camel(field.name) + 'Length')()
                self.test_group(field, getattr(data, self.make_camel(field.name)), length)
            elif field.rule == FieldRule.repeated:
                length = getattr(data, self.make_camel(field.name) + 'Length')()
                self.test_repeated_list(field, getattr(data, self.make_camel(field.name)), length)
            else:
                self.test_field(field, getattr(data, self.make_camel(field.name))())

    def test_array(self, array:ArrayFieldObject, getter:callable, length:int):
        assert length <= len(array.elements)
        for n in range(length):
            self.test_table(array.elements[n], getter(n))

    def test_group(self, group:GroupFieldObject, getter:callable, length:int):
        assert length <= len(group.items)
        for n in range(length):
            item = group.items[n]
            self.test_field(item, getter(n))

    def test_repeated_list(self, field:FieldObject, getter:callable, length:int):
        value = str(self.row_layout[self.cursor][field.offset].value).strip()
        items = self.parse_array(value)
        assert length == len(items)
        for n in range(length):
            self.test_field(field, getter(n), items[n])

    def test_field(self, field:FieldObject, store, value:str = None):
        if value is None:
            value = str(self.row_layout[self.cursor][field.offset].value).strip()
        if field.type == FieldType.string:
            store = store.decode('utf-8') if store else None
            self.check(value, store)
        elif isinstance(field, EnumFieldObject):
            if not field.default: field.hook_default()
            case_name = value if value else field.default
            value = self.get_enum_number(field.enum, case_name)
            self.check(value, store)
        else:
            if self.fixed64_codec and field.tag == FieldTag.fixed_float64:
                value = self.parse_float(value)
                store = getattr(store, self.make_camel(FIXED_MEMORY_NAME))()
                print(value, store)
                store = self.fixed64_codec.decode(store)
            elif self.fixed32_codec and field.tag == FieldTag.fixed_float32:
                value = self.parse_float(value)
                store = getattr(store, self.make_camel(FIXED_MEMORY_NAME))()
                store = self.fixed32_codec.decode(store)
            else:
                value = self.parse_scalar(value, field.type)
            self.check(value, store)

    def run(self):
        self.read_data()
        for n in range(len(self.row_layout)):
            self.cursor = n
            self.test_table(self.table, getattr(self.data, 'Items')(n))

if __name__ == '__main__':
    import argparse, sys
    arguments = argparse.ArgumentParser()
    arguments.add_argument('--excel-file', '-f', nargs='+', required=True)
    arguments.add_argument('--protobuf', '-pb', action='store_true')
    arguments.add_argument('--first-sheet', '-fs', action='store_true', help='only serialize first sheet')
    arguments.add_argument('--namespace', '-n', default='dataconfig', help='namespace for serialize class')
    arguments.add_argument('--workspace', '-w', default=p.expanduser('~/Downloads/flatcfg'), help='workspace path for outputs and temp files')
    arguments.add_argument('--debug', '-d', action='store_true', help='use debug mode to get more detial information')
    # arguments for fixed float encoding
    arguments.add_argument('--fixed32-fraction-bits', '-b32', default=10, type=int, help='use 2^exponent to present fractional part of a float32 value')
    arguments.add_argument('--fixed64-fraction-bits', '-b64', default=20, type=int, help='use 2^exponent to present fractional part of a float64 value')
    arguments.add_argument('--fixed64', '-64', action='store_true', help='encode double field values into FixedFloat64 type')
    arguments.add_argument('--fixed32', '-32', action='store_true', help='encode float field values into FixedFloat32 type')
    arguments.add_argument('--unsigned-encoding', '-0', action='store_true', help='encode fixed memory value into unsign integer type')
    options = arguments.parse_args(sys.argv[1:])
    for excel_filepath in options.excel_file:
        book = xlrd.open_workbook(excel_filepath)
        for sheet_name in book.sheet_names(): # type: str
            if not sheet_name.isupper(): continue
            sheet = book.sheet_by_name(sheet_name)
            serializer = SheetSerializer(debug=options.debug)
            serializer.signed_encoding = not options.unsigned_encoding
            if options.fixed32:
                serializer.fixed32_codec = FixedCodec(fraction_bits=options.fixed32_fraction_bits, type_size=32)
            if options.fixed64:
                serializer.fixed64_codec = FixedCodec(fraction_bits=options.fixed64_fraction_bits, type_size=64)
            serializer.parse_syntax(sheet)
            if not serializer.root_table.member_fields: continue
            if options.protobuf:
                suitcase = ProtobufSuitcase()
                suitcase.python_out = p.join(options.workspace, 'pp')
            else:
                suitcase = FlatbufSuitcase()
                suitcase.python_out = p.join(options.workspace, 'fp', options.namespace)
            sys.path.append(suitcase.python_out)
            suitcase.signed_encoding = serializer.signed_encoding
            suitcase.fixed64_codec = serializer.fixed64_codec
            suitcase.fixed32_codec = serializer.fixed32_codec
            suitcase.sheet = sheet
            suitcase.table = serializer.root_table
            suitcase.workspace = options.workspace
            suitcase.load_modules()
            suitcase.build_layout()
            suitcase.run()
            if options.first_sheet: exit()


