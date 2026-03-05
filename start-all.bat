@echo off
chcp 65001 > nul
echo ============================================================
echo Financial Asset QA System - 一键启动
echo ============================================================
echo.

REM 检查配置文件
if not exist "backend\.env" (
    echo [提示] 未检测到配置文件，启动配置向导...
    echo.
    python scripts\setup.py
    if errorlevel 1 (
        echo.
        echo [错误] 配置失败，请重试
        pause
        exit /b 1
    )
    echo.
)

REM 设置环境变量
set HF_HOME=D:\Financial_Asset_QA_System\models\huggingface
set TRANSFORMERS_CACHE=D:\Financial_Asset_QA_System\models\transformers
set HF_HUB_CACHE=D:\Financial_Asset_QA_System\models\huggingface\hub

echo [1/3] 启动后端服务...
cd backend
start "Financial QA Backend" cmd /c "call venv\Scripts\activate && uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"
cd ..
echo [成功] 后端服务已启动 (http://localhost:8000)
echo.

timeout /t 3 /nobreak > nul

echo [2/3] 启动前端服务...
cd frontend
start "Financial QA Frontend" cmd /c "npm run dev"
cd ..
echo [成功] 前端服务已启动
echo.

timeout /t 3 /nobreak > nul

echo [3/3] 检查服务状态...
timeout /t 2 /nobreak > nul

echo.
echo ============================================================
echo [完成] 所有服务已启动！
echo ============================================================
echo.
echo 访问地址:
echo   前端: http://localhost:3001
echo   后端: http://localhost:8000
echo   API文档: http://localhost:8000/docs
echo.
echo 提示:
echo   - 前端可能在 3000 或 3001 端口（自动选择）
echo   - 按 Ctrl+C 可停止服务
echo   - 查看日志: logs\backend.log 和 logs\frontend.log
echo.
pause
