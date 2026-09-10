"""
Judgment Orchestrator for TrustRAG.
Arbitrates between multiple proposals or evidence items with full risk control.

Enhanced with detailed refusal reasons and error tracing.
Includes structured Shadow Arbitration for algorithm upgrades.
"""
from typing import List, Dict, Any, Optional, Tuple
from pydantic import BaseModel, Field
import logging
import asyncio
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from .verdict import Verdict, Judgment
from trust_rag.core.profile import QueryProfile, QueryIntent
from trust_rag.config import get_config, get_feature_flags
from trust_rag.core.exceptions import (
    RefusalException, RefusalCode, JudgmentException,
    handle_exception, ErrorCategory, ErrorSeverity
)

logger = logging.getLogger(__name__)

class ArbitratedVerdict(BaseModel):
    """Result of evidence arbitration."""
    status: str  # ALLOW, REFUSE, CONFLICT
    reason: str
    confidence: float
    involved_ids: List[str] = Field(default_factory=list)
    reasons: List[str] = Field(default_factory=list)
    bindings: Dict[str, Any] = Field(default_factory=dict)
    risk_flags: Dict[str, bool] = Field(default_factory=dict)
    disclosure_required: bool = False


class ShadowArbitrationConfig(BaseModel):
    """Shadow Arbitration配置"""
    enabled: bool = True
    old_pipeline_weight: float = 0.0  # 生产流量中旧Pipeline权重
    shadow_sample_rate: float = 1.0   # Shadow流量采样率
    comparison_metrics: List[str] = Field(default_factory=lambda: [
        "recall_at_5", "confidence", "faithfulness", "citation_coverage"
    ])
    log_shadow_results: bool = True

class JudgmentOrchestrator:
    """
    Arbitrates query results based on evidence and risk profile.
    Integrates EvidenceSelector and EvidenceRoleClassifier for full risk control.

    structured: 实现真正的Shadow Arbitration并行算法流量
    """

    def __init__(self, shadow_config: Optional[ShadowArbitrationConfig] = None):
        # Lazy import to avoid circular dependency
        self._classifier = None
        self._selector = None

        # Shadow Arbitration配置
        self.shadow_config = shadow_config or ShadowArbitrationConfig()

        # Shadow性能统计
        self.shadow_stats = {
            "total_queries": 0,
            "shadow_success": 0,
            "old_vs_new_agreement": 0,
            "performance_comparison": {}
        }
    
    def _get_classifier(self):
        """Lazy load classifier."""
        if self._classifier is None:
            from trust_rag.engine.retrieval.evidence.classifier import EvidenceRoleClassifier
            self._classifier = EvidenceRoleClassifier()
        return self._classifier
    
    def _get_selector(self):
        """Lazy load selector."""
        if self._selector is None:
            from trust_rag.engine.retrieval.evidence.selector import EvidenceSelector
            from trust_rag.engine.retrieval.evidence.classifier import EvidenceRoleClassifier
            classifier = self._get_classifier()
            self._selector = EvidenceSelector(classifier=classifier)
        return self._selector
    
    def arbitrate(
        self,
        query: str,
        candidates: List[Any],
        profile: QueryProfile
    ) -> ArbitratedVerdict:
        """
        structured arbitration with Shadow Arbitration并行执行。

        同时运行新旧算法，进行对比分析，支持零风险上线。

        Steps:
        1. Check for empty candidates
        2. 并行执行Shadow Arbitration (新旧算法对比)
        3. Select and classify evidence using winner algorithm
        4. Evaluate risk flags
        5. Make decision based on evidence quality and risks

        Returns:
            ArbitratedVerdict with ALLOW, REFUSE, or CONFLICT status
        """
        config = get_config()
        flags = get_feature_flags()

        # PRODUCTION: Shadow Arbitration并行执行 (仅当启用时)
        if flags.enable_shadow_arbitration:
            shadow_results = self._execute_shadow_arbitration(query, candidates, profile)
            
            # 使用新算法的结果作为主要输出
            primary_result = shadow_results.get("new_algorithm")
            if not primary_result:
                logger.error("❌ CRITICAL: New algorithm failed during shadow arbitration")
                # Fallback to direct execution if shadow execution failed completely
                return self._arbitrate_new_algorithm(query, candidates, profile)

            # 记录Shadow Arbitration结果用于监控
            self._record_shadow_results(shadow_results)

            # 返回新算法的结果
            return primary_result
        else:
            # 直接执行新算法 (无Shadow开销)
            return self._arbitrate_new_algorithm(query, candidates, profile)

    def _execute_shadow_arbitration(
        self,
        query: str,
        candidates: List[Any],
        profile: QueryProfile
    ) -> Dict[str, ArbitratedVerdict]:
        """
        PRODUCTION: 并行执行新旧算法，进行Shadow Arbitration对比。

        Returns:
            Dict with 'new_algorithm' and 'old_algorithm' results
        """
        results = {}

        # 并行执行新旧算法
        with ThreadPoolExecutor(max_workers=2) as executor:
            # 提交新算法任务
            new_future = executor.submit(self._arbitrate_new_algorithm, query, candidates, profile)
            # 提交旧算法任务 (legacy)
            old_future = executor.submit(self._arbitrate_old_algorithm, query, candidates, profile)

            # 收集结果
            for future, algorithm in [(new_future, "new_algorithm"), (old_future, "old_algorithm")]:
                try:
                    result = future.result(timeout=30)  # 30秒超时
                    results[algorithm] = result
                    logger.info(f"✅ Shadow Arbitration: {algorithm} completed")
                except Exception as e:
                    logger.error(f"❌ Shadow Arbitration: {algorithm} failed: {e}")
                    results[algorithm] = None

        return results

    def _arbitrate_new_algorithm(
        self,
        query: str,
        candidates: List[Any],
        profile: QueryProfile
    ) -> ArbitratedVerdict:
        """
        新算法仲裁：使用完整Pipeline (BGE-M3 + Reranker + 风险控制)
        """
        config = get_config()
        flags = get_feature_flags()

        # Step 1: Empty candidates check
        if not candidates:
            return ArbitratedVerdict(
                status="REFUSE",
                reason="No supporting evidence found in document store",
                confidence=0.0,
                risk_flags={"evidence_insufficient": True}
            )

        # Step 2: Evidence selection with BGE-Reranker
        if flags.enable_evidence_selector:
            return self._arbitrate_with_selector(query, candidates, profile)
        else:
            return self._arbitrate_simple(query, candidates, profile)

    def _arbitrate_old_algorithm(
        self,
        query: str,
        candidates: List[Any],
        profile: QueryProfile
    ) -> ArbitratedVerdict:
        """
        旧算法仲裁：传统方法 (MiniLM + 基础评分)
        """
        # 这里实现旧算法作为对比基准
        # 简化为基本的证据质量检查

        if not candidates:
            return ArbitratedVerdict(
                status="REFUSE",
                reason="旧算法：未找到候选证据",
                confidence=0.0,
                risk_flags={"evidence_insufficient": True}
            )

        # 简单的质量检查
        high_quality_count = sum(1 for c in candidates if self._is_high_quality(c))
        total_count = len(candidates)

        if high_quality_count / total_count > 0.7:
            return ArbitratedVerdict(
                status="ALLOW",
                reason="旧算法：证据质量充足",
                confidence=min(0.8, high_quality_count / total_count),
                involved_ids=[getattr(c, 'evidence_id', str(i)) for i, c in enumerate(candidates)]
            )
        else:
            return ArbitratedVerdict(
                status="REFUSE",
                reason="旧算法：证据质量不足",
                confidence=0.3,
                risk_flags={"evidence_quality_low": True}
            )

    def _is_high_quality(self, candidate: Any) -> bool:
        """简单的高质量判断"""
        # 检查是否有文本内容
        text = getattr(candidate, 'text', '')
        if len(text.strip()) < 50:
            return False

        # 检查是否有来源信息
        if not hasattr(candidate, 'doc_id') or not candidate.doc_id:
            return False

        return True

    def _record_shadow_results(self, shadow_results: Dict[str, ArbitratedVerdict]):
        """
        记录Shadow Arbitration结果用于监控和分析
        """
        try:
            # 计算对比指标
            new_result = shadow_results.get("new_algorithm")
            old_result = shadow_results.get("old_algorithm")

            if new_result and old_result:
                # 对比分析
                comparison = {
                    "timestamp": time.time(),
                    "new_status": new_result.status,
                    "old_status": old_result.status,
                    "new_confidence": new_result.confidence,
                    "old_confidence": old_result.confidence,
                    "status_agreement": new_result.status == old_result.status,
                    "confidence_diff": new_result.confidence - old_result.confidence
                }

                logger.info(f"Shadow Arbitration对比: 新算法{new_result.status}({new_result.confidence:.2f}) "
                          f"vs 旧算法{old_result.status}({old_result.confidence:.2f})")

                # 这里可以保存到监控系统或数据库
                # TODO: 实现持久化存储用于趋势分析

        except Exception as e:
            logger.warning(f"Shadow结果记录失败: {e}")
    
    def _arbitrate_with_selector(
        self,
        query: str,
        candidates: List[Any],
        profile: QueryProfile
    ) -> ArbitratedVerdict:
        """Full arbitration using EvidenceSelector."""
        selector = self._get_selector()
        
        # Determine query type and characteristics
        is_numeric = profile.numeric_sensitive
        query_type = "factual" if QueryIntent.FACTUAL in profile.intents else "summary"
        
        # Convert candidates to ScoredChunk if needed
        scored_candidates = self._ensure_scored_chunks(candidates)
        
        if not scored_candidates:
            refusal_reason = (
                "证据候选转换失败。可能原因："
                "1) 证据格式不符合预期；"
                "2) 缺少必要的元数据字段；"
                "3) 数据损坏或格式错误。"
            )
            return ArbitratedVerdict(
                status="REFUSE",
                reason=refusal_reason,
                confidence=0.0,
                risk_flags={"evidence_insufficient": True},
                reasons=[
                    "证据候选无法转换为标准格式",
                    "建议：检查摄入文档质量、重新摄入文档、或联系技术支持"
                ]
            )
        
        # Run evidence selection
        try:
            selected = selector.select(
                candidates=scored_candidates,
                query_type=query_type,
                is_numeric=is_numeric
            )
        except Exception as e:
            logger.error(f"Evidence selection failed: {e}", exc_info=True)
            wrapped_exc = handle_exception(
                e,
                context={
                    "query": query,
                    "candidates_count": len(scored_candidates),
                    "query_type": query_type,
                    "is_numeric": is_numeric
                },
                default_category=ErrorCategory.JUDGMENT
            )
            return ArbitratedVerdict(
                status="REFUSE",
                reason=f"证据选择过程出错: {wrapped_exc.message}",
                confidence=0.0,
                reasons=[
                    f"错误类型: {type(e).__name__}",
                    f"技术详情: {wrapped_exc.technical_details}",
                    "建议：检查系统日志或联系技术支持"
                ]
            )
        
        # Extract risk flags
        risk_dict = {
            "conflict_likely": selected.risk_flags.conflict_likely,
            "disclosure_required": selected.risk_flags.disclosure_required,
            "evidence_insufficient": selected.risk_flags.evidence_insufficient,
            "ocr_only_numeric": selected.risk_flags.ocr_only_numeric,
            "modal_conflict": selected.risk_flags.modal_conflict,
            "requires_human_review": selected.risk_flags.requires_human_review,
        }
        
        # Decision logic based on risk flags
        
        # Case 1: Evidence insufficient
        if selected.risk_flags.evidence_insufficient or len(selected.core_evidence) == 0:
            refusal_reason = (
                f"证据不足，无法提供可靠答案。"
                f"经过筛选后，{len(selected.core_evidence)} 条核心证据符合要求（最低要求：1条）。"
            )
            return ArbitratedVerdict(
                status="REFUSE",
                reason=refusal_reason,
                confidence=0.0,
                risk_flags=risk_dict,
                reasons=[
                    f"证据选择后核心证据数量: {len(selected.core_evidence)}",
                    f"候选证据总数: {len(scored_candidates)}",
                    "可能原因：证据相关性不足、置信度阈值过高、或文档覆盖不完整",
                    "建议：尝试更宽泛的查询、降低风险级别、或摄入更多相关文档"
                ]
            )
        
        # Case 2: Conflict detected
        if selected.risk_flags.conflict_likely:
            # Get conflicting evidence IDs
            involved = [c.evidence_id for c in selected.core_evidence[:3]]
            conflict_reason = (
                f"检测到多个来源的证据冲突。"
                f"涉及 {len(involved)} 条证据，来自不同文档或章节，数值不一致。"
            )
            return ArbitratedVerdict(
                status="CONFLICT",
                reason=conflict_reason,
                confidence=0.3,
                involved_ids=involved,
                risk_flags=risk_dict,
                reasons=[
                    f"冲突证据数量: {len(involved)}",
                    "可能原因：不同文档版本、口径差异（GAAP vs Non-GAAP）、或数据错误",
                    "建议：检查证据来源文档、确认数据口径、或人工审核"
                ],
                disclosure_required=True
            )
        
        # Case 3: OCR-only numeric (high risk for financial data)
        if selected.risk_flags.ocr_only_numeric and is_numeric:
            refusal_reason = (
                f"数值查询需要原生数据源，但仅找到 OCR 提取的证据。"
                f"OCR 证据的准确性较低（约 70%），不适合用于财务数值查询。"
            )
            return ArbitratedVerdict(
                status="REFUSE",
                reason=refusal_reason,
                confidence=0.4,
                involved_ids=[c.evidence_id for c in selected.core_evidence],
                risk_flags=risk_dict,
                reasons=[
                    f"OCR 证据数量: {len(selected.core_evidence)}",
                    "OCR 置信度阈值: 0.70（低于数值查询要求）",
                    "可能原因：文档为扫描件、缺少原生文本、或解析失败",
                    "建议：使用原生 PDF、重新扫描高质量文档、或人工验证 OCR 结果"
                ],
                disclosure_required=True
            )
        
        # Case 4: Modal conflict (native vs OCR disagreement)
        if selected.risk_flags.modal_conflict:
            refusal_reason = (
                f"模态冲突：原生文本和 OCR 提取结果不一致。"
                f"这表明文档可能同时包含原生文本和扫描内容，且两者存在差异。"
            )
            return ArbitratedVerdict(
                status="REFUSE",
                reason=refusal_reason,
                confidence=0.5,
                involved_ids=[c.evidence_id for c in selected.core_evidence],
                risk_flags=risk_dict,
                reasons=[
                    f"冲突证据数量: {len(selected.core_evidence)}",
                    "冲突类型: 原生文本 vs OCR 提取",
                    "可能原因：混合文档格式、OCR 识别错误、或文档版本不一致",
                    "建议：检查文档质量、使用单一数据源、或人工审核冲突证据"
                ],
                disclosure_required=True
            )
        
        # Case 5: High risk only evidence
        if selected.high_risk_only and is_numeric:
            refusal_reason = (
                f"数值查询仅找到高风险证据。"
                f"所有可用证据均为高风险来源（如 OCR、图表、或低权威文档），"
                f"无法满足数值查询的准确性要求。"
            )
            return ArbitratedVerdict(
                status="REFUSE",
                reason=refusal_reason,
                confidence=0.4,
                involved_ids=[c.evidence_id for c in selected.core_evidence],
                risk_flags=risk_dict,
                reasons=[
                    f"高风险证据数量: {len(selected.core_evidence)}",
                    "证据类型: 仅包含高风险来源（OCR/图表/低权威）",
                    "可能原因：缺少高质量文档、摄入状态为 DEGRADED、或文档类型不匹配",
                    "建议：摄入高质量原生文档、使用权威来源（如 10-K）、或降低查询精度要求"
                ],
                disclosure_required=True
            )
        
        # Case 6: Normal approval
        core = selected.core_evidence
        top_evidence = core[0] if core else None
        confidence = top_evidence.scores.final if top_evidence and hasattr(top_evidence, 'scores') else 0.7
        
        # Build bindings for answer generation
        bindings = {
            "query": query,
            "core_evidence": core,
            "supporting_evidence": selected.supporting_evidence,
            "selection_reasoning": selected.selection_reason,
        }
        
        # Collect reasons
        reasons = []
        for ev in core[:3]:
            reason = selected.selection_reason.get(ev.evidence_id, "")
            if reason:
                reasons.append(f"{ev.evidence_id}: {reason}")
        
        return ArbitratedVerdict(
            status="ALLOW",
            reason="Supported by verified evidence",
            confidence=confidence,
            involved_ids=[c.evidence_id for c in core],
            reasons=reasons if reasons else ["Evidence matches query intent"],
            bindings=bindings,
            risk_flags=risk_dict,
            disclosure_required=selected.risk_flags.disclosure_required
        )
    
    def _arbitrate_simple(
        self,
        query: str,
        candidates: List[Any],
        profile: QueryProfile
    ) -> ArbitratedVerdict:
        """Simple arbitration without EvidenceSelector (fallback)."""
        # Get top candidate
        top_candidate = candidates[0]
        
        # Extract score
        if hasattr(top_candidate, 'score'):
            confidence = top_candidate.score
        elif hasattr(top_candidate, 'scores') and hasattr(top_candidate.scores, 'final'):
            confidence = top_candidate.scores.final
        else:
            confidence = 0.7
        
        # Basic risk check
        if profile.risk_level.value == "high" and confidence < 0.5:
            return ArbitratedVerdict(
                status="REFUSE",
                reason="Insufficient evidence confidence for high-risk query",
                confidence=confidence,
                risk_flags={"low_confidence": True}
            )
        
        # Build bindings
        chunk = getattr(top_candidate, 'chunk', top_candidate)
        bindings = {
            "query": query,
            "core_evidence": [top_candidate],
            "top_evidence": chunk
        }
        
        # Get evidence ID
        evidence_id = getattr(chunk, 'evidence_id', 'ev_unknown')
        
        return ArbitratedVerdict(
            status="ALLOW",
            reason="Supported by evidence",
            confidence=confidence,
            involved_ids=[evidence_id],
            reasons=["Evidence matches query intent"],
            bindings=bindings
        )
    
    def _ensure_scored_chunks(self, candidates: List[Any]) -> List[Any]:
        """
        Ensure candidates are in ScoredChunk format.
        Converts raw candidates if necessary.
        """
        from trust_rag.engine.retrieval.scored_chunk import ScoredChunk, ScoreBreakdown, RetrievalAudit
        
        result = []
        
        for cand in candidates:
            # Already a ScoredChunk
            if isinstance(cand, ScoredChunk):
                result.append(cand)
                continue
            
            # Has chunk attribute (wrapped)
            if hasattr(cand, 'chunk') and isinstance(cand.chunk, ScoredChunk):
                result.append(cand.chunk)
                continue
            
            # Convert from RawCandidate or dict-like
            try:
                if hasattr(cand, 'evidence_id'):
                    # RawCandidate-like
                    scores = ScoreBreakdown(
                        dense=getattr(cand, 'dense_score', 0.0),
                        sparse=getattr(cand, 'sparse_score', 0.0),
                        anchor=getattr(cand, 'anchor_score', 0.0),
                        final=getattr(cand, 'score', 0.0) or (
                            getattr(cand, 'dense_score', 0.0) * 0.4 +
                            getattr(cand, 'sparse_score', 0.0) * 0.4 +
                            getattr(cand, 'anchor_score', 0.0) * 0.2
                        )
                    )
                    
                    metadata = getattr(cand, 'metadata', {}) or {}
                    
                    scored = ScoredChunk(
                        chunk_id=getattr(cand, 'chunk_id', ''),
                        evidence_id=getattr(cand, 'evidence_id', ''),
                        doc_id=getattr(cand, 'doc_id', ''),
                        text=getattr(cand, 'text', ''),
                        tier=getattr(cand, 'tier', 'base'),
                        strategy=getattr(cand, 'strategy', 'sparse'),
                        scores=scores,
                        ingest_status=metadata.get('ingest_status', 'OK'),
                        metadata=metadata
                    )
                    result.append(scored)
                else:
                    logger.warning(f"Unknown candidate type: {type(cand)}")
            except Exception as e:
                logger.error(f"Failed to convert candidate: {e}")
        
        return result
