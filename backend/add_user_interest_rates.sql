-- Add interest rate columns to users table
-- This migration adds mortgage_interest_rate and loc_interest_rate columns

-- 1. Add mortgage_interest_rate column (30-year mortgage rate as decimal)
ALTER TABLE users 
ADD COLUMN IF NOT EXISTS mortgage_interest_rate NUMERIC(5, 4);

COMMENT ON COLUMN users.mortgage_interest_rate IS '30-year mortgage interest rate as decimal (e.g., 0.0700 for 7%)';

-- 2. Add loc_interest_rate column (Line of Credit rate as decimal)
ALTER TABLE users 
ADD COLUMN IF NOT EXISTS loc_interest_rate NUMERIC(5, 4);

COMMENT ON COLUMN users.loc_interest_rate IS 'Line of Credit interest rate as decimal (e.g., 0.0700 for 7%)';

-- 3. Set default values for existing users (optional - can be NULL)
-- If you want to set a default for existing users, uncomment and adjust:
-- UPDATE users SET mortgage_interest_rate = 0.07 WHERE mortgage_interest_rate IS NULL;
-- UPDATE users SET loc_interest_rate = 0.07 WHERE loc_interest_rate IS NULL;

-- Note: Both columns are nullable to allow users to set their own rates

