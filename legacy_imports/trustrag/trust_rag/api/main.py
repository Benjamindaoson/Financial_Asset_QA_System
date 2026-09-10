"""
TrustRAG Industrial API.

Provides endpoints for:
- Query processing
- Document ingestion
- System health and statistics
"""
import os
import sys
import logging
import tempfile
import shutil
from typing import List, Optional, Literal
from pathlib import Path

from fastapi import FastAPI, HTTPException, UploadFile, File, Form, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

# Ensure project root is in path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from trust_rag.system import TrustRAG
from trust_rag.config import get_config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="TrustRAG Industrial API",
    description="Deterministic, Evidence-Backed Financial QA System",
    version="1.0.0"
)

# Enable CORS for Frontend
config = get_config()
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.api.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize System
rag = TrustRAG(
    artifact_dir="artifacts",
    fact_store_path=config.paths.fact_store_file
)

# ============================================================================
# Request/Response Models
# ============================================================================

class QueryRequest(BaseModel):
    """Query request model."""
    query: str = Field(..., description="The question to ask")
    risk_level: Literal["low", "medium", "high"] = Field(
        default="medium",
        description="Risk level affecting strictness of verification"
    )


class EvidenceItemResponse(BaseModel):
    """Evidence item in response."""
    metric: str
    value: str
    source: str
    page: int


class AnswerResponse(BaseModel):
    """Answer component of response."""
    text: str
    confidence: float


class QueryResponse(BaseModel):
    """Query response model."""
    verdict: Literal["VERIFIED", "REFUSED", "CONFLICT"]
    answer: Optional[AnswerResponse] = None
    evidence: List[EvidenceItemResponse] = []
    trace_id: str
    reasons: List[str] = []
    risk_flags: dict = {}
    disclosure_required: bool = False
    verification_data: dict = {}


class IngestRequest(BaseModel):
    """Document ingestion request for URL-based ingestion."""
    url: Optional[str] = None
    doc_id: Optional[str] = None
    profile: str = "generic"


class IngestResponse(BaseModel):
    """Document ingestion response."""
    doc_id: str
    status: str
    chunks_count: int
    errors: List[str] = []
    message: str


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    version: str = "1.0.0"
    index_loaded: bool
    documents_count: int
    chunks_count: int


class ErrorResponse(BaseModel):
    """Error response model."""
    error: str
    detail: str
    trace_id: Optional[str] = None


class IndexStatsResponse(BaseModel):
    """Index statistics response."""
    total_chunks: int
    documents_loaded: int
    documents: List[str]
    chunks_by_tier: dict


# ============================================================================
# Exception Handlers
# ============================================================================

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler with detailed error response."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal Server Error",
            "detail": str(exc),
            "trace_id": f"err_{id(exc)}"
        }
    )


# ============================================================================
# Query Endpoints
# ============================================================================

@app.post("/api/query", response_model=QueryResponse)
async def query_endpoint(request: QueryRequest):
    """
    Process a financial question and return verified answer.
    
    The system will:
    1. Analyze query intent and risk level
    2. Search for supporting evidence
    3. Arbitrate evidence quality and conflicts
    4. Generate and verify answer
    
    Returns VERIFIED, REFUSED, or CONFLICT verdict.
    """
    if request.stream:
        return StreamingResponse(
            rag.process_query_stream(
                request.query,
                risk_level=request.risk_level
            ),
            media_type="text/event-stream"
        )

    try:
        logger.info(f"Query: {request.query[:100]}...")
        
        result = rag.process_query(
            request.query,
            risk_level=request.risk_level
        )
        
        response = QueryResponse(
            verdict=result.verdict,
            answer=AnswerResponse(
                text=result.answer.text,
                confidence=result.answer.confidence
            ) if result.answer else None,
            evidence=[
                EvidenceItemResponse(**ev.model_dump())
                for ev in result.evidence
            ],
            trace_id=result.trace_id,
            reasons=result.reasons,
            risk_flags=result.risk_flags,
            disclosure_required=result.disclosure_required,
            verification_data=result.verification_data
        )
        
        return response
        
    except Exception as e:
        logger.error(f"Query failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Query processing failed",
                "detail": str(e),
                "suggestion": "Please check your query format or try again later"
            }
        )


# ============================================================================
# Cloud Storage Link Processing
# ============================================================================

from trust_rag.engine.cloud_storage import CloudStorageManager

# Initialize cloud storage manager
cloud_manager = CloudStorageManager(
    cache_dir="artifacts/cloud_cache",
    max_cache_age_days=7,
    max_concurrent_downloads=3
)


class CloudLinkRequest(BaseModel):
    """Cloud storage link request."""
    url: str = Field(..., description="Cloud storage sharing link")
    validate_only: bool = Field(default=False, description="Only validate link without downloading")


class CloudBatchRequest(BaseModel):
    """Batch cloud storage links request."""
    urls: List[str] = Field(..., description="List of cloud storage sharing links")
    validate_only: bool = Field(default=False, description="Only validate links without downloading")


class CloudValidationResponse(BaseModel):
    """Cloud storage link validation response."""
    url: str
    is_valid: bool
    provider: Optional[str] = None
    file_info: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    confidence: float = 0.0


class CloudDownloadResponse(BaseModel):
    """Cloud storage download response."""
    url: str
    success: bool
    local_path: Optional[str] = None
    file_info: Optional[Dict[str, Any]] = None
    download_time_seconds: float = 0.0
    bytes_downloaded: int = 0
    error_message: Optional[str] = None


# ============================================================================
# Document Ingestion Endpoints
# ============================================================================

@app.post("/api/ingest", response_model=IngestResponse)
async def ingest_document(
    file: UploadFile = File(...),
    doc_id: Optional[str] = Form(None),
    profile: str = Form("generic")
):
    """
    Upload and ingest a document.
    
    Supports: PDF, HTML, TXT, CSV, XLSX
    
    The document will be:
    1. Parsed and structured
    2. Split into retrievable chunks
    3. Indexed for search
    """
    # Validate file type
    allowed_extensions = {'.pdf', '.html', '.htm', '.txt', '.csv', '.xlsx', '.xls'}
    file_ext = os.path.splitext(file.filename)[1].lower()
    
    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "Unsupported file type",
                "detail": f"File extension '{file_ext}' is not supported",
                "allowed": list(allowed_extensions)
            }
        )
    
    # Check file size
    max_size = config.api.max_upload_size_mb * 1024 * 1024
    
    # Save uploaded file temporarily
    temp_dir = tempfile.mkdtemp()
    temp_path = os.path.join(temp_dir, file.filename)
    
    try:
        # Write uploaded file
        with open(temp_path, "wb") as f:
            content = await file.read()
            if len(content) > max_size:
                raise HTTPException(
                    status_code=400,
                    detail={
                        "error": "File too large",
                        "detail": f"File size exceeds {config.api.max_upload_size_mb}MB limit"
                    }
                )
            f.write(content)
        
        # Ingest document
        result = rag.ingest_document(
            temp_path,
            doc_id=doc_id,
            profile=profile
        )
        
        status_message = {
            "OK": "Document ingested successfully",
            "DEGRADED": "Document ingested with some quality issues",
            "FAILED": "Document ingestion failed"
        }
        
        return IngestResponse(
            doc_id=result["doc_id"],
            status=result["status"],
            chunks_count=result["chunks_count"],
            errors=result.get("errors", []),
            message=status_message.get(result["status"], "Unknown status")
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ingestion failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Document ingestion failed",
                "detail": str(e)
            }
        )
    finally:
        # Cleanup temp file
        shutil.rmtree(temp_dir, ignore_errors=True)


@app.post("/api/ingest/refresh")
async def refresh_index():
    """
    Refresh the search index with newly ingested documents.

    Call this after manually adding documents to artifacts/ingestion/.
    """
    try:
        new_chunks = rag.refresh_index()
        return {
            "status": "success",
            "new_chunks_added": new_chunks,
            "message": f"Index refreshed with {new_chunks} new chunks"
        }
    except Exception as e:
        logger.error(f"Index refresh failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"error": "Index refresh failed", "detail": str(e)}
        )


# ============================================================================
# Cloud Storage Endpoints
# ============================================================================

@app.post("/api/cloud/validate", response_model=CloudValidationResponse)
async def validate_cloud_link(request: CloudLinkRequest):
    """
    Validate a cloud storage sharing link.

    Checks if the link is accessible, identifies the provider,
    and extracts basic file information.
    """
    try:
        logger.info(f"Validating cloud link: {request.url[:100]}...")

        validation = await cloud_manager.validate_link(request.url)

        response = CloudValidationResponse(
            url=request.url,
            is_valid=validation.is_valid,
            provider=validation.provider,
            file_info=validation.file_info.__dict__ if validation.file_info else None,
            error_message=validation.error_message,
            confidence=validation.confidence
        )

        return response

    except Exception as e:
        logger.error(f"Cloud link validation failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Cloud link validation failed",
                "detail": str(e)
            }
        )


@app.post("/api/cloud/download")
async def download_cloud_file(request: CloudLinkRequest):
    """
    Download and ingest a file from cloud storage.

    Validates the link, downloads the file, and processes it through
    the normal ingestion pipeline.
    """
    try:
        logger.info(f"Downloading cloud file: {request.url[:100]}...")

        # Validate first
        validation = await cloud_manager.validate_link(request.url)
        if not validation.is_valid:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "Invalid cloud storage link",
                    "detail": validation.error_message
                }
            )

        # Download file
        download_result = await cloud_manager.download_file(request.url)

        if not download_result.success:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "File download failed",
                    "detail": download_result.error_message
                }
            )

        # If validate_only, just return download info
        if request.validate_only:
            return CloudDownloadResponse(
                url=request.url,
                success=True,
                local_path=download_result.local_path,
                file_info=download_result.file_info.__dict__ if download_result.file_info else None,
                download_time_seconds=download_result.download_time,
                bytes_downloaded=download_result.bytes_downloaded
            )

        # Process through ingestion pipeline
        ingest_result = rag.ingest_document(
            download_result.local_path,
            doc_id=f"cloud_{validation.file_info.file_id}" if validation.file_info else None,
            profile="generic"
        )

        # Clean up downloaded file after successful ingestion
        if os.path.exists(download_result.local_path):
            try:
                os.remove(download_result.local_path)
            except OSError:
                pass  # Ignore cleanup errors

        status_message = {
            "OK": "Cloud file ingested successfully",
            "DEGRADED": "Cloud file ingested with some quality issues",
            "FAILED": "Cloud file ingestion failed"
        }

        return {
            "url": request.url,
            "success": True,
            "ingest_result": {
                "doc_id": ingest_result["doc_id"],
                "status": ingest_result["status"],
                "chunks_count": ingest_result["chunks_count"],
                "errors": ingest_result.get("errors", []),
                "message": status_message.get(ingest_result["status"], "Unknown status")
            },
            "download_info": {
                "bytes_downloaded": download_result.bytes_downloaded,
                "download_time_seconds": download_result.download_time
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Cloud file download failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Cloud file download failed",
                "detail": str(e)
            }
        )


@app.post("/api/cloud/batch/validate")
async def validate_cloud_links_batch(request: CloudBatchRequest):
    """
    Validate multiple cloud storage links in batch.

    Returns validation results for all links.
    """
    try:
        logger.info(f"Batch validating {len(request.urls)} cloud links")

        validations = await cloud_manager.batch_validate_links(request.urls)

        results = []
        for url, validation in validations.items():
            results.append(CloudValidationResponse(
                url=url,
                is_valid=validation.is_valid,
                provider=validation.provider,
                file_info=validation.file_info.__dict__ if validation.file_info else None,
                error_message=validation.error_message,
                confidence=validation.confidence
            ))

        return {
            "total_links": len(request.urls),
            "results": [result.dict() for result in results],
            "summary": {
                "valid_links": sum(1 for r in results if r.is_valid),
                "invalid_links": sum(1 for r in results if not r.is_valid),
                "supported_providers": cloud_manager.get_supported_providers()
            }
        }

    except Exception as e:
        logger.error(f"Batch cloud link validation failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Batch validation failed",
                "detail": str(e)
            }
        )


@app.post("/api/cloud/batch/download")
async def download_cloud_files_batch(request: CloudBatchRequest):
    """
    Download and ingest multiple files from cloud storage in batch.

    Processes all valid links concurrently.
    """
    try:
        logger.info(f"Batch downloading {len(request.urls)} cloud files")

        # First validate all links
        validations = await cloud_manager.batch_validate_links(request.urls)

        # Filter valid links
        valid_urls = [url for url, validation in validations.items() if validation.is_valid]
        invalid_results = [
            CloudValidationResponse(
                url=url,
                is_valid=False,
                error_message=validation.error_message,
                confidence=validation.confidence
            )
            for url, validation in validations.items() if not validation.is_valid
        ]

        if not valid_urls:
            return {
                "total_links": len(request.urls),
                "processed_links": 0,
                "successful_downloads": 0,
                "failed_downloads": 0,
                "results": [r.dict() for r in invalid_results],
                "summary": {
                    "message": "No valid links found",
                    "valid_links": 0,
                    "invalid_links": len(invalid_results)
                }
            }

        # Download files in batch
        download_results = await cloud_manager.batch_download_files(valid_urls)

        # Process successful downloads through ingestion
        successful_ingests = []
        failed_ingests = []

        for url, download_result in download_results.items():
            if not download_result.success:
                failed_ingests.append({
                    "url": url,
                    "error": download_result.error_message,
                    "stage": "download"
                })
                continue

            try:
                # Process through ingestion pipeline
                validation = validations[url]
                ingest_result = rag.ingest_document(
                    download_result.local_path,
                    doc_id=f"cloud_{validation.file_info.file_id}" if validation.file_info else None,
                    profile="generic"
                )

                successful_ingests.append({
                    "url": url,
                    "ingest_result": {
                        "doc_id": ingest_result["doc_id"],
                        "status": ingest_result["status"],
                        "chunks_count": ingest_result["chunks_count"],
                        "errors": ingest_result.get("errors", [])
                    },
                    "download_info": {
                        "bytes_downloaded": download_result.bytes_downloaded,
                        "download_time_seconds": download_result.download_time
                    }
                })

                # Clean up downloaded file
                if os.path.exists(download_result.local_path):
                    try:
                        os.remove(download_result.local_path)
                    except OSError:
                        pass

            except Exception as e:
                failed_ingests.append({
                    "url": url,
                    "error": str(e),
                    "stage": "ingestion"
                })

        # Combine results
        all_results = []

        # Add successful results
        for result in successful_ingests:
            all_results.append({
                "url": result["url"],
                "success": True,
                "ingest_result": result["ingest_result"],
                "download_info": result["download_info"]
            })

        # Add failed results
        for failed in failed_ingests:
            all_results.append({
                "url": failed["url"],
                "success": False,
                "error": failed["error"],
                "stage": failed["stage"]
            })

        # Add invalid link results
        for invalid in invalid_results:
            all_results.append({
                "url": invalid.url,
                "success": False,
                "error": invalid.error_message,
                "stage": "validation"
            })

        return {
            "total_links": len(request.urls),
            "processed_links": len(valid_urls),
            "successful_downloads": len(successful_ingests),
            "failed_operations": len(failed_ingests) + len(invalid_results),
            "results": all_results,
            "summary": {
                "valid_links": len(valid_urls),
                "invalid_links": len(invalid_results),
                "successful_ingests": len(successful_ingests),
                "failed_ingests": len(failed_ingests),
                "supported_providers": cloud_manager.get_supported_providers()
            }
        }

    except Exception as e:
        logger.error(f"Batch cloud file download failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Batch download failed",
                "detail": str(e)
            }
        )


@app.get("/api/cloud/providers")
async def get_supported_providers():
    """Get list of supported cloud storage providers."""
    return {
        "providers": cloud_manager.get_supported_providers(),
        "features": {
            "validation": True,
            "download": True,
            "batch_processing": True,
            "progress_tracking": True,
            "cache_support": True
        }
    }


@app.get("/api/cloud/cache/stats")
async def get_cloud_cache_stats():
    """Get cloud storage cache statistics."""
    try:
        stats = cloud_manager.get_cache_stats()
        return {
            "cache_stats": stats,
            "status": "success"
        }
    except Exception as e:
        logger.error(f"Failed to get cache stats: {e}")
        raise HTTPException(
            status_code=500,
            detail={"error": "Failed to get cache statistics", "detail": str(e)}
        )


@app.post("/api/cloud/cache/cleanup")
async def cleanup_cloud_cache(max_age_days: int = 7):
    """Clean up old cloud storage cache files."""
    try:
        cloud_manager.cleanup_cache(max_age_days)
        return {
            "status": "success",
            "message": f"Cleaned up cache files older than {max_age_days} days"
        }
    except Exception as e:
        logger.error(f"Cache cleanup failed: {e}")
        raise HTTPException(
            status_code=500,
            detail={"error": "Cache cleanup failed", "detail": str(e)}
        )


# ============================================================================
# System Status Endpoints
# ============================================================================

@app.get("/api/health", response_model=HealthResponse)
async def health():
    """
    Health check endpoint.
    
    Returns system status and basic statistics.
    """
    try:
        stats = rag.get_index_stats()
        return HealthResponse(
            status="healthy",
            version="1.0.0",
            index_loaded=stats["total_chunks"] > 0,
            documents_count=stats["documents_loaded"],
            chunks_count=stats["total_chunks"]
        )
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return HealthResponse(
            status="degraded",
            version="1.0.0",
            index_loaded=False,
            documents_count=0,
            chunks_count=0
        )


@app.get("/api/stats", response_model=IndexStatsResponse)
async def get_stats():
    """
    Get detailed index statistics.
    """
    try:
        stats = rag.get_index_stats()
        return IndexStatsResponse(
            total_chunks=stats["total_chunks"],
            documents_loaded=stats["documents_loaded"],
            documents=stats.get("documents", []),
            chunks_by_tier=stats.get("chunks_by_tier", {})
        )
    except Exception as e:
        logger.error(f"Stats retrieval failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"error": "Failed to retrieve statistics", "detail": str(e)}
        )


@app.get("/api/config")
async def get_system_config():
    """
    Get current system configuration (non-sensitive parts).
    """
    config = get_config()
    return {
        "feature_flags": config.feature_flags.model_dump(),
        "query_thresholds": config.query_thresholds.model_dump(),
        "evidence_selection": config.evidence_selection.model_dump(),
        "api": {
            "max_upload_size_mb": config.api.max_upload_size_mb
        }
    }


# ============================================================================
# Startup/Shutdown Events
# ============================================================================

@app.on_event("startup")
async def startup_event():
    """Initialize system on startup."""
    logger.info("TrustRAG API starting up...")
    stats = rag.get_index_stats()
    logger.info(
        f"Index loaded: {stats['total_chunks']} chunks from "
        f"{stats['documents_loaded']} documents"
    )


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    logger.info("TrustRAG API shutting down...")


# ============================================================================
# Main Entry Point
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host=config.api.host,
        port=config.api.port
    )
