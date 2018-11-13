#!/usr/bin/env python3
from typing import Tuple
import os.path as p
import os, re, io

class ScriptGenerator(object):
    def __init__(self):
        self.__buffer = io.StringIO()
        self.__depth:int = 0

    def __indent(self, depth: int = 0) -> str:
        return ' ' * 4 * depth

    def end(self, repeat:int = 1, gap:int = 0):
        if self.__depth <= 0: return
        if repeat <= 0: repeat = self.__depth
        self.__depth -= 1
        self.__buffer.write(self.__indent(self.__depth))
        self.__buffer.write('}\n')
        if gap > 0: self.__buffer.write('\n'*gap)
        if repeat > 1: self.end(repeat - 1)

    def gap(self, num = 1):
        if num >= 1: self.__buffer.write('\n'*num)

    def begin_namespace(self, name:str):
        indent = self.__indent(self.__depth)
        self.__buffer.write('{}namespace {}\n'.format(indent, name))
        self.__buffer.write('{}{{\n'.format(indent))
        self.__depth += 1

    def begin_class(self, name:str, static:bool = True, where:str = None):
        indent = self.__indent(self.__depth)
        self.__buffer.write('{}public'.format(indent))
        if static: self.__buffer.write(' static')
        self.__buffer.write(' class {}\n'.format(name))
        if where: self.__buffer.write(' where {}'.format(where))
        self.__buffer.write('{}{{\n'.format(indent))
        self.__depth += 1

    def begin_method(self, name:str, parameters:Tuple[Tuple[str,str],...] = (), return_type:str = None, static:bool = True, public:bool = True, where:str = None):
        indent = self.__indent(self.__depth)
        self.__buffer.write(indent)
        if public: self.__buffer.write('public')
        if static: self.__buffer.write('{}static'.format(' ' if public else ''))
        self.__buffer.write(' {}'.format(return_type if return_type else 'void'))
        self.__buffer.write(' {}'.format(name))
        self.__buffer.write('(')
        param_count = len(parameters)
        for n in range(param_count):
            param_type, param_name = parameters[n]
            self.__buffer.write('{} {}'.format(param_type, param_name))
            if n + 1 < param_count: self.__buffer.write(', ')
        self.__buffer.write(')')
        if where: self.__buffer.write(' where {}'.format(where))
        self.__buffer.write('\n')
        self.__buffer.write('{}{{\n'.format(indent))
        self.__depth += 1

    def write(self, s:str, *args):
        self.__buffer.write(self.__indent(self.__depth))
        self.__buffer.write(s.format(*args))
        self.__buffer.write('\n')

    def dump(self):
        self.__buffer.seek(0)
        return self.__buffer.read()

def generate_protobuf_manager()->ScriptGenerator:
    gen = ScriptGenerator()
    for package_name in ('System', 'System.IO', 'System.Collections.Generic', 'UnityEngine', 'dataconfig'):
        gen.write('using {};', package_name)
    gen.gap()
    gen.begin_class(options.class_name)
    gen.write('static ProtobufConfigSerializer serializer = new ProtobufConfigSerializer();')
    gen.write('static Dictionary<string, TextAsset> manager = new Dictionary<string, TextAsset>();')
    gen.write('static Dictionary<Type, object> database = new Dictionary<Type, object>();')
    gen.gap()
    gen.begin_method('Prepare')
    gen.write('TextAsset item;')
    for file_path in data_items:
        file_name = pattern.sub('', p.basename(file_path))
        gen.write('item = Resources.Load<TextAsset>("{}/{}");', load_path, file_name)
        gen.write('manager.Add("{}", item);'.format(file_name))
    gen.end(gap=1)
    gen.write('static MemoryStream stream;')
    gen.begin_method('GetConfig', parameters=(('Type', 'type'), ('byte[]', 'data')), return_type='object', public=False)
    gen.write('if (stream == null) {{ stream = new MemoryStream(); }}')
    gen.write('stream.Position = 0;')
    gen.write('stream.Write(data, 0, data.Length);')
    gen.write('stream.Position = 0;')
    gen.write('return serializer.Deserialize(stream, null, type, data.Length);')
    gen.end(gap=1)
    gen.begin_method('LoadConfig')
    gen.write('Type type;')
    gen.write('object config;')
    for file_path in data_items:
        file_name = pattern.sub('', p.basename(file_path))
        class_name = '{}_ARRAY'.format(file_name.upper())
        gen.write('type = typeof({});', class_name)
        gen.write('config = GetConfig(type, manager["{}"].bytes);', file_name)
        gen.write('database[type] = config;')
    gen.end(gap=1)
    gen.begin_method('GetConfig<T>', return_type='T', where='T:ProtoBuf.IExtensible')
    gen.write('return (T)database[typeof(T)];')
    gen.end(gap=1)
    gen.begin_method('Clear')
    gen.write('database.Clear();')
    gen.end(repeat=0)
    return gen

def generate_flatbuf_manager()->ScriptGenerator:
    gen = ScriptGenerator()
    for package_name in ('System', 'System.Collections.Generic', 'UnityEngine', 'FlatBuffers', 'dataconfig'):
        gen.write('using {};', package_name)
    gen.gap()
    gen.begin_class(options.class_name)
    gen.write('static readonly Dictionary<string, TextAsset> manager = new Dictionary<string, TextAsset>();')
    gen.write('static readonly Dictionary<Type, IFlatbufferObject> database = new Dictionary<Type, IFlatbufferObject>();')
    gen.gap()
    gen.begin_method('Prepare')
    gen.write('TextAsset item;')
    for file_path in data_items:
        file_name = pattern.sub('', p.basename(file_path))
        gen.write('item = Resources.Load<TextAsset>("{}/{}");', load_path, file_name)
        gen.write('manager.Add("{}", item);', file_name)
    gen.end(gap=1)
    gen.begin_method('LoadConfig')
    gen.write('TextAsset item;')
    gen.write('IFlatbufferObject config;')
    for file_path in data_items:
        file_name = pattern.sub('', p.basename(file_path))
        gen.write('item = manager["{}"];', file_name)
        class_name = '{}_ARRAY'.format(file_name.upper())
        gen.write('config = {}.GetRootAs{}(new ByteBuffer(item.bytes));', class_name, class_name)
        gen.write('database[config.GetType()] = config;')
    gen.end(gap=1)
    gen.begin_method('GetConfig<T>', return_type='T', where='T:IFlatbufferObject')
    gen.write('return (T)database[typeof(T)];')
    gen.end(gap=1)
    gen.begin_method('Clear')
    gen.write('database.Clear();')
    gen.end(repeat=0)
    return gen

if __name__ == '__main__':
    import argparse, sys
    arguments = argparse.ArgumentParser()
    arguments.add_argument('--data-path', '-p', default=p.expanduser('~/Downloads/flatcfg'))
    arguments.add_argument('--sync-proj', '-t')
    arguments.add_argument('--protobuf', '-pb', action='store_true')
    arguments.add_argument('--class-name', '-n', default='ConfigManager')
    options = arguments.parse_args(sys.argv[1:])
    sync_data_path = 'Assets/Resources/DataConfig'
    load_path = '/'.join(sync_data_path.split('/')[2:])
    os.system('mkdir -pv {}/{}'.format(options.sync_proj, sync_data_path))
    data_items = []
    pattern = re.compile(r'(\.ppb)$') if options.protobuf else re.compile(r'(\.fpb)$')
    for file_name in os.listdir(options.data_path): # type: str
        if not pattern.search(file_name): continue
        data_items.append(p.join(options.data_path, file_name))
    sync_proj:str = None
    if options.sync_proj:
        sync_proj = options.sync_proj # type:str
        with open('sync2proj.sh', 'w+') as fp:
            fp.write('#!/usr/bin/env bash\n')
            fp.write('set -x\n')
            for file_path in data_items:
                relative_path = p.join(sync_data_path, pattern.sub('.bytes', p.basename(file_path)))
                fp.write('cp -fv {!r} {!r}\n'.format(file_path, p.join(sync_proj, relative_path)))
            fp.write('rm -f {}\n'.format(fp.name))
            fp.close()
            assert os.system('bash -xe {}'.format(fp.name)) == 0
    if options.protobuf:
        gen = generate_protobuf_manager()
    else:
        gen = generate_flatbuf_manager()
    print(gen.dump())
    if sync_proj:
        script_out = p.join(sync_proj, 'Assets/Scripts')
        if not p.exists(script_out): os.makedirs(script_out)
        with open('{}/{}.cs'.format(script_out, options.class_name), 'w+') as fp:
            fp.write(gen.dump())
