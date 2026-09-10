from contextvars import ContextVar
from contextlib import contextmanager
from trust_rag.engine.ingest.profile import IngestProfile, FeatureFlags, ProfileManager

# Global ContextVar
_current_profile = ContextVar("ingest_profile", default=None)

def get_current_profile() -> IngestProfile:
    """Get the active IngestProfile or a default generic one."""
    profile = _current_profile.get()
    if profile is None:
        # Create a default generic profile if none set
        return IngestProfile(name="generic", features=FeatureFlags())
    return profile

@contextmanager
def ingest_profile_context(profile: IngestProfile):
    """Context manager to set the active ingest profile."""
    token = _current_profile.set(profile)
    try:
        yield
    finally:
        _current_profile.reset(token)
