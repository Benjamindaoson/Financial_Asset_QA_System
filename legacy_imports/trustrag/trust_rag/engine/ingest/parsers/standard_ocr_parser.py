"""
StandardOCRParser (Tier 2) - 标准OCR解析器

集成 MinerU (Magic-PDF) 或 PaddleOCR 的结构化OCR解析：
- Layout Analysis：识别Table、Figure、Heading和Reference
- 分页并行处理：利用multiprocessing提升CPU利用率
- 鲁棒性：OCR重试机制，自动回退到基础PaddleOCR
- 资源监控：内存占用监控，超过2GB触发垃圾回收
"""
import os
import gc
import time
import logging
import multiprocessing as mp
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed
import psutil

try:
    from magic_pdf.pipe.UNIPipe import UNIPipe
    from magic_pdf.rw.DiskReaderWriter import DiskReaderWriter
    HAS_MINERU = True
except ImportError:
    HAS_MINERU = False

try:
    import paddleocr
    from paddleocr import PaddleOCR
    HAS_PADDLE = True
except ImportError:
    HAS_PADDLE = False

from .base_parser import BaseParser, ParserTier, ParsedDocument, RetryableError, FatalError

logger = logging.getLogger(__name__)


class LayoutElement:
    """布局元素"""
    def __init__(self, element_type: str, bbox: Tuple[float, float, float, float],
                 content: str, confidence: float = 1.0):
        self.type = element_type  # 'table', 'figure', 'heading', 'reference', 'text'
        self.bbox = bbox  # (x0, y0, x1, y1)
        self.content = content
        self.confidence = confidence

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.type,
            "bbox": self.bbox,
            "content": self.content,
            "confidence": self.confidence
        }


class StandardOCRParser(BaseParser):
    """
    Tier 2: 标准OCR解析器

    核心特性：
    1. 优先使用MinerU (Magic-PDF)进行布局分析
    2. 自动回退到PaddleOCR检测模式
    3. 分页并行处理提升性能
    4. 内存监控和垃圾回收
    5. 识别Table、Figure、Heading、Reference等元素
    """

    tier = ParserTier.TIER_2
    name = "standard_ocr_parser"
    version = "2.0.0"

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)

        # 配置参数
        self.use_mineru = self.config.get('use_mineru', HAS_MINERU)
        self.use_paddle = self.config.get('use_paddle', HAS_PADDLE)
        self.max_workers = self.config.get('max_workers', min(mp.cpu_count(), 4))
        self.memory_limit_mb = self.config.get('memory_limit_mb', 2048)  # 2GB
        self.page_timeout = self.config.get('page_timeout', 60)  # 60秒超时
        self.batch_size = self.config.get('batch_size', 10)  # 批处理大小

        # 初始化OCR引擎
        self._paddle_ocr = None
        self._mineru_available = False

        # 性能监控
        self._process = psutil.Process()
        self._memory_checks = 0

    def _check_dependencies(self):
        """检查依赖项"""
        available_engines = []

        if HAS_MINERU:
            try:
                from magic_pdf.pipe.UNIPipe import UNIPipe
                available_engines.append("MinerU")
                self._mineru_available = True
            except Exception as e:
                logger.warning(f"MinerU初始化失败: {e}")

        if HAS_PADDLE:
            try:
                # 延迟初始化PaddleOCR
                available_engines.append("PaddleOCR")
            except Exception as e:
                logger.warning(f"PaddleOCR初始化失败: {e}")

        if not available_engines:
            raise ImportError("StandardOCRParser需要MinerU或PaddleOCR依赖")

        logger.info(f"StandardOCRParser初始化完成，可用引擎: {available_engines}")

    def _get_supported_formats(self) -> List[str]:
        """获取支持的文件格式"""
        return ['pdf']

    def _get_performance_profile(self) -> Dict[str, Any]:
        """获取性能配置"""
        return {
            "average_latency_ms": 3000,  # 3秒平均延迟
            "throughput_docs_per_minute": 5,  # 5文档/分钟
            "memory_usage_mb": 1024,  # 1GB内存使用
            "cpu_cores_required": self.max_workers  # 多核心
        }

    def _get_quality_profile(self) -> Dict[str, Any]:
        """获取质量配置"""
        return {
            "expected_accuracy": 0.85,  # 85%准确率
            "handles_complex_layouts": True,  # 处理复杂布局
            "handles_multilingual": True,  # 支持多语言
            "handles_tables": True,  # 处理表格
            "handles_images": True  # 处理图片
        }

    def _get_paddle_ocr(self):
        """延迟初始化PaddleOCR"""
        if self._paddle_ocr is None:
            logger.info("初始化PaddleOCR引擎...")
            self._paddle_ocr = PaddleOCR(
                use_angle_cls=True,
                lang='ch',  # 中英文混合
                use_gpu=False,  # CPU模式
                show_log=False
            )
        return self._paddle_ocr

    def parse(self, file_path: str, **kwargs) -> ParsedDocument:
        """
        同步解析方法

        Args:
            file_path: PDF文件路径
            **kwargs: 额外参数

        Returns:
            ParsedDocument: 解析结果
        """
        start_time = time.time()

        try:
            # 预检文件和内存
            self._validate_file(file_path)
            self._check_memory_usage()

            # 选择解析策略
            if self.use_mineru and self._mineru_available:
                result = self._parse_with_mineru(file_path)
            elif self.use_paddle:
                result = self._parse_with_paddle_parallel(file_path)
            else:
                raise FatalError("无可用OCR引擎")

            # 计算使用指标
            processing_time = time.time() - start_time
            usage_metrics = {
                "processing_time_seconds": round(processing_time, 3),
                "pages_processed": result.get("page_count", 0),
                "total_tokens_estimated": len(result.get("content", "").split()) * 1.3,
                "memory_peak_mb": self._get_memory_usage(),
                "tier_used": self.tier.value,
                "ocr_engine": result.get("engine", "unknown"),
                "parallel_workers": self.max_workers
            }

            # 创建解析结果
            parsed_doc = self._create_parsed_document(
                content=result.get("content", ""),
                raw_metadata={
                    "file_path": file_path,
                    "file_size": os.path.getsize(file_path),
                    "ocr_engine": result.get("engine", "unknown")
                },
                layout_profile=result.get("layout_profile", {}),
                usage_metrics=usage_metrics,
                page_count=result.get("page_count", 1),
                content_types=result.get("content_types", ["text"]),
                confidence_score=result.get("confidence", 0.85)
            )

            # 更新性能指标
            self._update_metrics(True, processing_time)

            logger.info(f"StandardOCRParser completed: {result.get('page_count', 0)} pages, "
                      f"{processing_time:.2f}s, engine: {result.get('engine', 'unknown')}")

            return parsed_doc

        except Exception as e:
            processing_time = time.time() - start_time
            self._update_metrics(False, processing_time)
            raise RetryableError(
                f"StandardOCRParser failed: {str(e)}",
                details={"file_path": file_path, "error_type": type(e).__name__}
            )

    async def async_parse(self, file_path: str, **kwargs) -> ParsedDocument:
        """
        异步解析方法（使用线程池避免阻塞）
        """
        import asyncio
        from concurrent.futures import ThreadPoolExecutor

        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor(max_workers=1) as executor:
            return await loop.run_in_executor(executor, self.parse, file_path, *[], kwargs)

    def _parse_with_mineru(self, file_path: str) -> Dict[str, Any]:
        """
        使用MinerU进行解析

        MinerU (Magic-PDF) 提供完整的文档结构分析
        """
        try:
            logger.info(f"使用MinerU解析文档: {file_path}")

            # 创建文档读取器
            pdf_bytes = open(file_path, "rb").read()
            file_name = os.path.basename(file_path)

            # 初始化MinerU管道
            pipe = UNIPipe(pdf_bytes, {}, file_name)

            # 执行解析
            pipe.pipe_classify()  # 分类
            pipe.pipe_parse()     # 解析

            # 获取解析结果
            parsed_content = pipe.pipe_mk_markdown()

            if not parsed_content or not parsed_content.strip():
                logger.warning("MinerU返回空内容，尝试回退到PaddleOCR")
                return self._parse_with_paddle_fallback(file_path)

            # 提取布局信息
            layout_profile = self._extract_mineru_layout(pipe)

            return {
                "content": parsed_content,
                "engine": "MinerU",
                "page_count": len(pipe.pdf_mid_data.get("pages", [])),
                "layout_profile": layout_profile,
                "content_types": ["text", "tables", "images"],
                "confidence": 0.88
            }

        except Exception as e:
            logger.warning(f"MinerU解析失败: {e}，回退到PaddleOCR")
            return self._parse_with_paddle_fallback(file_path)

    def _parse_with_paddle_parallel(self, file_path: str) -> Dict[str, Any]:
        """
        使用PaddleOCR进行并行解析

        分页处理，提升性能
        """
        import fitz

        logger.info(f"使用PaddleOCR并行解析文档: {file_path}")

        try:
            # 打开PDF
            doc = fitz.open(file_path)
            total_pages = len(doc)

            # 分批处理页面
            all_results = []
            batch_size = self.batch_size

            with ProcessPoolExecutor(max_workers=self.max_workers) as executor:
                futures = []

                for start_page in range(0, total_pages, batch_size):
                    end_page = min(start_page + batch_size, total_pages)
                    future = executor.submit(
                        self._process_page_batch,
                        file_path,
                        start_page,
                        end_page
                    )
                    futures.append((start_page, future))

                # 收集结果
                for start_page, future in futures:
                    try:
                        batch_result = future.result(timeout=self.page_timeout)
                        all_results.extend(batch_result)
                        self._check_memory_usage()  # 每批检查内存
                    except Exception as e:
                        logger.error(f"批次处理失败 {start_page}-{end_page}: {e}")
                        # 回退到单页处理
                        for page_num in range(start_page, min(start_page + batch_size, total_pages)):
                            try:
                                page_result = self._process_single_page(file_path, page_num)
                                all_results.append(page_result)
                            except Exception as pe:
                                logger.error(f"单页处理失败 {page_num}: {pe}")

            doc.close()

            # 合并结果
            return self._merge_page_results(all_results)

        except Exception as e:
            logger.error(f"PaddleOCR并行解析失败: {e}")
            raise

    def _parse_with_paddle_fallback(self, file_path: str) -> Dict[str, Any]:
        """
        PaddleOCR后备解析（单线程，基础检测模式）
        """
        logger.info(f"使用PaddleOCR后备模式解析文档: {file_path}")

        import fitz

        try:
            doc = fitz.open(file_path)
            all_results = []

            for page_num in range(len(doc)):
                try:
                    page_result = self._process_single_page(file_path, page_num)
                    all_results.append(page_result)
                except Exception as e:
                    logger.warning(f"页面 {page_num} 处理失败: {e}")

            doc.close()

            return self._merge_page_results(all_results)

        except Exception as e:
            raise FatalError(f"PaddleOCR后备解析失败: {e}")

    def _process_page_batch(self, file_path: str, start_page: int, end_page: int) -> List[Dict[str, Any]]:
        """
        处理一批页面（用于并行处理）
        """
        results = []

        for page_num in range(start_page, end_page):
            try:
                result = self._process_single_page(file_path, page_num)
                results.append(result)
            except Exception as e:
                logger.error(f"页面 {page_num} 处理失败: {e}")
                # 返回空结果
                results.append({
                    "page_num": page_num,
                    "content": "",
                    "layout_elements": [],
                    "confidence": 0.0
                })

        return results

    def _process_single_page(self, file_path: str, page_num: int) -> Dict[str, Any]:
        """
        处理单个页面
        """
        import fitz

        try:
            # 打开文档（每个进程独立打开）
            doc = fitz.open(file_path)
            page = doc.load_page(page_num)

            # 转换为图像
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))  # 2x缩放提升OCR质量
            img_data = pix.tobytes("png")

            # OCR识别
            ocr = self._get_paddle_ocr()
            ocr_result = ocr.ocr(img_data, cls=True)

            # 解析OCR结果
            layout_elements = []
            content_parts = []

            if ocr_result and ocr_result[0]:
                for line in ocr_result[0]:
                    if len(line) >= 2:
                        bbox, (text, confidence) = line
                        if text.strip():
                            # 分类元素类型
                            element_type = self._classify_text_element(text, bbox)

                            layout_elements.append(LayoutElement(
                                element_type=element_type,
                                bbox=tuple(bbox),
                                content=text,
                                confidence=float(confidence)
                            ))

                            content_parts.append(text)

            doc.close()

            return {
                "page_num": page_num,
                "content": " ".join(content_parts),
                "layout_elements": [elem.to_dict() for elem in layout_elements],
                "confidence": sum(elem.confidence for elem in layout_elements) / max(len(layout_elements), 1)
            }

        except Exception as e:
            if 'doc' in locals():
                doc.close()
            raise

    def _classify_text_element(self, text: str, bbox: List[float]) -> str:
        """
        分类文本元素类型

        基于启发式规则识别表格、标题等
        """
        # 检查是否为表格行（多个数字/分隔符）
        if re.search(r'\d+\s+\d+', text) or '|' in text or '\t' in text:
            return "table"

        # 检查是否为标题（短文本、大写等）
        if len(text.strip()) < 100 and (text.isupper() or text.istitle()):
            return "heading"

        # 检查是否为参考文献（包含数字引用等）
        if re.search(r'\[\d+\]|\(\d+\)', text):
            return "reference"

        # 检查是否为公式（包含特殊符号）
        if any(char in text for char in ['∑', '∫', '√', '±', '×', '÷', '∈', '∋']):
            return "formula"

        return "text"

    def _merge_page_results(self, page_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        合并页面结果
        """
        # 按页面排序
        page_results.sort(key=lambda x: x["page_num"])

        content_parts = []
        all_layout_elements = []
        total_confidence = 0
        valid_pages = 0

        for result in page_results:
            if result["content"].strip():
                # 添加页面分隔符
                if content_parts:
                    content_parts.append(f"\n\n--- Page {result['page_num'] + 1} ---\n\n")

                content_parts.append(result["content"])
                valid_pages += 1

            all_layout_elements.extend(result.get("layout_elements", []))
            if result["confidence"] > 0:
                total_confidence += result["confidence"]

        # 分析布局概况
        layout_profile = self._analyze_layout_profile(all_layout_elements)

        return {
            "content": "".join(content_parts),
            "engine": "PaddleOCR",
            "page_count": len(page_results),
            "layout_profile": layout_profile,
            "content_types": self._detect_content_types_from_layout(all_layout_elements),
            "confidence": total_confidence / max(valid_pages, 1)
        }

    def _analyze_layout_profile(self, layout_elements: List[Dict[str, Any]]) -> Dict[str, Any]:
        """分析布局概况"""
        element_counts = {}
        total_elements = len(layout_elements)

        for elem in layout_elements:
            elem_type = elem.get("type", "unknown")
            element_counts[elem_type] = element_counts.get(elem_type, 0) + 1

        return {
            "total_elements": total_elements,
            "element_distribution": element_counts,
            "has_tables": element_counts.get("table", 0) > 0,
            "has_headings": element_counts.get("heading", 0) > 0,
            "has_references": element_counts.get("reference", 0) > 0,
            "has_figures": element_counts.get("figure", 0) > 0
        }

    def _detect_content_types_from_layout(self, layout_elements: List[Dict[str, Any]]) -> List[str]:
        """从布局元素检测内容类型"""
        types = ["text"]

        elem_types = {elem.get("type", "unknown") for elem in layout_elements}

        if "table" in elem_types:
            types.append("tables")
        if "figure" in elem_types:
            types.append("images")

        return types

    def _extract_mineru_layout(self, pipe) -> Dict[str, Any]:
        """从MinerU管道提取布局信息"""
        # 这是一个简化的实现，实际需要根据MinerU的API调整
        try:
            # 获取页面数据
            pages_data = pipe.pdf_mid_data.get("pages", [])

            return {
                "total_pages": len(pages_data),
                "layout_analysis": True,
                "mineru_version": "detected",
                "content_structure": "markdown"  # MinerU输出Markdown格式
            }
        except Exception:
            return {"layout_analysis": False}

    def _validate_file(self, file_path: str):
        """验证文件"""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"文件不存在: {file_path}")

        if not file_path.lower().endswith('.pdf'):
            raise ValueError(f"不支持的文件格式: {file_path}")

        file_size = os.path.getsize(file_path)
        if file_size > 100 * 1024 * 1024:  # 100MB
            raise ValueError(f"文件过大: {file_size} bytes")

    def _check_memory_usage(self):
        """检查内存使用情况"""
        memory_mb = self._get_memory_usage()

        if memory_mb > self.memory_limit_mb:
            logger.warning(".1f")
            # 强制垃圾回收
            gc.collect()
            self._memory_checks += 1

            # 如果多次触发，记录告警
            if self._memory_checks > 3:
                logger.error(".1f")

    def _get_memory_usage(self) -> float:
        """获取当前内存使用（MB）"""
        try:
            return self._process.memory_info().rss / 1024 / 1024
        except Exception:
            return 0.0
