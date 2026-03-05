@echo off
cd /d D:\Financial_Asset_QA_System\backend
set PYTHONPATH=.
set HF_HOME=D:\Financial_Asset_QA_System\models\huggingface
set TRANSFORMERS_CACHE=D:\Financial_Asset_QA_System\models\transformers
set HF_HUB_CACHE=D:\Financial_Asset_QA_System\models\huggingface\hub
venv\Scripts\python -m app.main
