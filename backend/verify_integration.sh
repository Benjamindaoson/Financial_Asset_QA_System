#!/bin/bash
# 金融API集成 - 快速验证脚本

echo "=================================="
echo "金融API集成验证"
echo "=================================="
echo ""

# 检查Python环境
echo "1. 检查Python环境..."
python --version
echo ""

# 检查依赖
echo "2. 检查已安装的依赖..."
pip list | grep -E "(alpha-vantage|fredapi|requests|pandas|numpy)" || echo "需要安装依赖"
echo ""

# 测试无需密钥的API
echo "3. 测试无需密钥的API (CoinGecko & Frankfurter)..."
cd backend
python test_no_key_apis.py
echo ""

# 检查配置文件
echo "4. 检查配置文件..."
if [ -f ".env" ]; then
    echo "✅ .env 文件存在"
    echo "已配置的API密钥:"
    grep -E "^[A-Z_]+_API_KEY=" .env | sed 's/=.*/=***/' || echo "  未配置API密钥"
else
    echo "⚠️  .env 文件不存在，请从 .env.example 复制"
fi
echo ""

# 显示下一步
echo "=================================="
echo "下一步操作："
echo "=================================="
echo ""
echo "✅ 立即可用（无需配置）："
echo "   - CoinGecko (加密货币)"
echo "   - Frankfurter (外汇)"
echo ""
echo "📝 推荐获取API密钥："
echo "   1. Finnhub: https://finnhub.io/register"
echo "   2. FRED: https://fred.stlouisfed.org/docs/api/api_key.html"
echo ""
echo "📚 查看文档："
echo "   - 中文指南: ../集成指南.md"
echo "   - API列表: ../docs/FREE_FINANCIAL_APIS.md"
echo "   - 完成报告: ../API_集成完成.md"
echo ""
echo "🧪 运行完整测试："
echo "   pytest tests/test_api_providers.py -v"
echo ""
