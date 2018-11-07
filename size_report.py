#!/usr/bin/env python3

if __name__ == '__main__':
    import argparse, sys, os, re
    arguments = argparse.ArgumentParser()
    arguments.add_argument('--workspace', '-w', required=True)
    arguments.add_argument('--markdown', '-m', action='store_true')
    options = arguments.parse_args(sys.argv[1:])
    workspace = options.workspace # type: str
    markdown = options.markdown # type: bool
    result = []
    total = ['SUMMARY', 0, 0]
    max_name_length = 0
    for file_name in os.listdir(workspace):
        if not file_name.endswith('.fpb'): continue
        name = re.sub(r'\.fpb', '', file_name)
        fpb = os.path.join(workspace, file_name)
        ppb = os.path.join(workspace, '{}.ppb'.format(name))
        if not os.path.exists(ppb): continue
        stat = [name]
        max_name_length = max(max_name_length, len(name))
        result.append(stat)
        stat.append(os.path.getsize(fpb))
        stat.append(os.path.getsize(ppb))
        total[1] += stat[1]
        total[2] += stat[2]
    result.sort(key=lambda a:a[1])
    result.append(total)
    report_format = '{{:>{}s}} {{:9,}} {{:9,}} {{:9,}} {{:7.1f}}%'.format(max_name_length)
    if markdown:
        report_format = '| {} |'.format(report_format.replace(' ', ' | '))
        header_names = ['CONF_NAME', 'FLATBUF', 'PROTOBUF', 'DIFF', 'DIFF_PCT']
        header_sizes = [max(max_name_length, len(header_names[0])),
                        max(9, len(header_names[1])), max(9, len(header_names[1])), max(9, len(header_names[1])),
                        max(6, len(header_names[4]))]

        import io
        buffer = io.StringIO()
        buffer.write('|')
        for item in header_names:
            buffer.write(' {} |'.format(item))
        buffer.write('\n')
        buffer.write('|')
        for size in header_sizes:
            buffer.write('-{}:|'.format(size * '-'))
        buffer.seek(0)
        print(buffer.read())
    for stat in result:
        diff = stat[1] - stat[2]
        percent = diff / stat[1] * 100
        print(report_format.format(*stat, diff, percent))



