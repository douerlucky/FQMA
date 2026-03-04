@echo off
REM ========================================
REM 🚀 GeneTi-Maid Frontend 一键启动脚本
REM 支持: Windows CMD
REM ========================================

setlocal enabledelayedexpansion

REM 设置颜色
set "ESC=[27m"

echo.
echo ====================================
echo 🚀 GeneTi-Maid Frontend 一键启动
echo ====================================
echo.

REM 检查 Node.js
echo 检查 Node.js...
node -v >nul 2>&1
if errorlevel 1 (
    echo ❌ Node.js 未安装
    echo 请从 https://nodejs.org/ 下载安装
    pause
    exit /b 1
)

for /f "tokens=*" %%i in ('node -v') do set NODE_VERSION=%%i
echo ✅ Node.js 已安装: %NODE_VERSION%

npm -v >nul 2>&1
if errorlevel 1 (
    echo ❌ npm 未安装
    pause
    exit /b 1
)

for /f "tokens=*" %%i in ('npm -v') do set NPM_VERSION=%%i
echo ✅ npm 已安装: %NPM_VERSION%

echo.
echo 检查项目...

REM 检查 package.json
if not exist "package.json" (
    echo ❌ package.json 不存在！
    echo 请确保在项目根目录运行此脚本
    pause
    exit /b 1
)

for /f "delims=" %%i in ('findstr "name" package.json ^| findstr /v "displayName"') do (
    set "line=%%i"
    set "PROJECT_NAME=!line:*"name": "=!"
    set "PROJECT_NAME=!PROJECT_NAME:",*=!"
    goto :break
)
:break

echo ✅ 项目: %PROJECT_NAME%

echo.
echo 备份原文件...

if exist "src\App.vue" (
    if not exist "src\App.vue.backup" (
        copy "src\App.vue" "src\App.vue.backup" >nul
        echo ✅ 已备份 src\App.vue
    )
)

if exist "src\config.js" (
    if not exist "src\config.js.backup" (
        copy "src\config.js" "src\config.js.backup" >nul
        echo ✅ 已备份 src\config.js
    )
)

echo.
echo 检查更新文件...

if exist "App.vue" (
    copy /Y "App.vue" "src\App.vue" >nul
    echo ✅ 已复制 App.vue 到 src\
) else (
    echo ⚠️  App.vue 未找到（可选）
)

if exist "config.js" (
    copy /Y "config.js" "src\config.js" >nul
    echo ✅ 已复制 config.js 到 src\
) else (
    echo ⚠️  config.js 未找到（可选）
)

echo.
echo 检查依赖...

if not exist "node_modules" (
    echo.
    echo 正在下载依赖... (可能需要 2-5 分钟)
    echo.
    call npm install
    if errorlevel 1 (
        echo ❌ 依赖安装失败
        pause
        exit /b 1
    )
    echo ✅ 依赖安装完成
) else (
    echo ✅ node_modules 已存在，跳过安装
)

echo.
echo ==========================================
echo ✨ 服务器启动成功！
echo ==========================================
echo.
echo 📱 本地访问: http://localhost:5173/
echo.
echo 💡 提示：
echo   • 按 Ctrl+C 停止服务器
echo   • 修改代码后自动刷新（HMR）
echo.
echo 🔗 确保后端也在运行:
echo   python app.py (在另一个终端)
echo.
echo ==========================================
echo.

call npm run dev

pause
