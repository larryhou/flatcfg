#!/usr/bin/env python3
import os.path as p
import dict_to_protobuf

if __name__ == '__main__':
    import argparse, sys, re, os, json
    arguments = argparse.ArgumentParser()
    arguments.add_argument('--workspace', '-w', default=p.expanduser('~/Downloads/flatcfg'))
    arguments.add_argument('--name', '-n', required=True, help='config name without extension')
    arguments.add_argument('--protobuf', '-pb', action='store_true', help='decode protobuf serialized data')
    arguments.add_argument('--namespace', '-ns', default='dataconfig')
    options = arguments.parse_args(sys.argv[1:])
    os.chdir(options.workspace)

    name = re.sub(r'\.[^.]+$', '', options.name)
    if options.protobuf:
        python_out = 'pb'
        if not p.exists(python_out): os.makedirs(python_out)
        command = 'protoc --proto_path=. --python_out={} {}.proto shared_*.proto'.format(python_out, name)
        print('+ {}'.format(command))
        assert os.system(command) == 0
        sys.path.append(p.abspath(python_out))
        module_name = '{}_pb2'.format(name)
        exec('import {}'.format(module_name))
        module = locals().get(module_name)
        cls = getattr(module, '{}_ARRAY'.format(name.upper()))
        with open('{}.ppb'.format(name), 'rb') as fp:
            root = getattr(cls, 'FromString')(fp.read())
            data = dict_to_protobuf.protobuf_to_dict(root, use_enum_labels=True)
            print(json.dumps(data, ensure_ascii=False, indent=4))
    else:
        command = 'flatc --raw-binary --json --defaults-json --strict-json {}.fbs -- {}.fpb'.format(name, name)
        print('+ {}'.format(command))
        assert os.system(command) == 0
        with open('{}.json'.format(name), 'r') as fp:
            data = json.load(fp)
            print(json.dumps(data, ensure_ascii=False, indent=4))
