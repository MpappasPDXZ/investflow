"""
CDC-based authentication cache stored as Parquet in ADLS.

This service provides fast O(1) lookups for:
- User authentication (login/register)
- User profiles
- Sharing permission resolution

The cache is stored as Parquet files in ADLS and loaded into memory on startup.
Inline CDC updates keep the cache in sync after mutations.
"""
import io
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from typing import Optional, Dict, List, Set, Any
from datetime import datetime
from azure.storage.blob import BlobServiceClient
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

NAMESPACE = ("investflow",)


class AuthCacheService:
    """
    Unified CDC cache for authentication and sharing.
    Caches: users + user_shares tables as Parquet in ADLS.
    Provides O(1) lookups for login, profile, and sharing resolution.
    """
    
    # ADLS paths - container is configurable via CDC_CACHE_CONTAINER_NAME env var
    # If not set, falls back to AZURE_STORAGE_CONTAINER_NAME (documents)
    USERS_CACHE_PATH = "cdc/users/users_current.parquet"
    SHARES_CACHE_PATH = "cdc/shares/user_shares_current.parquet"
    
    @property
    def cache_container(self) -> str:
        """Get the container name for CDC cache (configurable)"""
        if settings.CDC_CACHE_CONTAINER_NAME:
            return settings.CDC_CACHE_CONTAINER_NAME
        return settings.AZURE_STORAGE_CONTAINER_NAME or "documents"
    
    # In-memory cache TTL
    CACHE_TTL_SECONDS = 300  # 5 minutes
    
    def __init__(self):
        # In-memory indexes (rebuilt from parquet on load)
        self._email_to_user: Dict[str, Dict[str, Any]] = {}
        self._user_id_to_user: Dict[str, Dict[str, Any]] = {}
        self._shares_by_user: Dict[str, Set[str]] = {}  # user_id → set of shared_emails
        self._shares_by_email: Dict[str, Set[str]] = {}  # shared_email → set of user_ids
        
        # Cache metadata
        self._cache_loaded_at: Optional[datetime] = None
        self._initialized = False
        
        # Blob client (lazy init)
        self._blob_service: Optional[BlobServiceClient] = None
    
    def _get_blob_service(self) -> Optional[BlobServiceClient]:
        """Get or create Azure Blob client (lazy initialization)"""
        if self._blob_service is not None:
            return self._blob_service
        
        try:
            if settings.AZURE_STORAGE_CONNECTION_STRING:
                self._blob_service = BlobServiceClient.from_connection_string(
                    settings.AZURE_STORAGE_CONNECTION_STRING
                )
            elif settings.AZURE_STORAGE_ACCOUNT_NAME and settings.AZURE_STORAGE_ACCOUNT_KEY:
                conn_str = (
                    f"DefaultEndpointsProtocol=https;"
                    f"AccountName={settings.AZURE_STORAGE_ACCOUNT_NAME};"
                    f"AccountKey={settings.AZURE_STORAGE_ACCOUNT_KEY};"
                    f"EndpointSuffix=core.windows.net"
                )
                self._blob_service = BlobServiceClient.from_connection_string(conn_str)
            else:
                logger.warning("Azure Storage not configured, CDC cache will use Iceberg fallback")
                return None
            
            return self._blob_service
        except Exception as e:
            logger.error(f"Failed to initialize blob service: {e}")
            return None
    
    # ═══════════════════════════════════════════════════════════════════
    # INITIALIZATION & LOADING
    # ═══════════════════════════════════════════════════════════════════
    
    def initialize(self) -> bool:
        """
        Initialize the cache on startup.
        Tries to load from ADLS first, falls back to Iceberg sync.
        """
        if self._initialized:
            return True
        
        logger.info("Initializing auth cache...")
        
        # Try loading from ADLS parquet first (fast)
        if self._load_from_adls():
            logger.info(f"Auth cache loaded from ADLS: {len(self._user_id_to_user)} users, {len(self._shares_by_user)} share records")
            self._initialized = True
            return True
        
        # Fall back to full Iceberg sync
        logger.info("ADLS cache not found, syncing from Iceberg...")
        if self.sync_from_iceberg():
            self._initialized = True
            return True
        
        logger.warning("Could not initialize auth cache, will use Iceberg fallback")
        return False
    
    def _load_from_adls(self) -> bool:
        """Load parquet caches from ADLS into memory indexes"""
        blob_service = self._get_blob_service()
        if blob_service is None:
            return False
        
        try:
            # Load users
            users_df = self._read_parquet_from_adls(self.USERS_CACHE_PATH)
            if users_df is None:
                return False
            
            # Load shares (may not exist yet)
            shares_df = self._read_parquet_from_adls(self.SHARES_CACHE_PATH)
            if shares_df is None:
                shares_df = pd.DataFrame()
            
            # Rebuild indexes
            self._rebuild_indexes(users_df, shares_df)
            self._cache_loaded_at = datetime.utcnow()
            
            return True
            
        except Exception as e:
            logger.error(f"Error loading from ADLS: {e}")
            return False
    
    def _read_parquet_from_adls(self, blob_path: str) -> Optional[pd.DataFrame]:
        """Read a parquet file from ADLS"""
        blob_service = self._get_blob_service()
        if blob_service is None:
            return None
        
        try:
            blob_client = blob_service.get_blob_client(
                container=self.cache_container,
                blob=blob_path
            )
            
            if not blob_client.exists():
                logger.debug(f"Cache file does not exist: {blob_path}")
                return None
            
            # Download and read parquet
            stream = io.BytesIO()
            blob_client.download_blob().readinto(stream)
            stream.seek(0)
            
            df = pq.read_table(stream).to_pandas()
            logger.debug(f"Loaded {len(df)} rows from {blob_path}")
            return df
            
        except Exception as e:
            logger.error(f"Error reading parquet from ADLS ({blob_path}): {e}")
            return None
    
    def _save_parquet_to_adls(self, df: pd.DataFrame, blob_path: str) -> bool:
        """Save a DataFrame as parquet to ADLS"""
        blob_service = self._get_blob_service()
        if blob_service is None:
            logger.warning("No blob service, skipping ADLS persist")
            return False
        
        try:
            # Ensure container exists
            container_client = blob_service.get_container_client(self.cache_container)
            if not container_client.exists():
                container_client.create_container()
                logger.info(f"Created container: {self.cache_container}")
            
            # Add CDC timestamp
            df = df.copy()
            df["_cdc_timestamp"] = pd.Timestamp.now()
            
            # Convert timestamps to microseconds (Parquet requirement)
            for col in df.columns:
                if pd.api.types.is_datetime64_any_dtype(df[col]):
                    df[col] = df[col].astype('datetime64[us]')
            
            # Convert to parquet bytes
            table = pa.Table.from_pandas(df, preserve_index=False)
            stream = io.BytesIO()
            pq.write_table(table, stream)
            stream.seek(0)
            
            # Upload to ADLS
            blob_client = blob_service.get_blob_client(
                container=self.cache_container,
                blob=blob_path
            )
            blob_client.upload_blob(stream, overwrite=True)
            
            logger.debug(f"Saved {len(df)} rows to {blob_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving parquet to ADLS ({blob_path}): {e}")
            return False
    
    def _rebuild_indexes(self, users_df: pd.DataFrame, shares_df: pd.DataFrame):
        """Rebuild in-memory indexes from DataFrames"""
        # Clear existing indexes
        self._email_to_user = {}
        self._user_id_to_user = {}
        self._shares_by_user = {}
        self._shares_by_email = {}
        
        # Build user indexes
        for _, row in users_df.iterrows():
            user_dict = row.to_dict()
            # Clean up any CDC columns
            user_dict.pop("_cdc_timestamp", None)
            
            email = user_dict.get("email")
            user_id = user_dict.get("id")
            
            if email:
                self._email_to_user[email] = user_dict
            if user_id:
                self._user_id_to_user[user_id] = user_dict
        
        # Build shares indexes
        if not shares_df.empty:
            for _, row in shares_df.iterrows():
                user_id = row.get("user_id")
                shared_email = row.get("shared_email")
                
                if user_id and shared_email:
                    # user_id → set of emails they shared with
                    if user_id not in self._shares_by_user:
                        self._shares_by_user[user_id] = set()
                    self._shares_by_user[user_id].add(shared_email)
                    
                    # shared_email → set of user_ids who shared with them
                    if shared_email not in self._shares_by_email:
                        self._shares_by_email[shared_email] = set()
                    self._shares_by_email[shared_email].add(user_id)
        
        logger.debug(f"Rebuilt indexes: {len(self._email_to_user)} users, {sum(len(v) for v in self._shares_by_user.values())} shares")
    
    # ═══════════════════════════════════════════════════════════════════
    # AUTHENTICATION METHODS (Fast login/register)
    # ═══════════════════════════════════════════════════════════════════
    
    def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """
        Fast lookup by email for login.
        O(1) dictionary lookup.
        """
        if not self._initialized:
            self.initialize()
        return self._email_to_user.get(email)
    
    def get_user_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Fast lookup by ID for profile.
        O(1) dictionary lookup.
        """
        if not self._initialized:
            self.initialize()
        return self._user_id_to_user.get(user_id)
    
    def email_exists(self, email: str) -> bool:
        """
        Check if email exists (for registration).
        O(1) dictionary lookup.
        """
        if not self._initialized:
            self.initialize()
        return email in self._email_to_user
    
    def get_users_by_ids(self, user_ids: List[str]) -> List[Dict[str, Any]]:
        """Get multiple users by ID (for shared users list)"""
        if not self._initialized:
            self.initialize()
        return [
            self._user_id_to_user[uid]
            for uid in user_ids
            if uid in self._user_id_to_user
        ]
    
    # ═══════════════════════════════════════════════════════════════════
    # SHARING METHODS (Fast permission resolution)
    # ═══════════════════════════════════════════════════════════════════
    
    def get_shared_user_ids(self, user_id: str, user_email: str) -> List[str]:
        """
        Get all user IDs with bidirectional sharing.
        Replaces sharing_utils.get_shared_user_ids() with O(1) lookups.
        
        Returns user IDs where:
        - Current user has shared with them (we added their email)
        - They have shared with us (they added our email)
        """
        if not self._initialized:
            self.initialize()
        
        shared_user_ids: Set[str] = set()
        
        # 1. Users I shared with (my user_id → their emails → their user_ids)
        emails_i_shared_with = self._shares_by_user.get(user_id, set())
        for shared_email in emails_i_shared_with:
            user = self._email_to_user.get(shared_email)
            if user:
                shared_user_ids.add(user["id"])
        
        # 2. Users who shared with me (their user_ids where they shared my email)
        users_who_shared = self._shares_by_email.get(user_email, set())
        shared_user_ids.update(users_who_shared)
        
        return list(shared_user_ids)
    
    def user_has_property_access(
        self,
        property_user_id: str,
        current_user_id: str,
        current_user_email: str
    ) -> bool:
        """
        Check if user can access a property.
        Replaces sharing_utils.user_has_property_access() with O(1) lookups.
        
        Access is granted if:
        1. User owns the property, OR
        2. User has share relationship with the property owner
        """
        if not self._initialized:
            self.initialize()
        
        # User owns the property
        if property_user_id == current_user_id:
            return True
        
        # Get property owner's email
        owner = self._user_id_to_user.get(property_user_id)
        if not owner:
            return False
        owner_email = owner.get("email")
        if not owner_email:
            return False
        
        # Did I share with the owner?
        my_shares = self._shares_by_user.get(current_user_id, set())
        if owner_email in my_shares:
            return True
        
        # Did the owner share with me?
        owner_shares = self._shares_by_user.get(property_user_id, set())
        if current_user_email in owner_shares:
            return True
        
        return False
    
    def get_shares_by_user(self, user_id: str) -> Set[str]:
        """Get all emails a user has shared with"""
        if not self._initialized:
            self.initialize()
        return self._shares_by_user.get(user_id, set()).copy()
    
    def get_shares_with_email(self, email: str) -> Set[str]:
        """Get all user IDs that have shared with an email"""
        if not self._initialized:
            self.initialize()
        return self._shares_by_email.get(email, set()).copy()
    
    # ═══════════════════════════════════════════════════════════════════
    # CDC SYNC METHODS (Full refresh)
    # ═══════════════════════════════════════════════════════════════════
    
    def sync_from_iceberg(self) -> bool:
        """
        Full refresh from Iceberg source tables.
        Called on startup if ADLS cache doesn't exist.
        """
        try:
            # Import here to avoid circular imports
            from app.core.iceberg import read_table, table_exists
            
            # Load users from Iceberg
            if not table_exists(NAMESPACE, "users"):
                logger.warning("Users table does not exist in Iceberg")
                return False
            
            users_df = read_table(NAMESPACE, "users")
            logger.info(f"Loaded {len(users_df)} users from Iceberg")
            
            # Load shares from Iceberg (may not exist)
            if table_exists(NAMESPACE, "user_shares"):
                shares_df = read_table(NAMESPACE, "user_shares")
                logger.info(f"Loaded {len(shares_df)} shares from Iceberg")
            else:
                shares_df = pd.DataFrame()
                logger.info("User shares table does not exist yet")
            
            # Save to ADLS
            self._save_parquet_to_adls(users_df, self.USERS_CACHE_PATH)
            if not shares_df.empty:
                self._save_parquet_to_adls(shares_df, self.SHARES_CACHE_PATH)
            
            # Rebuild indexes
            self._rebuild_indexes(users_df, shares_df)
            self._cache_loaded_at = datetime.utcnow()
            
            logger.info(f"Auth cache synced: {len(self._user_id_to_user)} users, {sum(len(v) for v in self._shares_by_user.values())} shares")
            return True
            
        except Exception as e:
            logger.error(f"Error syncing from Iceberg: {e}", exc_info=True)
            return False
    
    # ═══════════════════════════════════════════════════════════════════
    # INLINE CDC (called after mutations)
    # ═══════════════════════════════════════════════════════════════════
    
    def on_user_created(self, user_data: Dict[str, Any]):
        """
        Called after user registration.
        Updates in-memory indexes and persists to ADLS.
        """
        if not self._initialized:
            self.initialize()
        
        # Clean up any non-serializable types
        user_dict = self._clean_user_dict(user_data)
        
        # Update in-memory indexes
        email = user_dict.get("email")
        user_id = user_dict.get("id")
        
        if email:
            self._email_to_user[email] = user_dict
        if user_id:
            self._user_id_to_user[user_id] = user_dict
        
        logger.debug(f"Cache updated: user created {user_id}")
        
        # Persist to ADLS (async-friendly, non-blocking)
        self._persist_users_cache()
    
    def on_user_updated(self, user_data: Dict[str, Any]):
        """
        Called after user profile update.
        Updates in-memory indexes and persists to ADLS.
        """
        if not self._initialized:
            self.initialize()
        
        user_dict = self._clean_user_dict(user_data)
        user_id = user_dict.get("id")
        new_email = user_dict.get("email")
        
        # Handle email change
        old_user = self._user_id_to_user.get(user_id, {})
        old_email = old_user.get("email")
        if old_email and old_email != new_email:
            del self._email_to_user[old_email]
        
        # Update indexes
        if new_email:
            self._email_to_user[new_email] = user_dict
        if user_id:
            self._user_id_to_user[user_id] = user_dict
        
        logger.debug(f"Cache updated: user updated {user_id}")
        
        # Persist to ADLS
        self._persist_users_cache()
    
    def on_share_created(self, user_id: str, shared_email: str):
        """
        Called after share created.
        Updates in-memory indexes and persists to ADLS.
        """
        if not self._initialized:
            self.initialize()
        
        # Update user_id → shared_emails index
        if user_id not in self._shares_by_user:
            self._shares_by_user[user_id] = set()
        self._shares_by_user[user_id].add(shared_email)
        
        # Update shared_email → user_ids index
        if shared_email not in self._shares_by_email:
            self._shares_by_email[shared_email] = set()
        self._shares_by_email[shared_email].add(user_id)
        
        logger.debug(f"Cache updated: share created {user_id} → {shared_email}")
        
        # Persist to ADLS
        self._persist_shares_cache()
    
    def on_share_deleted(self, user_id: str, shared_email: str):
        """
        Called after share deleted.
        Updates in-memory indexes and persists to ADLS.
        """
        if not self._initialized:
            self.initialize()
        
        # Update user_id → shared_emails index
        if user_id in self._shares_by_user:
            self._shares_by_user[user_id].discard(shared_email)
            if not self._shares_by_user[user_id]:
                del self._shares_by_user[user_id]
        
        # Update shared_email → user_ids index
        if shared_email in self._shares_by_email:
            self._shares_by_email[shared_email].discard(user_id)
            if not self._shares_by_email[shared_email]:
                del self._shares_by_email[shared_email]
        
        logger.debug(f"Cache updated: share deleted {user_id} → {shared_email}")
        
        # Persist to ADLS
        self._persist_shares_cache()
    
    def _clean_user_dict(self, user_data: Dict[str, Any]) -> Dict[str, Any]:
        """Clean user dict for storage (handle pandas types, etc.)"""
        cleaned = {}
        for key, value in user_data.items():
            if key == "_cdc_timestamp":
                continue
            if pd.isna(value) if hasattr(pd, 'isna') else False:
                cleaned[key] = None
            elif hasattr(value, 'isoformat'):
                cleaned[key] = value
            else:
                cleaned[key] = value
        return cleaned
    
    def _persist_users_cache(self):
        """Persist current users cache to ADLS"""
        try:
            # Convert in-memory index to DataFrame
            users_list = list(self._user_id_to_user.values())
            if not users_list:
                return
            
            df = pd.DataFrame(users_list)
            self._save_parquet_to_adls(df, self.USERS_CACHE_PATH)
            
        except Exception as e:
            logger.error(f"Error persisting users cache: {e}")
    
    def _persist_shares_cache(self):
        """Persist current shares cache to ADLS"""
        try:
            # Convert in-memory indexes to DataFrame
            shares_list = []
            for user_id, emails in self._shares_by_user.items():
                for email in emails:
                    shares_list.append({
                        "user_id": user_id,
                        "shared_email": email
                    })
            
            if not shares_list:
                # Create empty DataFrame with correct schema
                df = pd.DataFrame(columns=["user_id", "shared_email"])
            else:
                df = pd.DataFrame(shares_list)
            
            self._save_parquet_to_adls(df, self.SHARES_CACHE_PATH)
            
        except Exception as e:
            logger.error(f"Error persisting shares cache: {e}")
    
    # ═══════════════════════════════════════════════════════════════════
    # CACHE MANAGEMENT
    # ═══════════════════════════════════════════════════════════════════
    
    def invalidate(self):
        """Force cache refresh on next access"""
        self._initialized = False
        self._email_to_user = {}
        self._user_id_to_user = {}
        self._shares_by_user = {}
        self._shares_by_email = {}
        self._cache_loaded_at = None
        logger.info("Auth cache invalidated")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        return {
            "initialized": self._initialized,
            "users_count": len(self._user_id_to_user),
            "shares_count": sum(len(v) for v in self._shares_by_user.values()),
            "users_with_shares": len(self._shares_by_user),
            "cache_loaded_at": self._cache_loaded_at.isoformat() if self._cache_loaded_at else None,
        }


# Global singleton
auth_cache = AuthCacheService()

