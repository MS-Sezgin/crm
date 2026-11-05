"""PostgreSQL connection settings.

Values are read from environment variables first, then from a .env file that sits
next to the program (next to the .exe when the app is built). The password is never
written in the source code. See .env.example for the names.

    CRM_DB_HOST      default: localhost
    CRM_DB_PORT      default: 5432
    CRM_DB_NAME      default: crm_db
    CRM_DB_USER      default: postgres
    CRM_DB_PASSWORD  required
    CRM_DB_SCHEMA    optional; use another schema than "public" (the tests use this)
"""
import os
import re
from dataclasses import dataclass

from paths import app_dir

ENV_FILE_NAME = ".env"
_SCHEMA_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class ConfigError(Exception):
    """Raised when the database settings are missing or invalid."""


def read_env_file(path):
    """Read KEY=VALUE lines from a .env file. A missing file gives an empty dict."""
    values = {}
    if not os.path.exists(path):
        return values
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            values[key.strip()] = value.strip().strip('"').strip("'")
    return values


@dataclass(frozen=True)
class DbConfig:
    host: str = "localhost"
    port: int = 5432
    dbname: str = "crm_db"
    user: str = "postgres"
    password: str = ""
    schema: str = ""

    @classmethod
    def load(cls, env_file=None):
        """Build the settings from the environment and the .env file."""
        path = env_file or os.path.join(app_dir(), ENV_FILE_NAME)
        file_values = read_env_file(path)

        def get(key, default=None):
            if key in os.environ:
                return os.environ[key]
            return file_values.get(key, default)

        password = get("CRM_DB_PASSWORD")
        if password is None:
            raise ConfigError(
                "CRM_DB_PASSWORD is not set. Put it in the environment or in a .env file "
                f"next to the program ({path}). See .env.example.")
        try:
            port = int(get("CRM_DB_PORT", "5432"))
        except ValueError as error:
            raise ConfigError("CRM_DB_PORT must be a number.") from error
        schema = get("CRM_DB_SCHEMA", "") or ""
        if schema and not _SCHEMA_PATTERN.match(schema):
            raise ConfigError("CRM_DB_SCHEMA may only contain letters, digits and underscores.")
        return cls(host=get("CRM_DB_HOST", "localhost"), port=port,
                   dbname=get("CRM_DB_NAME", "crm_db"), user=get("CRM_DB_USER", "postgres"),
                   password=password, schema=schema)

    def connect_kwargs(self):
        """Arguments for psycopg2.connect()."""
        kwargs = {"host": self.host, "port": self.port, "dbname": self.dbname, "user": self.user,
                  "password": self.password, "client_encoding": "UTF8", "connect_timeout": 10}
        if self.schema:
            kwargs["options"] = f"-c search_path={self.schema}"
        return kwargs
