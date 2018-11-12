#!/usr/bin/env python3
#encoding:utf-8

import os, uuid, re, shutil, time, platform
import os.path as p
import lxml.etree as etree

class configuration_names(object):
    debug, release = 'Debug', 'Release'

class UniqueArray(list):
    def unique_extend_paths(self, path_items): # type: (list[str], list[str])->None
        if not path_items: return
        for item in [p.abspath(x) for x in path_items]:
            if item not in self: self.append(item)

    def unique_extend_items(self, items): # type: (list[str], list[str])->None
        if not items: return
        for item in items:
            if item not in self: self.append(item)

    def unique_append(self, item):
        if item and item not in self: self.append(item)

class Compiler(object):
    def __init__(self):
        self.script_path = p.dirname(p.abspath(__file__))

class AssemblyCompiler(Compiler):
    def __init__(self, name, project_path:str = None):
        super(AssemblyCompiler, self).__init__()
        assert name
        self.name:str = name
        self.define_symbols:UniqueArray[str] = UniqueArray()
        self.assembly_dependences:UniqueArray[str] = UniqueArray()
        self.package_references:UniqueArray[str] = UniqueArray()
        self.source_paths:UniqueArray[str] = UniqueArray()
        self.debug:bool = False
        self.force:bool = False
        self.__xml_parser = etree.XMLParser(compact=True, remove_blank_text=True)
        self.__build_path:str = 'csharp_temp/{}'.format(name) if not project_path else project_path
        self.__csproj_path:str = p.join(self.__build_path, 'project.csproj')
        self.__csproj_data:str = None

    def add_assembly_dependences(self, assembly_dependences): # type: (list[str])->None
        print('>> add_assembly_dependences {!r}'.format(assembly_dependences))
        self.assembly_dependences.unique_extend_paths(assembly_dependences)

    def add_package_references(self, package_references): # type: (list[str])->None
        print('>> add_package_references {!r}'.format(package_references))
        self.package_references.unique_extend_items(package_references)

    def add_define_symbols(self, define_symbols): # type: (list[str])->None
        print('>> add_define_symbols {!r}'.format(define_symbols))
        self.define_symbols.unique_extend_items(define_symbols)

    def add_source_paths(self, source_paths): # type: (list[str])->None
        print('>> add_source_paths {!r}'.format(source_paths))
        self.source_paths.unique_extend_paths(source_paths)

    def __generate_project_config(self):
        node = etree.XML('<PropertyGroup/>')
        node.append(etree.XML('<Configuration Condition=" \'$(Configuration)\' == \'\' ">Debug</Configuration>'))
        node.append(etree.XML('<Platform Condition=" \'$(Platform)\' == \'\' ">AnyCPU</Platform>'))
        node.append(etree.XML('<ProjectGuid>{{{}}}</ProjectGuid>'.format(str(uuid.uuid1()).upper())))
        node.append(etree.XML('<OutputType>Library</OutputType>'))
        node.append(etree.XML('<RootNamespace>{}</RootNamespace>'.format(self.name)))
        node.append(etree.XML('<AssemblyName>{}</AssemblyName>'.format(self.name)))
        node.append(etree.XML('<TargetFrameworkVersion>v3.5</TargetFrameworkVersion>'))
        return node

    def __generate_reference_config(self):
        node = etree.XML('<ItemGroup/>')
        for reference in self.package_references:
            node.append(etree.XML('<Reference Include="{}" />'.format(reference)))

        for dependence in self.assembly_dependences:
            name = re.sub(r'\.dll$', '', p.basename(dependence), re.IGNORECASE)
            config = """
            <Reference Include="{}">
                <HintPath>{}</HintPath>
            </Reference>
            """.format(name, re.sub(r'/', r'\\', dependence))
            node.append(etree.XML(config, parser=self.__xml_parser))
        return node

    def __generate_class_config(self):
        node = etree.XML('<ItemGroup/>')
        for source_path in self.source_paths:
            node.append(etree.XML('<Compile Include="{}\***\*.cs" />'.format(re.sub(r'/', r'\\', p.abspath(source_path)))))
        # node.append(etree.XML('<Compile Include="Properties\AssemblyInfo.cs" />'))
        return node

    def __generate_build_config(self, debug): # type: (bool)->None
        name = configuration_names.debug if debug else configuration_names.release
        node = etree.XML('<PropertyGroup Condition=" \'$(Configuration)|$(Platform)\' == \'{}|AnyCPU\' "/>'.format(name))
        node.append(etree.XML('<DebugSymbols>{}</DebugSymbols>'.format(str(debug).lower())))
        node.append(etree.XML('<DebugType>full</DebugType>'))
        node.append(etree.XML('<Optimize>{}</Optimize>'.format(str(not debug).lower())))
        node.append(etree.XML('<OutputPath>bin\{}</OutputPath>'.format(name)))
        node.append(etree.XML('<DefineConstants>{};{}</DefineConstants>'.format(name.upper(), ';'.join(self.define_symbols))))
        node.append(etree.XML('<ErrorReport>prompt</ErrorReport>'))
        node.append(etree.XML('<WarningLevel>4</WarningLevel>'))
        node.append(etree.XML('<ConsolePause>false</ConsolePause>'))
        return node

    def __generate_assembly_properties(self, class_path):
        if not p.exists(p.dirname(class_path)): os.makedirs(p.dirname(class_path))
        timestamp = time.strftime('%Y-%m-%dT%H:%M:%S', time.localtime())
        with open(class_path, 'w+') as fp:
            fp.write('using System.Reflection;\n')
            fp.write('using System.Runtime.CompilerServices;\n\n')
            fp.write('[assembly: AssemblyTitle ("{}")]\n'.format(self.name))
            fp.write('[assembly: AssemblyDescription ("{}")]\n'.format(timestamp))
            fp.write('[assembly: AssemblyConfiguration ("")]\n')
            fp.write('[assembly: AssemblyCompany ("")]\n')
            fp.write('[assembly: AssemblyProduct ("")]\n')
            fp.write('[assembly: AssemblyCopyright ("larryhou")]\n')
            fp.write('[assembly: AssemblyTrademark ("")]\n')
            fp.write('[assembly: AssemblyCulture ("")]\n')
            fp.write('[assembly: AssemblyVersion ("1.0.*")]\n')
            fp.seek(0)
            print(fp.read())

    def __generate_csproj(self):
        assert self.__build_path
        if not p.exists(self.__build_path):
            os.makedirs(self.__build_path)
        assembly_class = p.join(self.__build_path, 'Properties', 'AssemblyInfo.cs')
        self.__generate_assembly_properties(class_path=assembly_class)
        root = etree.XML('<Project DefaultTargets="Build" ToolsVersion="4.0" />')
        root.append(self.__generate_project_config())
        root.append(self.__generate_build_config(debug=True))
        root.append(self.__generate_build_config(debug=False))
        root.append(self.__generate_reference_config())
        root.append(self.__generate_class_config())
        root.append(etree.XML('<Import Project="$(MSBuildBinPath)\Microsoft.CSharp.targets" />'))
        root.set('xmlns', 'http://schemas.microsoft.com/developer/msbuild/2003')
        with open(self.__csproj_path, 'w+') as fp:
            fp.write(self.__dump_xml(root))
            fp.seek(0)
            print(fp.read())
        self.__csproj_data = root

    def __dump_xml(self, node):
        return etree.tostring(node, pretty_print=True, encoding='utf-8', xml_declaration=True).decode('utf-8')

    def __is_windows(self):
        return platform.system().lower() == 'windows'

    def __get_build_config(self, debug): # type: (bool)->any
        name = configuration_names.debug if debug else configuration_names.release
        data = self.__csproj_data.xpath('//PropertyGroup[contains(@Condition, "{}")]'.format(name))[0]
        return data

    def __get_current_output_path(self):
        config = self.__get_build_config(debug=self.debug)
        return re.sub(r'\\', r'/', config.xpath('./OutputPath/text()')[0])

    def __generate_dll_assembly(self):
        build_type = configuration_names.debug if self.debug else configuration_names.release
        command = '{} /property:Configuration={} /toolsversion:3.5'.format(self.__csproj_path, build_type)
        if self.force:
            command += ' /target:Rebuild'
        if self.__is_windows():
            command = 'C:/Windows/Microsoft.NET/Framework64/v3.5/MSBuild.exe ' + command
        else:
            command = '/Library/Frameworks/Mono.framework/Versions/3.12.1/bin/xbuild ' + command
        print('+', command)
        assert os.system(command) == 0

    def compile(self, debug = False, force = False):
        self.debug, self.force = debug, force
        self.__generate_csproj()
        self.__generate_dll_assembly()
        return '{}/{}.dll'.format(p.join(self.__build_path, self.__get_current_output_path()), self.name)

if __name__ == '__main__':
    import argparse, sys
    arguments = argparse.ArgumentParser()
    arguments.add_argument('--name', '-n', required=True, help='assembly name for saving')
    arguments.add_argument('--csharp-path', '-p', nargs='+', required=True, help='C# source script paths')
    arguments.add_argument('--output-path', '-o', help='output path for generated *.dll file')
    arguments.add_argument('--package', '-g', nargs='+', default=['System'], help='package names which are referenced by source scripts')
    arguments.add_argument('--dependence', '-d', nargs='+', help='assembly files which source scripts depend on')
    arguments.add_argument('--symbol', '-s', help='add precompile symbols')
    arguments.add_argument('--debug', action='store_true', help='compile with \'/property:Configuration=Debug\' setting')
    arguments.add_argument('--force', action='store_true', help='compile with \'/target:Rebuild\' setting')
    options = arguments.parse_args(sys.argv[1:])
    compiler = AssemblyCompiler(options.name)
    compiler.add_assembly_dependences(assembly_dependences=options.dependence)
    compiler.add_package_references(package_references=options.package)
    compiler.add_define_symbols(define_symbols=options.symbol)
    compiler.add_source_paths(source_paths=options.csharp_path)
    assembly_path = compiler.compile(debug=options.debug, force=options.force)
    if options.output_path:
        print('+ copy {} -> {}'.format(assembly_path, options.output_path))
        shutil.copy(assembly_path, options.output_path)

