from django.db import migrations

SQL=r'''
CREATE POLICY manufacturing_update ON core_invoiceline FOR UPDATE USING (
  EXISTS (SELECT 1 FROM core_salesinvoice p JOIN core_membership m ON m.division_id=p.division_id
          WHERE p.id=core_invoiceline.invoice_id AND m.user_id=NULLIF(current_setting('app.user_id',true),'')::integer
          AND m.active AND m.role='operator'));
DO $$ BEGIN
 IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='plastics_app') THEN
  GRANT SELECT, INSERT, UPDATE ON core_product,core_mold,core_productionbatch,core_salesinvoice,
    core_invoiceline,core_stockevent,core_workflowattachment,core_capitalcontribution,
    core_capitalrepayment,core_invoicecredit,core_cashaccount,core_reinvestmentplan TO plastics_app;
 END IF;
END $$;
'''
class Migration(migrations.Migration):
    dependencies=[('core','0018_workflowattachment_workflow_attachment_one_parent')]
    operations=[migrations.RunSQL(SQL,reverse_sql=migrations.RunSQL.noop)]
