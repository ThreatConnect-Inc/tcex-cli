"""Run App Local"""

from pathlib import Path

from tcex_cli.cli.run.launch_abc import LaunchABC
from tcex_cli.cli.run.model.app_playbook_model import AppPlaybookInputModel
from tcex_cli.cli.run.playbook_create import PlaybookCreate
from tcex_cli.pleb.cached_property import cached_property
from tcex_cli.render.render import Render

# Inputs that DECLARE the App's output variables (the App writes them; it does not read them).
# Their values are lists of ``#App:...!Type`` strings and must NOT be treated as referenced reads,
# so they are never required in ``stage.kvstore``. A set so more output-style inputs can be added.
OUTPUT_VARIABLE_INPUTS = {'tc_playbook_out_variables'}


class LaunchPlaybook(LaunchABC):
    """Launch an App"""

    def __init__(self, config_json: Path, watch_backend: bool = False):
        """Initialize class properties."""
        super().__init__(config_json, watch_backend=watch_backend)
        self.playbook = PlaybookCreate(
            self.redis_client, self.model.inputs.tc_playbook_kvstore_context
        )

    @cached_property
    def model(self) -> AppPlaybookInputModel:
        """Return the App inputs."""
        inputs = self.construct_model_inputs()
        model = AppPlaybookInputModel(**inputs)
        model.stage.kvstore = inputs.get('stage', {}).get('kvstore', {})

        return model

    def _find_app_variables(self, value) -> set[str]:
        """Recursively extract ``#App:`` playbook-variable references from a config input value.

        Only ``#App:`` variables are returned; ``#Global:`` / ``#Trigger:`` references are
        runtime-provided and intentionally excluded.

        Args:
            value: A config input value (str / dict / list / scalar).

        Returns:
            The set of full ``#App:`` variable strings found in the value.
        """
        if isinstance(value, str):
            return {
                match.group(0)
                for match in self.util.variable_playbook_parse.finditer(value)
                if match.group('app_type') == 'App'
            }
        if isinstance(value, dict):
            return set().union(*(self._find_app_variables(v) for v in value.values()))
        if isinstance(value, list):
            return set().union(*(self._find_app_variables(v) for v in value))
        return set()

    def validate_inputs(self):
        """Cross-check ``#App:`` input references against staged ``kvstore`` keys.

        Referenced-but-unstaged variables are a hard error (rendered failure, process exit) raised
        before any Redis I/O. Staged-but-unreferenced keys produce a non-blocking warning.
        """
        config = self.construct_model_inputs()
        inputs = config.get('inputs') or {}
        staged = set((config.get('stage') or {}).get('kvstore', {}))

        # map each input name to the set of #App: variables it references; skip inputs that
        # declare output variables (e.g. tc_playbook_out_variables) since those are writes not reads
        referenced: dict[str, set[str]] = {
            name: vars_
            for name, value in inputs.items()
            if name not in OUTPUT_VARIABLE_INPUTS and (vars_ := self._find_app_variables(value))
        }

        # referenced variables that were never staged
        missing = sorted(
            (name, var)
            for name, vars_ in referenced.items()
            for var in sorted(vars_)
            if var not in staged
        )

        # staged keys that no input references
        all_refs = set().union(*referenced.values()) if referenced else set()
        unused = sorted(staged - all_refs)

        if missing:
            Render.panel.failure(self._missing_inputs_message(missing, staged))
        elif unused:
            unused_list = '\n'.join(f'  - {key}' for key in unused)
            Render.panel.warning(
                f'The following staged kvstore keys are not referenced by any input:\n{unused_list}'
            )

    def _missing_inputs_message(self, missing: list[tuple[str, str]], staged: set[str]) -> str:
        """Build the failure message for referenced-but-unstaged variables.

        Args:
            missing: Sorted (input-name, variable) pairs that are referenced but not staged.
            staged: The set of staged kvstore keys.

        Returns:
            A readable, markup-inert failure message.
        """
        lines = [
            f'Config file [{self.config_json}] references playbook variables that are not staged '
            'in [stage.kvstore]:',
            '',
        ]
        for name, var in missing:
            line = f'  - input [{name}] references [{var}]'
            suggestion = self._suggest_staged_key(var, staged)
            if suggestion is not None:
                line += f' - did you mean [{suggestion}]?'
            lines.append(line)

        lines.append('')
        if staged:
            lines.append('Available staged kvstore keys:')
            lines.extend(f'  - {key}' for key in sorted(staged))
        else:
            lines.append('No kvstore keys are staged.')

        return '\n'.join(lines)

    def _suggest_staged_key(self, variable: str, staged: set[str]) -> str | None:
        """Return a staged key matching the variable's key+type but a different job_id, if any.

        Args:
            variable: The missing (unstaged) variable string.
            staged: The set of staged kvstore keys.

        Returns:
            A best-effort "did you mean" staged key, or None when no match is found.
        """
        model = self.util.get_playbook_variable_model(variable)
        if model is None:
            return None

        for key in sorted(staged):
            staged_model = self.util.get_playbook_variable_model(key)
            if (
                staged_model is not None
                and staged_model.key == model.key
                and staged_model.type == model.type
                and staged_model.job_id != model.job_id
            ):
                return key
        return None

    def stage(self):
        """Stage the variables in redis."""
        # capture the stages keys?
        for key, value in self.model.stage.kvstore.items():
            self.staged_keys.append(key)
            self.playbook.any(key, value)

    def print_output_data(self):
        """Log the playbook output data."""
        output_data = self.live_format_dict(
            self.output_data(self.model.inputs.tc_playbook_kvstore_context)
        ).strip()
        Render.panel.info(f'{output_data}', f'[{self.panel_title}]Output Data[/]')
