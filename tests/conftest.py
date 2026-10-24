"""Isolate test records and startup recovery from the development application's data."""
from uuid import uuid4
import pytest
import psycopg
from psycopg import sql
from psycopg.conninfo import make_conninfo
from backend import app as module

@pytest.fixture(scope='session',autouse=True)
def isolated_database_schema():
    original=module.DB
    schema='test_'+uuid4().hex
    with psycopg.connect(original) as c:
        c.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(schema)))
    module.DB=make_conninfo(original,options='-c search_path='+schema)
    try:yield
    finally:
        module.DB=original
        with psycopg.connect(original) as c:
            c.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(schema)))
