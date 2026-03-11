"""Document ingestion and cleaning pipeline powered by MinerU."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import logging
import re
from typing import Dict, Iterable, List, Optional

from app.rag.mineru_client import MinerUClient, MinerUFileResult

logger = logging.getLogger(__name__)


@dataclass
class IngestionResult:
    """Summary of a single ingested source file."""

    source_file: str
    output_file: Optional[str]
    status: str
    message: str


class MinerUDocumentIngestor:
    """Use MinerU to parse raw documents and convert them into clean RAG Markdown files."""

    SUPPORTED_SUFFIXES = MinerUClient.SUPPORTED_SUFFIXES | {".md", ".html"}

    def __init__(
        self,
        raw_root: Path,
        knowledge_root: Path,
        dealed_root: Path,
        mineru_client: Optional[MinerUClient] = None,
    ) -> None:
        self.raw_root = Path(raw_root)
        self.knowledge_root = Path(knowledge_root)
        self.dealed_root = Path(dealed_root)
        self.mineru_client = mineru_client or MinerUClient()

        self.knowledge_root.mkdir(parents=True, exist_ok=True)
        self.dealed_root.mkdir(parents=True, exist_ok=True)

    def discover_files(self, limit: Optional[int] = None) -> List[Path]:
        candidates: List[Path] = []
        for file_path in self.raw_root.rglob("*"):
            if file_path.is_file() and file_path.suffix.lower() in self.SUPPORTED_SUFFIXES:
                candidates.append(file_path)
        candidates.sort(
            key=lambda item: (
                0 if item.suffix.lower() in MinerUClient.SUPPORTED_SUFFIXES else 1,
                str(item),
            )
        )
        return candidates[:limit] if limit else candidates

    def ingest(self, files: Iterable[Path]) -> List[IngestionResult]:
        file_list = [Path(file_path) for file_path in files]
        if not file_list:
            return []

        mineru_files = [file_path for file_path in file_list if file_path.suffix.lower() in MinerUClient.SUPPORTED_SUFFIXES]
        local_files = [file_path for file_path in file_list if file_path.suffix.lower() not in MinerUClient.SUPPORTED_SUFFIXES]
        results: List[IngestionResult] = []

        if mineru_files:
            if not self.mineru_client.is_configured():
                raise RuntimeError("MINERU_API_TOKEN 未配置，无法调用 MinerU 解析")
            parsed = self.mineru_client.parse_local_files(mineru_files, self.dealed_root)
            results.extend(
                self._write_knowledge_markdown(file_path, result)
                for file_path, result in zip(mineru_files, parsed)
            )

        for file_path in local_files:
            results.append(self._ingest_local_file(file_path))

        return results

    def _ingest_local_file(self, source_path: Path) -> IngestionResult:
        suffix = source_path.suffix.lower()
        if suffix == ".md":
            raw_text = source_path.read_text(encoding="utf-8", errors="ignore")
            return self._write_local_cleaned_markdown(source_path, raw_text, "本地 Markdown 清洗")

        if suffix == ".html":
            html_text = source_path.read_text(encoding="utf-8", errors="ignore")
            html_text = re.sub(r"(?is)<script.*?>.*?</script>", " ", html_text)
            html_text = re.sub(r"(?is)<style.*?>.*?</style>", " ", html_text)
            html_text = re.sub(r"(?s)<[^>]+>", " ", html_text)
            html_text = re.sub(r"\s+", " ", html_text)
            return self._write_local_cleaned_markdown(source_path, html_text, "本地 HTML 清洗")

        return IngestionResult(
            source_file=str(source_path),
            output_file=None,
            status="failed",
            message=f"不支持的本地清洗类型: {suffix}",
        )

    def _write_local_cleaned_markdown(self, source_path: Path, raw_text: str, source_label: str) -> IngestionResult:
        cleaned = self.clean_markdown(raw_text)
        title = self.derive_title(cleaned, source_path)
        output_name = self.build_output_name(source_path)
        output_path = self.knowledge_root / output_name
        output_path.write_text(
            "\n".join(
                [
                    f"# {title}",
                    "",
                    f"> 来源: {source_label}",
                    "",
                    cleaned.strip(),
                    "",
                ]
            ),
            encoding="utf-8",
        )
        return IngestionResult(
            source_file=str(source_path),
            output_file=str(output_path),
            status="done",
            message="已写入知识库",
        )

    def _write_knowledge_markdown(self, source_path: Path, parse_result: MinerUFileResult) -> IngestionResult:
        if parse_result.state != "done" or not parse_result.markdown:
            return IngestionResult(
                source_file=str(source_path),
                output_file=None,
                status="failed",
                message=parse_result.metadata.get("err_msg") or f"MinerU 状态: {parse_result.state}",
            )

        cleaned = self.clean_markdown(parse_result.markdown)
        title = self.derive_title(cleaned, source_path)
        output_name = self.build_output_name(source_path)
        output_path = self.knowledge_root / output_name

        content = [
            f"# {title}",
            "",
            "> 来源: MinerU 解析导入",
            "",
            cleaned.strip(),
            "",
        ]
        output_path.write_text("\n".join(content), encoding="utf-8")
        return IngestionResult(
            source_file=str(source_path),
            output_file=str(output_path),
            status="done",
            message="已写入知识库",
        )

    @staticmethod
    def clean_markdown(markdown: str) -> str:
        text = markdown.replace("\r\n", "\n").replace("\r", "\n")
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = re.sub(r"[ \t]+\n", "\n", text)
        text = re.sub(r"\n[ \t]+", "\n", text)
        text = re.sub(r"\n?-{3,}\n?", "\n\n", text)
        text = re.sub(r"\n?_{3,}\n?", "\n\n", text)
        text = re.sub(r"[ \t]{2,}", " ", text)
        text = re.sub(r"\n#+\s*\n", "\n", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    @staticmethod
    def derive_title(markdown: str, source_path: Path) -> str:
        for line in markdown.splitlines():
            stripped = line.strip()
            if stripped.startswith("#"):
                candidate = stripped.lstrip("#").strip()
                if candidate:
                    return candidate
        return source_path.stem

    @staticmethod
    def build_output_name(source_path: Path) -> str:
        safe_name = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff_-]+", "_", source_path.stem).strip("_")
        return f"MinerU_{safe_name}.md"
