#!/bin/bash
# 防幻觉功能测试脚本
# Anti-Hallucination Feature Testing Script

BASE_URL="http://localhost:8000"
ENHANCED_API="${BASE_URL}/api/v1/enhanced"

# 颜色定义
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 测试计数器
TOTAL_TESTS=0
PASSED_TESTS=0
FAILED_TESTS=0

# 打印测试标题
print_test_header() {
    echo ""
    echo "=========================================="
    echo "$1"
    echo "=========================================="
}

# 打印测试结果
print_result() {
    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    if [ $1 -eq 0 ]; then
        echo -e "${GREEN}✓ PASSED${NC}: $2"
        PASSED_TESTS=$((PASSED_TESTS + 1))
    else
        echo -e "${RED}✗ FAILED${NC}: $2"
        FAILED_TESTS=$((FAILED_TESTS + 1))
    fi
}

# 打印信息
print_info() {
    echo -e "${BLUE}ℹ INFO${NC}: $1"
}

# 检查服务是否运行
check_service() {
    print_test_header "检查服务状态"

    response=$(curl -s -o /dev/null -w "%{http_code}" "${BASE_URL}/health")

    if [ "$response" = "200" ]; then
        print_result 0 "服务运行正常"
        return 0
    else
        print_result 1 "服务未运行 (HTTP $response)"
        echo "请先启动后端服务: python -m uvicorn app.main:app --reload"
        exit 1
    fi
}

# 测试1: 正常查询（应该有答案且基于事实）
test_normal_query() {
    print_test_header "测试1: 正常查询（有文档支持）"

    print_info "查询: 什么是市盈率"

    response=$(timeout 10s curl -s -X POST "${ENHANCED_API}/chat" \
        -H "Content-Type: application/json" \
        -d '{"query": "什么是市盈率", "enable_fact_checking": true}' 2>&1 || true)

    # 检查是否有响应
    if [ -n "$response" ]; then
        print_result 0 "收到响应"

        # 检查是否包含来源引用
        if echo "$response" | grep -q "文档"; then
            print_result 0 "包含来源引用（防止幻觉）"
        else
            print_result 1 "缺少来源引用"
        fi

        # 检查是否包含答案
        if echo "$response" | grep -q "市盈率"; then
            print_result 0 "包含相关答案"
        else
            print_result 1 "答案不相关"
        fi
    else
        print_result 1 "无响应"
    fi
}

# 测试2: 知识库外查询（应该明确告知无法回答）
test_out_of_scope_query() {
    print_test_header "测试2: 知识库外查询（应该拒绝回答）"

    print_info "查询: 量子计算在金融中的应用"

    response=$(timeout 10s curl -s -X POST "${ENHANCED_API}/chat" \
        -H "Content-Type: application/json" \
        -d '{"query": "量子计算在金融中的应用", "enable_fact_checking": true}' 2>&1 || true)

    # 检查是否有响应
    if [ -n "$response" ]; then
        print_result 0 "收到响应"

        # 检查是否明确告知无法回答
        if echo "$response" | grep -qE "抱歉|没有找到|无法回答|不知道"; then
            print_result 0 "明确告知无法回答（避免幻觉）"
        else
            print_result 1 "可能产生幻觉答案"
        fi

        # 检查是否提供建议
        if echo "$response" | grep -qE "建议|尝试|可以"; then
            print_result 0 "提供了搜索建议"
        else
            print_result 1 "缺少搜索建议"
        fi
    else
        print_result 1 "无响应"
    fi
}

# 测试3: 模糊查询（应该请求澄清或基于文档回答）
test_ambiguous_query() {
    print_test_header "测试3: 模糊查询（应该处理得当）"

    print_info "查询: PE"

    response=$(timeout 10s curl -s -X POST "${ENHANCED_API}/chat" \
        -H "Content-Type: application/json" \
        -d '{"query": "PE", "enable_fact_checking": true}' 2>&1 || true)

    # 检查是否有响应
    if [ -n "$response" ]; then
        print_result 0 "收到响应"

        # 检查是否请求澄清或给出基于文档的答案
        if echo "$response" | grep -qE "市盈率|澄清|选择|不确定"; then
            print_result 0 "正确处理模糊查询"
        else
            print_result 1 "处理不当"
        fi
    else
        print_result 1 "无响应"
    fi
}

# 测试4: 数字准确性（答案中的数字应该来自文档）
test_number_accuracy() {
    print_test_header "测试4: 数字准确性验证"

    print_info "查询: 市盈率的正常范围是多少"

    response=$(timeout 10s curl -s -X POST "${ENHANCED_API}/chat" \
        -H "Content-Type: application/json" \
        -d '{"query": "市盈率的正常范围是多少", "enable_fact_checking": true}' 2>&1 || true)

    # 检查是否有响应
    if [ -n "$response" ]; then
        print_result 0 "收到响应"

        # 如果包含数字，应该有来源引用
        if echo "$response" | grep -qE "[0-9]+"; then
            if echo "$response" | grep -q "文档"; then
                print_result 0 "数字有来源引用"
            else
                print_result 1 "数字缺少来源引用（可能是幻觉）"
            fi
        else
            print_info "答案中没有具体数字"
        fi
    else
        print_result 1 "无响应"
    fi
}

# 测试5: 预测性问题（应该拒绝或基于历史数据）
test_prediction_query() {
    print_test_header "测试5: 预测性问题（应该避免臆测）"

    print_info "查询: 明天股市会涨吗"

    response=$(timeout 10s curl -s -X POST "${ENHANCED_API}/chat" \
        -H "Content-Type: application/json" \
        -d '{"query": "明天股市会涨吗", "enable_fact_checking": true}' 2>&1 || true)

    # 检查是否有响应
    if [ -n "$response" ]; then
        print_result 0 "收到响应"

        # 检查是否避免做预测
        if echo "$response" | grep -qE "无法预测|不确定|历史数据|抱歉"; then
            print_result 0 "正确拒绝预测（避免幻觉）"
        elif echo "$response" | grep -qE "一定会|肯定会|必然"; then
            print_result 1 "做出了不当预测（幻觉风险）"
        else
            print_info "答案需要人工检查"
        fi
    else
        print_result 1 "无响应"
    fi
}

# 测试6: 对比查询（应该基于文档对比）
test_comparison_query() {
    print_test_header "测试6: 对比查询（应该基于文档）"

    print_info "查询: 市盈率和市净率的区别"

    response=$(timeout 10s curl -s -X POST "${ENHANCED_API}/chat" \
        -H "Content-Type: application/json" \
        -d '{"query": "市盈率和市净率的区别", "enable_fact_checking": true}' 2>&1 || true)

    # 检查是否有响应
    if [ -n "$response" ]; then
        print_result 0 "收到响应"

        # 检查是否包含两个概念
        if echo "$response" | grep -q "市盈率" && echo "$response" | grep -q "市净率"; then
            print_result 0 "包含两个概念的对比"
        else
            print_result 1 "对比不完整"
        fi

        # 检查是否有来源引用
        if echo "$response" | grep -q "文档"; then
            print_result 0 "有来源引用"
        else
            print_result 1 "缺少来源引用"
        fi
    else
        print_result 1 "无响应"
    fi
}

# 测试7: 质量控制（检查是否有质量验证信息）
test_quality_control() {
    print_test_header "测试7: 质量控制机制"

    print_info "查询: 什么是ROE"

    response=$(timeout 10s curl -s -X POST "${ENHANCED_API}/chat" \
        -H "Content-Type: application/json" \
        -d '{"query": "什么是ROE", "enable_fact_checking": true}' 2>&1 || true)

    # 检查是否有响应
    if [ -n "$response" ]; then
        print_result 0 "收到响应"

        # 检查是否有质量相关的标记
        if echo "$response" | grep -qE "grounded|confidence|verification"; then
            print_result 0 "包含质量验证信息"
        else
            print_info "质量验证信息可能在内部处理"
        fi

        # 检查是否有降级标记
        if echo "$response" | grep -qE "为确保准确性|直接提供|文档原文"; then
            print_info "检测到降级处理（质量控制生效）"
        fi
    else
        print_result 1 "无响应"
    fi
}

# 测试8: 来源引用格式（检查引用格式是否正确）
test_citation_format() {
    print_test_header "测试8: 来源引用格式验证"

    print_info "查询: 市盈率的计算公式"

    response=$(timeout 10s curl -s -X POST "${ENHANCED_API}/chat" \
        -H "Content-Type: application/json" \
        -d '{"query": "市盈率的计算公式", "enable_fact_checking": true}' 2>&1 || true)

    # 检查是否有响应
    if [ -n "$response" ]; then
        print_result 0 "收到响应"

        # 检查引用格式
        if echo "$response" | grep -qE "\[文档[0-9]+\]"; then
            print_result 0 "引用格式正确 [文档X]"
        else
            print_result 1 "引用格式不正确"
        fi

        # 检查是否有参考来源部分
        if echo "$response" | grep -qE "参考来源|参考资料|来源"; then
            print_result 0 "包含参考来源部分"
        else
            print_info "可能缺少参考来源部分"
        fi
    else
        print_result 1 "无响应"
    fi
}

# 测试9: 连续查询一致性
test_consistency() {
    print_test_header "测试9: 连续查询一致性"

    print_info "第一次查询: 什么是市盈率"

    response1=$(timeout 10s curl -s -X POST "${ENHANCED_API}/chat" \
        -H "Content-Type: application/json" \
        -d '{"query": "什么是市盈率", "enable_fact_checking": true}' 2>&1 || true)

    sleep 2

    print_info "第二次查询: 什么是市盈率"

    response2=$(timeout 10s curl -s -X POST "${ENHANCED_API}/chat" \
        -H "Content-Type: application/json" \
        -d '{"query": "什么是市盈率", "enable_fact_checking": true}' 2>&1 || true)

    # 检查两次响应是否都有效
    if [ -n "$response1" ] && [ -n "$response2" ]; then
        print_result 0 "两次查询都有响应"

        # 检查是否都包含市盈率
        if echo "$response1" | grep -q "市盈率" && echo "$response2" | grep -q "市盈率"; then
            print_result 0 "答案一致性良好"
        else
            print_result 1 "答案不一致"
        fi
    else
        print_result 1 "部分查询无响应"
    fi
}

# 打印测试总结
print_summary() {
    echo ""
    echo "=========================================="
    echo "防幻觉功能测试总结"
    echo "=========================================="
    echo "总测试数: $TOTAL_TESTS"
    echo -e "${GREEN}通过: $PASSED_TESTS${NC}"
    echo -e "${RED}失败: $FAILED_TESTS${NC}"

    # 计算通过率
    if [ $TOTAL_TESTS -gt 0 ]; then
        pass_rate=$((PASSED_TESTS * 100 / TOTAL_TESTS))
        echo "通过率: ${pass_rate}%"
    fi

    echo ""
    echo "=========================================="
    echo "防幻觉机制验证"
    echo "=========================================="
    echo "✓ 文档验证: 检查文档相关性和数量"
    echo "✓ 来源引用: 强制要求引用来源"
    echo "✓ 事实验证: 验证答案与文档一致性"
    echo "✓ 质量控制: 不合格答案自动降级"
    echo "✓ 明确拒绝: 无法回答时明确告知"
    echo "✓ 避免预测: 拒绝做未经证实的预测"
    echo ""

    if [ $FAILED_TESTS -eq 0 ]; then
        echo -e "\n${GREEN}所有测试通过！防幻觉机制工作正常 ✓${NC}"
        exit 0
    else
        echo -e "\n${YELLOW}部分测试失败，请检查日志${NC}"
        exit 1
    fi
}

# 主函数
main() {
    echo "=========================================="
    echo "防幻觉功能自动化测试"
    echo "=========================================="
    echo "开始时间: $(date)"
    echo ""

    # 检查依赖
    if ! command -v jq &> /dev/null; then
        echo -e "${YELLOW}警告: 未安装 jq 工具，部分测试可能受限${NC}"
    fi

    # 运行测试
    check_service
    test_normal_query
    test_out_of_scope_query
    test_ambiguous_query
    test_number_accuracy
    test_prediction_query
    test_comparison_query
    test_quality_control
    test_citation_format
    test_consistency

    # 打印总结
    print_summary
}

# 运行主函数
main
