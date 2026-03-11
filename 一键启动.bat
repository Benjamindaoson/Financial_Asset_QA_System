@echo off
chcp 65001 >nul
echo ========================================
echo   金融资产问答系统 - 一键启动
echo ========================================
echo.

cd /d "%~dp0"

:: ================================
:: 0. 清理代理环境变量
:: ================================
set HTTP_PROXY=
set HTTPS_PROXY=
set ALL_PROXY=
set http_proxy=
set https_proxy=
set all_proxy=

:: ================================
:: 1. 检查环境是否已搭建
:: ================================
if not exist "backend\venv\Scripts\activate.bat" (
    echo ✗ 后端环境未搭建，请先运行「搭建环境.bat」
    pause
    exit /b 1
)
if not exist "frontend\node_modules" (
    echo ✗ 前端依赖未安装，请先运行「搭建环境.bat」
    pause
    exit /b 1
)
if not exist "backend\.env" (
    echo ✗ 未找到 backend\.env 配置文件，请先运行「搭建环境.bat」
    pause
    exit /b 1
)

:: ================================
:: 2. 关闭已有进程（占用端口 8001 和 5173）
:: ================================
echo [1/3] 清理旧进程...
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":8001 " ^| findstr "LISTENING"') do (
    taskkill /F /PID %%p >nul 2>&1
)
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":5173 " ^| findstr "LISTENING"') do (
    taskkill /F /PID %%p >nul 2>&1
)
echo ✓ 旧进程已清理
echo.

:: ================================
:: 3. 启动后端（新窗口）
:: ================================
echo [2/3] 启动后端服务...
start "金融QA-后端" cmd /k "chcp 65001 >nul && cd /d "%~dp0backend" && call venv\Scripts\activate.bat && set HTTP_PROXY= && set HTTPS_PROXY= && set ALL_PROXY= && echo ======================================== && echo   后端正在启动... && echo   看到 Application startup complete 表示成功 && echo ======================================== && echo. && python -m uvicorn app.main:app --host 127.0.0.1 --port 8001"
echo ✓ 后端已在新窗口启动
echo.

:: ================================
:: 4. 等待后端就绪后启动前端
:: ================================
echo [3/3] 等待后端就绪后启动前端...
set /a retry=0
:wait_backend
set /a retry+=1
if %retry% gtr 60 (
    echo ⚠ 后端启动超时（60秒），仍将启动前端
    goto start_frontend
)
timeout /t 1 /nobreak >nul
curl -s http://127.0.0.1:8001/api/health >nul 2>&1
if %errorlevel% neq 0 (
    goto wait_backend
)
echo ✓ 后端已就绪

:start_frontend
start "金融QA-前端" cmd /k "chcp 65001 >nul && cd /d "%~dp0frontend" && echo ======================================== && echo   前端正在启动... && echo   访问地址: http://127.0.0.1:5173 && echo ======================================== && echo. && npm run dev"
echo ✓ 前端已在新窗口启动
echo.

:: ================================
:: 完成
:: ================================
echo ========================================
echo   ✓ 系统启动完成！
echo ========================================
echo.
echo   后端: http://127.0.0.1:8001
echo   前端: http://127.0.0.1:5173
echo.
echo   关闭方法：关闭后端和前端的命令行窗口
echo.
pause
