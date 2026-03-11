"""MinerU API client for parsing local financial documents into clean Markdown."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import io
import json
import logging
import re
import time
from typing import Any, Dict, Iterable, List, Optional
import zipfile

import requests

from app.config import settings

logger = logging.getLogger(__name__)


class MinerUError(RuntimeError):
    """Raised when MinerU API returns an error or malformed payload."""


@dataclass
class MinerUFileResult:
    """Normalized parse result for a single file."""

    file_name: str
    state: str
    markdown: Optional[str]
    metadata: Dict[str, Any]
    extracted_files: List[str]


class MinerUClient:
    """Thin client around the MinerU v4 batch parsing APIs."""

    SUPPORTED_SUFFIXES = {".pdf", ".doc", ".docx", ".ppt", ".pptx", ".png", ".jpg", ".jpeg"}

    def __init__(
        self,
        token: Optional[str] = None,
        base_url: Optional[str] = None,
        session: Optional[requests.Session] = None,
    ) -> None:
        self.token = token or settings.MINERU_API_TOKEN
        self.base_url = (base_url or settings.MINERU_BASE_URL).rstrip("/")
        self.session = session or requests.Session()

        if self.token:
            self.session.headers.update(
                {
                    "Authorization": f"Bearer {self.token}",
                    "Accept": "*/*",
                }
            )

    def is_configured(self) -> bool:
        return bool(self.token)

    def ensure_configured(self) -> None:
        if not self.token:
            raise MinerUError("MINERU_API_TOKEN 未配置")

    def _post(self, endpoint: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        self.ensure_configured()
        response = self.session.post(
            f"{self.base_url}/{endpoint.lstrip('/')}",
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=60,
        )
        response.raise_for_status()
        data = response.json()
        if data.get("code") != 0:
            raise MinerUError(data.get("msg") or "MinerU API 返回失败")
        return data

    def _get(self, endpoint: str) -> Dict[str, Any]:
        self.ensure_configured()
        response = self.session.get(
            f"{self.base_url}/{endpoint.lstrip('/')}",
            headers={"Content-Type": "application/json"},
            timeout=60,
        )
        response.raise_for_status()
        data = response.json()
        if data.get("code") != 0:
            raise MinerUError(data.get("msg") or "MinerU API 返回失败")
        return data

    def apply_upload_urls(self, files: Iterable[Path], model_version: Optional[str] = None) -> Dict[str, Any]:
        file_list = list(files)
        if not file_list:
            raise MinerUError("没有待上传文件")
        if len(file_list) > settings.MINERU_MAX_BATCH_FILES:
            raise MinerUError(f"单批次文件数不能超过 {settings.MINERU_MAX_BATCH_FILES}")

        payload = {
            "enable_formula": settings.MINERU_ENABLE_FORMULA,
            "language": settings.MINERU_LANGUAGE,
            "enable_table": settings.MINERU_ENABLE_TABLE,
            "model_version": model_version or settings.MINERU_MODEL_VERSION,
            "files": [
                {
                    "name": file_path.name,
                    "is_ocr": settings.MINERU_OCR_BY_DEFAULT,
                    "data_id": self._build_data_id(file_path),
                }
                for file_path in file_list
            ],
        }
        return self._post("file-urls/batch", payload)

    @staticmethod
    def _build_data_id(file_path: Path) -> str:
        return re.sub(r"[^0-9a-zA-Z_-]+", "-", file_path.stem)[:64] or "document"

    def upload_files(self, files: Iterable[Path], upload_urls: List[str]) -> None:
        file_list = list(files)
        if len(file_list) != len(upload_urls):
            raise MinerUError("上传地址数量与文件数量不一致")

        for file_path, upload_url in zip(file_list, upload_urls):
            with file_path.open("rb") as file_obj:
                response = self.session.put(upload_url, data=file_obj, timeout=300)
                response.raise_for_status()

    def get_batch_result(self, batch_id: str) -> Dict[str, Any]:
        return self._get(f"extract-results/batch/{batch_id}")

    def wait_for_batch(self, batch_id: str, timeout_seconds: Optional[int] = None) -> Dict[str, Any]:
        deadline = time.time() + (timeout_seconds or settings.MINERU_POLL_TIMEOUT_SECONDS)
        while time.time() < deadline:
            result = self.get_batch_result(batch_id)
            extract_result = result.get("data", {}).get("extract_result", [])
            states = {item.get("state", "") for item in extract_result}
            if extract_result and states.issubset({"done", "failed"}):
                return result
            time.sleep(settings.MINERU_POLL_INTERVAL_SECONDS)
        raise MinerUError(f"MinerU 批处理超时: {batch_id}")

    def parse_local_files(
        self,
        files: Iterable[Path],
        download_dir: Path,
        model_version: Optional[str] = None,
    ) -> List[MinerUFileResult]:
        file_list = [Path(file_path) for file_path in files]
        upload_response = self.apply_upload_urls(file_list, model_version=model_version)
        batch_id = upload_response["data"]["batch_id"]
        upload_urls = upload_response["data"]["file_urls"]
        self.upload_files(file_list, upload_urls)
        final_result = self.wait_for_batch(batch_id)

        results: List[MinerUFileResult] = []
        for item in final_result.get("data", {}).get("extract_result", []):
            full_zip_url = item.get("full_zip_url")
            markdown = None
            extracted_files: List[str] = []
            metadata = {
                "batch_id": batch_id,
                "state": item.get("state"),
                "err_msg": item.get("err_msg", ""),
                "source": "MinerU",
            }
            if full_zip_url and item.get("state") == "done":
                downloaded = self._download_and_extract(full_zip_url, download_dir, item["file_name"])
                markdown = downloaded["markdown"]
                extracted_files = downloaded["files"]
                metadata.update(downloaded["metadata"])

            results.append(
                MinerUFileResult(
                    file_name=item["file_name"],
                    state=item.get("state", "unknown"),
                    markdown=markdown,
                    metadata=metadata,
                    extracted_files=extracted_files,
                )
            )
        return results

    def _download_and_extract(self, zip_url: str, download_dir: Path, file_name: str) -> Dict[str, Any]:
        download_dir.mkdir(parents=True, exist_ok=True)
        response = self.session.get(zip_url, timeout=300)
        response.raise_for_status()

        extracted_root = download_dir / f"{Path(file_name).stem}_mineru"
        extracted_root.mkdir(parents=True, exist_ok=True)
        extracted_files: List[str] = []

        markdown_candidates: List[tuple[str, str]] = []
        json_payload: Optional[Dict[str, Any]] = None

        with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
            for member in archive.infolist():
                if member.is_dir():
                    continue
                target_path = extracted_root / member.filename
                target_path.parent.mkdir(parents=True, exist_ok=True)
                target_path.write_bytes(archive.read(member))
                extracted_files.append(str(target_path))

                suffix = target_path.suffix.lower()
                if suffix == ".md":
                    markdown_candidates.append((target_path.name.lower(), target_path.read_text(encoding="utf-8", errors="ignore")))
                elif suffix == ".json" and json_payload is None:
                    try:
                        json_payload = json.loads(target_path.read_text(encoding="utf-8"))
                    except Exception:
                        json_payload = None

        markdown = self._select_best_markdown(markdown_candidates, json_payload)
        metadata = {
            "zip_url": zip_url,
            "extracted_root": str(extracted_root),
        }
        return {
            "markdown": markdown,
            "files": extracted_files,
            "metadata": metadata,
        }

    @staticmethod
    def _select_best_markdown(markdown_candidates: List[tuple[str, str]], json_payload: Optional[Dict[str, Any]]) -> Optional[str]:
        if markdown_candidates:
            markdown_candidates.sort(key=lambda item: (0 if "content" in item[0] else 1, len(item[1])), reverse=True)
            return markdown_candidates[0][1]

        if json_payload:
            for key in ("markdown", "md_content", "content", "text"):
                value = json_payload.get(key)
                if isinstance(value, str) and value.strip():
                    return value
        return None
