from django.db import migrations

SQL='''CREATE TRIGGER manufacturing_cash_account_immutable BEFORE UPDATE OR DELETE ON core_cashaccount FOR EACH ROW EXECUTE FUNCTION manufacturing_immutable();'''

class Migration(migrations.Migration):
    dependencies=[('core','0022_remove_invoicecredit_invoice_credit_positive_and_more')]
    operations=[migrations.RunSQL(SQL,reverse_sql=migrations.RunSQL.noop)]
