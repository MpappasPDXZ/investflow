-- Migration: Add unit_id to expenses table
-- This allows expenses to be associated with specific units in multi-unit properties

-- Add unit_id column
ALTER TABLE expenses 
ADD COLUMN unit_id UUID REFERENCES units(id) ON DELETE CASCADE;

-- Create index for unit queries
CREATE INDEX idx_expenses_unit ON expenses(unit_id);

-- Add composite index for property + unit queries
CREATE INDEX idx_expenses_property_unit ON expenses(property_id, unit_id);

-- Add comment
COMMENT ON COLUMN expenses.unit_id IS 'Optional unit ID for multi-unit properties';

-- Show updated schema
\d expenses;





