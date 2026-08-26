"""Tests for TemplateCli._build_merged_template using real fixture data.

Verifies parent-child merging, file exclusions, gitignore rename,
and manifest generation against the actual tcex-app-templates v2 branch.
"""

# standard library
import json
import re
import shutil
from pathlib import Path

# third-party
import pytest

# first-party
from tcex_cli.cli.template.planner import Hasher
from tcex_cli.cli.template.template_cli import TemplateCli


@pytest.fixture
def merged_playbook(template_cli: TemplateCli) -> Path:
    cache_dir = template_cli._cache_dir('v2')
    merged = template_cli._build_merged_template(cache_dir, 'basic', 'playbook')
    yield merged
    shutil.rmtree(merged, ignore_errors=True)


@pytest.fixture
def merged_organization(template_cli: TemplateCli) -> Path:
    cache_dir = template_cli._cache_dir('v2')
    merged = template_cli._build_merged_template(cache_dir, 'basic', 'organization')
    yield merged
    shutil.rmtree(merged, ignore_errors=True)


@pytest.fixture
def merged_egress(template_cli: TemplateCli) -> Path:
    cache_dir = template_cli._cache_dir('v2')
    merged = template_cli._build_merged_template(cache_dir, 'egress', 'organization')
    yield merged
    shutil.rmtree(merged, ignore_errors=True)


class ManifestHelper:
    @staticmethod
    def load(merged_dir: Path) -> dict:
        return json.loads((merged_dir / 'manifest.json').read_text())

    @staticmethod
    def actual_files(merged_dir: Path) -> set[str]:
        return {
            str(f.relative_to(merged_dir))
            for f in merged_dir.rglob('*')
            if f.is_file() and f.name != 'manifest.json'
        }


class TestBuildMergedPlaybook:
    """Merge playbook/basic (parent: _app_common) using real fixture data."""

    def test_child_files_present(self, merged_playbook: Path):
        """playbook/basic files (app.py, playbook_app.py, etc.) should appear."""
        assert (merged_playbook / 'app.py').is_file()
        assert (merged_playbook / 'playbook_app.py').is_file()
        assert (merged_playbook / 'install.json').is_file()
        assert (merged_playbook / 'run.py').is_file()
        # tcex.json is skipped during merge (handled separately by _ensure_tcex_json)
        assert not (merged_playbook / 'tcex.json').exists()

    def test_parent_files_inherited(self, merged_playbook: Path):
        """_app_common files (requirements.txt, pyproject.toml, etc.) should be inherited."""
        assert (merged_playbook / 'requirements.txt').is_file()
        assert (merged_playbook / 'pyproject.toml').is_file()
        assert (merged_playbook / '.coveragerc').is_file()

    def test_child_overwrites_parent_file(self, template_cli: TemplateCli, merged_playbook: Path):
        cache_dir = template_cli._cache_dir('v2')
        merged_content = (merged_playbook / 'README.md').read_text()
        child_content = (cache_dir / 'playbook' / 'basic' / 'README.md').read_text()
        parent_content = (cache_dir / '_app_common' / 'README.md').read_text()

        assert merged_content == child_content
        assert merged_content != parent_content

    def test_template_yaml_excluded(self, merged_playbook: Path):
        """template.yaml should never be in the merged output."""
        assert not (merged_playbook / 'template.yaml').exists()

    def test_gitignore_renamed_from_gitignore(self, merged_playbook: Path):
        """_app_common has a `gitignore` file — it should become `.gitignore`."""
        assert (merged_playbook / '.gitignore').is_file()
        assert not (merged_playbook / 'gitignore').exists()
        content = (merged_playbook / '.gitignore').read_text()
        assert len(content) > 0

    def test_manifest_json_generated(self, merged_playbook: Path):
        """A manifest.json should be generated even when upstream has none."""
        manifest_path = merged_playbook / 'manifest.json'
        assert manifest_path.is_file()

        manifest = ManifestHelper.load(merged_playbook)
        assert 'app.py' in manifest
        assert 'playbook_app.py' in manifest
        assert 'requirements.txt' in manifest
        assert '.gitignore' in manifest
        assert '.coveragerc' in manifest

        for key, entry in manifest.items():
            assert 'sha256' in entry, f'{key} missing sha256'
            assert 'template_path' in entry, f'{key} missing template_path'
            assert 'last_commit' in entry, f'{key} missing last_commit'

    def test_manifest_entry_count_matches_files(self, merged_playbook: Path):
        manifest = ManifestHelper.load(merged_playbook)
        actual = ManifestHelper.actual_files(merged_playbook)

        assert set(manifest.keys()) == actual, (
            f'Manifest/file mismatch:\n'
            f'  In manifest only: {set(manifest.keys()) - actual}\n'
            f'  On disk only: {actual - set(manifest.keys())}'
        )

    def test_manifest_sha256_values_are_valid_hex(self, merged_playbook: Path):
        manifest = ManifestHelper.load(merged_playbook)
        sha256_pattern = re.compile(r'^[0-9a-f]{64}$')
        git_sha_pattern = re.compile(r'^[0-9a-f]{40}$')

        for key, entry in manifest.items():
            assert sha256_pattern.match(entry['sha256']), (
                f'{key}: sha256 is not valid hex: {entry["sha256"]!r}'
            )
            assert git_sha_pattern.match(entry['last_commit']), (
                f'{key}: last_commit is not a valid git SHA: {entry["last_commit"]!r}'
            )

    def test_manifest_sha256_matches_actual_file_hash(self, merged_playbook: Path):
        manifest = ManifestHelper.load(merged_playbook)
        hasher = Hasher()

        for key, entry in manifest.items():
            actual = hasher.sha256_file(merged_playbook / key)
            assert actual == entry['sha256'], (
                f'{key}: manifest sha256 {entry["sha256"]} != actual {actual}'
            )

    def test_appbuilderconfig_excluded_by_default(self, merged_playbook: Path):
        """.appbuilderconfig should not appear when app_builder=False."""
        assert not (merged_playbook / '.appbuilderconfig').exists()


class TestBuildMergedOrganization:
    """Merge organization/basic (parent: _app_common) using real fixture data."""

    def test_org_specific_files_present(self, merged_organization: Path):
        """organization/basic should have job_app.py, not playbook_app.py."""
        assert (merged_organization / 'job_app.py').is_file()
        assert (merged_organization / 'app.py').is_file()
        assert not (merged_organization / 'playbook_app.py').exists()

    def test_inherits_app_common(self, merged_organization: Path):
        """Should inherit _app_common files like requirements.txt."""
        assert (merged_organization / 'requirements.txt').is_file()
        assert (merged_organization / 'pyproject.toml').is_file()
        assert (merged_organization / '.gitignore').is_file()


class TestBuildMergedThreeLevelChain:
    def test_egress_has_files_from_all_levels(self, merged_egress: Path):
        assert (merged_egress / 'requirements.txt').is_file()
        assert (merged_egress / 'pyproject.toml').is_file()
        assert (merged_egress / 'job_app.py').is_file()
        assert (merged_egress / 'app.py').is_file()

    def test_manifest_covers_all_files(self, merged_egress: Path):
        manifest = ManifestHelper.load(merged_egress)

        assert 'requirements.txt' in manifest
        assert 'job_app.py' in manifest
        assert 'app.py' in manifest
        assert '.gitignore' in manifest

    def test_manifest_entry_count_matches_files(self, merged_egress: Path):
        manifest = ManifestHelper.load(merged_egress)
        actual = ManifestHelper.actual_files(merged_egress)
        assert set(manifest.keys()) == actual
