from django.db import migrations

SQL = r'''
CREATE FUNCTION simple_cross_workspace() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE division_value uuid;
BEGIN
 IF TG_TABLE_NAME='core_financetransaction' THEN
   division_value:=NEW.division_id;
   IF NEW.settles_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM core_financetransaction WHERE id=NEW.settles_id AND division_id=division_value) THEN RAISE EXCEPTION 'Cross-workspace payment'; END IF;
   IF NEW.refund_of_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM core_financetransaction WHERE id=NEW.refund_of_id AND division_id=division_value) THEN RAISE EXCEPTION 'Cross-workspace refund'; END IF;
   IF NEW.decision_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM core_simpledecision WHERE id=NEW.decision_id AND division_id=division_value) THEN RAISE EXCEPTION 'Cross-workspace decision'; END IF;
 ELSIF TG_TABLE_NAME='core_simpledecision' THEN
   IF NEW.scenario_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM core_savedscenario WHERE id=NEW.scenario_id AND division_id=NEW.division_id) THEN RAISE EXCEPTION 'Cross-workspace scenario'; END IF;
 ELSIF TG_TABLE_NAME='core_documentlink' THEN
   SELECT division_id INTO division_value FROM core_document WHERE id=NEW.document_id;
   IF NEW.transaction_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM core_financetransaction WHERE id=NEW.transaction_id AND division_id=division_value) THEN RAISE EXCEPTION 'Cross-workspace attachment'; END IF;
   IF NEW.decision_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM core_simpledecision WHERE id=NEW.decision_id AND division_id=division_value) THEN RAISE EXCEPTION 'Cross-workspace attachment'; END IF;
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER simple_scope_transaction BEFORE INSERT OR UPDATE ON core_financetransaction FOR EACH ROW EXECUTE FUNCTION simple_cross_workspace();
CREATE TRIGGER simple_scope_decision BEFORE INSERT OR UPDATE ON core_simpledecision FOR EACH ROW EXECUTE FUNCTION simple_cross_workspace();
CREATE TRIGGER simple_scope_document BEFORE INSERT OR UPDATE ON core_documentlink FOR EACH ROW EXECUTE FUNCTION simple_cross_workspace();
'''
for table in ('financetransaction','savedscenario','simpledecision','cashopening'):
    SQL+=f'''ALTER TABLE core_{table} ENABLE ROW LEVEL SECURITY;
CREATE POLICY simple_read ON core_{table} FOR SELECT USING (EXISTS (SELECT 1 FROM core_membership m WHERE m.division_id=core_{table}.division_id AND m.user_id=NULLIF(current_setting('app.user_id',true),'')::integer AND m.active AND m.role IN ('operator','reader','reviewer')));
CREATE POLICY simple_insert ON core_{table} FOR INSERT WITH CHECK (EXISTS (SELECT 1 FROM core_membership m WHERE m.division_id=core_{table}.division_id AND m.user_id=NULLIF(current_setting('app.user_id',true),'')::integer AND m.active AND m.role='operator'));
CREATE POLICY simple_update ON core_{table} FOR UPDATE USING (EXISTS (SELECT 1 FROM core_membership m WHERE m.division_id=core_{table}.division_id AND m.user_id=NULLIF(current_setting('app.user_id',true),'')::integer AND m.active AND m.role='operator'));
'''
for table,parent,fk in [('transactionrevision','financetransaction','transaction_id'),('documentlink','document','document_id'),('decisionvote','simpledecision','decision_id'),('decisioncomment','simpledecision','decision_id')]:
    SQL+=f'''ALTER TABLE core_{table} ENABLE ROW LEVEL SECURITY;
CREATE POLICY simple_read ON core_{table} FOR SELECT USING (EXISTS (SELECT 1 FROM core_{parent} p JOIN core_membership m ON m.division_id=p.division_id WHERE p.id=core_{table}.{fk} AND m.user_id=NULLIF(current_setting('app.user_id',true),'')::integer AND m.active AND m.role IN ('operator','reader','reviewer')));
CREATE POLICY simple_insert ON core_{table} FOR INSERT WITH CHECK (EXISTS (SELECT 1 FROM core_{parent} p JOIN core_membership m ON m.division_id=p.division_id WHERE p.id=core_{table}.{fk} AND m.user_id=NULLIF(current_setting('app.user_id',true),'')::integer AND m.active AND m.role='operator')'''+(" AND user_id=NULLIF(current_setting('app.user_id',true),'')::integer" if table in ('decisionvote','decisioncomment') else '')+''');
'''

class Migration(migrations.Migration):
    dependencies=[('core','0008_remove_documentlink_document_link_one_parent_and_more')]
    operations=[migrations.RunSQL(SQL,reverse_sql=migrations.RunSQL.noop)]
