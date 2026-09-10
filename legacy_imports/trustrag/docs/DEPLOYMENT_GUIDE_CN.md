# TrustRAG AWS 部署详细指引

## 📋 前置准备清单

### 1. 必需工具
- [ ] **AWS CLI** 已安装并配置
- [ ] **Terraform** >= 1.0 已安装
- [ ] **Docker Desktop** 已安装并运行
- [ ] **OpenAI API Key** 已准备

### 2. 验证工具安装

```powershell
# 检查 AWS CLI
aws --version
# 预期输出: aws-cli/2.x.x

# 检查 Terraform
terraform --version
# 预期输出: Terraform v1.x.x

# 检查 Docker
docker --version
# 预期输出: Docker version 24.x.x

# 检查 AWS 凭证配置
aws sts get-caller-identity
# 应该返回你的 AWS 账户信息
```

### 3. 配置 AWS 凭证（如果还没配置）

```powershell
aws configure
```

输入：
- **AWS Access Key ID**: 你的访问密钥
- **AWS Secret Access Key**: 你的密钥
- **Default region name**: `us-east-1` （推荐）
- **Default output format**: `json`

---

## 🚀 部署步骤（详细版）

### 步骤 1: 设置环境变量

```powershell
# 设置 AWS 区域
$env:AWS_REGION = "us-east-1"

# 设置 OpenAI API Key（替换为你的实际密钥）
$env:TF_VAR_openai_api_key = "sk-proj-xxxxxxxxxxxxxxxxxx"

# 验证环境变量
echo "AWS Region: $env:AWS_REGION"
echo "OpenAI Key已设置: $($env:TF_VAR_openai_api_key.Substring(0,10))..."
```

⚠️ **重要**: 不要在命令历史中暴露完整的 API Key

---

### 步骤 2: 初始化 Terraform

```powershell
# 进入 terraform 目录
cd d:\trust_rag\terraform

# 初始化 Terraform（下载 AWS provider）
terraform init
```

**预期输出**:
```
Initializing the backend...
Initializing provider plugins...
- Finding hashicorp/aws versions matching "~> 5.0"...
- Installing hashicorp/aws v5.x.x...
Terraform has been successfully initialized!
```

---

### 步骤 3: 预览部署计划

```powershell
# 查看将要创建的资源
terraform plan
```

**预期输出**: 显示将创建约 25+ 个资源，包括：
- VPC 和子网
- ECS 集群
- ALB（负载均衡器）
- ElastiCache Redis
- IAM 角色
- 安全组
- ECR 仓库

**检查要点**:
- ✅ 确认区域是 `us-east-1`
- ✅ 确认没有错误信息
- ✅ 确认资源数量合理（约 25-30 个）

---

### 步骤 4: 部署基础设施

```powershell
# 执行部署（需要确认）
terraform apply
```

**交互提示**: 
```
Do you want to perform these actions?
  Terraform will perform the actions described above.
  Only 'yes' will be accepted to approve.

  Enter a value: 
```

输入 `yes` 并回车

**部署时间**: 约 5-8 分钟

**进度提示**:
```
aws_vpc.main: Creating...
aws_ecr_repository.main: Creating...
aws_elasticache_cluster.redis: Creating... (这个最慢，约 5 分钟)
...
Apply complete! Resources: 27 added, 0 changed, 0 destroyed.
```

**成功标志**:
```
Outputs:

alb_dns_name = "trustrag-alb-1234567890.us-east-1.elb.amazonaws.com"
ecr_repository_url = "123456789012.dkr.ecr.us-east-1.amazonaws.com/trustrag"
redis_endpoint = "trustrag-redis.xxxxx.0001.use1.cache.amazonaws.com:6379"
```

⚠️ **保存这些输出值**，后续步骤需要使用

---

### 步骤 5: 构建并推送 Docker 镜像

```powershell
# 返回项目根目录
cd d:\trust_rag

# 运行部署脚本
.\scripts\deploy.ps1
```

**脚本执行流程**:
1. 获取 AWS 账户 ID
2. 构建 Docker 镜像（约 2-3 分钟）
3. 标记镜像
4. 登录 ECR
5. 推送镜像到 ECR（约 1-2 分钟）

**预期输出**:
```
=== TrustRAG AWS Deployment ===
AWS Account: 123456789012
AWS Region: us-east-1
ECR Repository: 123456789012.dkr.ecr.us-east-1.amazonaws.com/trustrag

Step 1: Building Docker image...
[+] Building 120.5s (15/15) FINISHED

Step 2: Tagging image for ECR...

Step 3: Logging in to ECR...
Login Succeeded

Step 4: Pushing image to ECR...
latest: digest: sha256:xxxxx size: 2841

=== Deployment Complete ===
Image pushed to: 123456789012.dkr.ecr.us-east-1.amazonaws.com/trustrag:latest
```

---

### 步骤 6: 强制更新 ECS 服务

```powershell
# ECS 会自动检测新镜像，但我们可以强制更新
aws ecs update-service `
  --cluster trustrag-cluster `
  --service trustrag-service `
  --force-new-deployment `
  --region us-east-1
```

**预期输出**:
```json
{
    "service": {
        "serviceName": "trustrag-service",
        "status": "ACTIVE",
        "desiredCount": 1,
        ...
    }
}
```

---

### 步骤 7: 等待服务启动

```powershell
# 检查服务状态
aws ecs describe-services `
  --cluster trustrag-cluster `
  --services trustrag-service `
  --region us-east-1 `
  --query 'services[0].deployments[0].{Status:rolloutState,Running:runningCount,Desired:desiredCount}'
```

**等待直到看到**:
```json
{
    "Status": "COMPLETED",
    "Running": 1,
    "Desired": 1
}
```

这通常需要 2-3 分钟

---

### 步骤 8: 获取 ALB 端点

```powershell
# 获取负载均衡器 DNS
cd d:\trust_rag\terraform
$ALB_DNS = terraform output -raw alb_dns_name
echo "ALB Endpoint: http://$ALB_DNS"
```

**示例输出**:
```
ALB Endpoint: http://trustrag-alb-1234567890.us-east-1.elb.amazonaws.com
```

---

### 步骤 9: 验证部署

```powershell
# 运行验证脚本
cd d:\trust_rag
.\scripts\verify.ps1 -AlbDns $ALB_DNS
```

**预期输出**:

#### Test 1: Health Check ✅
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "loaded_facts": 2
}
```

#### Test 2: FastPath Query (Derivative) ✅
```json
{
  "verdict": "ALLOW",
  "answer": "The Revenue Growth (YoY) for Nvidia in FY2024 was 125.56%...",
  "confidence": 1.0,
  "trace_context": {
    "latency_ms": 12,
    "verification": {
      "derivative_path": true,
      "performance": {
        "total_tokens": 0,
        "llm_calls": 0
      }
    }
  }
}
```

**验证要点**:
- ✅ `derivative_path: true` - 使用了派生逻辑
- ✅ `total_tokens: 0` - 没有调用 LLM
- ✅ `latency_ms < 20` - 延迟低于 20ms

#### Test 3: Direct Fact Query ✅
```json
{
  "verdict": "ALLOW",
  "answer": "Determined via canonical fact store: The revenue for FY2024 (Nvidia) is 60.9 B USD.",
  "verification": {
    "fast_path": true
  }
}
```

#### Test 4: LLM Path Query ✅
```json
{
  "verdict": "ALLOW",
  "answer": "Based on verified data...",
  "trace_context": {
    "verification": {
      "performance": {
        "total_tokens": 150,
        "llm_calls": 1
      }
    }
  }
}
```

**验证要点**:
- ✅ `llm_calls: 1` - LLM 被调用
- ✅ `total_tokens > 0` - Token 使用被记录

---

### 步骤 10: 查看 CloudWatch 日志

```powershell
# 实时查看日志
aws logs tail /ecs/trustrag --follow --region us-east-1
```

**预期日志格式**:
```json
{
  "timestamp": "2024-12-21T00:00:00Z",
  "trace_id": "abc-123-def",
  "stage": "FAST_PATH",
  "level": "INFO",
  "message": "Fast-path hit",
  "data": {
    "latency": 2,
    "fact": {...}
  }
}
```

按 `Ctrl+C` 停止日志流

---

## 🎯 手动测试（可选）

### 使用 curl 测试

```powershell
# Test 1: 健康检查
curl http://$ALB_DNS/health

# Test 2: YoY 增长查询
$body = @{
    query = "Nvidia YoY revenue"
    risk_level = "medium"
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://$ALB_DNS/query" -Method Post -Body $body -ContentType "application/json" | ConvertTo-Json -Depth 10
```

---

## 📊 成本估算

| 资源 | 类型 | 月成本（美元） |
|------|------|---------------|
| ECS Fargate | 1 任务, 0.5 vCPU, 1GB | ~$15 |
| ALB | 标准 | ~$20 |
| ElastiCache | t3.micro | ~$12 |
| 数据传输 | 可变 | ~$5 |
| **总计** | | **~$52/月** |

*不包括 OpenAI API 调用费用*

---

## 🔧 故障排查

### 问题 1: Terraform apply 失败

**症状**: `Error: error creating ECS Cluster`

**解决方案**:
```powershell
# 检查 AWS 凭证
aws sts get-caller-identity

# 检查区域配置
echo $env:AWS_REGION

# 重试
terraform apply
```

### 问题 2: Docker push 失败

**症状**: `denied: Your authorization token has expired`

**解决方案**:
```powershell
# 重新登录 ECR
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin <ECR_URL>

# 重新推送
docker push <ECR_URL>:latest
```

### 问题 3: ECS 任务无法启动

**症状**: 服务一直显示 `RUNNING: 0`

**解决方案**:
```powershell
# 检查任务失败原因
aws ecs describe-tasks `
  --cluster trustrag-cluster `
  --tasks $(aws ecs list-tasks --cluster trustrag-cluster --service trustrag-service --query 'taskArns[0]' --output text) `
  --region us-east-1 `
  --query 'tasks[0].stoppedReason'
```

常见原因：
- OpenAI API Key 未正确设置
- 镜像拉取失败
- 内存不足

### 问题 4: ALB 健康检查失败

**症状**: Target Group 显示 `unhealthy`

**解决方案**:
```powershell
# 检查目标健康状态
aws elbv2 describe-target-health `
  --target-group-arn $(aws elbv2 describe-target-groups --names trustrag-tg --query 'TargetGroups[0].TargetGroupArn' --output text) `
  --region us-east-1
```

---

## 🧹 清理资源（如果需要）

```powershell
# 警告：这将删除所有资源！
cd d:\trust_rag\terraform
terraform destroy
```

输入 `yes` 确认

**删除时间**: 约 5-10 分钟

---

## ✅ 部署成功检查清单

- [ ] Terraform apply 成功完成
- [ ] Docker 镜像成功推送到 ECR
- [ ] ECS 服务显示 1 个运行中的任务
- [ ] ALB 健康检查通过
- [ ] `/health` 端点返回 200
- [ ] FastPath 查询返回正确结果（无 LLM）
- [ ] LLM 查询记录 token 使用
- [ ] CloudWatch 日志正常输出

---

## 📞 需要帮助？

如果遇到问题，请提供：
1. 错误信息的完整输出
2. `terraform plan` 的输出
3. CloudWatch 日志片段
4. ECS 任务状态

我会帮你诊断和解决！
