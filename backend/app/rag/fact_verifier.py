"""
事实验证器 - 检测和防止幻觉
Fact Verifier - Detect and Prevent Hallucinations
"""
from typing import Dict, List, Optional
import re
import logging

logger = logging.getLogger(__name__)


class FactVerifier:
    """
    事实验证器

    功能：
    1. 验证答案是否基于提供的文档
    2. 检测幻觉内容
    3. 验证数字和事实的准确性
    """

    def verify_answer(
        self,
        answer: str,
        source_documents: List[Dict],
        query: str
    ) -> Dict:
        """
        验证答案的事实性

        Args:
            answer: 生成的答案
            source_documents: 来源文档
            query: 原始查询

        Returns:
            验证结果
        """
        # 1. 提取答案中的关键声明
        claims = self._extract_claims(answer)

        # 2. 验证每个声明
        verification_results = []
        for claim in claims:
            result = self._verify_claim(claim, source_documents)
            verification_results.append(result)

        # 3. 检测数字准确性
        number_check = self._verify_numbers(answer, source_documents)

        # 4. 检测幻觉模式
        hallucination_check = self._detect_hallucination_patterns(answer)

        # 5. 计算总体可信度
        overall_score = self._calculate_overall_score(
            verification_results,
            number_check,
            hallucination_check
        )

        return {
            "is_factual": overall_score >= 0.7,
            "confidence": overall_score,
            "claims_verified": len([r for r in verification_results if r["verified"]]),
            "claims_total": len(claims),
            "number_accuracy": number_check["accurate"],
            "hallucination_detected": hallucination_check["detected"],
            "details": {
                "claims": verification_results,
                "numbers": number_check,
                "hallucination": hallucination_check
            }
        }

    def _extract_claims(self, answer: str) -> List[str]:
        """
        提取答案中的关键声明

        Args:
            answer: 答案文本

        Returns:
            声明列表
        """
        # 按句子分割
        sentences = re.split(r'[。！？\n]', answer)
        sentences = [s.strip() for s in sentences if s.strip()]

        # 过滤掉引用标记、问候语等
        claims = []
        for sentence in sentences:
            # 跳过太短的句子
            if len(sentence) < 5:
                continue

            # 跳过纯引用标记
            if re.match(r'^\[文档\d+\]$', sentence):
                continue

            # 跳过问候语
            greeting_keywords = ["您好", "谢谢", "希望", "如果您", "请问"]
            if any(kw in sentence for kw in greeting_keywords):
                continue

            claims.append(sentence)

        return claims

    def _verify_claim(
        self,
        claim: str,
        source_documents: List[Dict]
    ) -> Dict:
        """
        验证单个声明是否有文档支持

        Args:
            claim: 声明
            source_documents: 来源文档

        Returns:
            验证结果
        """
        # 提取声明中的关键词
        claim_keywords = self._extract_keywords(claim)

        # 在文档中查找支持
        best_match_score = 0.0
        best_match_doc = None

        for doc in source_documents:
            doc_content = doc.get("content", "")
            match_score = self._calculate_match_score(
                claim_keywords,
                doc_content
            )

            if match_score > best_match_score:
                best_match_score = match_score
                best_match_doc = doc

        # 判断是否验证通过
        verified = best_match_score >= 0.5

        return {
            "claim": claim,
            "verified": verified,
            "confidence": best_match_score,
            "source": best_match_doc.get("id") if best_match_doc else None
        }

    def _extract_keywords(self, text: str) -> List[str]:
        """
        提取文本中的关键词

        Args:
            text: 文本

        Returns:
            关键词列表
        """
        # 移除标点符号
        text = re.sub(r'[^\w\s]', ' ', text)

        # 分词
        words = text.split()

        # 过滤停用词
        stopwords = {
            "的", "是", "在", "和", "与", "或", "等", "了", "着", "过",
            "也", "都", "就", "可以", "能够", "需要", "应该", "可能"
        }

        keywords = [w for w in words if w not in stopwords and len(w) > 1]

        return keywords

    def _calculate_match_score(
        self,
        keywords: List[str],
        document: str
    ) -> float:
        """
        计算关键词与文档的匹配分数

        Args:
            keywords: 关键词列表
            document: 文档内容

        Returns:
            匹配分数 (0-1)
        """
        if not keywords:
            return 0.0

        document_lower = document.lower()
        matched = sum(1 for kw in keywords if kw.lower() in document_lower)

        return matched / len(keywords)

    def _verify_numbers(
        self,
        answer: str,
        source_documents: List[Dict]
    ) -> Dict:
        """
        验证答案中的数字是否准确

        Args:
            answer: 答案文本
            source_documents: 来源文档

        Returns:
            验证结果
        """
        # 提取答案中的数字
        answer_numbers = self._extract_numbers(answer)

        if not answer_numbers:
            return {
                "accurate": True,
                "numbers_found": 0,
                "numbers_verified": 0
            }

        # 提取文档中的数字
        doc_numbers = []
        for doc in source_documents:
            doc_numbers.extend(self._extract_numbers(doc.get("content", "")))

        # 验证每个数字
        verified_count = 0
        for num in answer_numbers:
            # 检查是否在文档中出现
            if self._number_in_list(num, doc_numbers):
                verified_count += 1

        accuracy = verified_count / len(answer_numbers) if answer_numbers else 1.0

        return {
            "accurate": accuracy >= 0.8,
            "accuracy_score": accuracy,
            "numbers_found": len(answer_numbers),
            "numbers_verified": verified_count,
            "unverified_numbers": [
                num for num in answer_numbers
                if not self._number_in_list(num, doc_numbers)
            ]
        }

    def _extract_numbers(self, text: str) -> List[float]:
        """
        提取文本中的数字

        Args:
            text: 文本

        Returns:
            数字列表
        """
        # 匹配数字（包括小数、百分比）
        pattern = r'\d+\.?\d*%?'
        matches = re.findall(pattern, text)

        numbers = []
        for match in matches:
            try:
                # 移除百分号
                num_str = match.replace('%', '')
                numbers.append(float(num_str))
            except ValueError:
                continue

        return numbers

    def _number_in_list(
        self,
        number: float,
        number_list: List[float],
        tolerance: float = 0.01
    ) -> bool:
        """
        检查数字是否在列表中（允许误差）

        Args:
            number: 要检查的数字
            number_list: 数字列表
            tolerance: 允许的相对误差

        Returns:
            是否存在
        """
        for num in number_list:
            if abs(number - num) / max(abs(number), abs(num), 1) <= tolerance:
                return True
        return False

    def _detect_hallucination_patterns(self, answer: str) -> Dict:
        """
        检测常见的幻觉模式

        Args:
            answer: 答案文本

        Returns:
            检测结果
        """
        hallucination_indicators = []

        # 模式1: 过度自信的表述
        overconfident_patterns = [
            r'一定是',
            r'肯定是',
            r'绝对是',
            r'毫无疑问',
            r'显而易见'
        ]

        for pattern in overconfident_patterns:
            if re.search(pattern, answer):
                hallucination_indicators.append({
                    "type": "overconfident",
                    "pattern": pattern,
                    "severity": "medium"
                })

        # 模式2: 未经证实的预测
        prediction_patterns = [
            r'将会',
            r'一定会',
            r'必然会',
            r'未来.*会'
        ]

        for pattern in prediction_patterns:
            if re.search(pattern, answer):
                hallucination_indicators.append({
                    "type": "prediction",
                    "pattern": pattern,
                    "severity": "high"
                })

        # 模式3: 缺乏来源引用
        has_citations = bool(re.search(r'\[文档\d+\]', answer))
        if not has_citations and len(answer) > 50:
            hallucination_indicators.append({
                "type": "no_citation",
                "pattern": "缺乏来源引用",
                "severity": "high"
            })

        # 模式4: 个人观点表述
        opinion_patterns = [
            r'我认为',
            r'我觉得',
            r'我建议',
            r'个人认为'
        ]

        for pattern in opinion_patterns:
            if re.search(pattern, answer):
                hallucination_indicators.append({
                    "type": "personal_opinion",
                    "pattern": pattern,
                    "severity": "medium"
                })

        return {
            "detected": len(hallucination_indicators) > 0,
            "count": len(hallucination_indicators),
            "indicators": hallucination_indicators,
            "risk_level": self._calculate_risk_level(hallucination_indicators)
        }

    def _calculate_risk_level(
        self,
        indicators: List[Dict]
    ) -> str:
        """
        计算幻觉风险等级

        Args:
            indicators: 指标列表

        Returns:
            风险等级 (low/medium/high)
        """
        if not indicators:
            return "low"

        high_severity_count = sum(
            1 for ind in indicators
            if ind["severity"] == "high"
        )

        if high_severity_count >= 2:
            return "high"
        elif high_severity_count >= 1 or len(indicators) >= 3:
            return "medium"
        else:
            return "low"

    def _calculate_overall_score(
        self,
        verification_results: List[Dict],
        number_check: Dict,
        hallucination_check: Dict
    ) -> float:
        """
        计算总体可信度分数

        Args:
            verification_results: 声明验证结果
            number_check: 数字验证结果
            hallucination_check: 幻觉检测结果

        Returns:
            可信度分数 (0-1)
        """
        score = 1.0

        # 1. 声明验证 (权重 0.4)
        if verification_results:
            verified_ratio = sum(
                1 for r in verification_results if r["verified"]
            ) / len(verification_results)
            score *= (0.6 + 0.4 * verified_ratio)

        # 2. 数字准确性 (权重 0.3)
        if not number_check["accurate"]:
            score *= 0.7

        # 3. 幻觉检测 (权重 0.3)
        risk_level = hallucination_check["risk_level"]
        if risk_level == "high":
            score *= 0.5
        elif risk_level == "medium":
            score *= 0.7

        return max(score, 0.0)


class AnswerQualityController:
    """
    答案质量控制器

    功能：
    1. 在返回答案前进行质量检查
    2. 如果质量不合格，拒绝返回或降级处理
    3. 记录质量问题用于改进
    """

    def __init__(self):
        self.fact_verifier = FactVerifier()
        self.quality_log = []

    def check_and_control(
        self,
        answer: str,
        source_documents: List[Dict],
        query: str,
        min_confidence: float = 0.7
    ) -> Dict:
        """
        检查并控制答案质量

        Args:
            answer: 生成的答案
            source_documents: 来源文档
            query: 原始查询
            min_confidence: 最低置信度要求

        Returns:
            质量控制结果
        """
        # 1. 事实验证
        verification = self.fact_verifier.verify_answer(
            answer,
            source_documents,
            query
        )

        # 2. 判断是否通过
        passed = verification["confidence"] >= min_confidence

        # 3. 记录质量问题
        if not passed:
            self._log_quality_issue(query, answer, verification)

        # 4. 决定如何处理
        if not passed:
            # 质量不合格，返回降级答案
            controlled_answer = self._generate_fallback_answer(
                query,
                source_documents,
                verification
            )
        else:
            controlled_answer = answer

        return {
            "answer": controlled_answer,
            "passed_quality_check": passed,
            "original_confidence": verification["confidence"],
            "verification_details": verification,
            "fallback_used": not passed
        }

    def _log_quality_issue(
        self,
        query: str,
        answer: str,
        verification: Dict
    ):
        """记录质量问题"""
        self.quality_log.append({
            "query": query,
            "answer": answer[:200],
            "confidence": verification["confidence"],
            "issues": verification["details"]
        })

        logger.warning(
            f"答案质量不合格 - 查询: {query}, "
            f"置信度: {verification['confidence']:.2f}"
        )

    def _generate_fallback_answer(
        self,
        query: str,
        source_documents: List[Dict],
        verification: Dict
    ) -> str:
        """
        生成降级答案
        直接使用文档内容，不经过LLM生成

        Args:
            query: 查询
            source_documents: 来源文档
            verification: 验证结果

        Returns:
            降级答案
        """
        if not source_documents:
            return "抱歉，我在知识库中没有找到相关信息，无法回答您的问题。"

        # 使用最相关的文档
        best_doc = source_documents[0]

        answer = f"""根据相关资料：

{best_doc.get('content', '')}

【说明】为确保信息准确性，我直接提供了文档原文供您参考。

【参考来源】
[文档{best_doc.get('id', 1)}]
"""

        return answer

    def get_quality_report(self) -> Dict:
        """获取质量报告"""
        if not self.quality_log:
            return {
                "total_issues": 0,
                "average_confidence": 1.0
            }

        return {
            "total_issues": len(self.quality_log),
            "average_confidence": sum(
                log["confidence"] for log in self.quality_log
            ) / len(self.quality_log),
            "recent_issues": self.quality_log[-10:]  # 最近10个问题
        }
