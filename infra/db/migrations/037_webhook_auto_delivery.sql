-- Stage 3: post-call webhooks deliver automatically unless the review policy
-- flagged the call. A delivery for an unflagged result has no review request,
-- so review_id becomes optional. Flagged results still require an approved
-- review (enforced in the repository before a delivery row is written).
-- Additive: existing rows keep their review_id; the composite foreign key
-- still applies whenever review_id is present (MATCH SIMPLE).
ALTER TABLE webhook_deliveries ALTER COLUMN review_id DROP NOT NULL;
