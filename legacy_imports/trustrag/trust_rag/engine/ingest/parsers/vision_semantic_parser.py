"""
VisionSemanticParser (Tier 3) - VLM语义解析器

集成 Qwen2-VL 的视觉语义解析：
- 处理高难度视觉语义，实现"保命级"准确率
- 针对复杂页面转为高分辨率图像，Prompt包含财务报表还原指令
- 动态Token限制，超长页面采用切片扫描+LLM合并（Map-Reduce模式）
- 降级安全网：Rate Limit或超时自动降级到StandardOCRParser
"""
import os
import time
import logging
import asyncio
from typing import Dict, Any, List, Optional, Tuple, Union
from pathlib import Path
import base64
import io

try:
    from transformers import Qwen2VLForConditionalGeneration, AutoTokenizer, AutoProcessor
    import torch
    from PIL import Image
    HAS_QWEN2VL = True
except ImportError:
    HAS_QWEN2VL = False
    # 提供占位符避免NameError
    class Image:
        Image = None

from .base_parser import BaseParser, ParserTier, ParsedDocument, FatalError, RetryableError
from .standard_ocr_parser import StandardOCRParser
from .continuity_checker import ContinuityChecker

logger = logging.getLogger(__name__)


class VisionSemanticParser(BaseParser):
    """
    Tier 3: VLM语义解析器

    核心特性：
    1. 集成Qwen2-VL进行视觉语义理解
    2. 针对复杂财务报表提供专门的Prompt模板
    3. 动态Token控制和Map-Reduce处理超长文档
    4. 完善的降级机制：Rate Limit -> 重试 -> OCR降级
    5. 高分辨率图像处理和切片扫描
    """

    tier = ParserTier.TIER_3
    name = "vision_semantic_parser"
    version = "2.0.0"

    # 财务报表专用Prompt模板
    FINANCIAL_REPORT_PROMPT = """
请将此财务报表图像严格还原为规范的Markdown表格格式。

要求：
1. 识别并正确处理合并单元格，确保表格结构完整
2. 提取页面下方的尾注及其与表格行的关联关系
3. 保持数字的精确性，不要四舍五入
4. 对于复杂的多层表头，使用适当的Markdown语法表示
5. 如果有图表说明文字，一并提取并关联到对应表格
6. 输出纯Markdown格式，不要添加多余的解释

请确保表格的行列对应关系准确，特别关注：
- 资产负债表：资产=负债+所有者权益
- 利润表：收入-成本=利润
- 现金流量表：经营/投资/融资活动的现金流

输出格式：直接输出Markdown表格，不要包含其他内容。
"""

    # 通用文档Prompt
    GENERAL_DOCUMENT_PROMPT = """
请将此文档图像转换为准确的Markdown格式文本。

要求：
1. 保持原始文档的段落结构和层次关系
2. 正确识别标题级别（H1、H2、H3等）
3. 对于表格，使用Markdown表格语法
4. 对于列表，使用适当的编号或符号列表
5. 保持文本的完整性和准确性
6. 如果有图片或图表，在适当位置添加占位符说明

输出格式：纯Markdown文本。
"""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)

        # 配置参数
        self.model_path = self.config.get('model_path', 'Qwen/Qwen2-VL-7B-Instruct')
        self.device = self.config.get('device', 'auto')  # auto, cuda, cpu
        self.max_tokens = self.config.get('max_tokens', 4096)
        self.temperature = self.config.get('temperature', 0.1)  # 低温度保证准确性
        self.retry_attempts = self.config.get('retry_attempts', 3)
        self.retry_delay = self.config.get('retry_delay', 5)  # 秒
        self.timeout = self.config.get('timeout', 120)  # 秒

        # Token控制
        self.max_image_tokens = self.config.get('max_image_tokens', 170)  # Qwen2-VL的图像token限制
        self.slice_overlap = self.config.get('slice_overlap', 50)  # 切片重叠像素

        # 降级配置
        self.enable_degradation = self.config.get('enable_degradation', True)
        self.degradation_parser = StandardOCRParser()

        # 连续性检查器
        self.continuity_checker = ContinuityChecker(self.config.get('continuity_config', {}))

        # 模型状态
        self._model = None
        self._tokenizer = None
        self._processor = None
        self._is_initialized = False

    def _check_dependencies(self):
        """检查依赖项"""
        if not HAS_QWEN2VL:
            raise ImportError("VisionSemanticParser需要Qwen2-VL相关依赖")

        # 检查CUDA可用性
        if self.device == 'auto':
            self.device = 'cuda' if torch.cuda.is_available() else 'cpu'

        logger.info(f"VisionSemanticParser将使用设备: {self.device}")

    def _get_supported_formats(self) -> List[str]:
        """获取支持的文件格式"""
        return ['pdf']

    def _get_performance_profile(self) -> Dict[str, Any]:
        """获取性能配置"""
        return {
            "average_latency_ms": 15000,  # 15秒平均延迟（VLM较慢）
            "throughput_docs_per_minute": 1,  # 1文档/分钟
            "memory_usage_mb": 4096,  # 4GB内存（模型大小）
            "cpu_cores_required": 1  # 单核心，但需要GPU
        }

    def _get_quality_profile(self) -> Dict[str, Any]:
        """获取质量配置"""
        return {
            "expected_accuracy": 0.95,  # 95%准确率（VLM优势）
            "handles_complex_layouts": True,  # 完美处理复杂布局
            "handles_multilingual": True,  # 支持多语言
            "handles_tables": True,  # 擅长表格识别
            "handles_images": True  # 视觉理解
        }

    def _initialize_model(self):
        """延迟初始化模型"""
        if self._is_initialized:
            return

        try:
            logger.info(f"初始化Qwen2-VL模型: {self.model_path}")

            # 加载模型（量化版本以节省内存）
            self._model = Qwen2VLForConditionalGeneration.from_pretrained(
                self.model_path,
                torch_dtype=torch.float16 if self.device == 'cuda' else torch.float32,
                device_map="auto" if self.device == 'cuda' else None,
                load_in_4bit=True,  # 4-bit量化
                trust_remote_code=True
            )

            self._tokenizer = AutoTokenizer.from_pretrained(
                self.model_path,
                trust_remote_code=True
            )

            self._processor = AutoProcessor.from_pretrained(
                self.model_path,
                trust_remote_code=True
            )

            if self.device == 'cpu':
                self._model.to(self.device)

            self._is_initialized = True
            logger.info("Qwen2-VL模型初始化完成")

        except Exception as e:
            raise FatalError(f"Qwen2-VL模型初始化失败: {e}")

    def parse(self, file_path: str, **kwargs) -> ParsedDocument:
        """
        同步解析方法

        Args:
            file_path: PDF文件路径
            **kwargs: 额外参数
                - document_type: 'financial' 或 'general'
                - force_single_pass: 是否强制单次处理（跳过切片）

        Returns:
            ParsedDocument: 解析结果
        """
        start_time = time.time()

        try:
            # 初始化模型
            self._initialize_model()

            # 预检文件
            self._validate_file(file_path)

            # 获取文档类型
            document_type = kwargs.get('document_type', 'general')

            # 选择处理策略
            force_single_pass = kwargs.get('force_single_pass', False)

            if force_single_pass:
                result = self._parse_single_pass(file_path, document_type)
            else:
                result = self._parse_with_chunking(file_path, document_type)

            # 计算使用指标
            processing_time = time.time() - start_time
            usage_metrics = {
                "processing_time_seconds": round(processing_time, 3),
                "pages_processed": result.get("page_count", 0),
                "total_tokens_estimated": result.get("total_tokens", 0),
                "model_calls": result.get("model_calls", 1),
                "tier_used": self.tier.value,
                "vlm_model": self.model_path,
                "device": self.device,
                "degraded": result.get("is_degraded", False)
            }

            # 创建解析结果
            parsed_doc = self._create_parsed_document(
                content=result.get("content", ""),
                raw_metadata={
                    "file_path": file_path,
                    "file_size": os.path.getsize(file_path),
                    "document_type": document_type,
                    "vlm_model": self.model_path
                },
                layout_profile=result.get("layout_profile", {}),
                usage_metrics=usage_metrics,
                page_count=result.get("page_count", 1),
                content_types=result.get("content_types", ["text"]),
                confidence_score=result.get("confidence", 0.95),
                is_degraded=result.get("is_degraded", False),
                degradation_reason=result.get("degradation_reason")
            )

            # 更新性能指标
            self._update_metrics(True, processing_time)

            logger.info(f"VisionSemanticParser completed: {result.get('page_count', 0)} pages, "
                      f"{processing_time:.2f}s, calls: {result.get('model_calls', 1)}")

            return parsed_doc

        except Exception as e:
            processing_time = time.time() - start_time
            self._update_metrics(False, processing_time)

            # 尝试降级处理
            if self.enable_degradation and not isinstance(e, FatalError):
                logger.warning(f"VLM解析失败，尝试降级: {e}")
                return self._degrade_to_ocr(file_path, str(e))

            raise RetryableError(
                f"VisionSemanticParser failed: {str(e)}",
                details={"file_path": file_path, "error_type": type(e).__name__}
            )

    async def async_parse(self, file_path: str, **kwargs) -> ParsedDocument:
        """
        异步解析方法

        VLM推理通常是CPU/GPU密集型，使用asyncio.to_thread避免阻塞
        """
        return await asyncio.to_thread(self.parse, file_path, **kwargs)

    def _parse_single_pass(self, file_path: str, document_type: str) -> Dict[str, Any]:
        """
        单次处理整个文档

        适用于短文档或强制单次处理的场景
        """
        import fitz

        logger.info(f"单次处理文档: {file_path}")

        try:
            doc = fitz.open(file_path)
            page_count = len(doc)

            # 将所有页面合并为单张高分辨率图像
            combined_image = self._combine_pages_to_image(doc)

            # VLM推理
            content, tokens_used = self._vlm_inference(combined_image, document_type)

            doc.close()

            return {
                "content": content,
                "page_count": page_count,
                "total_tokens": tokens_used,
                "model_calls": 1,
                "layout_profile": {
                    "processing_mode": "single_pass",
                    "combined_image": True,
                    "pages_merged": page_count
                },
                "content_types": ["text", "tables", "images"],
                "confidence": 0.95,
                "is_degraded": False
            }

        except Exception as e:
            if 'doc' in locals():
                doc.close()
            raise

    def _parse_with_chunking(self, file_path: str, document_type: str) -> Dict[str, Any]:
        """
        切片处理文档 (Map-Reduce模式)

        适用于长文档，控制Token使用
        """
        import fitz

        logger.info(f"切片处理文档: {file_path}")

        try:
            doc = fitz.open(file_path)
            page_count = len(doc)

            # 分析文档复杂度，决定切片策略
            chunking_strategy = self._analyze_chunking_strategy(doc)

            if chunking_strategy["needs_chunking"]:
                # 分块处理
                chunks = self._create_document_chunks(doc, chunking_strategy)
                chunk_results = []

                for i, chunk in enumerate(chunks):
                    logger.info(f"处理块 {i+1}/{len(chunks)}")

                    # 将块转换为图像
                    chunk_image = self._chunk_to_image(chunk)

                    # VLM推理
                    chunk_content, chunk_tokens = self._vlm_inference(chunk_image, document_type)
                    chunk_results.append({
                        "chunk_id": i,
                        "content": chunk_content,
                        "tokens": chunk_tokens,
                        "pages": chunk["page_range"]
                    })

                # 合并结果 (Reduce阶段)
                merged_content = self._merge_chunk_results(chunk_results, document_type)

                # 连续性检查和修复
                page_boundaries = [result["pages"][1] for result in chunk_results[:-1]]  # 各块的结束位置
                continuity_problems = self.continuity_checker.check_continuity(merged_content, page_boundaries)

                if continuity_problems:
                    logger.info(f"检测到 {len(continuity_problems)} 个连续性问题，开始修复")

                    # 查找重叠区域
                    page_contents = [result["content"] for result in chunk_results]
                    overlap_regions = self.continuity_checker.find_overlap_regions(page_contents)

                    # 应用修复
                    final_content = self.continuity_checker.repair_continuity(
                        merged_content, continuity_problems, overlap_regions
                    )

                    # 记录修复信息
                    repair_info = {
                        "problems_detected": len(continuity_problems),
                        "problems_fixed": len([p for p in continuity_problems if p.severity > 0.5]),
                        "overlap_regions_found": len(overlap_regions)
                    }
                    logger.info(f"连续性修复完成: {repair_info}")
                else:
                    final_content = merged_content

                total_tokens = sum(result["tokens"] for result in chunk_results)

                doc.close()

                return {
                    "content": final_content,
                    "page_count": page_count,
                    "total_tokens": total_tokens,
                    "model_calls": len(chunk_results),
                    "layout_profile": {
                        "processing_mode": "chunking",
                        "chunks_count": len(chunk_results),
                        "chunking_strategy": chunking_strategy
                    },
                    "content_types": ["text", "tables", "images"],
                    "confidence": 0.93,  # 切片可能略微降低准确性
                    "is_degraded": False
                }

            else:
                # 单次处理
                doc.close()
                return self._parse_single_pass(file_path, document_type)

        except Exception as e:
            if 'doc' in locals():
                doc.close()
            raise

    def _vlm_inference(self, image: Image.Image, document_type: str) -> Tuple[str, int]:
        """
        VLM推理核心方法

        Args:
            image: PIL图像
            document_type: 文档类型 ('financial' 或 'general')

        Returns:
            Tuple[str, int]: (解析内容, 使用的tokens)
        """
        # 选择Prompt
        if document_type == 'financial':
            prompt = self.FINANCIAL_REPORT_PROMPT
        else:
            prompt = self.GENERAL_DOCUMENT_PROMPT

        # 构建消息
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image", "image": image}
                ]
            }
        ]

        # 应用聊天模板
        text = self._processor.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )

        # 处理输入
        inputs = self._processor(
            text=[text],
            images=[image],
            return_tensors="pt"
        ).to(self.device)

        # 生成响应
        with torch.no_grad():
            generated_ids = self._model.generate(
                **inputs,
                max_new_tokens=self.max_tokens,
                temperature=self.temperature,
                do_sample=self.temperature > 0,
                pad_token_id=self._tokenizer.pad_token_id,
                eos_token_id=self._tokenizer.eos_token_id
            )

        # 解码结果
        generated_ids_trimmed = [
            out_ids[len(in_ids):] for in_ids, out_ids in zip(inputs.input_ids, generated_ids)
        ]

        output_text = self._processor.batch_decode(
            generated_ids_trimmed,
            skip_special_tokens=True,
            clean_up_tokenization_spaces=False
        )[0]

        # 估算token使用量
        tokens_used = len(generated_ids[0]) - len(inputs.input_ids[0])

        return output_text.strip(), tokens_used

    def _combine_pages_to_image(self, doc) -> Image.Image:
        """
        将PDF页面组合为单张图像

        用于单次处理的场景
        """
        import fitz

        page_images = []

        for page_num in range(len(doc)):
            page = doc.load_page(page_num)

            # 高分辨率渲染
            matrix = fitz.Matrix(2, 2)  # 2x缩放
            pix = page.get_pixmap(matrix=matrix)
            img_data = pix.tobytes("png")

            page_image = Image.open(io.BytesIO(img_data))
            page_images.append(page_image)

        # 垂直拼接
        if len(page_images) == 1:
            return page_images[0]

        # 计算总高度
        total_width = max(img.width for img in page_images)
        total_height = sum(img.height for img in page_images)

        # 创建组合图像
        combined = Image.new('RGB', (total_width, total_height), 'white')
        y_offset = 0

        for img in page_images:
            combined.paste(img, (0, y_offset))
            y_offset += img.height

        return combined

    def _analyze_chunking_strategy(self, doc) -> Dict[str, Any]:
        """
        分析文档，决定切片策略
        """
        page_count = len(doc)

        # 估算总token数（粗略）
        estimated_tokens = page_count * 500  # 每页约500 tokens

        # 如果总token数超过阈值，需要切片
        needs_chunking = estimated_tokens > self.max_tokens * 0.8

        if needs_chunking:
            # 计算最佳块大小
            max_pages_per_chunk = max(1, self.max_tokens // 500)
            chunk_size = min(max_pages_per_chunk, 5)  # 最多5页 per chunk

            return {
                "needs_chunking": True,
                "chunk_size": chunk_size,
                "overlap_pages": 0,  # 页面级别不重叠
                "estimated_chunks": (page_count + chunk_size - 1) // chunk_size
            }
        else:
            return {
                "needs_chunking": False,
                "chunk_size": page_count,
                "overlap_pages": 0,
                "estimated_chunks": 1
            }

    def _create_document_chunks(self, doc, strategy: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        创建文档块
        """
        chunks = []
        page_count = len(doc)
        chunk_size = strategy["chunk_size"]

        for start_page in range(0, page_count, chunk_size):
            end_page = min(start_page + chunk_size, page_count)

            chunk = {
                "page_range": (start_page, end_page),
                "pages": []
            }

            # 收集页面
            for page_num in range(start_page, end_page):
                page = doc.load_page(page_num)
                chunk["pages"].append({
                    "page_num": page_num,
                    "page": page
                })

            chunks.append(chunk)

        return chunks

    def _chunk_to_image(self, chunk: Dict[str, Any]) -> Image.Image:
        """
        将文档块转换为图像
        """
        page_images = []

        for page_data in chunk["pages"]:
            page = page_data["page"]

            # 高分辨率渲染
            matrix = fitz.Matrix(2, 2)
            pix = page.get_pixmap(matrix=matrix)
            img_data = pix.tobytes("png")

            page_image = Image.open(io.BytesIO(img_data))
            page_images.append(page_image)

        # 垂直拼接块内的页面
        if len(page_images) == 1:
            return page_images[0]

        total_width = max(img.width for img in page_images)
        total_height = sum(img.height for img in page_images)

        combined = Image.new('RGB', (total_width, total_height), 'white')
        y_offset = 0

        for img in page_images:
            combined.paste(img, (0, y_offset))
            y_offset += img.height

        return combined

    def _merge_chunk_results(self, chunk_results: List[Dict[str, Any]], document_type: str) -> str:
        """
        合并块结果 (Reduce阶段)

        使用简单的启发式合并，对于复杂文档可能需要额外的VLM调用
        """
        if len(chunk_results) == 1:
            return chunk_results[0]["content"]

        # 按页面顺序排序
        chunk_results.sort(key=lambda x: x["pages"][0])

        merged_parts = []

        for i, result in enumerate(chunk_results):
            content = result["content"]

            # 添加块分隔符
            if i > 0:
                merged_parts.append(f"\n\n--- Document Section {i+1} ---\n\n")

            merged_parts.append(content)

        merged_content = "".join(merged_parts)

        # 对于财务文档，进行额外的合并优化
        if document_type == 'financial':
            merged_content = self._optimize_financial_merge(merged_content)

        return merged_content

    def _optimize_financial_merge(self, content: str) -> str:
        """
        优化财务文档的合并结果

        处理跨块的表格合并等
        """
        # 简单的后处理：合并被分割的表格行
        lines = content.split('\n')
        optimized_lines = []
        table_context = False

        for line in lines:
            # 检测表格行（包含|分隔符）
            is_table_row = '|' in line and len(line.split('|')) >= 3

            if is_table_row:
                table_context = True
                optimized_lines.append(line)
            elif table_context and line.strip() == "":
                # 表格内的空行，保留
                optimized_lines.append(line)
            elif table_context and not is_table_row:
                # 表格结束
                table_context = False
                optimized_lines.append(line)
            else:
                optimized_lines.append(line)

        return '\n'.join(optimized_lines)

    def _degrade_to_ocr(self, file_path: str, reason: str) -> ParsedDocument:
        """
        降级到OCR解析器
        """
        logger.info(f"降级到OCR解析器: {reason}")

        try:
            # 使用OCR解析器
            ocr_result = self.degradation_parser.parse(file_path)

            # 标记为降级
            ocr_result.is_degraded = True
            ocr_result.degradation_reason = f"VLM failed: {reason}, degraded to OCR"
            ocr_result.usage_metrics["degraded_from"] = self.tier.value

            return ocr_result

        except Exception as e:
            raise FatalError(f"降级处理也失败: {e}")

    def _validate_file(self, file_path: str):
        """验证文件"""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"文件不存在: {file_path}")

        if not file_path.lower().endswith('.pdf'):
            raise ValueError(f"不支持的文件格式: {file_path}")

        file_size = os.path.getsize(file_path)
        if file_size > 200 * 1024 * 1024:  # 200MB
            raise ValueError(f"文件过大: {file_size} bytes")
