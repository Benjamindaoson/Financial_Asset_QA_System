@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ========================================
echo   FinSight 金融 QA 系统 - 启动前后端
echo ========================================
echo.

:: 后端 (port 8001)
echo [1] 启动后端...
start "FinSight-后端" cmd /k "cd /d "%~dp0backend" && (if exist venv\Scripts\activate.bat call venv\Scripts\activate.bat) && set HTTP_PROXY= && set HTTPS_PROXY= && set ALL_PROXY= && python -m uvicorn app.main:app --host 127.0.0.1 --port 8001"
timeout /t 3 /nobreak >nul

:: 前端 (port 5173)
echo [2] 启动前端...
start "FinSight-前端" cmd /k "cd /d "%~dp0frontend" && npm run dev"

echo.
echo ========================================
echo   后端: http://127.0.0.1:8001
echo   前端: http://127.0.0.1:5173
echo   健康检查: http://127.0.0.1:8001/api/health
echo ========================================
pause
