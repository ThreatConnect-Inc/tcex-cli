"""TcEx Framework Module"""
# standard library
import os
from pathlib import Path

# first-party
from tcex_cli.cli.cli_abc import CliABC
from tcex_cli.input.field_type.sensitive import Sensitive
from tcex_cli.pleb.proxies import proxies
from tcex_cli.render.render import Render
from tcex_cli.requests_tc import TcSession
from tcex_cli.requests_tc.auth.hmac_auth import HmacAuth


class DeployCli(CliABC):
    """CLI command for deploying Apps to ThreatConnect Exchange."""

    def __init__(
        self,
        server: str,
        allow_all_orgs: bool,
        allow_distribution: bool,
        app_file: str | None,
        proxy_host: str | None,
        proxy_port: int | None,
        proxy_user: str | None,
        proxy_pass: str | None,
    ):
        """Initialize instance properties."""
        super().__init__()
        self._app_file = app_file
        self.allow_all_orgs = allow_all_orgs
        self.allow_distribution = allow_distribution
        self.proxy_host = proxy_host
        self.proxy_port = proxy_port
        self.proxy_user = proxy_user
        self.proxy_pass = self._process_proxy_pass(proxy_pass)
        self.server = server

    def _process_proxy_pass(self, proxy_pass: str | None) -> Sensitive | None:
        """Process proxy password."""
        return None if proxy_pass is None else Sensitive(proxy_pass)

    def _check_file(self):
        """Return True if file exists."""
        if self._app_file and not os.path.isfile(self._app_file):
            Render.panel.failure(f'Could not find file: {self._app_file}.')

    @property
    def app_file(self):
        """Return app file."""
        if self._app_file is None:
            target_fqpn = Path('target')
            app_files = list(target_fqpn.glob('*.tcx'))
            if len(app_files) > 1:
                Render.panel.failure(
                    'More than one App file found, can\'t autodetect the correct file.',
                )
            elif not app_files:
                Render.panel.failure('No App package found. Please run "tcex package" first.')

            # set app_file to the only file found
            self._app_file = app_files[0]

        # validate the file exists
        self._check_file()

        return Path(self._app_file)

    @property
    def auth(self):
        """Authenticate with TcEx."""
        tc_api_access_id = os.getenv('TC_API_ACCESS_ID')
        tc_api_secret_key = os.getenv('TC_API_SECRET_KEY')
        if tc_api_access_id is None:
            Render.panel.failure('Could not find environment variable: TC_API_ACCESS_ID')
        if tc_api_secret_key is None:
            Render.panel.failure('Could not find environment variable: TC_API_SECRET_KEY')

        return HmacAuth(tc_api_access_id, Sensitive(tc_api_secret_key))

    @property
    def base_url(self):
        """Authenticate with TcEx."""
        return f'https://{self.server}/api'

    # pylint: disable=consider-using-with
    def deploy_app(self):
        """Deploy the App to ThreatConnect Exchange."""
        files = {
            'allowAllOrgs': self.allow_all_orgs,
            'allowAppDistribution': self.allow_distribution,
            'fileData': ('filename', open(self.app_file, 'rb'), 'application/octet-stream'),
        }
        try:
            response = self.session.post('/internal/apps/exchange/install', files=files, timeout=60)
        except Exception as err:
            Render.panel.failure(f'Failed Deploying App: {err}')

        if not response.ok:
            reason = response.text or response.reason
            Render.table.key_value(
                'Failed To Deploy App',
                {
                    'File Name': os.path.basename(self.app_file),
                    'Reason': reason,
                    'Status Code': str(response.status_code),
                    'URL': response.request.url,
                },
            )

        else:
            response_data = response.json()[0]
            Render.table.key_value(
                'Successfully Deployed App',
                {
                    'File Name': os.path.basename(self.app_file),
                    'Display Name': response_data.get('displayName'),
                    'Program Name': response_data.get('programName'),
                    'Program Version': response_data.get('programVersion'),
                    'Allow All Orgs': str(self.allow_all_orgs),
                    'Allow Distribution': str(self.allow_distribution),
                    'Status Code': str(response.status_code),
                    'URL': response.request.url,
                },
            )

    @property
    def session(self):
        """Create a TcEx Session."""
        _proxies = proxies(
            proxy_host=self.proxy_host,
            proxy_port=self.proxy_port,
            proxy_user=self.proxy_user,
            proxy_pass=self.proxy_pass,
        )
        return TcSession(auth=self.auth, base_url=self.base_url, proxies=_proxies)
