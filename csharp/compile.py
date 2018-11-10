#!/usr/bin/env python3
import os.path as p
import os, shutil
from assembly import AssemblyCompiler

if __name__ == '__main__':
    import argparse, sys
    arguments = argparse.ArgumentParser()
    arguments.add_argument('--workspace', '-w', default=p.expanduser('~/Downloads/flatcfg'))
    arguments.add_argument('--name', '-n', default='FlatbufConfig', help='config name without extension')
    arguments.add_argument('--protobuf', '-pb', action='store_true', help='decode protobuf serialized data')
    arguments.add_argument('--dependence', '-d', nargs='+', help='assembly files which source scripts depend on')
    options = arguments.parse_args(sys.argv[1:])
    workspace = p.abspath(options.workspace)
    if not options.protobuf:
        csharp_out = p.join(workspace, 'fn')
        command = 'flatc -n -o {} --gen-onefile {}/*.fbs'.format(csharp_out, workspace)
        print('+ {}'.format(command))
        assert os.system(command) == 0
        compiler = AssemblyCompiler(options.name)
        compiler.add_assembly_dependences(assembly_dependences=options.dependence)
        compiler.add_package_references(package_references=['System.Core'])
        compiler.add_source_paths(source_paths=[csharp_out])
        assembly_path = compiler.compile(debug=True, force=True)
        print('+ copy {} -> {}'.format(assembly_path, workspace))
        shutil.copy(assembly_path, workspace)
    else:
        raise NotImplementedError()