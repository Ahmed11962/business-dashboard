from django.db import migrations

SQL=r'''
CREATE FUNCTION manufacturing_cross_workspace() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE d uuid;
BEGIN
 IF TG_TABLE_NAME='core_mold' THEN
   IF NOT EXISTS (SELECT 1 FROM core_product WHERE id=NEW.product_id AND division_id=NEW.division_id) THEN RAISE EXCEPTION 'Cross-workspace mold product'; END IF;
 ELSIF TG_TABLE_NAME='core_productionbatch' THEN
   IF NOT EXISTS (SELECT 1 FROM core_mold WHERE id=NEW.mold_id AND division_id=NEW.division_id) THEN RAISE EXCEPTION 'Cross-workspace batch mold'; END IF;
 ELSIF TG_TABLE_NAME='core_invoiceline' THEN
   SELECT division_id INTO d FROM core_salesinvoice WHERE id=NEW.invoice_id;
   IF NOT EXISTS (SELECT 1 FROM core_product WHERE id=NEW.product_id AND division_id=d) THEN RAISE EXCEPTION 'Cross-workspace invoice product'; END IF;
 ELSIF TG_TABLE_NAME='core_stockevent' THEN
   IF NOT EXISTS (SELECT 1 FROM core_product WHERE id=NEW.product_id AND division_id=NEW.division_id) THEN RAISE EXCEPTION 'Cross-workspace stock product'; END IF;
   IF NEW.batch_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM core_productionbatch WHERE id=NEW.batch_id AND division_id=NEW.division_id) THEN RAISE EXCEPTION 'Cross-workspace receipt'; END IF;
   IF NEW.invoice_line_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM core_invoiceline l JOIN core_salesinvoice i ON i.id=l.invoice_id WHERE l.id=NEW.invoice_line_id AND i.division_id=NEW.division_id) THEN RAISE EXCEPTION 'Cross-workspace dispatch'; END IF;
 ELSIF TG_TABLE_NAME='core_workflowattachment' THEN
   SELECT division_id INTO d FROM core_document WHERE id=NEW.document_id;
   IF NEW.mold_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM core_mold WHERE id=NEW.mold_id AND division_id=d) THEN RAISE EXCEPTION 'Cross-workspace mold file'; END IF;
   IF NEW.product_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM core_product WHERE id=NEW.product_id AND division_id=d) THEN RAISE EXCEPTION 'Cross-workspace product file'; END IF;
   IF NEW.batch_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM core_productionbatch WHERE id=NEW.batch_id AND division_id=d) THEN RAISE EXCEPTION 'Cross-workspace batch file'; END IF;
   IF NEW.invoice_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM core_salesinvoice WHERE id=NEW.invoice_id AND division_id=d) THEN RAISE EXCEPTION 'Cross-workspace invoice file'; END IF;
 ELSIF TG_TABLE_NAME='core_financetransaction' THEN
   IF NEW.mold_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM core_mold WHERE id=NEW.mold_id AND division_id=NEW.division_id) THEN RAISE EXCEPTION 'Cross-workspace mold payment'; END IF;
   IF NEW.batch_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM core_productionbatch WHERE id=NEW.batch_id AND division_id=NEW.division_id) THEN RAISE EXCEPTION 'Cross-workspace production payment'; END IF;
   IF NEW.invoice_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM core_salesinvoice WHERE id=NEW.invoice_id AND division_id=NEW.division_id) THEN RAISE EXCEPTION 'Cross-workspace invoice payment'; END IF;
   IF NEW.account_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM core_cashaccount WHERE id=NEW.account_id AND division_id=NEW.division_id) THEN RAISE EXCEPTION 'Cross-workspace account'; END IF;
 ELSIF TG_TABLE_NAME='core_capitalcontribution' THEN
   IF NOT EXISTS (SELECT 1 FROM core_financetransaction WHERE id=NEW.transaction_id AND division_id=NEW.division_id) THEN RAISE EXCEPTION 'Cross-workspace capital'; END IF;
 END IF;
 RETURN NEW;
END $$;
'''
for table in ('mold','productionbatch','invoiceline','stockevent','workflowattachment','financetransaction','capitalcontribution'):
    SQL+=f'CREATE TRIGGER manufacturing_scope_{table} BEFORE INSERT OR UPDATE ON core_{table} FOR EACH ROW EXECUTE FUNCTION manufacturing_cross_workspace();\n'
for table in ('product','mold','productionbatch','salesinvoice','stockevent','capitalcontribution','cashaccount','reinvestmentplan'):
    SQL+=f'''ALTER TABLE core_{table} ENABLE ROW LEVEL SECURITY;
CREATE POLICY manufacturing_read ON core_{table} FOR SELECT USING (EXISTS (SELECT 1 FROM core_membership m WHERE m.division_id=core_{table}.division_id AND m.user_id=NULLIF(current_setting('app.user_id',true),'')::integer AND m.active AND m.role IN ('operator','reader','reviewer')));
CREATE POLICY manufacturing_insert ON core_{table} FOR INSERT WITH CHECK (EXISTS (SELECT 1 FROM core_membership m WHERE m.division_id=core_{table}.division_id AND m.user_id=NULLIF(current_setting('app.user_id',true),'')::integer AND m.active AND m.role='operator'));
CREATE POLICY manufacturing_update ON core_{table} FOR UPDATE USING (EXISTS (SELECT 1 FROM core_membership m WHERE m.division_id=core_{table}.division_id AND m.user_id=NULLIF(current_setting('app.user_id',true),'')::integer AND m.active AND m.role='operator'));
'''
for table,parent,fk in [('invoiceline','salesinvoice','invoice_id'),('workflowattachment','document','document_id')]:
    SQL+=f'''ALTER TABLE core_{table} ENABLE ROW LEVEL SECURITY;
CREATE POLICY manufacturing_read ON core_{table} FOR SELECT USING (EXISTS (SELECT 1 FROM core_{parent} p JOIN core_membership m ON m.division_id=p.division_id WHERE p.id=core_{table}.{fk} AND m.user_id=NULLIF(current_setting('app.user_id',true),'')::integer AND m.active AND m.role IN ('operator','reader','reviewer')));
CREATE POLICY manufacturing_insert ON core_{table} FOR INSERT WITH CHECK (EXISTS (SELECT 1 FROM core_{parent} p JOIN core_membership m ON m.division_id=p.division_id WHERE p.id=core_{table}.{fk} AND m.user_id=NULLIF(current_setting('app.user_id',true),'')::integer AND m.active AND m.role='operator'));
'''

class Migration(migrations.Migration):
    dependencies=[('core','0013_remove_stockevent_stock_event_nonzero')]
    operations=[migrations.RunSQL(SQL,reverse_sql=migrations.RunSQL.noop)]
