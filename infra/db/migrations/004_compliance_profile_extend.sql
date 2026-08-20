-- UCVE Compliance Profile Extensions Migration
-- Migration: 004_compliance_profile_extend.sql
-- Description: Extends tenant_compliance_profile with BAA timestamp, lawful basis, and JSONB policy overrides.

ALTER TABLE tenant_compliance_profile
    ADD COLUMN IF NOT EXISTS lawful_basis VARCHAR(64) NOT NULL DEFAULT 'consent',
    ADD COLUMN IF NOT EXISTS policy_overrides JSONB NOT NULL DEFAULT '{}'::jsonb;
