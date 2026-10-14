"""Owner-only provisioning for a non-owner app role. Never run as a web request.
DATABASE_URL supplies the owner connection; APP_DB_PASSWORD supplies the secret.
No credentials are printed. Review the grants before use on the chosen provider.
"""
import os
import psycopg
from psycopg import sql
role=os.environ.get('APP_DB_ROLE','plastics_app')
password=os.environ.get('APP_DB_PASSWORD')
if not password or len(password)<24: raise SystemExit('Supply a strong APP_DB_PASSWORD through secret management (24+ characters).')
with psycopg.connect(os.environ['DATABASE_URL']) as conn:
    if conn.execute('SELECT 1 FROM pg_roles WHERE rolname=%s',[role]).fetchone():
        raise SystemExit('Role already exists. Review existing ownership, membership and grants rather than overwriting them.')
    conn.execute(sql.SQL('CREATE ROLE {} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS PASSWORD {}').format(sql.Identifier(role),sql.Literal(password)))
    conn.execute(sql.SQL('GRANT USAGE ON SCHEMA public TO {}').format(sql.Identifier(role)))
    conn.execute(sql.SQL('GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA public TO {}').format(sql.Identifier(role)))
    conn.execute(sql.SQL('GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {}').format(sql.Identifier(role)))
    conn.execute(sql.SQL('GRANT DELETE ON django_session TO {}').format(sql.Identifier(role)))
    # Deny changing the financial boundary or authority using the app identity.
    for table in ('core_entity','core_division','core_membership','core_invitation'):
        conn.execute(sql.SQL('REVOKE UPDATE ON {} FROM {}').format(sql.Identifier(table),sql.Identifier(role)))
    # Initial invitation acceptance is a constrained bootstrap path; needs these columns.
    conn.execute(sql.SQL('GRANT UPDATE (accepted_at) ON core_invitation TO {}').format(sql.Identifier(role)))
    # Period locks are changed only by jointly approved services; table triggers enforce posting checks.
    conn.execute(sql.SQL('GRANT UPDATE (closed_through) ON core_division TO {}').format(sql.Identifier(role)))
print('Non-owner runtime role provisioned. Validate hosted tenant isolation and MFA enrollment before launch.')
