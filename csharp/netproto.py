#!/usr/bin/env python3
import os.path as p
import os, re, platform
from assembly import Compiler, AssemblyCompiler, UniqueArray

class ProtobufCompiler(Compiler):
    def __init__(self, name:str):
        super(ProtobufCompiler, self).__init__()
        self.__proto_file_list:UniqueArray[str] = UniqueArray()
        self.__proto_path_list:UniqueArray[str] = UniqueArray()
        self.__build_path:str = p.join(self.script_path, 'proto_temp/{}'.format(name))
        self.__csharp_out:str = p.join(self.__build_path, 'Scripts')
        if not p.exists(self.__build_path): os.makedirs(self.__build_path)
        self.name = name
        assert name

    def add_proto_files(self, proto_files):  # type: (list[str])->None
        print('>> add_proto_files {!r}'.format(proto_files))
        if proto_files:
            self.__proto_file_list.unique_extend_paths(proto_files)
            self.__proto_path_list.unique_extend_paths([p.dirname(x) for x in proto_files])

    def add_proto_paths(self, proto_paths):  # type: (list[str])->None
        print('>> add_proto_paths {!r}'.format(proto_paths))
        for proto_path in proto_paths:
            proto_path = p.abspath(proto_path)
            self.__proto_path_list.unique_append(proto_path)
            for file_name in os.listdir(proto_path):
                if file_name.endswith('.proto'):
                    self.__proto_file_list.unique_append(p.join(proto_path, file_name))

    def add_proto_dependence_files(self, proto_files):  # type: (list[str])->None
        print('>> add_proto_dependence_files {!r}'.format(proto_files))
        if proto_files: self.__proto_path_list.unique_extend_paths([p.dirname(x) for x in proto_files])

    def add_proto_dependence_paths(self, proto_paths):  # type: (list[str])->None
        print('>> add_proto_dependence_paths {!r}'.format(proto_paths))
        self.__proto_path_list.unique_extend_paths(proto_paths)

    def __is_windows(self):
        return platform.system().lower() == 'windows'

    def __generate_descriptor(self):
        command_template = 'protoc'
        for proto_path in self.__proto_path_list:
            command_template += ' --proto_path={}'.format(proto_path)
        command_template += ' --descriptor_set_out={}/{{}}.desc {{}}'.format(self.__build_path)
        for proto_file in self.__proto_file_list:
            proto_name = re.sub(r'\.proto$', '', p.basename(proto_file), re.IGNORECASE)
            command = command_template.format(proto_name, proto_file)
            print('+', command)
            print(os.popen(command).read())

    def __generate_csharp_script(self):
        protogen = p.join(self.script_path, 'protobuf-net/ProtoGen/protogen.exe')
        script_path = self.__csharp_out
        if not p.exists(script_path): os.makedirs(script_path)
        command_template = protogen + ' -p:detectMissing -i:{{}} -o:{}/{{}}.cs'.format(script_path)
        if not self.__is_windows():
            command_template = 'mono {}'.format(command_template)
        for file_name in os.listdir(self.__build_path):
            if not file_name.endswith('.desc'): continue
            desc_temp = p.join(self.__build_path, file_name)
            command = command_template.format(desc_temp, re.sub(r'\.[^.]+$', '', file_name))
            print('+', command)
            assert os.system(command) == 0
            os.remove(desc_temp)

    def compile(self, debug:bool = True, force:bool = False):
        self.__generate_descriptor()
        self.__generate_csharp_script()
        asmCompiler = AssemblyCompiler(name=self.name, project_path=self.__build_path)
        asmCompiler.add_source_paths(source_paths=[self.__build_path])
        asmCompiler.add_package_references(package_references=['System', 'System.xml'])
        asmCompiler.add_assembly_dependences(assembly_dependences=[p.join(self.script_path, 'protobuf-net/ProtoGen/protobuf-net.dll')])
        assembly_path = asmCompiler.compile(debug, force)
        print('+ copy {} -> {}'.format(assembly_path, self.script_path))
        import shutil
        shutil.copy(assembly_path, self.script_path)


if __name__ == '__main__':
    import argparse, sys
    arguments = argparse.ArgumentParser()
    arguments.add_argument('--name', '-n', required=True)
    arguments.add_argument('--proto-file', '-f', nargs='+')
    arguments.add_argument('--proto-path', '-p', nargs='+')
    arguments.add_argument('--dependence-proto-file', '-df', nargs='+')
    arguments.add_argument('--dependence-proto-path', '-dp', nargs='+')
    arguments.add_argument('--debug', action='store_true')
    arguments.add_argument('--force', action='store_true')
    options = arguments.parse_args(sys.argv[1:])
    assert options.proto_file or options.proto_path
    pbCompiler = ProtobufCompiler(options.name)
    pbCompiler.add_proto_files(proto_files=options.proto_file)
    pbCompiler.add_proto_paths(proto_paths=options.proto_path)
    pbCompiler.add_proto_dependence_files(proto_files=options.dependence_proto_file)
    pbCompiler.add_proto_dependence_paths(proto_paths=options.dependence_proto_path)
    pbCompiler.compile(debug=options.debug, force=options.force)