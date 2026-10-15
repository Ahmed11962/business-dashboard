from django.db import migrations
SQL=''
for table in ('transactionrevision','decisionvote','decisioncomment','documentlink','savedscenario','cashopening'):
    SQL+=f'CREATE TRIGGER immutable_simple_{table} BEFORE UPDATE OR DELETE ON core_{table} FOR EACH ROW EXECUTE FUNCTION plastics_immutable();\n'
SQL+='''
CREATE FUNCTION simple_decision_protect() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF ROW(NEW.title,NEW.description,NEW.estimated_cost,NEW.expected_benefit,NEW.risks,NEW.scenario_id,NEW.required_approvals,NEW.created_by_id,NEW.division_id)
 IS DISTINCT FROM ROW(OLD.title,OLD.description,OLD.estimated_cost,OLD.expected_benefit,OLD.risks,OLD.scenario_id,OLD.required_approvals,OLD.created_by_id,OLD.division_id)
 THEN RAISE EXCEPTION 'Proposal terms cannot change after creation'; END IF;
 IF NEW.status='approved' AND (SELECT count(*) FROM core_decisionvote WHERE decision_id=NEW.id AND choice='approve') < NEW.required_approvals THEN RAISE EXCEPTION 'Insufficient independent approvals'; END IF;
 IF NEW.status='rejected' AND NOT EXISTS (SELECT 1 FROM core_decisionvote WHERE decision_id=NEW.id AND choice='reject') THEN RAISE EXCEPTION 'A rejection vote is required'; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER simple_proposal_protect BEFORE UPDATE ON core_simpledecision FOR EACH ROW EXECUTE FUNCTION simple_decision_protect();
'''
class Migration(migrations.Migration):
    dependencies=[('core','0009_simple_security')]
    operations=[migrations.RunSQL(SQL,reverse_sql=migrations.RunSQL.noop)]
