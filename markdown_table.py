#!/usr/bin/env python3

import xlrd, sys, io, re, argparse

if __name__ == '__main__':
    arguments = argparse.ArgumentParser()
    arguments.add_argument('--excel-file', '-f', nargs='+')
    arguments.add_argument('--print-full', '-a', action='store_true')
    arguments.add_argument('--show-row-info', '-i', action='store_true')
    arguments.add_argument('--fraction-num', '-n', type=int, default=3)
    options = arguments.parse_args(sys.argv[1:])
    buffer = io.StringIO()
    show_row_info = options.show_row_info
    note_column = ('FIELD_RULE', 'FIELD_TYPE', 'FIELD_NAME', 'FIELD_ACES', 'FIELD_DESC')
    float_format_ge = '{{:.{}f}}'.format(options.fraction_num)
    float_format_lt = '{{:.{}f}}'.format(options.fraction_num*2)
    for book_filepath in options.excel_file:
        book = xlrd.open_workbook(book_filepath)
        buffer.write('> {}\n'.format(book_filepath))
        for sheet_name in book.sheet_names(): # type: str
            if not sheet_name.isupper(): continue
            buffer.write('### {}\n'.format(sheet_name))
            sheet = book.sheet_by_name(sheet_name)
            column_count = sheet.ncols
            if show_row_info:
                buffer.write('|{}\n'.format(' |'*(column_count+1)))
                buffer.write('|{}\n'.format(':--|'*(column_count+1)))
            else:
                buffer.write('|{}\n'.format(' |' * column_count))
                buffer.write('|{}\n'.format(':--|' * column_count))
            print_count = sheet.nrows if options.print_full else 5
            for r in range(print_count):
                if show_row_info:
                    if r < len(note_column):
                        buffer.write('| {} |'.format(note_column[r]))
                    else:
                        buffer.write('| FIELD_DATA |')
                else:
                    buffer.write('|')
                for c in range(column_count):
                    cell = sheet.cell(r, c)
                    value = cell.value
                    if isinstance(value, float):
                        if value.is_integer():
                            value = int(value)
                        else:
                            if value >= 1:
                                value = float_format_ge.format(value)
                            else:
                                value = float_format_lt.format(value)
                    if isinstance(value, str):
                        value = re.split(r'\s*[\r\n]\s*', value)[0]
                    buffer.write(' {} |'.format(value))
                buffer.write('\n')
            buffer.write('\n'*2)
        book.release_resources()
    buffer.seek(0)
    print(buffer.read())