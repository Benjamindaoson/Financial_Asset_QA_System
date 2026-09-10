import os
import yaml
import logging
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

class FeatureFlags(BaseModel):
    """Explicit feature flags controlled by profile."""
    # Table features
    cross_page_table: bool = True
    
    # Chart features
    chart_weak_semantics: bool = True
    
    # Layout features
    layout_chunking: bool = True
    title_isolation: bool = True
    
    # Text features
    free_text_merge: bool = True

class IngestProfile(BaseModel):
    """
    Configuration profile for ingestion.
    Contols which features are enabled/disabled for a document type.
    """
    name: str
    features: FeatureFlags

    def is_enabled(self, feature_name: str) -> bool:
        if not hasattr(self.features, feature_name):
            logger.warning(f"Unknown feature requested: {feature_name}, defaulting to False")
            return False
        return getattr(self.features, feature_name)

class ProfileManager:
    """Loads and manages ingest profiles."""
    
    DEFAULT_PROFILE_NAME = "generic"
    
    def __init__(self, config_path: str = None):
        if config_path is None:
            # Default to adjacent config directory
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            config_path = os.path.join(base_dir, "config", "ingest_profiles.yaml")
        
        self.config_path = config_path
        self._profiles: Dict[str, IngestProfile] = {}
        self._load_profiles()

    def _load_profiles(self):
        if not os.path.exists(self.config_path):
            logger.warning(f"Profile config not found at {self.config_path}, using defaults.")
            self._create_default_profile()
            return

        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
            
            for name, config in data.items():
                self._profiles[name] = self._parse_profile(name, config)
                
        except Exception as e:
            logger.error(f"Failed to load profiles: {e}")
            self._create_default_profile()

    def _parse_profile(self, name: str, config: Dict[str, Any]) -> IngestProfile:
        # Start with defaults (everything True or set by FeatureFlags default)
        # But wait, we want 'generic' to be the baseline.
        # Actually, let's just default to True for everything unless disabled, 
        # OR implementation specifics. 
        # The FeatureFlags class has defaults.
        
        # Override based on enable/disable lists
        flags = FeatureFlags().dict()
        
        if 'enable' in config and config['enable']:
            for k, v in config['enable'].items():
                if k in flags:
                    flags[k] = v
        
        if 'disable' in config and config['disable']:
            for k, v in config['disable'].items():
                if k in flags:
                    # If it's in disable block and set to true (meaning "yes, disable it")
                    # then we set the flag to False.
                    # Or is it "disable: { feature: true }" ??
                    # Example says: disable: { free_text_merge: true }
                    if v is True:
                        flags[k] = False
        
        return IngestProfile(name=name, features=FeatureFlags(**flags))

    def _create_default_profile(self):
        self._profiles[self.DEFAULT_PROFILE_NAME] = IngestProfile(
            name=self.DEFAULT_PROFILE_NAME,
            features=FeatureFlags()
        )

    def get_profile(self, name: str) -> IngestProfile:
        if name not in self._profiles:
            logger.warning(f"Profile '{name}' not found, falling back to '{self.DEFAULT_PROFILE_NAME}'")
            return self._profiles.get(self.DEFAULT_PROFILE_NAME, self._parse_profile("fallback", {}))
        return self._profiles[name]
