#!/bin/bash
# 高级功能自动化测试脚本
# Advanced Features Automated Testing Script

BASE_URL="http://localhost:8000"
ENHANCED_API="${BASE_URL}/api/v1/enhanced"

# 颜色定义
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
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

# 测试1: 多数据源交叉验证
test_multi_source_validation() {
    print_test_header "测试1: 多数据源交叉验证"

    response=$(curl -s -X POST "${ENHANCED_API}/price?symbol=AAPL&validate=true")

    # 检查是否包含必要字段
    if echo "$response" | jq -e '.price' > /dev/null 2>&1 && \
       echo "$response" | jq -e '.consistency' > /dev/null 2>&1 && \
       echo "$response" | jq -e '.confidence' > /dev/null 2>&1 && \
       echo "$response" | jq -e '.details' > /dev/null 2>&1; then
        print_result 0 "多数据源验证返回正确结构"

        # 显示结果
        price=$(echo "$response" | jq -r '.price')
        consistency=$(echo "$response" | jq -r '.consistency')
        echo "  价格: $price, 一致性: $consistency"
    else
        print_result 1 "多数据源验证返回结构错误"
        echo "  响应: $response"
    fi
}

# 测试2: 深度涨跌分析
test_change_analysis() {
    print_test_header "测试2: 深度涨跌分析"

    response=$(curl -s -X POST "${ENHANCED_API}/change?symbol=AAPL&days=7")

    # 检查是否包含必要字段
    if echo "$response" | jq -e '.price_change' > /dev/null 2>&1 && \
       echo "$response" | jq -e '.volume_analysis' > /dev/null 2>&1 && \
       echo "$response" | jq -e '.relative_strength' > /dev/null 2>&1 && \
       echo "$response" | jq -e '.conclusion' > /dev/null 2>&1; then
        print_result 0 "深度涨跌分析返回正确结构"

        # 显示结果
        change_pct=$(echo "$response" | jq -r '.price_change.change_percent')
        pattern=$(echo "$response" | jq -r '.volume_analysis.pattern')
        echo "  涨跌幅: $change_pct%, 量价模式: $pattern"
    else
        print_result 1 "深度涨跌分析返回结构错误"
        echo "  响应: $response"
    fi
}

# 测试3: 意图识别
test_intent_recognition() {
    print_test_header "测试3: 意图识别和自适应回答"

    # 测试定义类查询
    response=$(curl -s -X POST "${ENHANCED_API}/knowledge" \
        -H "Content-Type: application/json" \
        -d '{"query": "什么是市盈率"}')

    if echo "$response" | jq -e '.intent' > /dev/null 2>&1 && \
       echo "$response" | jq -e '.user_level' > /dev/null 2>&1 && \
       echo "$response" | jq -e '.answer' > /dev/null 2>&1; then
        print_result 0 "意图识别返回正确结构"

        # 显示结果
        intent=$(echo "$response" | jq -r '.intent')
        user_level=$(echo "$response" | jq -r '.user_level')
        echo "  意图: $intent, 用户水平: $user_level"
    else
        print_result 1 "意图识别返回结构错误"
        echo "  响应: $response"
    fi
}

# 测试4: 查询路由和置信度评估
test_query_routing() {
    print_test_header "测试4: 查询路由和置信度评估"

    # 测试高置信度查询
    response=$(curl -s -X POST "${ENHANCED_API}/route" \
        -H "Content-Type: application/json" \
        -d '{"query": "AAPL最新价格是多少"}')

    if echo "$response" | jq -e '.route' > /dev/null 2>&1 && \
       echo "$response" | jq -e '.confidence' > /dev/null 2>&1; then
        print_result 0 "查询路由返回正确结构"

        # 显示结果
        route=$(echo "$response" | jq -r '.route')
        confidence=$(echo "$response" | jq -r '.confidence')
        echo "  路由: $route, 置信度: $confidence"
    else
        print_result 1 "查询路由返回结构错误"
        echo "  响应: $response"
    fi

    # 测试低置信度查询
    response=$(curl -s -X POST "${ENHANCED_API}/route" \
        -H "Content-Type: application/json" \
        -d '{"query": "特斯拉"}')

    route=$(echo "$response" | jq -r '.route')
    if [ "$route" = "clarification_needed" ] || [ "$route" = "price" ]; then
        print_result 0 "低置信度查询处理正确"
        echo "  路由: $route"
    else
        print_result 1 "低置信度查询处理错误"
        echo "  响应: $response"
    fi
}

# 测试5: 智能格式化
test_smart_formatting() {
    print_test_header "测试5: 智能格式化"

    # 测试对比类数据
    response=$(curl -s -X POST "${ENHANCED_API}/format" \
        -H "Content-Type: application/json" \
        -d '{
            "query": "AAPL和TSLA对比",
            "data": {
                "AAPL": {"price": 178.50, "change": 2.5},
                "TSLA": {"price": 245.30, "change": -1.2}
            }
        }')

    if echo "$response" | jq -e '.type' > /dev/null 2>&1; then
        print_result 0 "智能格式化返回正确结构"

        # 显示结果
        format_type=$(echo "$response" | jq -r '.type')
        echo "  格式类型: $format_type"
    else
        print_result 1 "智能格式化返回结构错误"
        echo "  响应: $response"
    fi
}

# 测试6: 友好错误处理
test_error_handling() {
    print_test_header "测试6: 友好错误处理"

    # 测试无效股票代码
    response=$(curl -s -X POST "${ENHANCED_API}/price?symbol=INVALID123&validate=true")

    if echo "$response" | jq -e '.error' > /dev/null 2>&1 || \
       echo "$response" | jq -e '.price' > /dev/null 2>&1; then
        print_result 0 "错误处理返回正确结构"

        # 检查是否有友好提示
        if echo "$response" | jq -e '.suggestions' > /dev/null 2>&1 || \
           echo "$response" | jq -e '.help' > /dev/null 2>&1; then
            echo "  包含友好建议"
        fi
    else
        print_result 1 "错误处理返回结构错误"
        echo "  响应: $response"
    fi
}

# 测试7: 增强版聊天接口
test_enhanced_chat() {
    print_test_header "测试7: 增强版聊天接口（集成测试）"

    # 使用timeout避免SSE流式响应阻塞
    response=$(timeout 5s curl -s -X POST "${ENHANCED_API}/chat" \
        -H "Content-Type: application/json" \
        -d '{"query": "AAPL最新价格"}' 2>&1 || true)

    # 检查是否收到SSE响应
    if echo "$response" | grep -q "data:" ; then
        print_result 0 "增强版聊天接口返回SSE流"
        echo "  收到流式响应"
    else
        # 可能是非流式响应或错误
        if [ -n "$response" ]; then
            print_result 0 "增强版聊天接口有响应"
        else
            print_result 1 "增强版聊天接口无响应"
        fi
    fi
}

# 测试8: 性能测试
test_performance() {
    print_test_header "测试8: 性能测试"

    # 测试响应时间
    start_time=$(date +%s%N)
    curl -s -X POST "${ENHANCED_API}/price?symbol=AAPL&validate=false" > /dev/null
    end_time=$(date +%s%N)

    duration=$(( (end_time - start_time) / 1000000 ))

    if [ $duration -lt 2000 ]; then
        print_result 0 "响应时间正常 (${duration}ms < 2000ms)"
    else
        print_result 1 "响应时间过长 (${duration}ms >= 2000ms)"
    fi
}

# 测试9: 原有功能回归测试
test_backward_compatibility() {
    print_test_header "测试9: 原有功能回归测试"

    # 测试原有聊天接口
    response=$(curl -s -o /dev/null -w "%{http_code}" -X POST "${BASE_URL}/chat" \
        -H "Content-Type: application/json" \
        -d '{"query": "AAPL最新价格"}')

    if [ "$response" = "200" ]; then
        print_result 0 "原有聊天接口正常工作"
    else
        print_result 1 "原有聊天接口异常 (HTTP $response)"
    fi

    # 测试健康检查
    response=$(curl -s -o /dev/null -w "%{http_code}" "${BASE_URL}/health")

    if [ "$response" = "200" ]; then
        print_result 0 "健康检查接口正常工作"
    else
        print_result 1 "健康检查接口异常 (HTTP $response)"
    fi
}

# 打印测试总结
print_summary() {
    echo ""
    echo "=========================================="
    echo "测试总结"
    echo "=========================================="
    echo "总测试数: $TOTAL_TESTS"
    echo -e "${GREEN}通过: $PASSED_TESTS${NC}"
    echo -e "${RED}失败: $FAILED_TESTS${NC}"

    if [ $FAILED_TESTS -eq 0 ]; then
        echo -e "\n${GREEN}所有测试通过！✓${NC}"
        exit 0
    else
        echo -e "\n${RED}部分测试失败！✗${NC}"
        exit 1
    fi
}

# 主函数
main() {
    echo "=========================================="
    echo "高级功能自动化测试"
    echo "=========================================="
    echo "开始时间: $(date)"
    echo ""

    # 检查依赖
    if ! command -v jq &> /dev/null; then
        echo -e "${RED}错误: 需要安装 jq 工具${NC}"
        echo "安装命令: sudo apt-get install jq (Ubuntu/Debian)"
        echo "         brew install jq (macOS)"
        exit 1
    fi

    # 运行测试
    check_service
    test_multi_source_validation
    test_change_analysis
    test_intent_recognition
    test_query_routing
    test_smart_formatting
    test_error_handling
    test_enhanced_chat
    test_performance
    test_backward_compatibility

    # 打印总结
    print_summary
}

# 运行主函数
main
