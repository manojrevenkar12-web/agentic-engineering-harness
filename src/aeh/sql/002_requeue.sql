-- Attempts that failed because of a harness fault can be run again. Their spend stays counted:
-- 'reverse' takes it off the attempt's settled cost, 'requeued' adds it to the attempt's abandoned spend.
ALTER TABLE aeh.spend DROP CONSTRAINT IF EXISTS spend_kind_check;
ALTER TABLE aeh.spend ADD CONSTRAINT spend_kind_check CHECK (kind IN ('reserve', 'settle', 'release', 'abandon', 'reverse', 'requeued'));
