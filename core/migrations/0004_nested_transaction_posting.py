from django.db import migrations
# PostgreSQL xmin can be a subtransaction ID inside Django savepoints. Store the
# top-level transaction ID explicitly, rather than comparing xmin to the parent.
SQL=r'''
ALTER TABLE core_journal ADD COLUMN posting_transaction text NOT NULL DEFAULT pg_current_xact_id()::text;
CREATE OR REPLACE FUNCTION plastics_new_journal_only() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF NOT EXISTS (SELECT 1 FROM core_journal WHERE id=NEW.journal_id AND posting_transaction=pg_current_xact_id()::text) THEN
 RAISE EXCEPTION 'Cannot append lines to a previously posted journal'; END IF;
 RETURN NEW;
END $$;
'''
class Migration(migrations.Migration):
    dependencies=[('core','0003_posting_guards')]
    operations=[migrations.RunSQL(SQL)]
