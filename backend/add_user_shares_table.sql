-- Create user_shares table for bidirectional property sharing
-- When User A adds User B's email, both users can see each other's properties

-- 1. Create user_shares table
CREATE TABLE IF NOT EXISTS user_shares (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,  -- The user who added the share
    shared_email TEXT NOT NULL,  -- The email they're sharing with (bidirectional)
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,
    UNIQUE(user_id, shared_email)
);

-- 2. Add foreign key constraint
ALTER TABLE user_shares 
ADD CONSTRAINT user_shares_user_id_fkey 
FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;

-- 3. Add index for faster lookups
CREATE INDEX IF NOT EXISTS user_shares_user_id_idx ON user_shares(user_id);
CREATE INDEX IF NOT EXISTS user_shares_shared_email_idx ON user_shares(shared_email);

-- 4. Add comments
COMMENT ON TABLE user_shares IS 'Bidirectional property sharing - when A adds B, both can see each others properties';
COMMENT ON COLUMN user_shares.user_id IS 'User who created the share';
COMMENT ON COLUMN user_shares.shared_email IS 'Email of the user to share with (bidirectional)';

