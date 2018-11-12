#!/usr/bin/env python3
import os.path as p
import os, shutil
from assembly import AssemblyCompiler

if __name__ == '__main__':
    import argparse, sys
    arguments = argparse.ArgumentParser()
    arguments.add_argument('--workspace', '-w', default=p.expanduser('~/Downloads/flatcfg'))
    arguments.add_argument('--name', '-n', default='FlatbufConfig', help='config name without extension')
    arguments.add_argument('--dependence', '-d', nargs='+', help='assembly files which source scripts depend on')
    options = arguments.parse_args(sys.argv[1:])
    workspace = p.abspath(options.workspace)
    script_path = p.dirname(p.abspath(__file__))
    project_path = p.join(script_path, 'temp_flat/{}'.format(options.name))
    command = 'flatc -n -o {} --gen-onefile {}/*.fbs'.format(p.join(project_path, 'Scripts'), workspace)
    print('+ {}'.format(command))
    assert os.system(command) == 0
    compiler = AssemblyCompiler(options.name, project_path=script_path)
    compiler.add_assembly_dependences(assembly_dependences=[p.join(script_path, 'flatbuffer.dll')])
    compiler.add_package_references(package_references=['System.Core'])
    compiler.add_source_paths(source_paths=[project_path])
    assembly_path = compiler.compile(debug=True, force=True)
    print('+ copy {} -> {}'.format(assembly_path, workspace))
    shutil.copy(assembly_path, workspace)