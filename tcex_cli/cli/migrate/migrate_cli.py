"""TcEx Framework Module"""

# standard library
import ast
import logging
import re
from functools import cached_property
from pathlib import Path

# first-party
from tcex_cli.cli.cli_abc import CliABC
from tcex_cli.render.render import Render

# get logger
_logger = logging.getLogger(__name__.split('.', maxsplit=1)[0])


class MigrateCli(CliABC):
    """Migration Module."""

    def __init__(
        self,
        forward_ref: bool,
        update_code: bool,
    ):
        """Initialize instance properties."""
        super().__init__()
        self.forward_ref = forward_ref
        self.update_code = update_code

    def _replace_string(self, filename: Path, string: str, replacement: str):
        """Replace string in file."""
        file_changed = False
        new_file = []
        for line_no, line in enumerate(filename.open(mode='r', encoding='utf-8'), start=1):
            line = line.rstrip('\n')
            if string in line:
                Render.table.key_value(
                    'Replace Code',
                    {
                        'File Link': f'{filename}:{line_no}',
                        'Current Line': f'{line}',
                        'New Line': f'{line.replace(string, replacement)}',
                    },
                )
                response = Render.prompt.input(
                    'Replace line:',
                    prompt_default=f' (Default: [{self.accent}]yes[/{self.accent}])',
                )
                if response in ('', 'y', 'yes'):
                    line = line.replace(string, replacement)
                    file_changed = True
            new_file.append(line)

        if file_changed is True:
            with filename.open(mode='w', encoding='utf-8') as fh:
                fh.write('\n'.join(new_file) + '\n')

    @cached_property
    def _skip_directories(self):
        return [
            '.history',
            'deps',
            'deps_tests',
            'target',
        ]

    @cached_property
    def _skip_files(self):
        return [
            '__init__.py',
        ]

    @cached_property
    def _code_replacements(self):
        """Combined Code Replacements"""
        _code_replacements = self._tcex_app_testing_code_replacements
        _code_replacements.update(self._tcex_code_replacements)
        _code_replacements.update(self._tcex_import_replacements)
        _code_replacements.update(self._misc_code_replacements)
        return _code_replacements

    @property
    def _misc_code_replacements(self):
        """Replace TcEx code."""
        return {
            r'utils = Utils\(\)': {
                'replacement': 'utils = Util()',
            },
            r'Utils\(': {
                'replacement': 'Util(',
            },
            r'Utils\.': {
                'replacement': 'Util.',
            },
        }

    @property
    def _tcex_app_testing_code_replacements(self):
        """Replace TcEx code."""
        return {
            r'test_feature\.tcex\.playbook\.read\(': {
                'replacement': 'test_feature.aux.playbook.read.any(',
            },
            r'test_feature\.aux\.util\.file_operation\.write_temp_file\(': {
                'replacement': 'test_feature.aux.app.file_operation.write_temp_file(',
            },
            r'test_feature\.tcex\.log\.debug\(': {
                'replacement': 'test_feature.log.debug(',
            },
            r'test_feature\.test_case_feature': {
                'replacement': 'test_feature.aux.config_model.test_case_feature',
            },
            r'test_feature\.session': {
                'replacement': 'test_feature.aux.session_tc',
            },
            r'test_feature\.aux\.config_model\.profile\.data\.get\(': {
                'replacement': 'test_feature.aux.profile_runner.contents.get(',
            },
            # imports
            r'from tcex_testing\.env_store import EnvStore': {
                'replacement': 'from tcex_app_testing.env_store import EnvStore'
            },
        }

    @property
    def _tcex_code_replacements(self):
        """Replace TcEx code."""

        return {
            r'self\.args': {
                'replacement': 'self.in_',
                'in_file': ['app.py'],  # replacement only works in app.py
            },
            r'self\.ij\.model': {
                'replacement': 'self.tcex.app.ij.model',
            },
            r'self\.inputs\.model\.': {
                'replacement': 'self.in_.',
                'in_file': ['app.py'],  # replacement only works in app.py
            },
            r'self\.playbook\.output\.create\.variable\(': {
                'replacement': 'self.out.variable(',
                'in_file': ['app.py'],  # replacement only works in app.py
            },
            r'self\.tcex\.app\.playbook\.create_output': {
                'replacement': 'self.out.variables',
                'in_file': ['app.py'],  # replacement only works in app.py
            },
            r'self\.tcex\.file_operations\.': {
                'replacement': 'self.tcex.app.file_operation.',
            },
            r'self\.tcex\.get_session_external\(': {
                'replacement': 'self.tcex.requests_external.get_session(',
            },
            r'self\.tcex\.ij': {
                'replacement': 'self.tcex.app.ij',
            },
            r'self\.tcex\.inputs.model\.': {
                'replacement': 'self.in_.',
                'in_file': ['app.py'],  # replacement only works in app.py
            },
            r'self\.tcex\.inputs.model_unresolved\.': {
                'replacement': 'self.in_unresolved.',
                'in_file': ['app.py'],  # replacement only works in app.py
            },
            r'self\.tcex\.exit\(': {
                'replacement': 'self.tcex.exit.exit(',
            },
            r'self\.tcex\.lj': {
                'replacement': 'self.tcex.app.lj',
            },
            r'self\.tcex\.log\.': {
                'replacement': 'self.log.',
                'in_file': ['app.py'],  # replacement only works in app.py
            },
            r'self\.tcex\.playbook.create_output': {
                'replacement': 'self.out.variable',
                'in_file': ['app.py'],  # replacement only works in app.py
            },
            r'self\.tcex\.playbook.create.variable\(': {
                'replacement': 'self.out.variable(',
                'in_file': ['app.py'],  # replacement only works in app.py
            },
            r'self\.tcex\.playbook.exit\(': {
                'replacement': 'self.tcex.exit.exit(',
            },
            # playbook catch-all
            r'self\.tcex\.playbook': {
                'replacement': 'self.tcex.app.playbook',
                'in_file': ['app.py'],  # replacement only works in app.py
            },
            r'self\.tcex\.results_tc': {
                'replacement': 'self.tcex.app.results_tc',
            },
            r'self\.tcex\.service\.': {
                'replacement': 'self.tcex.app.service.',
            },
            r'self\.tcex\.session_external\.': {
                'replacement': 'self.tcex.session.external.',
            },
            r'self\.tcex\.utils\.': {
                'replacement': 'self.tcex.util.',
            },
            r'self\.tcex\.v2\.': {
                'replacement': 'self.tcex.api.tc.v2.',
            },
            r'self\.tcex\.v3\.': {
                'replacement': 'self.tcex.api.tc.v3.',
            },
        }

    @property
    def _tcex_import_replacements(self):
        """Replace TcEx code."""
        return {
            (
                r'from\stcex\simport'
                r'((?:\s)(?:OnException|OnSuccess|ReadArg)(?:,)?'
                r'(?:(?:\s)(?:OnException|OnSuccess|ReadArg)(?:,)?)?'
                r'(?:(?:\s)(?:OnException|OnSuccess|ReadArg)(?:,)?)?'
                r'(?:(?:\s)(?:OnException|OnSuccess|ReadArg)(?:,)?)?'
                r'(?:(?:\s)(?:OnException|OnSuccess|ReadArg)(?:,)?)?)'
            ): {
                'capture_group': 1,
                'replacement': 'from tcex.app import ',
            },
            r'from tcex\.app\.playbook\.advanced_request': {
                'replacement': 'from tcex.app.playbook.advanced_request',
            },
            r'from tcex\.backports import cached_property': {
                'replacement': 'from tcex.pleb.cached_property import cached_property',
            },
            r'from tcex\.input\.field_types': {
                'replacement': 'from tcex.input.field_type',
            },
            r'from tcex\.input\.models': {
                'replacement': 'from tcex.input.model',
            },
            r'from tcex\.decorators': {
                'replacement': 'from tcex.app.decorator',
            },
            r'from tcex\.playbook': {
                'replacement': 'from tcex.app.playbook',
            },
            r'from tcex\.sessions\.tc_session import TcSession': {
                'replacement': 'from tcex.requests_tc.tc_session import TcSession'
            },
            r'from tcex\.session_external': {
                'replacement': 'from tcex.session.external',
            },
            r'from tcex\.utils import Utils': {
                'replacement': 'from tcex.util import Util',
            },
            r'from tcex\.v2\.datastore': {
                'replacement': 'from tcex.api.tc.v2.datastore',
            },
            r'from tcex\.v3\.ti\.ti_utils\.indicator_types': {
                'replacement': 'from tcex.api.tc.utils.indicator_types',
            },
        }

    def _handle_constant_annotation(
        self,
        filename: Path,
        annotation: ast.Constant,
        imported_packages: dict[str, list[str]],
    ):
        """."""
        # handle Forward Ref
        if annotation.value:
            package = annotation.value.split('.')[0]
            if package in imported_packages['standard']:
                # _logger.debug(f'Forward Ref: {arg.annotation.value}')
                self._replace_string(
                    filename,
                    f'\'{annotation.value}\'',
                    annotation.value,
                )

    def parse_ast_body(
        self,
        filename: Path,
        body: list,
        imports_: dict[str, list[str]],
        in_typing_imports: bool = False,
    ):
        """."""
        for item in body:
            match item:
                case ast.Import() | ast.ImportFrom():
                    import_type = 'typing' if in_typing_imports else 'standard'
                    imports_[import_type].extend([n.name for n in item.names])

                case ast.AnnAssign():
                    match item.annotation:
                        case ast.Constant():
                            self._handle_constant_annotation(filename, item.annotation, imports_)

                case ast.Assign():
                    pass

                case ast.ClassDef():
                    # _logger.debug('Found Class')
                    self.parse_ast_body(filename, item.body, imports_)

                case ast.Expr():
                    # _logger.debug(f'Found Expr: {type(item.value)}')
                    pass

                case ast.For():
                    pass

                case ast.If():
                    # _logger.debug('Found If')
                    if isinstance(item.test, ast.Name):
                        if item.test.id == 'TYPE_CHECKING':
                            self.parse_ast_body(filename, item.body, imports_, True)

                case ast.Name():
                    pass

                case ast.FunctionDef():
                    # _logger.debug(f'Found function: {item.name}')
                    for arg in item.args.args:
                        # _logger.debug(f'ARG: Name={arg.arg}')
                        match arg.annotation:
                            case ast.Constant():
                                self._handle_constant_annotation(filename, arg.annotation, imports_)

                            case ast.BinOp():
                                # _logger.debug(f'ARG: BinOp -> {arg.annotation.op}')
                                pass

                            case _:
                                # _logger.debug(f'ARG: other type -> {type(arg.annotation)}')
                                pass

                    match item.returns:
                        case ast.Constant():
                            self._handle_constant_annotation(filename, item.returns, imports_)
                            ## # handle Forward Ref
                            ## if item.returns.value in imports_['standard']:
                            ##     # _logger.debug(f'Forward Ref: {item.returns.value}')
                            ##     # _logger.debug(f'{filename}:{item.lineno}')

                        case ast.Name():
                            # _logger.debug(f'Found Return: {item.returns.id}')
                            pass

                    # parse nested data
                    self.parse_ast_body(filename, item.body, imports_, True)

                case ast.Try():
                    pass

                case ast.Return():
                    pass

                case ast.While():
                    pass

                # case _:
                #     _logger.debug(f'Unknown Type: {type(item)}')

    def run_update_code(self, filename: Path):
        """Run replace code logic."""
        file_changed = False
        new_file = []
        for line_no, line in enumerate(filename.open(mode='r', encoding='utf-8'), start=1):
            line = line.rstrip('\n')

            for pattern, data in self._code_replacements.items():
                match_pattern = re.compile(pattern)
                match_data = list(match_pattern.finditer(line))
                in_file = data.get('in_file') or []
                if match_data and (not in_file or filename.name in in_file):
                    match_data = list(match_data)[0]
                    new_line = re.sub(pattern, data['replacement'], line)

                    Render.table.key_value(
                        'Replace Code',
                        {
                            'File Link': f'{filename}:{line_no}:{match_data.start() + 1}',
                            'Current Line': f'{line}',
                            'New Line': f'{new_line}',
                        },
                    )
                    response = Render.prompt.input(
                        'Replace line:',
                        prompt_default=f' (Default: [{self.accent}]yes[/{self.accent}])',
                    )
                    if response in ('', 'y', 'yes'):
                        line = re.sub(pattern, data['replacement'], line)
                        file_changed = True

            new_file.append(line)

        if file_changed is True:
            with filename.open(mode='w', encoding='utf-8') as fh:
                fh.write('\n'.join(new_file) + '\n')

    def walk_code(self):
        """."""
        for item in Path.cwd().rglob('*.py'):
            # skip directories
            parents = item.relative_to(Path.cwd()).parents
            if len(parents) > 1:
                parent_name = parents[-2].name
                if parent_name in self._skip_directories:
                    continue

            # skip files
            if item.name in self._skip_files:
                continue

            Render.panel.info(f'FILE: {item}')

            # run simple regex replacements
            if self.update_code is True:
                self.run_update_code(item)

            if self.forward_ref is True:
                with item.open(mode='r', encoding='utf-8') as fh:
                    code = fh.read()

                imports = {
                    'standard': [],
                    'typing': [],
                }
                parsed_code = ast.parse(code)
                self.parse_ast_body(item, parsed_code.body, imports)
