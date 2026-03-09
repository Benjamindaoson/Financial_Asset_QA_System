@echo off
chcp 65001 >nul
echo ========================================
echo   金融资产问答系统 - 后端启动脚本
echo ========================================
echo.

echo [1/6] 关闭所有Python进程...
taskkill /F /IM python.exe /T >nul 2>&1
if %errorlevel% equ 0 (
    echo ✓ Python进程已关闭
) else (
    echo ✓ 没有运行中的Python进程
)
echo.

echo [2/6] 等待2秒...
timeout /t 2 /nobreak >nul
echo ✓ 等待完成
echo.

echo [3/6] 检查虚拟环境...
cd /d "%~dp0"
if not exist "backend\venv" (
    echo ⚠ 虚拟环境不存在，正在创建...
    cd backend
    python -m venv venv
    if %errorlevel% equ 0 (
        echo ✓ 虚拟环境创建完成
    ) else (
        echo ✗ 虚拟环境创建失败，请检查Python安装
        pause
        exit /b 1
    )
    cd ..
) else (
    echo ✓ 虚拟环境已存在
)
echo.

echo [4/6] 激活虚拟环境并安装依赖...
cd backend
call venv\Scripts\activate.bat
if %errorlevel% neq 0 (
    echo ✗ 虚拟环境激活失败
    cd ..
    pause
    exit /b 1
)
echo 正在安装依赖包，请稍候...
pip install -r requirements.txt --quiet
if %errorlevel% equ 0 (
    echo ✓ 依赖安装完成
) else (
    echo ⚠ 部分依赖安装失败，但将尝试继续启动
)
cd ..
echo.

echo [5/6] 清理旧的ChromaDB数据库...
if exist "vectorstore\chroma\chroma.sqlite3" (
    del /F /Q "vectorstore\chroma\chroma.sqlite3" >nul 2>&1
    if %errorlevel% equ 0 (
        echo ✓ 数据库文件已删除
    ) else (
        echo ⚠ 无法删除数据库文件，尝试重命名目录...
        ren "vectorstore\chroma" "chroma_backup_%date:~0,4%%date:~5,2%%date:~8,2%_%time:~0,2%%time:~3,2%%time:~6,2%" >nul 2>&1
        mkdir "vectorstore\chroma" >nul 2>&1
        echo ✓ 已重命名旧目录并创建新目录
    )
) else (
    echo ✓ 数据库文件不存在或已删除
)
echo.

echo [6/6] 启动后端服务...
echo.
echo ========================================
echo   后端正在启动，请等待...
echo   首次启动会下载约1.5GB的模型文件
echo   看到 "Application startup complete" 表示成功
echo ========================================
echo.

cd backend
call venv\Scripts\activate.bat
python -m uvicorn app.main:app --host 127.0.0.1 --port 8001

pause
