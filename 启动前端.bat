@echo off
chcp 65001 >nul
echo ========================================
echo   金融资产问答系统 - 前端启动脚本
echo ========================================
echo.

cd /d "%~dp0frontend"

echo [1/2] 检查依赖...
if not exist "node_modules" (
    echo ⚠ 依赖未安装，正在安装...
    call npm install
    echo ✓ 依赖安装完成
) else (
    echo ✓ 依赖已安装
)
echo.

echo [2/2] 启动前端服务...
echo.
echo ========================================
echo   前端正在启动...
echo   启动后会自动打开浏览器
echo   访问地址: http://127.0.0.1:5173
echo ========================================
echo.

npm run dev

pause
