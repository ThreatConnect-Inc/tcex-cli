"""TcEx Framework Module"""

import contextlib
import json
import os
import shutil
import tempfile
import zipfile
from datetime import UTC, datetime
from pathlib import Path

import yaml
from pydantic import ValidationError
from requests import Session
from requests.auth import HTTPBasicAuth

from tcex_cli.cli.cli_abc import CliABC
from tcex_cli.cli.template.model.template_config_model import TemplateConfigModel
from tcex_cli.cli.template.planner import Hasher, ManifestStore, Planner, SafeFileOps
from tcex_cli.pleb.cached_property import cached_property
from tcex_cli.pleb.proxies import proxies
from tcex_cli.render.render import Render


class TemplateCli(CliABC):
    """CLI for initializing, listing, and updating template files.

    Manages a local cache of the tcex-app-templates GitHub repository,
    resolves template inheritance chains (e.g., _app_common -> basic -> egress),
    and uses the Planner to compute and apply file-level diffs between the
    template and a user's project.

    Templates are cached locally at ``~/.tcex/templates/templates-{branch}``.
    Cache freshness is checked via a single GitHub API call per session,
    comparing the remote branch's latest commit date against the local
    cache directory's filesystem mtime.
    """

    # ==================================================================
    # Construction & Properties
    # ==================================================================

    def __init__(
        self,
        proxy_host,
        proxy_port,
        proxy_user,
        proxy_pass,
        authenticate: bool = False,
    ):
        """Initialize instance properties.

        Sets up GitHub API configuration, proxy settings, and the
        planner pipeline (Hasher -> ManifestStore -> Planner).
        """
        super().__init__()

        # gate GitHub auth behind an explicit --authenticate flag
        self.authenticate = authenticate

        # GitHub API configuration
        # Override with TCEX_TEMPLATE_GITHUB_USER env var to use a personal fork
        _default_github_user = 'ThreatConnect-Inc'
        _github_user = os.getenv('TCEX_TEMPLATE_GITHUB_USER', _default_github_user)
        self.accent = 'dark_orange'
        self.base_url = f'https://api.github.com/repos/{_github_user}/tcex-app-templates'
        # raw.githubusercontent.com serves file content at an arbitrary ref. It is a
        # separate host from the REST API and does NOT consume the api.github.com
        # rate limit, so per-file base lookups here are effectively free.
        self.raw_url = f'https://raw.githubusercontent.com/{_github_user}/tcex-app-templates'
        self.errors = False

        # optional GitHub auth (for private forks or to avoid rate limits)
        self.gh_password = os.getenv('GITHUB_PAT')
        self.gh_username = os.getenv('GITHUB_USER')

        # proxy settings (processed by CliABC helpers)
        self.proxy_host = self._process_proxy_host(proxy_host)
        self.proxy_port = self._process_proxy_port(proxy_port)
        self.proxy_user = self._process_proxy_user(proxy_user)
        self.proxy_pass = self._process_proxy_pass(proxy_pass)

        # planner pipeline
        self.hasher = Hasher()
        self.manifest_store = ManifestStore()
        self.file_ops = SafeFileOps()
        self.planner = Planner(self.manifest_store, self.hasher, self.file_ops)

        # populated by list_()
        self.template_data: dict[str, list[TemplateConfigModel]] = {}

        # log non-default GitHub user
        if _github_user != _default_github_user:
            Render.panel.info(f'Using GitHub user: [{self.accent}]{_github_user}')

    @cached_property
    def session(self) -> Session:
        """Return a requests Session configured with proxy and optional auth.

        Auth is only needed for private forks of tcex-app-templates.
        The default public repo works without auth, but GitHub's
        unauthenticated rate limit is 60 requests/hour.
        """
        session = Session()
        session.headers.update({'Cache-Control': 'no-cache'})
        session.proxies = proxies(
            proxy_host=self.proxy_host,
            proxy_port=self.proxy_port,
            proxy_user=self.proxy_user,
            proxy_pass=self.proxy_pass,
        )

        if self.authenticate:
            if self.gh_username is not None and self.gh_password is not None:
                session.auth = HTTPBasicAuth(self.gh_username, self.gh_password)
            else:
                Render.panel.warning(
                    'GitHub authentication was requested (--authenticate) but the '
                    'GITHUB_USER and/or GITHUB_PAT environment variables are not set. '
                    'Continuing with unauthenticated requests (60 requests/hour limit).'
                )

        return session

    @property
    def template_types(self) -> list[str]:
        """Return the valid template type strings."""
        return [
            'api_service',
            'external',
            'feed_api_service',
            'organization',
            'playbook',
            'tie',
            'trigger_service',
            # 'web_api_service',
            'webhook_trigger_service',
        ]

    @property
    def template_to_prefix_map(self) -> dict[str, str]:
        """Map template_type -> app_name prefix (e.g., playbook -> TCPB)."""
        return {
            'api_service': 'tcva',
            'feed_api_service': 'tcvf',
            'organization': 'tc',
            'playbook': 'tcpb',
            'trigger_service': 'tcvc',
            'web_api_service': 'tcvp',
            'webhook_trigger_service': 'tcvw',
        }

    # ==================================================================
    # Commands (called from init.py, update.py, list_.py)
    # ==================================================================

    def list_(self, branch: str, template_type: str | None = None):
        """List available templates by walking cached template directories.

        Populates ``self.template_data`` with parsed TemplateConfigModel
        entries grouped by type.
        """
        cache_dir = self.ensure_cache(branch)

        template_types = self.template_types
        if template_type is not None:
            if template_type not in self.template_types:
                ex_msg = f'Invalid Types: {template_type}'
                raise ValueError(ex_msg)
            template_types = [template_type]

        for selected_type in template_types:
            type_dir = cache_dir / selected_type
            if not type_dir.is_dir():
                continue
            for entry in sorted(type_dir.iterdir()):
                if not entry.is_dir():
                    continue
                config = self.read_template_config(cache_dir, selected_type, entry.name)
                if config is not None:
                    self.template_data.setdefault(selected_type, [])
                    self.template_data[selected_type].append(config)

    def update(
        self,
        branch: str,
        template_name: str | None = None,
        template_type: str | None = None,
        force: bool = False,
        app_builder: bool = False,
        managed: bool = False,
        safe: bool = False,
        plan_out: Path | None = None,
    ):
        """Update (or initialize) a project with the latest template files.

        When called from init.py, ``force=True`` and template_name/type
        are always provided so the tcex.json fallback is skipped.

        Steps:
        1. Resolve template_name/type from args or fall back to tcex.json
        2. Validate template_type and template_name against the cache
        3. Build a merged template directory (parent chain resolution)
        4. Migrate legacy .template_manifest.json if present
        5. Build an update plan via Planner.build()
        6. Apply the plan via Planner.apply() with user prompts
        7. Copy the merged manifest.json to the project root

        When ``managed`` is set, the run is silent and non-interactive: only
        template-managed (boilerplate) files are updated, all other files are
        left untouched, and nothing is deleted.

        With ``safe`` set, files you have not modified are updated as usual,
        but files you have modified are left untouched and recorded in a plan
        file along with the template version you last synced, so a separate
        step can perform a three-way merge.
        """
        # resolve from tcex.json if not provided
        _template_name = template_name or self.app.tj.model.template_name
        _template_type = template_type or self.app.tj.model.template_type

        if not _template_name or not _template_type:
            Render.panel.failure(
                'Template name and type are required. Provide via --template/--type '
                'or ensure they are set in tcex.json.'
            )

        # validate template type against known types
        if _template_type not in self.template_types:
            Render.panel.failure(
                f'Unknown template type: {_template_type!r}. '
                f'Valid types: {", ".join(self.template_types)}'
            )

        cache_dir = self.ensure_cache(branch)

        # validate template name exists in the cache
        template_dir = cache_dir / _template_type / _template_name  # type: ignore[operator]
        if not template_dir.is_dir():
            available = [
                d.name
                for d in (cache_dir / _template_type).iterdir()  # type: ignore[operator]
                if d.is_dir()
            ]
            Render.panel.failure(
                f'Template {_template_name!r} not found for type {_template_type!r}. '
                f'Available templates: {", ".join(sorted(available)) or "none"}'
            )

        merged_dir = self._build_merged_template(
            cache_dir,
            _template_name,
            _template_type,
            app_builder,  # type: ignore[arg-type]
        )
        try:
            self._migrate_legacy_manifest(merged_dir, Path.cwd())

            # capture the pre-update manifest before it is overwritten below — it
            # records which template version each local file was last synced from,
            # which is what --safe needs to locate the three-way merge base.
            local_meta = self.manifest_store.load_json(Path.cwd() / 'manifest.json')

            plan = self.planner.build(
                merged_dir,
                Path.cwd(),
                force=force,
                managed_only=managed,
            )
            Render.table.key_value('Plan Summary', plan.summary)

            def _prompt_fn(msg: str) -> str:
                return Render.prompt.ask(msg, choices=['y', 'N'], default='N') or 'N'

            # in safe mode every conflict is declined, so nothing modified is touched
            # and nothing is prompted. auto-update files still apply normally.
            self.planner.apply(
                plan,
                template_root=merged_dir,
                project_root=Path.cwd(),
                force=force,
                prompt_fn=(lambda _: 'N') if safe else _prompt_fn,
            )

            deferred: list[tuple] = plan.prompt_user if safe else []

            if safe:
                self._write_safe_plan(
                    plan,
                    merged_dir=merged_dir,
                    project_root=Path.cwd(),
                    local_meta=local_meta,
                    plan_out=Path(plan_out or '.tcex-update/plan.json'),
                    branch=branch,
                    template_name=str(_template_name),
                    template_type=str(_template_type),
                    parents=self.resolve_template_parents(
                        cache_dir, str(_template_name), str(_template_type)
                    ),
                )

            # copy manifest.json to project root so future updates can compare
            merged_manifest = merged_dir / 'manifest.json'
            if merged_manifest.is_file():
                self._write_project_manifest(
                    merged_manifest, Path.cwd() / 'manifest.json', local_meta, deferred
                )

            # ensure tcex.json exists with correct template values
            self._ensure_tcex_json(cache_dir, _template_name, _template_type)
        finally:
            shutil.rmtree(merged_dir, ignore_errors=True)

    # ==================================================================
    # Safe Mode (--safe)
    #
    # Applies only non-conflicting updates, then records every file the
    # user has modified into a plan file alongside the three versions a
    # merge needs:
    #   base   - the template file as of the last sync (fetched by ref)
    #   theirs - the template file now
    #   ours   - the file currently in the project
    # ==================================================================

    def _write_project_manifest(
        self,
        merged_manifest: Path,
        dest: Path,
        local_meta: dict,
        deferred: list[tuple],
    ) -> None:
        """Write the project manifest, preserving entries for deferred conflicts.

        A deferred file was NOT updated, so stamping it with the new template's
        ``last_commit`` would make the next run believe it is already in sync and
        skip it — silently dropping the template change forever. Those keys keep
        their previous entry so the conflict resurfaces until it is resolved.
        """
        meta = self.manifest_store.load_json(merged_manifest)

        for key, _template_path in deferred:
            if key in local_meta:
                meta[key] = local_meta[key]
            else:
                meta.pop(key, None)

        with dest.open('w', encoding='utf-8') as fh:
            json.dump(meta, fh, indent=2, sort_keys=True)
            fh.write('\n')

    @staticmethod
    def _source_path_candidates(
        key: str, entry_meta: dict, template_type: str, parents: list[str]
    ) -> list[str]:
        """Return repo-relative paths to try when fetching *key* at an older ref.

        Manifests written by a current CLI carry ``source_path`` (the exact repo
        path), so there is a single candidate. Manifests written before that field
        existed only have the project-relative path, so fall back to walking the
        parent chain leaf-first — the same precedence the merge itself uses.
        """
        source_path = entry_meta.get('source_path')
        if source_path:
            return [source_path]

        candidates = []
        for parent in reversed(parents):
            prefix = '_app_common' if parent == '_app_common' else f'{template_type}/{parent}'
            candidates.append(f'{prefix}/{key}')
        return candidates

    def _fetch_base_file(self, candidates: list[str], ref: str, dest: Path) -> bool:
        """Fetch a template file at a specific git ref into *dest*.

        Uses raw.githubusercontent.com rather than the REST API — it serves the
        same content but does not consume the api.github.com rate limit, so this
        stays cheap even with many conflicts. Only conflicted files are fetched.

        Returns True on success. Any failure returns False so the caller can fall
        back to a two-way merge rather than aborting the whole update.
        """
        if not ref or ref == 'legacy_migrated':
            return False

        for template_path in candidates:
            url = f'{self.raw_url}/{ref}/{template_path}'
            try:
                r = self.session.get(url, timeout=10)
                if not r.ok:
                    continue
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(r.content)
            except Exception:
                self.log.exception(f'action=fetch-base, url={url}')
                continue
            return True

        self.log.warning(
            f'action=fetch-base, ref={ref}, candidates={candidates}, '
            f'message=base unavailable, merge will be two-way'
        )
        return False

    def _write_safe_plan(
        self,
        plan,
        merged_dir: Path,
        project_root: Path,
        local_meta: dict,
        plan_out: Path,
        branch: str,
        template_name: str,
        template_type: str,
        parents: list[str],
    ) -> None:
        """Write the plan file describing every deferred conflict.

        Materializes ``base`` (fetched by ref) and ``theirs`` (copied out of the
        merged template) next to the plan, because the merged directory is a temp
        dir that is removed as soon as this command exits.
        """
        out_dir = plan_out.parent
        removed_keys = {key for key, _ in plan.template_removed}
        merged_meta = self.manifest_store.load_json(merged_dir / 'manifest.json')

        conflicts = []
        for key, template_path in sorted(plan.prompt_user):
            entry_meta = local_meta.get(key, {})
            ref = entry_meta.get('last_commit', '')

            base_path = out_dir / 'base' / key
            has_base = self._fetch_base_file(
                self._source_path_candidates(key, entry_meta, template_type, parents),
                ref,
                base_path,
            )

            # 'theirs' only exists for updates; a removal has no new version
            theirs_path = None
            if key not in removed_keys:
                src = merged_dir / template_path
                if src.is_file():
                    theirs_path = out_dir / 'theirs' / key
                    theirs_path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(str(src), str(theirs_path))

            conflicts.append(
                {
                    'key': key,
                    'action': 'remove' if key in removed_keys else 'update',
                    'template_path': template_path,
                    'merge': 'three_way' if has_base else 'two_way',
                    # all three paths are relative to project_root so the plan stays
                    # valid if the project is moved or read from another machine
                    'base': {
                        'ref': ref,
                        'path': base_path.as_posix() if has_base else None,
                        'sha256': entry_meta.get('sha256'),
                    },
                    'theirs': {'path': theirs_path.as_posix() if theirs_path else None},
                    'ours': {'path': key},
                    # written back into manifest.json by whoever resolves this file,
                    # so the next update sees it as in sync
                    'resolved_manifest_entry': merged_meta.get(key),
                }
            )

        document = {
            'schema_version': 1,
            'template': {'name': template_name, 'type': template_type, 'branch': branch},
            'project_root': str(project_root),
            'manifest_path': 'manifest.json',
            'applied': {
                'auto_update': [k for k, _ in plan.auto_update],
                'template_new': [k for k, _ in plan.template_new],
                'template_removed': [k for k, _ in plan.template_removed],
            },
            'conflicts': conflicts,
        }

        plan_out.parent.mkdir(parents=True, exist_ok=True)
        with plan_out.open('w', encoding='utf-8') as fh:
            json.dump(document, fh, indent=2, sort_keys=True)
            fh.write('\n')

        Render.panel.info(
            f'Deferred [{self.accent}]{len(conflicts)}[/] modified file(s) to {plan_out}'
        )

    def _ensure_tcex_json(self, cache_dir: Path, template_name: str, template_type: str) -> None:
        """Ensure tcex.json exists with correct template_name and template_type.

        tcex.json is skipped during template merge because it contains
        project-specific values (app_name, excludes, etc.) that shouldn't
        be overwritten. Only template_name and template_type are managed.

        - If tcex.json doesn't exist: copy the fresh one from the leaf template
          (it already contains the correct template_name/template_type).
        - If tcex.json exists: update template_name and template_type via the model.
        """
        project_tcex = Path.cwd() / 'tcex.json'

        if not project_tcex.is_file():
            # copy fresh from the leaf template in the cache
            src = cache_dir / template_type / template_name / 'tcex.json'
            if src.is_file():
                shutil.copy2(str(src), str(project_tcex))
        else:
            # update only the template-managed fields via the existing model
            self.app.tj.model.template_name = template_name
            self.app.tj.model.template_type = template_type
            self.app.tj.write()

    # ==================================================================
    # Cache Management
    #
    # Templates are cached at ~/.tcex/templates/templates-{branch}.
    # Staleness is determined by a single GitHub API call that fetches
    # the latest commit date, then compares against the cache dir's
    # filesystem mtime. This avoids per-file API calls (the old approach
    # that caused rate limiting at 60 req/hr unauthenticated).
    # ==================================================================

    def ensure_cache(self, branch: str) -> Path:
        """Ensure the local cache is fresh; download if stale. Return cache dir."""
        if self._cache_is_stale(branch):
            Render.panel.info('Downloading templates...')
            self._download_and_extract(branch)
        return self._cache_dir(branch)

    def clear_cache(self, branch: str) -> None:
        """Remove the cache directory for a given branch."""
        cache_dir = self._cache_dir(branch)
        if cache_dir.exists():
            shutil.rmtree(cache_dir)
        Render.panel.info('Clearing template cache.')

    def _cache_dir(self, branch: str) -> Path:
        """Return the local cache directory path for a given branch."""
        return self.cli_out_path / 'templates' / f'templates-{branch}'

    def _cache_is_stale(self, branch: str) -> bool:
        """Check if the cache is missing or older than the remote commit.

        Compares the latest commit date from the GitHub API against
        the cache directory's filesystem mtime. Returns False on API
        failure so the existing cache is used as a fallback.
        """
        cache_dir = self._cache_dir(branch)
        if not cache_dir.exists():
            return True

        remote_date = self._remote_commit_date(branch)
        if remote_date is None:
            return False  # API failed — use existing cache

        try:
            remote_dt = datetime.fromisoformat(remote_date.replace('Z', '+00:00'))
        except (ValueError, AttributeError):
            return False

        cache_mtime = datetime.fromtimestamp(cache_dir.stat().st_mtime, tz=UTC)
        return remote_dt > cache_mtime

    def _remote_commit_date(self, branch: str) -> str | None:
        """Fetch the latest commit date for a branch from the GitHub API.

        GET /repos/{owner}/{repo}/commits/{branch}
        Returns the ``commit.committer.date`` field (ISO 8601).
        This is the cheapest way to check for new commits without
        downloading the full zipball every time.

        Returns None on any failure (network error, rate limit, etc.)
        so the caller can fall back to the existing cache.
        """
        url = f'{self.base_url}/commits/{branch}'
        try:
            r = self.session.get(url, timeout=5)
            if not r.ok:
                self.log.error(
                    f'action=remote-commit-date, url={r.request.url}, '
                    f'status_code={r.status_code}, response={r.text or r.reason}'
                )
                return None
            return r.json().get('commit', {}).get('committer', {}).get('date')
        except Exception:
            self.log.exception('action=remote-commit-date, failed to fetch commit date')
            return None

    def _download_and_extract(self, branch: str) -> None:
        """Download the repo zipball and extract to the cache directory.

        GET /repos/{owner}/{repo}/zipball/{branch}
        GitHub returns a redirect to a CDN URL serving the zip file.
        The requests library follows the redirect automatically.

        GitHub zips include a top-level directory named
        ``{owner}-{repo}-{short_sha}/`` — we flatten this prefix
        so the cache dir contains bare template directories.

        Uses temp files (not CWD) to avoid polluting the user's project.
        The atomic move prevents a corrupted cache if interrupted mid-download.
        """
        url = f'{self.base_url}/zipball/{branch}'

        # stream the zipball to a temp file
        with tempfile.NamedTemporaryFile(suffix='.zip', delete=False) as tmp_zip:
            tmp_zip_path = Path(tmp_zip.name)
            with self.session.get(url, stream=True, timeout=30) as r:
                r.raise_for_status()
                for chunk in r.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        tmp_zip.write(chunk)

        # extract to a temp directory, then flatten the top-level prefix
        tmp_extract = Path(tempfile.mkdtemp())
        try:
            with zipfile.ZipFile(tmp_zip_path, 'r') as zf:
                names = zf.namelist()
                if not names:
                    return
                # GitHub zips always have a top-level dir: {owner}-{repo}-{sha}/
                top_prefix = names[0].split('/', 1)[0]
                zf.extractall(tmp_extract)

            # flatten: move contents up one level, removing the prefix dir
            top_dir = tmp_extract / top_prefix
            flat_dir = Path(tempfile.mkdtemp())
            if top_dir.exists() and top_dir.is_dir():
                for child in top_dir.iterdir():
                    target = flat_dir / child.name
                    shutil.move(str(child), str(target))
                shutil.rmtree(top_dir)
            else:
                flat_dir = tmp_extract
                tmp_extract = None  # prevent cleanup of the dir we're using

            # atomically replace the cache directory
            cache_dir = self._cache_dir(branch)
            if cache_dir.exists():
                shutil.rmtree(cache_dir)
            cache_dir.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(flat_dir), str(cache_dir))

        finally:
            tmp_zip_path.unlink(missing_ok=True)
            if tmp_extract is not None and tmp_extract.exists():
                shutil.rmtree(tmp_extract, ignore_errors=True)

    # ==================================================================
    # Template Resolution & Merging
    #
    # Templates support inheritance via template_parents in template.yaml.
    # Files are copied parent-first so child files override parent files,
    # like CSS cascading:
    #   _app_common -> basic -> egress
    #   1. Copy all _app_common files into merged dir
    #   2. Copy basic files (overwriting any _app_common files)
    #   3. Copy egress files (overwriting any basic/_app_common files)
    # ==================================================================

    def _build_merged_template(
        self,
        cache_dir: Path,
        template_name: str,
        template_type: str,
        app_builder: bool = False,
    ) -> Path:
        """Build a merged template directory resolving parent inheritance.

        Creates a temp directory, copies files in parent-first order
        (child overwrites parent), and generates a combined manifest.json.
        Returns the path to the merged directory — caller must clean up.
        """
        parents = self.resolve_template_parents(cache_dir, template_name, template_type)
        merged_dir = Path(tempfile.mkdtemp(prefix='tcex_merged_'))

        merged_manifest: dict = {}

        # files to skip — these are meta-files not intended for the project
        skip_names = {'template.yaml', '.gitignore', 'tcex.json'}

        for parent_name in parents:
            # _app_common lives at the repo root, not under a type subdirectory
            if parent_name == '_app_common':
                src_dir = cache_dir / '_app_common'
            else:
                src_dir = cache_dir / template_type / parent_name

            if not src_dir.is_dir():
                self.log.warning(
                    f'action=build-merged-template, missing-dir={src_dir}, parent={parent_name}'
                )
                continue

            # load this parent's manifest.json (generated by the template
            # repo's post-commit hook — contains correct git commit SHAs
            # and the per-file ``managed`` flag)
            parent_manifest: dict = {}
            with contextlib.suppress(Exception):
                parent_manifest = json.loads(
                    (src_dir / 'manifest.json').read_text(encoding='utf-8')
                )
            if not isinstance(parent_manifest, dict):
                parent_manifest = {}

            # copy files from this parent (child overwrites parent)
            for src_file in src_dir.rglob('*'):
                if not src_file.is_file():
                    continue

                rel = src_file.relative_to(src_dir)
                name = rel.parts[0] if rel.parts else rel.name

                if name in skip_names:
                    continue
                if str(rel) == 'manifest.json':
                    continue
                if name == '.appbuilderconfig' and not app_builder:
                    continue

                # template repos store gitignore without the dot to avoid
                # GitHub ignoring the file — rename it for the project
                parts = list(rel.parts)
                renamed_gitignore = parts[-1] == 'gitignore'
                if renamed_gitignore:
                    parts[-1] = '.gitignore'
                    rel = Path(*parts)

                dest = merged_dir / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(str(src_file), str(dest))

                # merge manifest entry from parent — child entries
                # overwrite parent entries naturally via iteration order.
                # use rel_key for template_path (project-relative), not the
                # prefixed path from the parent's manifest.
                rel_key = str(rel)
                parent_entry = parent_manifest.get(rel_key)
                if renamed_gitignore:
                    # the dot-less `gitignore` was renamed to `.gitignore`; the
                    # parent manifest's `.gitignore` key (if any) describes a
                    # different, stray file. compute sha256 from the file we
                    # actually wrote so the manifest matches the content on disk.
                    merged_manifest[rel_key] = {
                        'last_commit': (parent_entry['last_commit'] if parent_entry else 'unknown'),
                        'sha256': self.hasher.sha256_file(dest),
                        'template_path': rel_key,
                        'managed': bool(parent_entry.get('managed', False))
                        if parent_entry
                        else False,
                    }
                elif parent_entry:
                    merged_manifest[rel_key] = {
                        'last_commit': parent_entry['last_commit'],
                        'sha256': parent_entry['sha256'],
                        'template_path': rel_key,
                        'managed': bool(parent_entry.get('managed', False)),
                        # repo-relative origin (e.g. "tie/basic/core/pipeline.py").
                        # template_path above is flattened to the project-relative
                        # path, which loses which template dir the file came from —
                        # needed to fetch this file at an older ref.
                        'source_path': parent_entry.get('template_path', rel_key),
                    }
                else:
                    self.log.warning(
                        f'action=build-merged-template, file={rel_key}, '
                        f'parent={parent_name}, message=no manifest entry found'
                    )

        # write the combined manifest to the merged dir
        manifest_out = merged_dir / 'manifest.json'
        with manifest_out.open('w', encoding='utf-8') as fh:
            json.dump(merged_manifest, fh, indent=2, sort_keys=True)
            fh.write('\n')

        return merged_dir

    def read_template_config(
        self, cache_dir: Path, template_type: str, template_name: str
    ) -> TemplateConfigModel | None:
        """Read and parse template.yaml from the local cache.

        Path resolution:
        - _app_common: ``cache_dir/_app_common/template.yaml``
        - Others:      ``cache_dir/{template_type}/{template_name}/template.yaml``
        """
        if template_name == '_app_common':
            config_path = cache_dir / '_app_common' / 'template.yaml'
        else:
            config_path = cache_dir / template_type / template_name / 'template.yaml'

        if not config_path.is_file():
            self.log.warning(f'action=read-template-config, file-not-found={config_path}')
            return None

        try:
            with config_path.open(encoding='utf-8') as fh:
                data = yaml.safe_load(fh)
            data.update({'name': template_name, 'type': template_type})
            return TemplateConfigModel(**data)
        except ValidationError:
            self.log.exception('action=read-template-config, validation-error')
            Render.panel.warning(f'Could not parse template config file ({config_path}).')
            self.errors = True
            return None
        except Exception:
            self.log.exception(f'action=read-template-config, path={config_path}')
            self.errors = True
            return None

    def resolve_template_parents(
        self, cache_dir: Path, template_name: str, template_type: str
    ) -> list[str]:
        """Recursively resolve the full parent chain for a template.

        Returns an ordered list with ancestors first, template last.
        E.g., ``['_app_common', 'basic']`` or ``['_app_common', 'basic', 'egress']``.
        Deduplicates via a ``seen`` set to prevent infinite loops from
        circular references.
        """
        resolved: list[str] = []
        seen: set[str] = set()

        def _resolve(name: str):
            if name in seen:
                return
            seen.add(name)

            config = self.read_template_config(cache_dir, template_type, name)
            if config is None:
                # still add it so the caller can try to copy files
                resolved.append(name)
                return

            # resolve each parent's full ancestry before adding this template
            for parent in config.template_parents or []:
                _resolve(parent)

            resolved.append(name)

        _resolve(template_name)

        if not resolved:
            Render.panel.failure(
                'Failed retrieving template.yaml: \n'
                f'template-type={template_type}, template-name={template_name}'
                '\n\nTry running "tcex list" to get valid template types and names.'
            )

        return resolved

    # ==================================================================
    # Legacy Migration
    # ==================================================================

    def _migrate_legacy_manifest(self, merged_dir: Path, project_root: Path):
        """Migrate .template_manifest.json (old MD5 system) to manifest.json.

        Old projects track template files in ``.template_manifest.json`` using
        MD5 hashes and repo-relative keys.  The new system uses ``manifest.json``
        with SHA-256 hashes and project-relative keys.

        This method builds a ``manifest.json`` so that every locally-existing
        template file lands in the Planner's hash-comparison path:

        * Files whose SHA-256 already matches the current template get the
          template's manifest entry -> Planner skips them.
        * Files that differ get a dummy ``last_commit`` -> Planner falls through
          to hash comparison -> prompts the user before overwriting.
        * Files not on disk are omitted -> Planner auto-creates them.
        """
        legacy_path = project_root / '.template_manifest.json'
        new_path = project_root / 'manifest.json'

        if new_path.exists() or not legacy_path.exists():
            return

        template_meta = self.manifest_store.load_json(merged_dir / 'manifest.json')
        local_manifest: dict = {}

        for key, entry in template_meta.items():
            local_file = project_root / key
            if not local_file.exists():
                continue

            local_hash = self.hasher.sha256_file(local_file)

            if local_hash == entry['sha256']:
                # in sync with current template — Planner will skip
                local_manifest[key] = entry
            else:
                # differs — dummy last_commit forces hash-comparison path;
                # store the template's sha256 (not local) so the planner can
                # distinguish "user never touched this" from "user modified it"
                local_manifest[key] = {
                    'last_commit': 'legacy_migrated',
                    'sha256': entry['sha256'],
                    'template_path': entry['template_path'],
                }

        with new_path.open('w', encoding='utf-8') as fh:
            json.dump(local_manifest, fh, indent=2, sort_keys=True)
            fh.write('\n')

        legacy_path.unlink()
        self.log.info('action=migrate-legacy-manifest, migrated-files=%d', len(local_manifest))
