@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

REM ========================================
REM  FQMA 一键启动脚本 (Windows)
REM  放在 FQMA\ 目录下（与 app.py 同级）运行
REM ========================================

echo.
echo ════════════════════════════════════════
echo           🧬 FQMA 一键启动
echo ════════════════════════════════════════
echo.
echo  请选择启动模式:
echo    [1] 启动 Web 应用（前端 + 后端）
echo    [2] 交互式命令行查询（直接运行 main.py）
echo.
set /p MODE_CHOICE="请输入选项 (1/2，默认 1): "
if "!MODE_CHOICE!"=="" set "MODE_CHOICE=1"
if "!MODE_CHOICE!" NEQ "1" if "!MODE_CHOICE!" NEQ "2" (
    echo  X 无效选项，请输入 1 或 2
    pause
    exit /b 1
)

REM 获取脚本所在目录
set "SCRIPT_DIR=%~dp0"
set "FRONTEND_DIR=%SCRIPT_DIR%frontend"
set "BACKEND_LOG=%SCRIPT_DIR%backend.log"
set "VENV_DIR=%SCRIPT_DIR%.venv"
set "REQUIREMENTS=%SCRIPT_DIR%requirements.txt"

REM ── 检查 Python 3.12 ─────────────────────
echo.
echo [1/5] 检查 Python...

set "PYTHON_CMD="

REM 优先尝试 py -3.12 (Python Launcher)
py -3.12 --version >nul 2>&1
if not errorlevel 1 (
    for /f "tokens=2" %%v in ('py -3.12 --version 2^>^&1') do (
        echo %%v | findstr /b "3.12" >nul 2>&1
        if not errorlevel 1 (
            set "PYTHON_CMD=py -3.12"
        )
    )
)

REM 如果 py -3.12 不可用，尝试 python3.12
if "!PYTHON_CMD!"=="" (
    python3.12 --version >nul 2>&1
    if not errorlevel 1 (
        set "PYTHON_CMD=python3.12"
    )
)

REM 最后尝试 python / python3，但验证版本必须是 3.12
if "!PYTHON_CMD!"=="" (
    for %%c in (python python3) do (
        if "!PYTHON_CMD!"=="" (
            %%c --version >nul 2>&1
            if not errorlevel 1 (
                for /f "tokens=2" %%v in ('%%c --version 2^>^&1') do (
                    echo %%v | findstr /b "3.12" >nul 2>&1
                    if not errorlevel 1 (
                        set "PYTHON_CMD=%%c"
                    )
                )
            )
        )
    )
)

if "!PYTHON_CMD!"=="" (
    echo  X 未找到 Python 3.12，当前系统检测到的版本:
    for %%c in (python python3 python3.11 python3.10) do (
        %%c --version >nul 2>&1
        if not errorlevel 1 (
            for /f "tokens=*" %%v in ('%%c --version 2^>^&1') do echo    %%c -^> %%v
        )
    )
    echo.
    echo  提示: 请从 https://www.python.org/downloads/ 安装 Python 3.12
    echo        或使用 py -3.12 确认 Python Launcher 已安装 3.12
    pause
    exit /b 1
)

for /f "tokens=*" %%v in ('!PYTHON_CMD! --version 2^>^&1') do echo  OK %%v  (!PYTHON_CMD!)

REM ── 创建/检查虚拟环境 ────────────────────
echo [2/5] 检查 Python 虚拟环境与依赖...

if not exist "%VENV_DIR%" (
    echo   正在创建虚拟环境 .venv ...
    !PYTHON_CMD! -m venv "%VENV_DIR%"
    if errorlevel 1 (
        echo  X 虚拟环境创建失败
        pause
        exit /b 1
    )
    echo  OK 虚拟环境创建完成
) else (
    REM 检查已有虚拟环境的 Python 版本
    for /f "tokens=2" %%v in ('"%VENV_DIR%\Scripts\python.exe" --version 2^>^&1') do (
        echo %%v | findstr /b "3.12" >nul 2>&1
        if errorlevel 1 (
            echo  ! 已有虚拟环境使用的不是 Python 3.12，正在重新创建...
            rmdir /s /q "%VENV_DIR%"
            !PYTHON_CMD! -m venv "%VENV_DIR%"
            if errorlevel 1 (
                echo  X 虚拟环境重建失败
                pause
                exit /b 1
            )
            echo  OK 虚拟环境重建完成 (Python 3.12^)
        ) else (
            echo  OK 虚拟环境已存在 (Python %%v^)
        )
    )
)

REM 激活虚拟环境
call "%VENV_DIR%\Scripts\activate.bat"

REM 安装/补全依赖
if exist "%REQUIREMENTS%" (
    echo   正在检查并安装 requirements.txt 中的依赖...
    pip install -r "%REQUIREMENTS%" --disable-pip-version-check ^
        --trusted-host pypi.org ^
        --trusted-host pypi.python.org ^
        --trusted-host files.pythonhosted.org ^
        --resume-retries 5
    if errorlevel 1 (
        echo  X 依赖安装失败，请检查 requirements.txt
        pause
        exit /b 1
    )
    echo  OK Python 依赖已就绪
) else (
    echo   未找到 requirements.txt，跳过
)

REM ══════════════════════════════════════════
REM  模式 2: 交互式命令行查询
REM ══════════════════════════════════════════
if "!MODE_CHOICE!"=="2" (
    echo.
    echo ════════════════════════════════════════
    echo   🔬 交互式查询模式
    echo ════════════════════════════════════════
    echo.
    echo  直接运行 main.py，可手动输入自然语言问题进行查询。
    echo  输入 exit 或直接回车退出。
    echo.
    cd /d "%SCRIPT_DIR%"
    python main.py --interactive
    echo.
    echo  查询会话已结束。
    pause
    exit /b 0
)

REM ══════════════════════════════════════════
REM  模式 1: 启动 Web 应用
REM ══════════════════════════════════════════

REM ── 检查 Node.js ─────────────────────────
echo [3/5] 检查 Node.js...

node -v >nul 2>&1
if errorlevel 1 (
    echo  X 未找到 Node.js，请从 https://nodejs.org 安装
    pause
    exit /b 1
)
for /f "tokens=*" %%i in ('node -v') do echo  OK Node.js %%i

REM ── 安装前端依赖（仅首次）────────────────
echo [4/5] 检查前端依赖...

if not exist "%FRONTEND_DIR%" (
    echo  X 未找到 frontend 目录
    pause
    exit /b 1
)

if not exist "%FRONTEND_DIR%\node_modules" (
    echo   首次运行，正在安装前端依赖（约 2-5 分钟）...
    cd /d "%FRONTEND_DIR%"
    call npm install
    if errorlevel 1 (
        echo  X 前端依赖安装失败
        pause
        exit /b 1
    )
    echo  OK 前端依赖安装完成
) else (
    echo  OK 前端依赖已就绪
)

REM ── 启动服务 ─────────────────────────────
echo [5/5] 启动服务...

REM 清理占用端口的旧进程
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":5000 " 2^>nul') do (
    taskkill /F /PID %%a >nul 2>&1
)
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":5173 " 2^>nul') do (
    taskkill /F /PID %%a >nul 2>&1
)
timeout /t 1 /nobreak >nul

REM 启动后端（新窗口）
echo   启动后端 (端口 5000)...
cd /d "%SCRIPT_DIR%"
start "FQMA-Backend" cmd /k "chcp 65001 >nul && call %VENV_DIR%\Scripts\activate.bat && echo [后端] 正在启动... && python app.py"

REM 等待后端就绪
echo   等待后端启动...
set /a count=0
:wait_backend
timeout /t 2 /nobreak >nul
set /a count+=1
curl -s http://localhost:5000/api/health >nul 2>&1
if not errorlevel 1 (
    echo  OK 后端已就绪
    goto backend_ready
)
if !count! lss 10 goto wait_backend
echo   警告：后端启动超时，请检查 FQMA-Backend 窗口

:backend_ready

REM 启动前端（新窗口）
echo   启动前端 (端口 5173)...
cd /d "%FRONTEND_DIR%"
start "FQMA-Frontend" cmd /k "chcp 65001 >nul && echo [前端] 正在启动... && npm run dev"

REM 等待前端启动后打开浏览器
timeout /t 5 /nobreak >nul
echo   自动打开浏览器...
start http://localhost:5173

echo.
echo ════════════════════════════════════════
echo   ✨ 启动完成！
echo ════════════════════════════════════════
echo.
echo   前端地址: http://localhost:5173
echo   后端地址: http://localhost:5000
echo.
echo   关闭说明:
echo     - 关闭 FQMA-Backend  窗口停止后端
echo     - 关闭 FQMA-Frontend 窗口停止前端
echo.
echo ════════════════════════════════════════
echo.
pause