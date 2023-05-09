"""TcEx Framework Module"""

# third-party
from pydantic import BaseSettings, Extra

# first-party
from tcex_cli.input.field_type.sensitive import Sensitive


class ServiceModel(BaseSettings):
    """Model Definition"""

    # service model
    tc_svc_broker_cacert_file: str | None = None
    tc_svc_broker_cert_file: str | None = None
    tc_svc_broker_conn_timeout: int = 60
    tc_svc_broker_host: str = 'localhost'
    tc_svc_broker_port: int = 1883
    tc_svc_broker_timeout: int = 60
    tc_svc_broker_token: Sensitive | None = None
    tc_svc_client_topic: str = 'tcex-app-testing-client-topic'
    tc_svc_hb_timeout_seconds: int = 600
    tc_svc_id: int | None = None
    tc_svc_server_topic: str = 'tcex-app-testing-server-topic'

    class Config:
        """DataModel Config"""

        extra = Extra.allow
        case_sensitive = False
        env_file = '.env'
        env_file_encoding = 'utf-8'
        validate_assignment = True
