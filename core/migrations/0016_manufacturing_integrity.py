from django.db import migrations

SQL=r'''
CREATE OR REPLACE FUNCTION manufacturing_cross_workspace() RETURNS trigger LANGUAGE plpgsql AS $$
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
   IF NEW.reverses_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM core_stockevent WHERE id=NEW.reverses_id AND division_id=NEW.division_id) THEN RAISE EXCEPTION 'Cross-workspace return'; END IF;
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
   IF NEW.reinvestment_plan_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM core_reinvestmentplan WHERE id=NEW.reinvestment_plan_id AND division_id=NEW.division_id) THEN RAISE EXCEPTION 'Cross-workspace reinvestment'; END IF;
 ELSIF TG_TABLE_NAME='core_capitalcontribution' THEN
   IF NOT EXISTS (SELECT 1 FROM core_financetransaction WHERE id=NEW.transaction_id AND division_id=NEW.division_id) THEN RAISE EXCEPTION 'Cross-workspace capital'; END IF;
 ELSIF TG_TABLE_NAME='core_capitalrepayment' THEN
   IF NOT EXISTS (SELECT 1 FROM core_financetransaction WHERE id=NEW.transaction_id AND division_id=NEW.division_id) OR NOT EXISTS (SELECT 1 FROM core_capitalcontribution WHERE id=NEW.contribution_id AND division_id=NEW.division_id) THEN RAISE EXCEPTION 'Cross-workspace repayment'; END IF;
 ELSIF TG_TABLE_NAME='core_invoicecredit' THEN
   IF NOT EXISTS (SELECT 1 FROM core_salesinvoice WHERE id=NEW.invoice_id AND division_id=NEW.division_id) THEN RAISE EXCEPTION 'Cross-workspace credit'; END IF;
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER manufacturing_scope_capitalrepayment BEFORE INSERT OR UPDATE ON core_capitalrepayment FOR EACH ROW EXECUTE FUNCTION manufacturing_cross_workspace();
CREATE TRIGGER manufacturing_scope_invoicecredit BEFORE INSERT OR UPDATE ON core_invoicecredit FOR EACH ROW EXECUTE FUNCTION manufacturing_cross_workspace();
CREATE FUNCTION manufacturing_immutable() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'This history is append-only'; END $$;
CREATE TRIGGER manufacturing_stock_immutable BEFORE UPDATE OR DELETE ON core_stockevent FOR EACH ROW EXECUTE FUNCTION manufacturing_immutable();
CREATE TRIGGER manufacturing_credit_immutable BEFORE UPDATE OR DELETE ON core_invoicecredit FOR EACH ROW EXECUTE FUNCTION manufacturing_immutable();
CREATE TRIGGER manufacturing_repayment_immutable BEFORE UPDATE OR DELETE ON core_capitalrepayment FOR EACH ROW EXECUTE FUNCTION manufacturing_immutable();
CREATE FUNCTION manufacturing_payment_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF OLD.mold_id IS NOT NULL OR OLD.batch_id IS NOT NULL OR OLD.invoice_id IS NOT NULL OR EXISTS (SELECT 1 FROM core_capitalcontribution WHERE transaction_id=OLD.id) OR EXISTS (SELECT 1 FROM core_capitalrepayment WHERE transaction_id=OLD.id) THEN
   IF OLD.amount IS DISTINCT FROM NEW.amount OR OLD.direction IS DISTINCT FROM NEW.direction OR OLD.reference IS DISTINCT FROM NEW.reference OR OLD.mold_id IS DISTINCT FROM NEW.mold_id OR OLD.batch_id IS DISTINCT FROM NEW.batch_id OR OLD.invoice_id IS DISTINCT FROM NEW.invoice_id OR OLD.account_id IS DISTINCT FROM NEW.account_id OR OLD.date IS DISTINCT FROM NEW.date THEN RAISE EXCEPTION 'Linked payment history is immutable; enter a correction'; END IF;
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER manufacturing_payment_history BEFORE UPDATE ON core_financetransaction FOR EACH ROW EXECUTE FUNCTION manufacturing_payment_immutable();
'''
for table in ('capitalrepayment','invoicecredit'):
    SQL+=f'''ALTER TABLE core_{table} ENABLE ROW LEVEL SECURITY;
CREATE POLICY manufacturing_read ON core_{table} FOR SELECT USING (EXISTS (SELECT 1 FROM core_membership m WHERE m.division_id=core_{table}.division_id AND m.user_id=NULLIF(current_setting('app.user_id',true),'')::integer AND m.active AND m.role IN ('operator','reader','reviewer')));
CREATE POLICY manufacturing_insert ON core_{table} FOR INSERT WITH CHECK (EXISTS (SELECT 1 FROM core_membership m WHERE m.division_id=core_{table}.division_id AND m.user_id=NULLIF(current_setting('app.user_id',true),'')::integer AND m.active AND m.role='operator'));
'''

class Migration(migrations.Migration):
    dependencies=[('core','0015_financetransaction_reinvestment_plan_and_more')]
    operations=[migrations.RunSQL(SQL,reverse_sql=migrations.RunSQL.noop)]
