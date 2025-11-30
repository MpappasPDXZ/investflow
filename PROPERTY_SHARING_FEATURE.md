# Property Sharing Feature

## Overview
The property sharing feature allows users to share their properties with friends in a bidirectional manner. When User A adds User B's email, both users can see each other's properties.

## Architecture

### Backend (Iceberg-based)

#### Database Schema
- **user_shares** table (Iceberg table in `investflow` namespace)
  - `id` (string): Unique identifier
  - `user_id` (string): User who created the share
  - `shared_email` (string): Email of the user to share with
  - `created_at` (timestamp): When the share was created
  - `updated_at` (timestamp): Last update timestamp
  - Unique constraint on (user_id, shared_email)

#### API Endpoints

1. **POST /api/v1/users/me/shares**
   - Create a new share relationship
   - Request: `{ "shared_email": "friend@example.com" }`
   - Response: UserShare object
   - Validates: Cannot share with yourself, no duplicate shares

2. **GET /api/v1/users/me/shares**
   - Get list of users you're sharing with (emails you added)
   - Response: Array of UserShare objects

3. **GET /api/v1/users/me/shares/shared-with-me**
   - Get list of users who are sharing with you (users who added your email)
   - Response: Array of UserShare objects

4. **DELETE /api/v1/users/me/shares/{share_id}**
   - Remove a share relationship
   - Only the creator can delete their own share

5. **GET /api/v1/users/shared**
   - Get list of users with active bidirectional sharing
   - Returns full user profiles (excluding password_hash)
   - Uses `sharing_utils.get_shared_user_ids()` for logic

#### Sharing Logic (sharing_utils.py)

**Bidirectional Sharing:**
- Uses Iceberg tables (no SQLAlchemy)
- `get_shared_user_ids(user_id, user_email)`: Returns list of user IDs with bidirectional access
- `user_has_property_access(property_user_id, current_user_id, current_user_email)`: Checks if user can access a property

**Property Access Rules:**
1. User owns the property, OR
2. User has bidirectional share with property owner:
   - Current user added property owner's email, OR
   - Property owner added current user's email

#### Integration with Properties API

The properties API (`properties.py`) integrates sharing:

- **GET /api/v1/properties**: Lists user's properties + shared properties
- **GET /api/v1/properties/{id}**: Checks ownership or shared access
- **PUT /api/v1/properties/{id}**: Allows updates if owner or shared access
- **DELETE /api/v1/properties/{id}**: Only owner can delete (shared users cannot)

### Frontend

#### TypeScript Types (`lib/types.ts`)
```typescript
interface UserShare {
  id: string;
  user_id: string;
  shared_email: string;
  created_at: string;
  updated_at: string;
}

interface SharedUser {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
}
```

#### Custom Hook (`lib/hooks/use-shares.ts`)
- `useShares()`: Manages all sharing operations
- State: shares, sharedWithMe, sharedUsers, loading, error
- Methods: createShare, deleteShare, fetchShares, fetchSharedWithMe, fetchSharedUsers

#### UI Components (`app/(dashboard)/profile/page.tsx`)

**Property Sharing Card** includes:
1. **Add Share Form**: Input email and add friend
2. **People I'm Sharing With**: List of emails you added with delete buttons
3. **People Sharing With Me**: List of users who added your email
4. **Active Connections**: Users with bidirectional sharing (can see their properties)

## User Experience

### Adding a Friend
1. Navigate to Profile page
2. Enter friend's email in "Add Friend's Email" field
3. Click "Add" button
4. Friend appears in "People I'm Sharing With" section

### Viewing Shared Properties
- Once bidirectional sharing is established (both users add each other), both users see:
  - Their own properties
  - Friend's properties in the properties list
  - Full access to view and edit shared properties

### Removing a Share
1. Navigate to Profile page
2. Find the email in "People I'm Sharing With"
3. Click trash icon
4. Confirm deletion
5. Sharing is removed (properties no longer visible)

## Data Flow

### Creating a Share
```
User → Profile UI → useShares.createShare() 
→ POST /users/me/shares 
→ Iceberg: append to user_shares table
→ Refresh shares list
```

### Viewing Properties with Sharing
```
User → Properties Page
→ GET /properties
→ Backend:
  1. Read properties table (Iceberg)
  2. Get shared_user_ids from user_shares table (Iceberg)
  3. Filter: (user_id = current_user) OR (user_id IN shared_user_ids)
  4. Return combined list
→ Frontend: Display all accessible properties
```

## Implementation Notes

### Iceberg-Only Approach
- All data stored in Iceberg tables (no SQLAlchemy ORM)
- Direct read/write operations using PyIceberg
- Tables: `investflow.user_shares`, `investflow.users`, `investflow.properties`

### Security
- User can only create/delete their own shares
- Property access validated on every request
- Email validation prevents self-sharing
- Unique constraint prevents duplicate shares

### Performance
- Indexes on user_id and shared_email (PostgreSQL catalog)
- Efficient Iceberg table scans using pandas filtering
- Caching opportunities: shared_user_ids can be cached per user

## Testing

To test the sharing feature:

1. **Create two users:**
   - User A: user1@example.com
   - User B: user2@example.com

2. **User A adds User B:**
   - Login as User A
   - Go to Profile
   - Add user2@example.com
   - Verify User B appears in "People I'm Sharing With"

3. **User B adds User A:**
   - Login as User B
   - Go to Profile
   - Add user1@example.com
   - Verify User A appears in "People I'm Sharing With"

4. **Verify Bidirectional Access:**
   - Both users should see "Active Connections" with 1 user
   - Both users should see each other's properties in Properties list

5. **Test Property Access:**
   - Create properties as both users
   - Verify both can see all properties
   - Verify both can view/edit shared properties
   - Verify only owner can delete properties

6. **Remove Share:**
   - As User A, delete the share with User B
   - Verify properties are no longer visible to each other

