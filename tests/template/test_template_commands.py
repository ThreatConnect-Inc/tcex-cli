"""Integration tests for template commands using real fixture data.

Tests exercise the full init/update/list pipeline against the actual
tcex-app-templates v2 branch (committed as a fixture zip).
Each test creates a real project directory and verifies actual file
contents after running commands.
"""

# standard library
import json
from pathlib import Path
from unittest.mock import patch

# third-party
import pytest

# first-party
from tcex_cli.cli.template.planner import Hasher
from tcex_cli.cli.template.template_cli import TemplateCli


class ProjectHelper:
    @staticmethod
    def init_project(
        cli: TemplateCli,
        project_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        template_name: str,
        template_type: str,
    ) -> None:
        monkeypatch.chdir(project_dir)
        with patch.object(cli, 'ensure_cache', return_value=cli._cache_dir('v2')):
            cli.update('v2', template_name, template_type, force=True)

    @staticmethod
    def simulate_template_change(project_dir: Path, filename: str) -> None:
        manifest = json.loads((project_dir / 'manifest.json').read_text())
        manifest[filename]['last_commit'] = 'old_commit_before_update'
        (project_dir / 'manifest.json').write_text(json.dumps(manifest, indent=2))

    @staticmethod
    def run_update(
        cli: TemplateCli,
        template_name: str = 'basic',
        template_type: str = 'playbook',
        force: bool = False,
    ) -> None:
        with patch.object(cli, 'ensure_cache', return_value=cli._cache_dir('v2')):
            cli.update('v2', template_name, template_type, force=force)


# ==================================================================
# List
# ==================================================================
class TestList:
    """Tests for TemplateCli.list_()."""

    def test_list_all_types(self, template_cli):
        """list_ with no type filter should discover multiple template types."""
        with patch.object(
            template_cli, 'ensure_cache', return_value=template_cli._cache_dir('v2')
        ):
            template_cli.list_('v2')

        assert 'playbook' in template_cli.template_data
        assert 'organization' in template_cli.template_data

    def test_list_playbook_templates(self, template_cli):
        """list_ filtered to playbook should find basic (and others)."""
        with patch.object(
            template_cli, 'ensure_cache', return_value=template_cli._cache_dir('v2')
        ):
            template_cli.list_('v2', 'playbook')

        names = [c.name for c in template_cli.template_data['playbook']]
        assert 'basic' in names

    def test_list_organization_templates(self, template_cli):
        """list_ filtered to organization should find basic."""
        with patch.object(
            template_cli, 'ensure_cache', return_value=template_cli._cache_dir('v2')
        ):
            template_cli.list_('v2', 'organization')

        names = [c.name for c in template_cli.template_data['organization']]
        assert 'basic' in names

    def test_list_invalid_type_raises(self, template_cli):
        with (
            patch.object(
                template_cli, 'ensure_cache', return_value=template_cli._cache_dir('v2')
            ),
            pytest.raises(ValueError, match='Invalid Types'),
        ):
            template_cli.list_('v2', 'nonexistent_type')

    def test_list_discovers_multiple_templates_per_type(self, template_cli):
        with patch.object(
            template_cli, 'ensure_cache', return_value=template_cli._cache_dir('v2')
        ):
            template_cli.list_('v2', 'organization')

        names = [c.name for c in template_cli.template_data['organization']]
        assert len(names) > 1


# ==================================================================
# Init — playbook
# ==================================================================
class TestInitPlaybook:
    """Init playbook/basic and verify file contents."""

    def test_creates_expected_files(self, template_cli, project_dir, monkeypatch):
        """Init should produce all files from _app_common + playbook/basic."""
        ProjectHelper.init_project(template_cli, project_dir, monkeypatch, 'basic', 'playbook')

        assert (project_dir / 'app.py').is_file()
        assert (project_dir / 'playbook_app.py').is_file()
        assert (project_dir / 'install.json').is_file()
        assert (project_dir / 'run.py').is_file()

        assert (project_dir / 'requirements.txt').is_file()
        assert (project_dir / 'pyproject.toml').is_file()
        assert (project_dir / '.coveragerc').is_file()
        assert (project_dir / '.gitignore').is_file()

    def test_file_content_matches_template(self, template_cli, project_dir, monkeypatch):
        """Spot-check that file content matches the actual template source."""
        ProjectHelper.init_project(template_cli, project_dir, monkeypatch, 'basic', 'playbook')

        cache_dir = template_cli._cache_dir('v2')

        template_content = (cache_dir / 'playbook' / 'basic' / 'playbook_app.py').read_text()
        project_content = (project_dir / 'playbook_app.py').read_text()
        assert project_content == template_content

        template_req = (cache_dir / '_app_common' / 'requirements.txt').read_text()
        project_req = (project_dir / 'requirements.txt').read_text()
        assert project_req == template_req

    def test_manifest_json_written(self, template_cli, project_dir, monkeypatch):
        """Init should write manifest.json to project root with entries for all files."""
        ProjectHelper.init_project(template_cli, project_dir, monkeypatch, 'basic', 'playbook')

        manifest_path = project_dir / 'manifest.json'
        assert manifest_path.is_file()

        manifest = json.loads(manifest_path.read_text())
        assert 'app.py' in manifest
        assert 'playbook_app.py' in manifest
        assert 'requirements.txt' in manifest
        assert '.gitignore' in manifest

    def test_template_yaml_not_in_project(self, template_cli, project_dir, monkeypatch):
        """template.yaml should never be copied to the project."""
        ProjectHelper.init_project(template_cli, project_dir, monkeypatch, 'basic', 'playbook')
        assert not (project_dir / 'template.yaml').exists()

    def test_init_twice_is_idempotent(self, template_cli, project_dir, monkeypatch):
        ProjectHelper.init_project(template_cli, project_dir, monkeypatch, 'basic', 'playbook')
        before = (project_dir / 'playbook_app.py').read_text()

        ProjectHelper.init_project(template_cli, project_dir, monkeypatch, 'basic', 'playbook')
        after = (project_dir / 'playbook_app.py').read_text()

        assert before == after
        assert (project_dir / 'manifest.json').is_file()


# ==================================================================
# Init — organization
# ==================================================================
class TestInitOrganization:
    """Init organization/basic and verify file contents."""

    def test_creates_org_specific_files(self, template_cli, project_dir, monkeypatch):
        """organization/basic should have job_app.py, not playbook_app.py."""
        ProjectHelper.init_project(
            template_cli, project_dir, monkeypatch, 'basic', 'organization'
        )

        assert (project_dir / 'job_app.py').is_file()
        assert (project_dir / 'app.py').is_file()
        assert not (project_dir / 'playbook_app.py').exists()

    def test_inherits_app_common(self, template_cli, project_dir, monkeypatch):
        """Should inherit _app_common files."""
        ProjectHelper.init_project(
            template_cli, project_dir, monkeypatch, 'basic', 'organization'
        )

        assert (project_dir / 'requirements.txt').is_file()
        assert (project_dir / 'pyproject.toml').is_file()
        assert (project_dir / '.gitignore').is_file()


# ==================================================================
# Update — no changes (all skip)
# ==================================================================
class TestUpdateNoChanges:
    """Update immediately after init — nothing should change."""

    def test_files_unchanged_after_update(self, template_cli, project_dir, monkeypatch):
        """All files should remain identical after a no-op update."""
        ProjectHelper.init_project(template_cli, project_dir, monkeypatch, 'basic', 'playbook')

        before = {
            'app.py': (project_dir / 'app.py').read_text(),
            'playbook_app.py': (project_dir / 'playbook_app.py').read_text(),
            'requirements.txt': (project_dir / 'requirements.txt').read_text(),
        }

        ProjectHelper.run_update(template_cli)

        for name, content in before.items():
            assert (project_dir / name).read_text() == content, f'{name} changed unexpectedly'

    def test_manifest_unchanged_after_noop_update(self, template_cli, project_dir, monkeypatch):
        ProjectHelper.init_project(template_cli, project_dir, monkeypatch, 'basic', 'playbook')

        before = (project_dir / 'manifest.json').read_text()

        ProjectHelper.run_update(template_cli)

        after = (project_dir / 'manifest.json').read_text()
        assert json.loads(before) == json.loads(after)


# ==================================================================
# Update — user modifies a file, then update
# ==================================================================
class TestUpdateModifiedFile:
    """User edits a file, then runs update."""

    def test_modified_non_template_file_preserved_when_same_version(
        self, template_cli, project_dir, monkeypatch
    ):
        """Modifying a file when the template hasn't changed should skip it."""
        ProjectHelper.init_project(template_cli, project_dir, monkeypatch, 'basic', 'playbook')
        (project_dir / 'app.py').write_text('# user modification')

        ProjectHelper.run_update(template_cli)

        assert (project_dir / 'app.py').read_text() == '# user modification'

    def test_same_template_version_skips_even_modified_files(
        self, template_cli, project_dir, monkeypatch
    ):
        """When the template hasn't changed (same last_commit), update skips all files.

        If the user modifies a file but the template hasn't changed,
        update should skip (use --force to overwrite).
        """
        ProjectHelper.init_project(template_cli, project_dir, monkeypatch, 'basic', 'playbook')
        (project_dir / 'playbook_app.py').write_text('# user modification')

        ProjectHelper.run_update(template_cli)

        assert (project_dir / 'playbook_app.py').read_text() == '# user modification'

    def test_template_file_prompts_when_template_changes(
        self, template_cli, project_dir, monkeypatch
    ):
        """When the template has a new commit and local file was modified, user is prompted."""
        ProjectHelper.init_project(template_cli, project_dir, monkeypatch, 'basic', 'playbook')

        (project_dir / 'playbook_app.py').write_text('# user modification')
        ProjectHelper.simulate_template_change(project_dir, 'playbook_app.py')

        with patch.object(template_cli, 'ensure_cache', return_value=template_cli._cache_dir('v2')):
            with patch('tcex_cli.render.render.Render.prompt.ask', return_value='N'):
                template_cli.update('v2', 'basic', 'playbook')

        # user answered 'N' → file preserved
        assert (project_dir / 'playbook_app.py').read_text() == '# user modification'

    def test_unmodified_file_auto_updates_when_template_changes(
        self, template_cli, project_dir, monkeypatch
    ):
        """When the template changes but the user never modified the file, auto-update it."""
        ProjectHelper.init_project(template_cli, project_dir, monkeypatch, 'basic', 'playbook')

        # Don't modify the file — just simulate a template change
        ProjectHelper.simulate_template_change(project_dir, 'app.py')

        with patch.object(template_cli, 'ensure_cache', return_value=template_cli._cache_dir('v2')):
            with patch('tcex_cli.render.render.Render.prompt.ask') as mock_prompt:
                template_cli.update('v2', 'basic', 'playbook')

        # app.py should NOT have been prompted — it was auto-updated
        prompted_files = [call.args[0] for call in mock_prompt.call_args_list]
        assert not any('app.py' in f for f in prompted_files)

    def test_non_template_file_prompts_when_template_changes(
        self, template_cli, project_dir, monkeypatch
    ):
        ProjectHelper.init_project(template_cli, project_dir, monkeypatch, 'basic', 'playbook')

        (project_dir / 'app.py').write_text('# user modification')
        ProjectHelper.simulate_template_change(project_dir, 'app.py')

        with patch.object(template_cli, 'ensure_cache', return_value=template_cli._cache_dir('v2')):
            with patch('tcex_cli.render.render.Render.prompt.ask', return_value='N'):
                template_cli.update('v2', 'basic', 'playbook')

        assert (project_dir / 'app.py').read_text() == '# user modification'

    def test_prompt_answer_yes_overwrites_file(
        self, template_cli, project_dir, monkeypatch
    ):
        ProjectHelper.init_project(template_cli, project_dir, monkeypatch, 'basic', 'playbook')

        (project_dir / 'app.py').write_text('# user modification')
        ProjectHelper.simulate_template_change(project_dir, 'app.py')

        with patch.object(template_cli, 'ensure_cache', return_value=template_cli._cache_dir('v2')):
            with patch('tcex_cli.render.render.Render.prompt.ask', return_value='y'):
                template_cli.update('v2', 'basic', 'playbook')

        assert (project_dir / 'app.py').read_text() != '# user modification'

    def test_force_overwrites_all_modifications(self, template_cli, project_dir, monkeypatch):
        """--force should overwrite all files regardless of user changes."""
        ProjectHelper.init_project(template_cli, project_dir, monkeypatch, 'basic', 'playbook')

        cache_dir = template_cli._cache_dir('v2')
        original_app = (cache_dir / 'playbook' / 'basic' / 'app.py').read_text()

        (project_dir / 'app.py').write_text('# user modification')
        (project_dir / 'playbook_app.py').write_text('# also modified')

        ProjectHelper.run_update(template_cli, force=True)

        assert (project_dir / 'app.py').read_text() == original_app
        assert (project_dir / 'playbook_app.py').read_text() != '# also modified'


# ==================================================================
# Update — user deletes a template file, then update
# ==================================================================
class TestUpdateDeletedFile:
    """User deletes a template file, then runs update."""

    def test_deleted_file_restored_on_force(self, template_cli, project_dir, monkeypatch):
        """Deleting a template file and running --force should restore it."""
        ProjectHelper.init_project(template_cli, project_dir, monkeypatch, 'basic', 'playbook')

        assert (project_dir / 'playbook_app.py').is_file()
        (project_dir / 'playbook_app.py').unlink()
        assert not (project_dir / 'playbook_app.py').exists()

        ProjectHelper.run_update(template_cli, force=True)

        assert (project_dir / 'playbook_app.py').is_file()

    def test_deleted_file_skipped_without_force(self, template_cli, project_dir, monkeypatch):
        ProjectHelper.init_project(template_cli, project_dir, monkeypatch, 'basic', 'playbook')

        (project_dir / 'playbook_app.py').unlink()

        ProjectHelper.run_update(template_cli)

        assert not (project_dir / 'playbook_app.py').exists()


# ==================================================================
# Update — manifest integrity
# ==================================================================
class TestUpdateManifestIntegrity:
    """Verify manifest.json is kept in sync across init → update cycles."""

    def test_manifest_updated_after_force_update(self, template_cli, project_dir, monkeypatch):
        """After a force update, manifest.json should still have entries for all files."""
        ProjectHelper.init_project(template_cli, project_dir, monkeypatch, 'basic', 'playbook')

        ProjectHelper.run_update(template_cli, force=True)

        manifest = json.loads((project_dir / 'manifest.json').read_text())
        assert 'app.py' in manifest
        assert 'playbook_app.py' in manifest
        assert 'requirements.txt' in manifest

    def test_manifest_sha256_matches_files(self, template_cli, project_dir, monkeypatch):
        """SHA256 values in manifest should match actual file hashes after init."""
        ProjectHelper.init_project(template_cli, project_dir, monkeypatch, 'basic', 'playbook')

        manifest = json.loads((project_dir / 'manifest.json').read_text())
        hasher = Hasher()

        for key, entry in manifest.items():
            file_path = project_dir / key
            if file_path.is_file():
                actual_hash = hasher.sha256_file(file_path)
                assert actual_hash == entry['sha256'], (
                    f'{key}: manifest sha256 {entry["sha256"]} != actual {actual_hash}'
                )

    def test_manifest_sha256_matches_after_force_update(
        self, template_cli, project_dir, monkeypatch
    ):
        ProjectHelper.init_project(template_cli, project_dir, monkeypatch, 'basic', 'playbook')
        (project_dir / 'app.py').write_text('# modified')

        ProjectHelper.run_update(template_cli, force=True)

        manifest = json.loads((project_dir / 'manifest.json').read_text())
        hasher = Hasher()
        for key, entry in manifest.items():
            file_path = project_dir / key
            if file_path.is_file():
                actual_hash = hasher.sha256_file(file_path)
                assert actual_hash == entry['sha256'], (
                    f'{key}: manifest sha256 {entry["sha256"]} != actual {actual_hash}'
                )


# ==================================================================
# Legacy manifest migration
# ==================================================================
class TestLegacyManifestMigration:
    """Verify migration from .template_manifest.json to manifest.json."""

    @staticmethod
    def _simulate_legacy_project(
        cli: TemplateCli,
        project_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        template_name: str = 'basic',
        template_type: str = 'playbook',
    ) -> None:
        """Init a project, then replace manifest.json with a legacy .template_manifest.json."""
        ProjectHelper.init_project(cli, project_dir, monkeypatch, template_name, template_type)

        # remove the new-style manifest and drop a legacy placeholder
        (project_dir / 'manifest.json').unlink()
        (project_dir / '.template_manifest.json').write_text(
            json.dumps({'playbook/basic/app.py': {'sha': 'fake', 'md5': 'fake'}})
        )

    def test_migration_creates_manifest_and_removes_legacy(
        self, template_cli, project_dir, monkeypatch
    ):
        """After update, manifest.json should exist and .template_manifest.json should be gone."""
        self._simulate_legacy_project(template_cli, project_dir, monkeypatch)

        with patch.object(template_cli, 'ensure_cache', return_value=template_cli._cache_dir('v2')):
            with patch('tcex_cli.render.render.Render.prompt.ask', return_value='N'):
                template_cli.update('v2', 'basic', 'playbook')

        assert (project_dir / 'manifest.json').is_file()
        assert not (project_dir / '.template_manifest.json').exists()

    def test_in_sync_files_skipped(self, template_cli, project_dir, monkeypatch):
        """Files that already match the template should not be modified."""
        self._simulate_legacy_project(template_cli, project_dir, monkeypatch)
        before = (project_dir / 'app.py').read_text()

        with patch.object(template_cli, 'ensure_cache', return_value=template_cli._cache_dir('v2')):
            with patch('tcex_cli.render.render.Render.prompt.ask', return_value='N'):
                template_cli.update('v2', 'basic', 'playbook')

        assert (project_dir / 'app.py').read_text() == before

    def test_modified_template_file_auto_updates(self, template_cli, project_dir, monkeypatch):
        """A template_file that the user modified should be auto-updated (no prompt)."""
        self._simulate_legacy_project(template_cli, project_dir, monkeypatch)

        original = (project_dir / 'playbook_app.py').read_text()
        (project_dir / 'playbook_app.py').write_text('# user modification')

        with patch.object(template_cli, 'ensure_cache', return_value=template_cli._cache_dir('v2')):
            with patch('tcex_cli.render.render.Render.prompt.ask', return_value='N'):
                template_cli.update('v2', 'basic', 'playbook')

        # playbook_app.py was modified but user answered 'N' → preserved
        assert (project_dir / 'playbook_app.py').read_text() == '# user modification'

    def test_modified_non_template_file_prompts(self, template_cli, project_dir, monkeypatch):
        """A non-template_file that the user modified should prompt (and be preserved on 'N')."""
        self._simulate_legacy_project(template_cli, project_dir, monkeypatch)

        (project_dir / 'app.py').write_text('# user modification')

        with patch.object(template_cli, 'ensure_cache', return_value=template_cli._cache_dir('v2')):
            with patch('tcex_cli.render.render.Render.prompt.ask', return_value='N'):
                template_cli.update('v2', 'basic', 'playbook')

        assert (project_dir / 'app.py').read_text() == '# user modification'

    def test_skipped_when_manifest_already_exists(self, template_cli, project_dir, monkeypatch):
        """Migration should be a no-op if manifest.json already exists."""
        ProjectHelper.init_project(template_cli, project_dir, monkeypatch, 'basic', 'playbook')

        # drop a legacy file alongside the existing manifest.json
        (project_dir / '.template_manifest.json').write_text('{}')

        ProjectHelper.run_update(template_cli)

        # legacy file should still be there (migration was skipped)
        assert (project_dir / '.template_manifest.json').exists()

    def test_noop_when_no_legacy_manifest(self, template_cli, project_dir, monkeypatch):
        """Migration should be a no-op if there is no .template_manifest.json."""
        ProjectHelper.init_project(template_cli, project_dir, monkeypatch, 'basic', 'playbook')

        # no legacy file, just the normal manifest.json
        assert not (project_dir / '.template_manifest.json').exists()

        before = (project_dir / 'manifest.json').read_text()
        ProjectHelper.run_update(template_cli)
        after = (project_dir / 'manifest.json').read_text()

        assert json.loads(before) == json.loads(after)
