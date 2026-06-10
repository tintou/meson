# SPDX-License-Identifier: Apache-2.0
# Copyright 2024 The Meson development team

"""Loader that extracts function/kwarg metadata from typed_kwargs decorators.

This loader introspects the interpreter at import time to extract structural
documentation (argument names, types, required, defaults, version info) from
the @typed_kwargs and @typed_pos_args decorators.  Prose descriptions are not
available here — they must come from a YAML overlay.
"""

from __future__ import annotations

import inspect
import typing as T

from .loaderbase import LoaderBase
from .model import (
    Function,
    Kwarg,
    Method,
    Object,
    ObjectType,
    PosArg,
    ReferenceManual,
    Type,
    VarArgs,
)

from mesonbuild import mlog
from mesonbuild.interpreterbase.decorators import ContainerTypeInfo, KwargInfo


def _type_to_str(types: T.Union[T.Type, T.Tuple, ContainerTypeInfo]) -> str:
    """Convert a KwargInfo type annotation to a Meson doc type string."""
    if not isinstance(types, tuple):
        types = (types,)

    parts: T.List[str] = []
    for t in types:
        if isinstance(t, ContainerTypeInfo):
            container = 'dict' if t.container is dict else 'list'
            if isinstance(t.contains, tuple):
                inner = ' | '.join(_single_type_name(x) for x in t.contains)
            else:
                inner = _single_type_name(t.contains)
            parts.append(f'{container}[{inner}]')
        elif t is type(None):
            pass  # NoneType means the argument is optional, not a distinct doc type
        else:
            parts.append(_single_type_name(t))

    return ' | '.join(parts) if parts else 'void'


# Map Python class names to Meson reference-manual type names.
_PYTHON_TO_MESON_TYPE: T.Dict[str, str] = {
    'str': 'str',
    'bool': 'bool',
    'int': 'int',
    'float': 'str',  # not a first-class Meson type
    'list': 'list',
    'dict': 'dict',
    'File': 'file',
    'BuildTarget': 'build_tgt',
    'CustomTarget': 'custom_tgt',
    'CustomTargetIndex': 'custom_idx',
    'Executable': 'exe',
    'StaticLibrary': 'lib',
    'SharedLibrary': 'lib',
    'BothLibraries': 'both_libs',
    'SharedModule': 'lib',
    'Jar': 'jar',
    'Dependency': 'dep',
    'InternalDependency': 'dep',
    'ExternalProgram': 'external_program',
    'Program': 'external_program',
    'EnvironmentVariables': 'env',
    'ExtractedObjects': 'extracted_obj',
    'GeneratedList': 'generated_list',
    'IncludeDirs': 'inc',
    'RunTarget': 'run_tgt',
    'AliasTarget': 'alias_tgt',
    'SubprojectHolder': 'subproject',
    'MachineHolder': 'build_machine',
    'Feature': 'feature',
    'Disabler': 'disabler',
    'StructuredSources': 'structured_src',
    'RangeHolder': 'range',
    'Generator': 'generator',
    'ConfigurationData': 'cfg_data',
}


def _single_type_name(t: T.Type) -> str:
    name = t.__name__
    return _PYTHON_TO_MESON_TYPE.get(name, name.lower())


def _default_str(v: T.Any) -> str:
    if v is None:
        return ''
    if v is True:
        return 'true'
    if v is False:
        return 'false'
    if isinstance(v, str):
        return repr(v)
    if isinstance(v, list):
        return '[]'
    if isinstance(v, dict):
        return '{}'
    return str(v)


def _kwarginfo_to_kwarg(info: KwargInfo) -> Kwarg:
    return Kwarg(
        name=info.name,
        description='',
        since=info.since or '',
        deprecated=info.deprecated or '',
        type=Type(_type_to_str(info.types)),
        required=info.required,
        default=_default_str(info.default),
    )


def _pos_type_to_str(t: T.Union[T.Type, T.Tuple]) -> str:
    if isinstance(t, tuple):
        return ' | '.join(_single_type_name(x) for x in t if x is not type(None))
    return _single_type_name(t)


def _extract_function(meson_name: str, method: T.Callable) -> T.Optional[Function]:
    """Build a Function from a decorated interpreter method."""
    kwargs: T.Dict[str, Kwarg] = {}
    posargs: T.List[PosArg] = []
    optargs: T.List[PosArg] = []
    varargs: T.Optional[VarArgs] = None

    if hasattr(method, '__typed_kwargs__'):
        _func_name, kw_infos = method.__typed_kwargs__
        for info in kw_infos:
            kwargs[info.name] = _kwarginfo_to_kwarg(info)

    if hasattr(method, '__typed_pos_args__'):
        pa = method.__typed_pos_args__
        for i, t in enumerate(pa['types']):
            posargs.append(PosArg(
                name=f'arg{i}',
                description='',
                since='',
                deprecated='',
                type=Type(_pos_type_to_str(t)),
                default='',
            ))
        if pa['optargs']:
            for i, t in enumerate(pa['optargs']):
                optargs.append(PosArg(
                    name=f'arg{len(posargs) + i}',
                    description='',
                    since='',
                    deprecated='',
                    type=Type(_pos_type_to_str(t)),
                    default='',
                ))
        if pa['varargs'] is not None:
            varargs = VarArgs(
                name='args',
                description='',
                since='',
                deprecated='',
                type=Type(_pos_type_to_str(pa['varargs'])),
                min_varargs=pa['min_varargs'],
                max_varargs=pa['max_varargs'],
            )

    if not kwargs and not posargs and not optargs and varargs is None:
        return None

    return Function(
        name=meson_name,
        description='',
        since='',
        deprecated='',
        notes=[],
        warnings=[],
        returns=Type('void'),
        example='',
        posargs=posargs,
        optargs=optargs,
        varargs=varargs,
        kwargs=kwargs,
        posargs_inherit='',
        optargs_inherit='',
        varargs_inherit='',
        kwargs_inherit=[],
        arg_flattening=True,
    )


class LoaderPython(LoaderBase):
    """Extract documentation structure from @typed_kwargs/@typed_pos_args decorators.

    This loader produces Function objects with raw (unresolved) type strings and
    empty descriptions.  It is intended to be used either standalone for tooling
    (e.g. diffing code vs YAML) or as the structural source in a merged loader
    that overlays YAML for prose descriptions and object definitions.
    """

    def load(self) -> ReferenceManual:
        # Skip the resolver: our raw type strings are not in the YAML type map
        # and descriptions are intentionally empty.  Callers that need resolved
        # types should use a merged loader instead.
        self._input_files = []
        return self.load_impl()

    def load_impl(self) -> ReferenceManual:
        mlog.log('Loading Python (typed_kwargs) reference data')
        with mlog.nested():
            functions = self._load_interpreter_functions()
        return ReferenceManual(functions=functions, objects=[])

    def _load_interpreter_functions(self) -> T.List[Function]:
        # Import lazily to avoid side-effects at module level
        from mesonbuild.interpreter.interpreter import Interpreter

        # Build name→method mapping from the funcs dict template
        # We use the class's unbound methods to avoid needing a real environment
        name_to_pymethod: T.Dict[str, T.Callable] = {}
        for py_name, member in inspect.getmembers(Interpreter, predicate=inspect.isfunction):
            name_to_pymethod[py_name] = member

        # Reverse-map meson function names → Python method names via build_func_dict
        # We parse the source of build_func_dict to avoid instantiating the interpreter
        meson_to_py = self._map_meson_names_to_methods(name_to_pymethod)

        functions: T.List[Function] = []
        for meson_name, method in sorted(meson_to_py.items()):
            func = _extract_function(meson_name, method)
            if func is not None:
                mlog.log('Extracted', mlog.bold(meson_name))
                functions.append(func)
            else:
                mlog.log('Skipped (no type info)', mlog.bold(meson_name))

        return functions

    def _map_meson_names_to_methods(
        self, name_to_pymethod: T.Dict[str, T.Callable]
    ) -> T.Dict[str, T.Callable]:
        """Parse build_func_dict source to map meson names to Python methods."""
        import ast
        import textwrap
        from mesonbuild.interpreter.interpreter import Interpreter

        src = textwrap.dedent(inspect.getsource(Interpreter.build_func_dict))
        tree = ast.parse(src)

        mapping: T.Dict[str, T.Callable] = {}
        for node in ast.walk(tree):
            # Look for dict literals: {'meson_name': self.func_xxx, ...}
            if not isinstance(node, ast.Dict):
                continue
            for key, val in zip(node.keys, node.values):
                if not isinstance(key, ast.Constant) or not isinstance(key.value, str):
                    continue
                # val should be an Attribute node: self.func_xxx
                if not isinstance(val, ast.Attribute):
                    continue
                py_name = val.attr
                if py_name in name_to_pymethod:
                    mapping[key.value] = name_to_pymethod[py_name]

        return mapping
