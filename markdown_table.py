#!/usr/bin/env python3

import xlrd, sys, io, re

PRINT_ROW_COUNT = 5

if __name__ == '__main__':
    buffer = io.StringIO()
    note_column = ('FIELD_RULE', 'FIELD_TYPE', 'FIELD_NAME', 'FIELD_ACES', 'FIELD_DESC')
    for book_filepath in sys.argv[1:]:
        book = xlrd.open_workbook(book_filepath)
        buffer.write('> {}\n'.format(book_filepath))
        for sheet_name in book.sheet_names(): # type: str
            if not sheet_name.isupper(): continue
            buffer.write('### {}\n'.format(sheet_name))
            sheet = book.sheet_by_name(sheet_name)
            column_count = sheet.ncols
            buffer.write('|{}\n'.format(' |'*(column_count+1)))
            buffer.write('|{}\n'.format(':--|'*(column_count+1)))
            for r in range(PRINT_ROW_COUNT):
                buffer.write('| {} |'.format(note_column[r]))
                for c in range(column_count):
                    cell = sheet.cell(r, c)
                    value = cell.value
                    if isinstance(value, float):
                        value = int(value) if value.is_integer() else value
                    if isinstance(value, str):
                        value = re.split(r'\s*[\r\n]\s*', value)[0]
                    buffer.write(' {} |'.format(value))
                buffer.write('\n')
            buffer.write('\n'*2)
        book.release_resources()
    buffer.seek(0)
    print(buffer.read())