#!/usr/bin/env python3

import xlrd, sys, io, re, argparse

if __name__ == '__main__':
    arguments = argparse.ArgumentParser()
    arguments.add_argument('--excel-file', '-f', nargs='+')
    arguments.add_argument('--print-full', '-a', action='store_true')
    options = arguments.parse_args(sys.argv[1:])
    buffer = io.StringIO()
    note_column = ('FIELD_RULE', 'FIELD_TYPE', 'FIELD_NAME', 'FIELD_ACES', 'FIELD_DESC')
    for book_filepath in options.excel_file:
        book = xlrd.open_workbook(book_filepath)
        buffer.write('> {}\n'.format(book_filepath))
        for sheet_name in book.sheet_names(): # type: str
            if not sheet_name.isupper(): continue
            buffer.write('### {}\n'.format(sheet_name))
            sheet = book.sheet_by_name(sheet_name)
            column_count = sheet.ncols
            buffer.write('|{}\n'.format(' |'*(column_count+1)))
            buffer.write('|{}\n'.format(':--|'*(column_count+1)))
            print_count = sheet.nrows if options.print_full else 5
            for r in range(print_count):
                if r < len(note_column):
                    buffer.write('| {} |'.format(note_column[r]))
                else:
                    buffer.write('| FIELD_DATA |')
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