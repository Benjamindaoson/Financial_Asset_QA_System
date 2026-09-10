"""
Multi-tenant Support and Data Isolation.

Provides tenant context management and data isolation utilities.
"""
import logging
from typing import Optional, Dict, Any
from contextvars import ContextVar
from trust_rag.config import get_config

logger = logging.getLogger(__name__)

# Context variable for current tenant ID (thread-safe)
_current_tenant_id: ContextVar[Optional[str]] = ContextVar('tenant_id', default=None)


class TenantContext:
    """
    Tenant context manager for data isolation.
    
    Usage:
        with TenantContext(tenant_id="tenant_123"):
            # All operations within this context are isolated to tenant_123
            rag.process_query("...")
    """
    
    def __init__(self, tenant_id: Optional[str] = None):
        """
        Initialize tenant context.
        
        Args:
            tenant_id: Tenant identifier. If None, uses default from config.
        """
        config = get_config()
        self.tenant_id = tenant_id or config.multi_tenant.default_tenant_id
        self._token = None
    
    def __enter__(self):
        """Enter tenant context."""
        self._token = _current_tenant_id.set(self.tenant_id)
        logger.debug(f"Entered tenant context: {self.tenant_id}")
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit tenant context."""
        if self._token:
            _current_tenant_id.reset(self._token)
            logger.debug(f"Exited tenant context: {self.tenant_id}")
        return False
    
    @staticmethod
    def get_current() -> Optional[str]:
        """Get current tenant ID from context."""
        return _current_tenant_id.get()
    
    @staticmethod
    def set_current(tenant_id: Optional[str]):
        """Set current tenant ID (for testing or manual control)."""
        config = get_config()
        tenant = tenant_id or config.multi_tenant.default_tenant_id
        _current_tenant_id.set(tenant)
        return tenant


def get_tenant_id() -> Optional[str]:
    """
    Get current tenant ID.
    
    Returns:
        Current tenant ID or None if multi-tenant is disabled
    """
    config = get_config()
    if not config.multi_tenant.enabled:
        return None
    
    tenant_id = TenantContext.get_current()
    if tenant_id is None:
        return config.multi_tenant.default_tenant_id
    return tenant_id


def ensure_tenant_id(data: Dict[str, Any], tenant_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Ensure tenant_id is present in data dictionary.
    
    Args:
        data: Data dictionary to update
        tenant_id: Explicit tenant ID (if None, uses current context)
        
    Returns:
        Updated data dictionary with tenant_id
    """
    config = get_config()
    if not config.multi_tenant.enabled:
        return data
    
    if config.multi_tenant.tenant_id_field not in data:
        tenant = tenant_id or get_tenant_id()
        data[config.multi_tenant.tenant_id_field] = tenant
    
    return data


def filter_by_tenant(data_list: list, tenant_id: Optional[str] = None) -> list:
    """
    Filter data list by tenant ID.
    
    Args:
        data_list: List of data dictionaries
        tenant_id: Tenant ID to filter by (if None, uses current context)
        
    Returns:
        Filtered list containing only items for the specified tenant
    """
    config = get_config()
    if not config.multi_tenant.enabled or not config.multi_tenant.enforce_isolation:
        return data_list
    
    tenant = tenant_id or get_tenant_id()
    tenant_field = config.multi_tenant.tenant_id_field
    
    return [
        item for item in data_list
        if item.get(tenant_field) == tenant
    ]


def validate_tenant_access(resource_tenant_id: Optional[str], requested_tenant_id: Optional[str] = None) -> bool:
    """
    Validate tenant access to a resource.
    
    Args:
        resource_tenant_id: Tenant ID of the resource
        requested_tenant_id: Tenant ID requesting access (if None, uses current context)
        
    Returns:
        True if access is allowed, False otherwise
    """
    config = get_config()
    if not config.multi_tenant.enabled:
        return True  # No isolation when disabled
    
    if not config.multi_tenant.enforce_isolation:
        return True  # Isolation not enforced
    
    tenant = requested_tenant_id or get_tenant_id()
    
    # None tenant_id means shared resource (if allowed)
    if resource_tenant_id is None:
        return True  # Shared resources accessible to all
    
    return resource_tenant_id == tenant



