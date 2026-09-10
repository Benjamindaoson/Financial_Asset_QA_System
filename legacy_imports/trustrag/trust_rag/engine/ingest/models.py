"""
Core data models for the Ingestion pipeline.
"""
from typing import Optional, Literal, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime
import hashlib
import os
from enum import Enum

class Granularity(str, Enum):
    """Chunk granularity level."""
    ATOMIC = "atomic"       # Sentence, Table Row, List Item
    COMPOSITE = "composite" # Paragraph, Table, Section

class ChunkTier(str, Enum):
    """MCU Indexing Tier."""
    MICRO = "micro"   # Clause, row, atomic fact - Sparse only
    BASE = "base"     # Paragraph, table block - Dense + Sparse
    MACRO = "macro"   # Section with summary - Multi-vector + Dense + Sparse

class DocInput(BaseModel):
    """Input descriptor for ingestion."""
    path: str  # File path or URL
    content_type: Optional[Literal["pdf", "image", "audio", "csv", "xlsx", "html", "text"]] = None
    source_name: Optional[str] = None  # Original filename
    received_at: datetime = Field(default_factory=datetime.now)
    
    def infer_content_type(self) -> str:
        """Infer content type from file extension."""
        if self.content_type:
            return self.content_type
        ext = os.path.splitext(self.path)[1].lower()
        mapping = {
            ".pdf": "pdf",
            ".png": "image", ".jpg": "image", ".jpeg": "image", ".tiff": "image", ".bmp": "image",
            ".mp3": "audio", ".wav": "audio", ".m4a": "audio", ".flac": "audio",
            ".csv": "csv",
            ".xlsx": "xlsx", ".xls": "xlsx",
            ".html": "html", ".htm": "html",
            ".txt": "text", ".md": "text",
        }
        return mapping.get(ext, "text")
    
    def compute_content_hash(self) -> str:
        """Compute SHA256 hash of the file content."""
        if not os.path.exists(self.path):
            return hashlib.sha256(self.path.encode()).hexdigest()[:16]
        with open(self.path, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()[:16]

class ChunkProvenance(BaseModel):
    """Enhanced provenance for each chunk."""
    doc_id: str
    page_number: Optional[int] = None
    bbox: Optional[tuple] = None  # (x1, y1, x2, y2)
    source_path: str
    parser_name: str
    language: Literal["zh", "en", "unknown"]
    modality: str  # pdf, image, audio, table, web, text
    block_index: int = 0

class Chunk(BaseModel):
    """Output chunk from ingestion."""
    evidence_id: str
    text: str
    provenance: ChunkProvenance
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    # Multi-tenant support: Data isolation
    tenant_id: Optional[str] = Field(default=None, description="Tenant ID for data isolation")
    
    # Phase F: Retrieval Optimization Protocol
    parent_id: Optional[str] = None  # Evidence ID of the semantic parent
    semantic_context: Dict[str, Any] = Field(default_factory=dict)
    granularity: Granularity = Granularity.COMPOSITE
    
    # Industrial-Grade MCU Fields
    tier: ChunkTier = ChunkTier.BASE  # Default to BASE for backward compatibility
    section_path: List[str] = Field(default_factory=list)  # ["Chapter 1", "Section 1.2"]
    parent_refs: List[str] = Field(default_factory=list)  # Parent chunk evidence IDs
    sibling_refs: List[str] = Field(default_factory=list)  # Adjacent chunk evidence IDs
    virtual_links: Dict[str, str] = Field(default_factory=dict)  # {"preceding_text": "ev_123"}
    summary: Optional[str] = None  # Required for MACRO tier
    anchors: List[str] = Field(default_factory=list)  # Bilingual term anchors for Entity Bridging

class IngestResult(BaseModel):
    """Result of ingestion for a single document."""
    doc_id: str
    language: Literal["zh", "en", "unknown"]
    modality: str
    chunks: List[Chunk]
    total_pages: Optional[int] = None
    parser_used: str
    content_hash: str
    ingest_time_ms: int
    errors: List[str] = Field(default_factory=list)
    
    # Multi-tenant support: Data isolation
    tenant_id: Optional[str] = Field(default=None, description="Tenant ID for data isolation")
    
    # Versioned Corpus Management
    document_group_id: Optional[str] = None
    version_tag: Optional[str] = None
    
    # New Guardrail Fields
    ingest_profile: str = "generic"
    ingest_status: Literal["OK", "DEGRADED", "FAILED"] = "OK"
    ingest_status_reason: List[str] = Field(default_factory=list)
    quality_report: Optional[Dict[str, Any]] = None

class ChunkIR(BaseModel):
    model_config = ConfigDict(frozen=True)
    
    doc_id: str
    chunk_policy_id: str
    chunks: List[Chunk] = Field(default_factory=list)

class ChunkTrace(BaseModel):
    trace_id: str
    chunk_policy_id: str
    doc_id: str
    decision_signals: Dict[str, float]
    policy_reason: str
    timestamp: str
    docir_validation: Optional[Dict[str, Any]] = None


# ============================================================================
# Cloud Storage Models
# ============================================================================

class CloudProvider(str, Enum):
    """Supported cloud storage providers."""
    GOOGLE_DRIVE = "google_drive"
    BAIDU_YUN = "baidu_yun"
    QUARK = "quark"
    ONEDRIVE = "onedrive"
    DROPBOX = "dropbox"
    MEGA = "mega"
    BOX = "box"
    PCLOUD = "pcloud"
    MEDIAFIRE = "mediafire"


class CloudFileMetadata(BaseModel):
    """Metadata for cloud storage files."""
    cloud_file_id: str  # Provider-specific file ID
    provider: CloudProvider
    original_url: str  # Original sharing URL
    direct_url: Optional[str] = None  # Direct download URL if available
    filename: str
    mime_type: str
    file_size_bytes: int
    created_time: Optional[datetime] = None
    modified_time: Optional[datetime] = None
    owner: Optional[str] = None
    is_public: bool = True
    expires_at: Optional[datetime] = None
    last_validated: datetime = Field(default_factory=datetime.now)
    validation_status: Literal["valid", "expired", "invalid", "unknown"] = "unknown"
    download_count: int = 0
    last_downloaded: Optional[datetime] = None

    # Additional metadata from provider
    provider_metadata: Dict[str, Any] = Field(default_factory=dict)

    def is_expired(self) -> bool:
        """Check if the file link has expired."""
        if self.expires_at is None:
            return False
        return datetime.now() > self.expires_at

    def should_revalidate(self) -> bool:
        """Check if link should be revalidated (every 24 hours)."""
        if self.last_validated is None:
            return True
        time_since_validation = datetime.now() - self.last_validated
        return time_since_validation.total_seconds() > 24 * 60 * 60


class CloudFileDownload(BaseModel):
    """Record of cloud file downloads."""
    download_id: str
    cloud_file_id: str
    local_path: str
    downloaded_at: datetime = Field(default_factory=datetime.now)
    download_duration_ms: int
    bytes_downloaded: int
    success: bool
    error_message: Optional[str] = None
    client_ip: Optional[str] = None
    user_agent: Optional[str] = None


class CloudStorageLink(BaseModel):
    """User-submitted cloud storage link."""
    link_id: str
    original_url: str
    submitted_by: Optional[str] = None  # User ID
    submitted_at: datetime = Field(default_factory=datetime.now)
    provider: Optional[CloudProvider] = None
    validation_status: Literal["pending", "valid", "invalid", "expired"] = "pending"
    file_metadata: Optional[CloudFileMetadata] = None
    last_validated: Optional[datetime] = None
    is_active: bool = True  # Can be deactivated by admin

    # Processing status
    processing_status: Literal["pending", "processing", "completed", "failed"] = "pending"
    processing_started_at: Optional[datetime] = None
    processing_completed_at: Optional[datetime] = None
    processing_error: Optional[str] = None

    # Resulting document info
    resulting_doc_id: Optional[str] = None
    chunks_created: int = 0

    # Access control
    access_level: Literal["public", "private", "restricted"] = "public"
    allowed_users: List[str] = Field(default_factory=list)  # User IDs with access


class CloudStorageBatch(BaseModel):
    """Batch processing of multiple cloud storage links."""
    batch_id: str
    submitted_by: Optional[str] = None
    submitted_at: datetime = Field(default_factory=datetime.now)
    links: List[str] = Field(default_factory=list)  # List of link URLs
    status: Literal["pending", "processing", "completed", "failed", "partial"] = "pending"

    # Progress tracking
    total_links: int = 0
    processed_links: int = 0
    successful_links: int = 0
    failed_links: int = 0

    # Timing
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    # Results
    results: Dict[str, Dict[str, Any]] = Field(default_factory=dict)  # link_url -> result
    errors: Dict[str, str] = Field(default_factory=dict)  # link_url -> error_message
