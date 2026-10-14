from django.db import migrations
SQL = r'''
CREATE FUNCTION plastics_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'Immutable evidence or posting: use a new version or linked reversal'; END $$;
CREATE FUNCTION plastics_balanced() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE jid uuid; dr numeric; cr numeric; n integer;
BEGIN
 IF TG_TABLE_NAME = 'core_journal' THEN jid := NEW.id; ELSE jid := NEW.journal_id; END IF;
 SELECT COALESCE(SUM(debit),0), COALESCE(SUM(credit),0), COUNT(*) INTO dr,cr,n FROM core_line WHERE journal_id=jid;
 IF n < 2 OR dr <> cr THEN RAISE EXCEPTION 'Posted journal must have balanced debit and credit lines'; END IF;
 RETURN NEW;
END $$;
CREATE CONSTRAINT TRIGGER journal_balanced AFTER INSERT ON core_journal DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION plastics_balanced();
CREATE CONSTRAINT TRIGGER line_balanced AFTER INSERT ON core_line DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION plastics_balanced();
CREATE FUNCTION plastics_new_journal_only() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF NOT EXISTS (SELECT 1 FROM core_journal WHERE id=NEW.journal_id AND xmin=pg_current_xact_id()::text::xid) THEN
 RAISE EXCEPTION 'Cannot append lines to a previously posted journal'; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER no_late_lines BEFORE INSERT ON core_line FOR EACH ROW EXECUTE FUNCTION plastics_new_journal_only();
'''
IMMUTABLE=['journal','line','decisionversion','signature','execution','movement','audit','document']
for table in IMMUTABLE:
    SQL+=f'CREATE TRIGGER immutable_{table} BEFORE UPDATE OR DELETE ON core_{table} FOR EACH ROW EXECUTE FUNCTION plastics_immutable();\n'
# The runtime role must not own these tables or have BYPASSRLS; owner is reserved for migrations.
SCOPED=['record','document','decision','execution','journal','stock','movement','openitem','bankrow','audit','contract']
for table in SCOPED:
    SQL+=f'''ALTER TABLE core_{table} ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_read ON core_{table} FOR SELECT USING (EXISTS (SELECT 1 FROM core_membership m WHERE m.division_id=core_{table}.division_id AND m.user_id=NULLIF(current_setting('app.user_id',true),'')::integer AND m.active AND m.role IN ('operator','reader','reviewer')));
CREATE POLICY tenant_insert ON core_{table} FOR INSERT WITH CHECK (EXISTS (SELECT 1 FROM core_membership m WHERE m.division_id=core_{table}.division_id AND m.user_id=NULLIF(current_setting('app.user_id',true),'')::integer AND m.active AND m.role IN ('operator','reviewer')));
CREATE POLICY tenant_update ON core_{table} FOR UPDATE USING (EXISTS (SELECT 1 FROM core_membership m WHERE m.division_id=core_{table}.division_id AND m.user_id=NULLIF(current_setting('app.user_id',true),'')::integer AND m.active AND m.role IN ('operator','reviewer')));
'''
for table,condition in [('decisionversion','EXISTS (SELECT 1 FROM core_decision d WHERE d.id=decision_id)'),('signature','EXISTS (SELECT 1 FROM core_decisionversion v WHERE v.id=version_id)'),('line','EXISTS (SELECT 1 FROM core_journal j WHERE j.id=journal_id)')]:
    SQL+=f'ALTER TABLE core_{table} ENABLE ROW LEVEL SECURITY; CREATE POLICY scoped_read ON core_{table} FOR SELECT USING ({condition}); CREATE POLICY scoped_insert ON core_{table} FOR INSERT WITH CHECK ({condition}'+(" AND user_id=NULLIF(current_setting('app.user_id',true),'')::integer" if table=='signature' else '')+');\n'
# Cross-division references must also be rejected at the database boundary.
for table,field,parent in [('execution','decision_id','decision'),('journal','decision_id','decision'),('stock','division_id','division'),('movement','stock_id','stock'),('movement','decision_id','decision'),('openitem','decision_id','decision'),('contract','internal_decision_id','decision'),('contract','evidence_id','document'),('document','replaces_id','document')]:
    if table=='stock': continue
    name=f'plastics_scope_{table}_{field}'
    SQL+=f'''CREATE FUNCTION {name}() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
 IF NEW.{field} IS NOT NULL AND NOT EXISTS (SELECT 1 FROM core_{parent} WHERE id=NEW.{field} AND division_id=NEW.division_id) THEN RAISE EXCEPTION 'Cross-division reference rejected'; END IF; RETURN NEW; END $$;
 CREATE TRIGGER {name} BEFORE INSERT OR UPDATE ON core_{table} FOR EACH ROW EXECUTE FUNCTION {name}();\n'''
class Migration(migrations.Migration):
    dependencies=[('core','0001_initial')]
    operations=[migrations.RunSQL(SQL)]
