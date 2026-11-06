"""PostgreSQL access for the CRM (OOP layer).

    DbConfig          connection settings (environment / .env)
    Database          owns the connection, runs queries and transactions
    PasswordHasher    salted password hashes
    RecordService     add / change / delete rules (validation, transactions)
    *Repository       one class per table; CrmRepositories bundles them
"""
from database.config import ConfigError, DbConfig
from database.connection import Database, DatabaseError
from database.repositories import (BasvuruRepository, CrmRepositories, KullaniciRepository,
                                   KursiyerRepository, MentorRepository, MulakatRepository)
from database.security import PasswordHasher
from database.services import OLD_LIST_PERIODS, RecordService, ValidationError

__all__ = [
    "BasvuruRepository", "ConfigError", "CrmRepositories", "Database", "DatabaseError",
    "DbConfig", "KullaniciRepository", "KursiyerRepository", "MentorRepository",
    "MulakatRepository", "OLD_LIST_PERIODS", "PasswordHasher", "RecordService", "ValidationError",
]
