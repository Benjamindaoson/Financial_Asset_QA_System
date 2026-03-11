@echo off
chcp 65001 >nul
echo ========================================
echo   金融资产问答系统 - 一键搭建环境
echo ========================================
echo.

cd /d "%~dp0"

:: ================================
:: 1. 检测 conda
:: ================================
echo [1/5] 检测 conda...
call conda --version >nul 2>&1
if %errorlevel% neq 0 goto :no_conda
for /f "tokens=1,2" %%a in ('conda --version 2^>^&1') do echo √ %%a %%b
echo.
goto :step2

:no_conda
echo X 未检测到 conda
echo   请安装 Anaconda: https://www.anaconda.com/download
echo   或 Miniconda:    https://docs.conda.io/en/latest/miniconda.html
pause
exit /b 1

:: ================================
:: 2. 创建 conda 环境
:: ================================
:step2
echo [2/5] 检查 conda 环境 financial_qa...
if exist "%USERPROFILE%\.conda\envs\financial_qa" goto :env_exists

echo   正在创建 conda 环境 financial_qa...
echo   包含 python=3.11 + nodejs, 请耐心等待...
call conda create -n financial_qa python=3.11 nodejs -y
if %errorlevel% neq 0 goto :env_create_failed
echo √ conda 环境创建完成
echo.
goto :step3

:env_exists
echo √ conda 环境 financial_qa 已存在
echo.
goto :step3

:env_create_failed
echo X conda 环境创建失败, 请检查网络后重试
echo   手动重试: conda create -n financial_qa python=3.11 nodejs -y
pause
exit /b 1

:: ================================
:: 3. 激活环境并安装后端依赖
:: ================================
:step3
echo [3/5] 安装后端 Python 依赖...
call conda activate financial_qa
if %errorlevel% neq 0 goto :activate_failed

cd backend
echo   正在安装依赖...
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple --trusted-host pypi.tuna.tsinghua.edu.cn
if %errorlevel% equ 0 (
    echo √ 后端依赖安装完成
) else (
    echo ! 部分依赖安装失败, 请检查网络后重试
    echo   手动重试: conda activate financial_qa
    echo   pip install -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple
)
cd ..
echo.
goto :step4

:activate_failed
echo X conda activate 失败
pause
exit /b 1

:: ================================
:: 4. 安装前端依赖
:: ================================
:step4
echo [4/5] 安装前端 Node.js 依赖...
cd frontend
call npm install
if %errorlevel% equ 0 (
    echo √ 前端依赖安装完成
) else (
    echo ! 前端依赖安装失败, 请检查网络后重试
)
cd ..
echo.

:: ================================
:: 5. 配置 .env 文件
:: ================================
echo [5/5] 检查环境变量配置...
if exist "backend\.env" goto :env_exists_file

copy "backend\.env.example" "backend\.env" >nul
echo √ 已创建 backend\.env
echo.
echo ========================================
echo   !!! 请编辑 backend\.env 填入密钥 !!!
echo ========================================
echo   必须配置:
echo     DEEPSEEK_API_KEY=你的密钥
echo   国内用户还需:
echo     FINNHUB_API_KEY=你的密钥
echo     DISABLE_YFINANCE=true
echo.
echo   获取密钥:
echo     DeepSeek: https://platform.deepseek.com/
echo     Finnhub:  https://finnhub.io/
echo ========================================
goto :done

:env_exists_file
echo √ backend\.env 已存在

:done
echo.
echo ========================================
echo   √ 环境搭建完成
echo ========================================
echo.
echo   下一步:
echo     1. 编辑 backend\.env 填入 API 密钥
echo     2. 双击 一键启动.bat 启动系统
echo.
pause
