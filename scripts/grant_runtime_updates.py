"""Owner-only, idempotent grants for an existing non-owner runtime role after migrations."""
import os
import psycopg
from psycopg import sql

role=os.environ.get('APP_DB_ROLE','plastics_app')
url=os.environ.get('DATABASE_URL')
if not url: raise SystemExit('Supply the owner DATABASE_URL through secret management.')
with psycopg.connect(url) as conn:
    if not conn.execute('SELECT 1 FROM pg_roles WHERE rolname=%s',[role]).fetchone():
        raise SystemExit('Runtime role does not exist; provision it first.')
    conn.execute(sql.SQL('GRANT USAGE ON SCHEMA public TO {}').format(sql.Identifier(role)))
    conn.execute(sql.SQL('GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA public TO {}').format(sql.Identifier(role)))
    conn.execute(sql.SQL('GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {}').format(sql.Identifier(role)))
    conn.execute(sql.SQL('ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE ON TABLES TO {}').format(sql.Identifier(role)))
    conn.execute(sql.SQL('GRANT DELETE ON django_session TO {}').format(sql.Identifier(role)))
    for table in ('core_entity','core_division','core_membership','core_invitation'):
        conn.execute(sql.SQL('REVOKE UPDATE ON {} FROM {}').format(sql.Identifier(table),sql.Identifier(role)))
    conn.execute(sql.SQL('GRANT UPDATE (accepted_at) ON core_invitation TO {}').format(sql.Identifier(role)))
    conn.execute(sql.SQL('GRANT UPDATE (closed_through) ON core_division TO {}').format(sql.Identifier(role)))
print('Runtime role grants updated. Confirm RLS, MFA, and tenant isolation in the target environment.')
