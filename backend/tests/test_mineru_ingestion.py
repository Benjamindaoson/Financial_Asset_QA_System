from pathlib import Path

from app.rag.mineru_client import MinerUFileResult
from app.rag.mineru_ingestion import MinerUDocumentIngestor


class StubMinerUClient:
    def is_configured(self):
        return True

    def parse_local_files(self, files, download_dir):
        return [
            MinerUFileResult(
                file_name=Path(file_path).name,
                state="done",
                markdown="# 示例标题\n\n这是清洗前的内容。\n\n---\n\n## 表格区\n\n数据",
                metadata={"source": "MinerU"},
                extracted_files=[],
            )
            for file_path in files
        ]


def test_clean_markdown():
    raw = "# 标题\r\n\r\n正文   \r\n\r\n---\r\n\r\n## 小节\r\n\r\n内容"
    cleaned = MinerUDocumentIngestor.clean_markdown(raw)
    assert "---" not in cleaned
    assert "正文" in cleaned
    assert "## 小节" in cleaned


def test_ingest_writes_clean_markdown(tmp_path):
    raw_dir = tmp_path / "raw"
    knowledge_dir = tmp_path / "knowledge"
    dealed_dir = tmp_path / "dealed"
    raw_dir.mkdir()
    sample_pdf = raw_dir / "report.pdf"
    sample_pdf.write_bytes(b"fake")

    ingestor = MinerUDocumentIngestor(
        raw_root=raw_dir,
        knowledge_root=knowledge_dir,
        dealed_root=dealed_dir,
        mineru_client=StubMinerUClient(),
    )

    results = ingestor.ingest([sample_pdf])
    assert results[0].status == "done"
    output_path = Path(results[0].output_file)
    assert output_path.exists()
    content = output_path.read_text(encoding="utf-8")
    assert "# 示例标题" in content
    assert "来源: MinerU 解析导入" in content
