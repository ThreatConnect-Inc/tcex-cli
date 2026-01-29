"""tcex_cli CLI Template TCV Helper Module"""

# standard library
import contextlib
import hashlib
import json
import shutil
import zipfile
from collections.abc import Callable
from pathlib import Path
from typing import TypedDict

# third-party
from pydantic import BaseModel, Field

# first-party
from tcex_cli.render.render import Render


# =========================
# Shared Types / Data Models
# =========================
class FileMeta(TypedDict):
    """Metadata for a single file in the manifest."""

    last_commit: str
    sha256: str
    template_path: str


Meta = dict[str, FileMeta]  # key: POSIX-style path


class Plan(BaseModel):
    """Update plan for template files."""

    skip: list[tuple] = Field(default=[], description='Files that are unchanged.')
    auto_update: list[tuple] = Field(
        default=[], description='Files that will be updated automatically.'
    )
    prompt_user: list[tuple] = Field(
        default=[], description='Files that require user confirmation.'
    )
    template_new: list[tuple] = Field(default=[], description='New files in the template.')
    template_removed: list[tuple] = Field(
        default=[], description='Files removed from the template.'
    )

    @property
    def summary(self) -> dict[str, str]:
        """Return a summary of the plan as a dict suitable for Render.table.key_value."""
        return {
            'Skip': str(len(self.skip)),
            'Auto Update': str(len(self.auto_update)),
            'Prompt User': str(len(self.prompt_user)),
            'Template New': str(len(self.template_new)),
            'Template Removed': str(len(self.template_removed)),
        }

    @property
    def details(self) -> dict:
        """Return detailed plan information as a dictionary."""
        return {
            'skip': self.skip,
            'auto_update': self.auto_update,
            'prompt_user': self.prompt_user,
            'template_new': self.template_new,
            'template_removed': self.template_removed,
        }


class Hasher:
    """Stable SHA-256 hashing for files."""

    @staticmethod
    def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str | None:
        """Return the SHA-256 hash of a file, or None if the file does not exist."""
        if not path.exists():
            return None
        h = hashlib.sha256()
        with path.open('rb') as f:
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                h.update(chunk)
        return h.hexdigest()


class ManifestStore:
    """Load JSON manifest files and compute key sets."""

    @staticmethod
    def load_json(path: Path) -> Meta:
        """Load manifest JSON from path."""
        if not path.exists():
            return {}
        with path.open('r', encoding='utf-8') as f:
            data = json.load(f)
        if not isinstance(data, dict):
            ex_msg = f'Expected object at top-level in {path}'
            raise TypeError(ex_msg)
        return data  # type: ignore[return-value]

    @staticmethod
    def collect_keys(template_meta: Meta, main_meta: Meta) -> tuple[list[str], list[str]]:
        """Return (keys_in_template, removed_in_template)."""
        template_keys = set(template_meta.keys())
        main_keys = set(main_meta.keys())
        return sorted(template_keys), sorted(main_keys - template_keys)


# =========================
# Repository: Download / Extract
# =========================
class TemplateRepository:
    """Download/extract the template zipball into a destination directory."""

    def __init__(self, template_cli):
        """Initialize TemplateRepository with TemplateCli instance."""
        self.template_cli = template_cli  # expects .session, .base_url, .log

    def dir_metadata_url(self, branch: str) -> str:
        """Return the URL to download the zipball for the given branch."""
        # URL pattern: https://api.github.com/repos/{org}/{repo}/zipball/{branch}
        return f'{self.template_cli.base_url}/zipball/{branch}'

    def download_directory(self, branch: str, dest: Path) -> None:
        """Download and extract the template directory for the given branch into dest."""
        url = self.dir_metadata_url(branch)
        dest_zip = Path('template.zip')
        dest_zip.parent.mkdir(parents=True, exist_ok=True)

        # Stream download
        with self.template_cli.session.get(url, stream=True) as r:
            r.raise_for_status()
            with Path.open(dest_zip, 'wb') as fh:
                for chunk in r.iter_content(chunk_size=1024 * 1024):
                    if chunk:  # filter out keep-alive chunks
                        fh.write(chunk)

        # Unzip + flatten top-level directory (GitHub zipballs)
        try:
            with zipfile.ZipFile(dest_zip, 'r') as zf:
                names = zf.namelist()
                if not names:
                    return
                top_prefix = names[0].split('/', 1)[0]
                zf.extractall(dest)

            top_dir = dest / top_prefix
            if top_dir.exists() and top_dir.is_dir():
                for child in top_dir.iterdir():
                    target = dest / child.name
                    if target.exists():
                        if target.is_dir():
                            shutil.rmtree(target)
                        else:
                            target.unlink()
                    shutil.move(str(child), str(target))
                shutil.rmtree(top_dir)
        finally:
            dest_zip.unlink(missing_ok=True)


# =========================
# File Operations (copy/remove) — preserves modes + behavior
# =========================
class SafeFileOps:
    """Encapsulate local filesystem mutations with same semantics as original."""

    def copy_from_template(self, template_root: Path, key: str, dest: Path) -> None:
        """Copy file from template to dest path, preserving mode when overwriting."""
        src = template_root / key
        if not src.exists():
            ex_msg = f'Template file does not exist: {src}'
            raise FileNotFoundError(ex_msg)
        self.ensure_parent(dest)

        data = src.read_bytes()
        if dest.exists():
            # preserve current file mode
            mode = dest.stat().st_mode
            dest.write_bytes(data)  # in-place overwrite (same path)
            dest.chmod(mode)
        else:
            dest.write_bytes(data)
            with contextlib.suppress(Exception):
                shutil.copymode(src, dest)  # copy execute bit, etc.

    @staticmethod
    def ensure_parent(path: Path) -> None:
        """Ensure parent directory exists for path."""
        path.parent.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def remove_file(path: Path) -> None:
        """Remove file at path if it exists."""
        if path.exists():
            path.unlink()

    @staticmethod
    def copy_tree_or_file(src: Path, target: Path) -> None:
        """Copy a file or directory from src to target."""
        if src.is_dir():
            shutil.copytree(src, target)
        else:
            shutil.copy2(src, target)


class Planner:
    """Planner for template updates."""

    def __init__(
        self,
        manifest: ManifestStore,
        hasher: Hasher,
        file_ops: SafeFileOps,
    ):
        """Initialize Planner with dependencies."""
        self.manifest = manifest
        self.hasher = hasher
        self.file_ops = file_ops

    def build(
        self, temp_dest: Path, dest: Path, file_name: str = 'manifest.json', force=False
    ) -> Plan:
        """Build an update plan by comparing template and main manifests.

        Syncing logic:
        1. Load both the remote template manifest and the local project manifest.
        2. Determine which file keys exist in the template and which were removed.
        3. For each key still in the template:
           - If ``force`` is set, auto-update unconditionally.
           - If the key is absent from the local manifest, it is a new file. Auto-update
             when the file doesn't exist on disk yet; prompt the user if it already exists
             (to avoid silently overwriting local work).
           - If both manifests share the same ``last_commit``, the file is unchanged — skip.
           - Otherwise, hash the local file and compare:
             * If the hash already matches the new template or the file is missing, skip
               (the user already has the latest content or deliberately deleted it).
             * If the file lives under ``core/`` or ``ui/``, auto-update (these dirs are
               considered framework-managed).
             * All other modified files require user confirmation before overwriting.
        4. For each key removed from the template:
           - If the local file is already gone or unchanged from the last-known hash,
             auto-remove (safe cleanup).
           - If the user has modified the file, prompt before removing.
        """
        template_meta = self.manifest.load_json(temp_dest / file_name)
        local_meta = self.manifest.load_json(dest / file_name)

        plan = Plan()

        keys_in_template, removed_in_template = self.manifest.collect_keys(
            template_meta, local_meta
        )

        # Updates / Adds
        for key in keys_in_template:
            template_info = template_meta[key]
            local_info = local_meta.get(key)
            value = (key, template_info['template_path'])

            project_path = dest / key

            if force is True:
                plan.auto_update.append(value)
                continue

            # New file being tracked in the template
            if local_info is None:
                plan.template_new.append(value)
                if project_path.exists():
                    plan.prompt_user.append(value)
                else:
                    plan.auto_update.append(value)
                continue

            # Both sides have metadata and neither have changed
            if template_info['last_commit'] == local_info['last_commit']:
                plan.skip.append(value)
                continue

            # File was changed so that it matches the latest_changes or the file was removed.
            current_hash = self.hasher.sha256_file(project_path)
            if current_hash == template_info['sha256'] or current_hash is None:
                plan.skip.append(value)
            # auto update all files tracked in the core or ui dirs
            elif key.startswith(('core/', 'ui/')):
                plan.auto_update.append(value)
            else:
                plan.prompt_user.append(value)

        # Removals
        for key in removed_in_template:
            local_info = local_meta[key]
            value = (key, local_info['template_path'])
            plan.template_removed.append(value)

            current_hash = self.hasher.sha256_file(dest / key)

            if current_hash is None:
                plan.auto_update.append(value)  # already gone; no-op
            elif current_hash == local_info['sha256']:
                plan.auto_update.append(value)  # unchanged; auto-remove
            else:
                plan.prompt_user.append(value)  # changed; confirm removal
        return plan

    def apply(
        self,
        plan: Plan,
        *,
        template_root: Path,
        project_root: Path,
        force: bool = False,
        prompt_fn: Callable[[str], str] = input,  # dependency injection for tests
    ) -> None:
        """Apply the plan. If `force` is False, items in prompt_user will ask for confirmation."""
        auto_set = set(plan.auto_update)
        prompt_set = set(plan.prompt_user)
        removed_keys = {local for local, _template in plan.template_removed}

        # 1) Handle AUTO_UPDATE (copies + removals)
        for local, template in auto_set:
            local_ = project_root / local
            if local in removed_keys:
                self.file_ops.remove_file(local_)
            else:
                self.file_ops.copy_from_template(template_root, template, local_)

        # 2) Handle PROMPT_USER
        if prompt_set and not force:
            for local, template in sorted(prompt_set):
                local_ = project_root / local
                if local in removed_keys:
                    response = (
                        prompt_fn(f"Remove modified file '{local}'? [y/N] (default: N): ")
                        .strip()
                        .lower()
                    )
                    if response == 'y':
                        self.file_ops.remove_file(local_)
                else:
                    response = (
                        prompt_fn(
                            f"Overwrite modified file '{local}' from template? [y/N] (default: N): "
                        )
                        .strip()
                        .lower()
                    )
                    if response == 'y':
                        self.file_ops.copy_from_template(template_root, template, local_)
        elif prompt_set and force:
            # Force means proceed without prompting.
            for local, template in prompt_set:
                local_ = project_root / local
                if local in removed_keys:
                    self.file_ops.remove_file(local_)
                else:
                    self.file_ops.copy_from_template(template_root, template, local_)


class TCVHelper:
    """Helper class for TCV template operations."""

    def __init__(self, template_cli):
        """Initialize TCVHelper with TemplateCli instance."""
        self.template_cli = template_cli
        self.repo = TemplateRepository(template_cli)
        self.hasher = Hasher()
        self.manifest = ManifestStore()
        self.file_ops = SafeFileOps()
        self.planner = Planner(self.manifest, self.hasher, self.file_ops)

    # Behavior-compatible helpers
    def copy_files(self, files_of_interest: list[str] | list[Path], dest: Path) -> None:
        """Copy files of interest to destination."""
        dest = Path(dest)
        dest.mkdir(parents=True, exist_ok=True)
        for p in files_of_interest:
            src = Path(p)
            target = dest / src.name
            self.file_ops.copy_tree_or_file(src, target)

    def _run(
        self,
        branch: str,
        template_name: str,
        template_type: str,
        dest=Path(),
        force=False,
    ):
        template_dest = Path('template')
        try:
            self.repo.download_directory(branch, dest=template_dest)
            temp_dest = template_dest / template_type / template_name
            plan = self.planner.build(temp_dest, dest, force=force)
            Render.table.key_value('Plan Summary', plan.summary)
            temp_dest = template_dest / template_type
            self.planner.apply(plan, template_root=temp_dest, project_root=dest)
        finally:
            shutil.rmtree(template_dest, ignore_errors=True)

    def init(
        self,
        branch: str,
        template_name: str,
        template_type: str,
        dest=Path(),
        force=True,
    ):
        """Init template files in `dest` directory."""
        self._run(branch, template_name, template_type, dest, force)

    def update(
        self,
        branch: str,
        template_name: str,
        template_type: str,
        dest=Path(),
        force=False,
    ):
        """Update existing template files in `dest` directory."""
        self._run(branch, template_name, template_type, dest, force)
