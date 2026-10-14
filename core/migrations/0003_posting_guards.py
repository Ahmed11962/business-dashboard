from django.db import migrations
SQL=r'''
CREATE FUNCTION plastics_posting_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE current_num integer; state text; approved_count integer; required_users jsonb; v_id bigint; hash text; cutoff date; demo boolean;
BEGIN
 SELECT current_version,status INTO current_num,state FROM core_decision WHERE id=NEW.decision_id AND division_id=NEW.division_id;
 IF state <> 'authorized' OR state IS NULL THEN RAISE EXCEPTION 'Journal requires an authorized decision'; END IF;
 SELECT id,digest,payload->'approvers' INTO v_id,hash,required_users FROM core_decisionversion WHERE decision_id=NEW.decision_id AND number=current_num;
 SELECT COUNT(DISTINCT s.user_id) INTO approved_count FROM core_signature s JOIN core_membership m ON m.user_id=s.user_id AND m.division_id=NEW.division_id AND m.active AND m.role='operator'
 WHERE s.version_id=v_id AND s.digest=hash AND required_users @> to_jsonb(s.user_id);
 IF approved_count<>2 OR jsonb_array_length(required_users)<>2 THEN RAISE EXCEPTION 'Two distinct current operator signatures required'; END IF;
 SELECT closed_through,is_demo INTO cutoff,demo FROM core_division WHERE id=NEW.division_id;
 IF NOT demo THEN RAISE EXCEPTION 'Live financial posting locked pending validation'; END IF;
 IF cutoff IS NOT NULL AND NEW.date<=cutoff THEN RAISE EXCEPTION 'Accounting period closed'; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER guarded_posting BEFORE INSERT ON core_journal FOR EACH ROW EXECUTE FUNCTION plastics_posting_guard();
CREATE FUNCTION plastics_execution_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF NOT EXISTS (SELECT 1 FROM core_decisionversion v JOIN core_decision d ON d.id=v.decision_id WHERE v.id=NEW.version_id AND d.id=NEW.decision_id AND d.division_id=NEW.division_id AND v.number=d.current_version AND d.status='authorized') THEN RAISE EXCEPTION 'Execution version or scope mismatch'; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER guarded_execution BEFORE INSERT ON core_execution FOR EACH ROW EXECUTE FUNCTION plastics_execution_guard();
CREATE FUNCTION plastics_bank_scope() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF NEW.matched_line_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM core_line l JOIN core_journal j ON j.id=l.journal_id WHERE l.id=NEW.matched_line_id AND j.division_id=NEW.division_id AND l.account='bank' AND l.debit-l.credit=NEW.amount) THEN RAISE EXCEPTION 'Bank match must have same division and exact amount'; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER guarded_bank_match BEFORE INSERT OR UPDATE ON core_bankrow FOR EACH ROW EXECUTE FUNCTION plastics_bank_scope();
'''
class Migration(migrations.Migration):
    dependencies=[('core','0002_integrity')]
    operations=[migrations.RunSQL(SQL)]
