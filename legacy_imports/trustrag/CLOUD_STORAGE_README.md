# 云存储链接上传与管理系统

## 📋 功能概述

GraphRAG 系统现在支持从各大云存储平台直接上传和处理文件，无需先下载到本地。支持 Google Drive、百度网盘、夸克网盘、OneDrive、Dropbox 等主流云存储平台。

## 🌟 主要特性

### 🔗 支持的云存储平台
- **Google Drive** - 完全支持，无需 API 密钥
- **百度网盘** - 支持公开分享链接
- **夸克网盘** - 支持公开分享链接
- **OneDrive** - 支持 Microsoft 账户分享链接
- **Dropbox** - 支持公开分享链接
- **Mega.nz** - 支持公开分享链接
- **Box** - 支持公开分享链接

### 📁 支持的文件格式
- **文档**: PDF, DOC, DOCX, TXT, HTML, HTM
- **数据表格**: CSV, XLSX, XLS
- **演示文稿**: PPT, PPTX
- **图像**: JPG, JPEG, PNG, GIF, BMP, TIFF
- **音频**: MP3, WAV, MP4, AVI, MOV, M4A

### ⚡ 核心功能
- **链接验证**: 实时验证分享链接的有效性和可访问性
- **批量上传**: 支持一次性处理多个云存储链接
- **进度跟踪**: 实时显示下载和处理进度
- **智能缓存**: 避免重复下载，提高效率
- **安全保护**: 加密传输和存储，确保数据安全

## 🚀 快速开始

### 1. 获取云存储分享链接

#### Google Drive
1. 右键文件 → "获取链接"
2. 设置权限为 "任何人有链接都可以查看"
3. 复制分享链接，例如：
   ```
   https://drive.google.com/file/d/1ABC123.../view?usp=sharing
   ```

#### 百度网盘
1. 右键文件 → "分享"
2. 创建分享链接，设置提取码
3. 复制分享链接，例如：
   ```
   https://pan.baidu.com/s/1ABC123...
   ```

#### 其他平台
类似操作获取公开分享链接。

### 2. 使用系统上传

#### 网页界面操作
1. 访问 GraphRAG 界面 (http://localhost:3000)
2. 点击 "☁️ Cloud Storage" 标签
3. 选择 "Single Upload" 或 "Batch Upload"
4. 粘贴云存储链接
5. 点击 "Validate" 检查链接有效性
6. 点击 "Download & Process" 开始处理

#### API 调用方式

```bash
# 验证单个链接
curl -X POST "http://localhost:8000/api/cloud/validate" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://drive.google.com/file/d/..."}'

# 下载并处理文件
curl -X POST "http://localhost:8000/api/cloud/download" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://drive.google.com/file/d/..."}'

# 批量验证
curl -X POST "http://localhost:8000/api/cloud/batch/validate" \
  -H "Content-Type: application/json" \
  -d '{"urls": ["url1", "url2", "url3"]}'

# 批量下载
curl -X POST "http://localhost:8000/api/cloud/batch/download" \
  -H "Content-Type: application/json" \
  -d '{"urls": ["url1", "url2", "url3"]}'
```

## 🔧 系统架构

### 存储设计
```
本地存储 (Metadata Only):
├── 用户信息
├── 文件元数据
├── 访问链接
└── 处理状态

云存储 (File Content):
├── Google Drive
├── 百度网盘
├── OneDrive
├── Dropbox
└── 其他平台
```

### 工作流程
```
用户提交链接 → 链接验证 → 文件下载 → 内容处理 → 知识图谱更新
     ↓              ↓          ↓          ↓              ↓
  实时反馈      权限检查   进度跟踪   文本提取     向量嵌入
```

## 🛠️ 技术实现

### 核心组件

#### 1. 链接验证器 (`validators.py`)
```python
class LinkValidator:
    - identify_provider(): 识别云存储平台
    - validate_cloud_link(): 验证链接有效性
    - batch_validate_links(): 批量验证
```

#### 2. 存储处理器 (`processors/`)
```python
class GoogleDriveProcessor:
    - validate_link(): 验证 Google Drive 链接
    - download_file(): 下载文件内容

class BaiduYunProcessor:
    - validate_link(): 验证百度网盘链接
    - download_file(): 下载文件内容
```

#### 3. 管理器 (`manager.py`)
```python
class CloudStorageManager:
    - validate_link(): 统一验证接口
    - download_file(): 统一下载接口
    - batch_download_files(): 批量处理
    - cleanup_cache(): 缓存清理
```

### API 端点

| 端点 | 方法 | 功能 |
|------|------|------|
| `/api/cloud/validate` | POST | 验证单个链接 |
| `/api/cloud/download` | POST | 下载并处理单个文件 |
| `/api/cloud/batch/validate` | POST | 批量验证链接 |
| `/api/cloud/batch/download` | POST | 批量下载文件 |
| `/api/cloud/providers` | GET | 获取支持的平台列表 |
| `/api/cloud/cache/stats` | GET | 获取缓存统计 |
| `/api/cloud/cache/cleanup` | POST | 清理缓存 |

## 🔐 安全与隐私

### 链接安全验证
- ✅ 检查链接有效性
- ✅ 验证公开访问权限
- ✅ 检测链接过期状态
- ✅ 防止恶意链接注入

### 数据传输保护
- 🔒 HTTPS 加密传输
- 🛡️ 文件内容加密存储
- 🚫 不保存用户认证信息
- ⚡ 临时文件自动清理

### 隐私保护措施
- 👤 不收集用户个人云存储信息
- 🔑 API 密钥可选配置
- 📊 最小权限访问原则
- 🗑️ 处理完成后自动清理缓存

## 📊 性能优化

### 缓存策略
- **验证缓存**: 24小时内避免重复验证
- **文件缓存**: 7天自动清理过期缓存
- **并发控制**: 最多3个同时下载任务

### 监控指标
- 下载速度统计
- 成功率跟踪
- 缓存命中率
- 错误率监控

## 🐛 故障排除

### 常见问题

#### 链接验证失败
**问题**: "Invalid cloud storage link"
**解决**:
- 检查链接是否正确复制
- 确认文件设置为公开分享
- 验证链接是否过期

#### 下载失败
**问题**: "Download failed"
**解决**:
- 检查网络连接
- 确认文件权限设置
- 查看文件大小是否超过限制 (50MB)

#### 批量处理问题
**问题**: "Some downloads failed"
**解决**:
- 检查失败的具体链接
- 分批次处理大量文件
- 查看系统资源使用情况

### 日志查看
```bash
# 查看应用日志
docker-compose logs api

# 查看缓存统计
curl http://localhost:8000/api/cloud/cache/stats
```

## 🔧 配置选项

### 环境变量
```bash
# 缓存配置
CLOUD_STORAGE_CACHE_DIR=/app/artifacts/cloud_cache
CLOUD_STORAGE_MAX_CACHE_AGE_DAYS=7
CLOUD_STORAGE_MAX_CONCURRENT_DOWNLOADS=3
CLOUD_STORAGE_TIMEOUT=30

# API 密钥 (可选，用于增强功能)
GOOGLE_DRIVE_API_KEY=your_key
BAIDU_APP_ID=your_app_id
BAIDU_API_KEY=your_api_key
BAIDU_SECRET_KEY=your_secret
```

### Docker 配置
```yaml
# 在 docker-compose.yml 中添加
environment:
  - CLOUD_STORAGE_CACHE_DIR=/app/artifacts/cloud_cache
  - CLOUD_STORAGE_MAX_CONCURRENT_DOWNLOADS=3
```

## 📈 扩展开发

### 添加新云存储平台
1. 在 `processors/` 中创建新处理器类
2. 继承 `CloudStorageProvider` 基类
3. 实现 `validate_link()` 和 `download_file()` 方法
4. 在 `validators.py` 中添加 URL 模式
5. 更新 `manager.py` 中的提供商列表

### 自定义验证逻辑
```python
class CustomProcessor(CloudStorageProvider):
    def validate_link(self, url: str) -> ValidationResult:
        # 自定义验证逻辑
        pass

    def download_file(self, url: str, local_path: str) -> DownloadResult:
        # 自定义下载逻辑
        pass
```

## 📞 支持与反馈

如果您在使用过程中遇到问题或有功能建议，请：

1. 查看本文档的故障排除部分
2. 检查系统日志获取详细错误信息
3. 在 GitHub Issues 中提交问题报告

## 🎯 使用建议

### 最佳实践
- **批量上传**: 对于多个文件，建议使用批量上传功能
- **链接验证**: 上传前先验证链接有效性
- **文件大小**: 注意单个文件大小限制 (50MB)
- **网络稳定**: 确保网络连接稳定，避免大文件传输中断

### 性能优化
- **并发控制**: 避免同时上传过多文件
- **缓存利用**: 系统会自动缓存已验证的链接
- **定期清理**: 定期清理缓存释放存储空间

---

*最后更新: 2025-01-07 | GraphRAG v2.0*







