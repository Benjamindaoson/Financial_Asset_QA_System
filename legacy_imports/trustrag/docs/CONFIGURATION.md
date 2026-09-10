# TrustRAG Configuration Guide

## Environment Variables

Create a `.env` file in the project root with the following variables:

```bash
# LLM Provider (choose one: openai, dashscope, local)
TRUST_RAG_LLM_PROVIDER=openai

# API Keys (NEVER commit real keys to version control)
OPENAI_API_KEY=your_openai_api_key_here
DASHSCOPE_API_KEY=your_dashscope_api_key_here

# Feature Flags
DEV_ALLOW_UNVERIFIED=false
ENABLE_CACHE=true
ENABLE_FAST_PATH=true
TRUST_RAG_DEBUG=true

# Embedding Configuration
EMBEDDING_PROVIDER=sentence-transformers
EMBEDDING_MODEL=all-MiniLM-L6-v2

# Document Processing
OCR_LANGUAGES=eng+chi_sim
ASR_LANGUAGE=en-US
```

## Security Notes

- **NEVER** commit real API keys to version control
- Use environment variables for all sensitive configuration
- The `.env` file is automatically ignored by `.gitignore`
- For production deployment, use your platform's secret management (e.g., AWS Secrets Manager, Azure Key Vault)

## Embedding Providers

### Local (Recommended for Development)
```bash
EMBEDDING_PROVIDER=sentence-transformers
EMBEDDING_MODEL=all-MiniLM-L6-v2
```

### OpenAI
```bash
EMBEDDING_PROVIDER=openai
OPENAI_API_KEY=your_key_here
```

### DashScope (Qwen)
```bash
EMBEDDING_PROVIDER=dashscope
DASHSCOPE_API_KEY=your_key_here
```

