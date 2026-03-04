#!/bin/bash

# ========================================
# 🚀 FQMA 一键启动脚本 (macOS / Linux)
# 放在 FQMA/ 目录下（与 app.py 同级）运行
# ========================================

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FRONTEND_DIR="$SCRIPT_DIR/frontend"
BACKEND_LOG="$SCRIPT_DIR/backend.log"
VENV_DIR="$SCRIPT_DIR/.venv"
REQUIREMENTS="$SCRIPT_DIR/requirements.txt"

echo ""
echo -e "${BLUE}════════════════════════════════════════${NC}"
echo -e "${BLUE}         🧬 FQMA 一键启动               ${NC}"
echo -e "${BLUE}════════════════════════════════════════${NC}"
echo ""
echo -e "  请选择启动模式:"
echo -e "    ${GREEN}[1]${NC} 启动 Web 应用（前端 + 后端）"
echo -e "    ${GREEN}[2]${NC} 交互式命令行查询（直接运行 main.py）"
echo ""
read -rp "  请输入选项 (1/2，默认 1): " MODE_CHOICE
MODE_CHOICE="${MODE_CHOICE:-1}"

if [[ "$MODE_CHOICE" != "1" && "$MODE_CHOICE" != "2" ]]; then
    echo -e "${RED}❌ 无效选项，请输入 1 或 2${NC}"
    exit 1
fi

# ── 检查 Python ──────────────────────────
echo ""
echo -e "${YELLOW}[1/5] 检查 Python...${NC}"

PYTHON_CMD=""
for cmd in python3.12 python3 python; do
    if command -v "$cmd" &>/dev/null; then
        VERSION=$("$cmd" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null)
        if [ "$VERSION" = "3.12" ]; then
            PYTHON_CMD="$cmd"
            break
        fi
    fi
done

if [ -z "$PYTHON_CMD" ]; then
    echo -e "${RED}❌ 未找到 Python 3.12，当前系统中检测到：${NC}"
    for cmd in python3.12 python3.11 python3.10 python3 python; do
        if command -v "$cmd" &>/dev/null; then
            echo "   $cmd -> $($cmd --version 2>&1)"
        fi
    done
    echo ""
    echo -e "${YELLOW}💡 请确认 Python 3.12 已安装，或修改此脚本第一行的版本要求${NC}"
    echo -e "${YELLOW}   macOS 用户可尝试: brew install python@3.12${NC}"
    exit 1
fi
echo -e "${GREEN}✅ Python: $($PYTHON_CMD --version) ($PYTHON_CMD)${NC}"

# ── 创建虚拟环境 + 安装依赖 ──────────────
echo -e "${YELLOW}[2/5] 检查 Python 虚拟环境与依赖...${NC}"

if [ ! -d "$VENV_DIR" ]; then
    echo "  正在创建虚拟环境 .venv ..."
    $PYTHON_CMD -m venv "$VENV_DIR"
    if [ $? -ne 0 ]; then
        echo -e "${RED}❌ 虚拟环境创建失败${NC}"
        exit 1
    fi
    echo -e "${GREEN}✅ 虚拟环境创建完成${NC}"
else
    VENV_VERSION=$("$VENV_DIR/bin/python" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null)
    if [ "$VENV_VERSION" != "3.12" ]; then
        echo -e "${YELLOW}⚠️  已有虚拟环境使用的是 Python $VENV_VERSION，正在重新创建...${NC}"
        rm -rf "$VENV_DIR"
        $PYTHON_CMD -m venv "$VENV_DIR"
        if [ $? -ne 0 ]; then
            echo -e "${RED}❌ 虚拟环境创建失败${NC}"
            exit 1
        fi
        echo -e "${GREEN}✅ 虚拟环境重建完成（Python 3.12）${NC}"
    else
        echo -e "${GREEN}✅ 虚拟环境已存在 (Python $VENV_VERSION)${NC}"
    fi
fi

source "$VENV_DIR/bin/activate"

# ── 修复 macOS Python SSL 证书问题 ──────
CERT_CMD="/Applications/Python 3.12/Install Certificates.command"
if [ -f "$CERT_CMD" ] && ! python3.12 -c "import ssl; ssl.create_default_context()" &>/dev/null 2>&1; then
    echo "  🔐 修复 macOS Python SSL 证书..."
    bash "$CERT_CMD" > /dev/null 2>&1
fi

if [ -f "$REQUIREMENTS" ]; then
    echo "  正在检查并安装 requirements.txt 中的依赖..."
    pip install -r "$REQUIREMENTS" --disable-pip-version-check \
        --trusted-host pypi.org \
        --trusted-host pypi.python.org \
        --trusted-host files.pythonhosted.org \
        --resume-retries 5
    if [ $? -ne 0 ]; then
        echo -e "${RED}❌ 依赖安装失败，请检查 requirements.txt${NC}"
        exit 1
    fi
    echo -e "${GREEN}✅ Python 依赖已就绪${NC}"
else
    echo -e "${YELLOW}⚠️  未找到 requirements.txt，跳过${NC}"
fi

# ══════════════════════════════════════════
#  模式 2: 交互式命令行查询
# ══════════════════════════════════════════
if [ "$MODE_CHOICE" = "2" ]; then
    echo ""
    echo -e "${BLUE}════════════════════════════════════════${NC}"
    echo -e "${BLUE}   🔬 交互式查询模式                    ${NC}"
    echo -e "${BLUE}════════════════════════════════════════${NC}"
    echo ""
    echo -e "  直接运行 main.py，可手动输入自然语言问题进行查询。"
    echo -e "  输入 ${YELLOW}exit${NC} 或直接回车退出。"
    echo ""
    cd "$SCRIPT_DIR"
    "$VENV_DIR/bin/python" main.py --interactive
    echo ""
    echo -e "${GREEN}✅ 查询会话已结束。${NC}"
    exit 0
fi

# ══════════════════════════════════════════
#  模式 1: 启动 Web 应用
# ══════════════════════════════════════════
echo -e "${YELLOW}[3/5] 检查 Node.js...${NC}"

if ! command -v node &>/dev/null; then
    echo -e "${RED}❌ 未找到 Node.js，请从 https://nodejs.org 安装${NC}"
    exit 1
fi
echo -e "${GREEN}✅ Node.js: $(node -v)${NC}"

echo -e "${YELLOW}[4/5] 检查前端依赖...${NC}"

if [ ! -d "$FRONTEND_DIR" ]; then
    echo -e "${RED}❌ 未找到 frontend 目录: $FRONTEND_DIR${NC}"
    exit 1
fi

if [ ! -d "$FRONTEND_DIR/node_modules" ]; then
    echo "  首次运行，正在安装前端依赖（约 2-5 分钟）..."
    cd "$FRONTEND_DIR" && npm install
    if [ $? -ne 0 ]; then
        echo -e "${RED}❌ 前端依赖安装失败${NC}"
        exit 1
    fi
    echo -e "${GREEN}✅ 前端依赖安装完成${NC}"
else
    echo -e "${GREEN}✅ 前端依赖已就绪${NC}"
fi

echo -e "${YELLOW}[5/5] 启动服务...${NC}"

lsof -ti:5000 | xargs kill -9 2>/dev/null
lsof -ti:5173 | xargs kill -9 2>/dev/null
sleep 1

echo "  🔧 启动后端 (端口 5000)..."
cd "$SCRIPT_DIR"
"$VENV_DIR/bin/python" app.py > "$BACKEND_LOG" 2>&1 &
BACKEND_PID=$!

echo -n "  等待后端启动"
for i in $(seq 1 20); do
    sleep 1
    echo -n "."
    if curl -s http://localhost:5000/api/health > /dev/null 2>&1; then
        echo ""
        echo -e "  ${GREEN}✅ 后端已就绪${NC}"
        break
    fi
    if [ $i -eq 20 ]; then
        echo ""
        echo -e "  ${RED}❌ 后端启动失败，最近错误：${NC}"
        echo "  ─────────────────────────────"
        tail -20 "$BACKEND_LOG"
        echo "  ─────────────────────────────"
        echo -e "  完整日志: ${BACKEND_LOG}"
    fi
done

echo "  🎨 启动前端 (端口 5173)..."
cd "$FRONTEND_DIR"
npm run dev &
FRONTEND_PID=$!

sleep 4
open "http://localhost:5173" 2>/dev/null || xdg-open "http://localhost:5173" 2>/dev/null

echo ""
echo -e "${BLUE}════════════════════════════════════════${NC}"
echo -e "${GREEN}  ✨ 启动完成！                         ${NC}"
echo -e "${BLUE}════════════════════════════════════════${NC}"
echo ""
echo -e "  🌐 前端地址: ${GREEN}http://localhost:5173${NC}"
echo -e "  🔧 后端地址: ${GREEN}http://localhost:5000${NC}"
echo -e "  📄 后端日志: ${BACKEND_LOG}"
echo ""
echo -e "${YELLOW}  按 Ctrl+C 停止所有服务${NC}"
echo ""

cleanup() {
    echo ""
    echo -e "${YELLOW}正在停止所有服务...${NC}"
    kill $BACKEND_PID 2>/dev/null
    kill $FRONTEND_PID 2>/dev/null
    lsof -ti:5000 | xargs kill -9 2>/dev/null
    lsof -ti:5173 | xargs kill -9 2>/dev/null
    echo -e "${GREEN}✅ 已停止${NC}"
    exit 0
}
trap cleanup SIGINT SIGTERM

wait