#!/bin/bash

# ========================================
# 🚀 GeneTi-Maid Frontend 一键启动脚本
# 支持: macOS, Linux, Windows (Git Bash)
# ========================================

set -e  # 任何命令失败时退出

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 输出函数
print_header() {
    echo -e "${BLUE}═══════════════════════════════════════${NC}"
    echo -e "${BLUE}🚀 $1${NC}"
    echo -e "${BLUE}═══════════════════════════════════════${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

# 检查系统
detect_system() {
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        OS="linux"
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        OS="macos"
    elif [[ "$OSTYPE" == "msys" ]] || [[ "$OSTYPE" == "win32" ]]; then
        OS="windows"
    else
        OS="unknown"
    fi
}

# 检查 Node.js
check_nodejs() {
    print_header "检查 Node.js"
    
    if ! command -v node &> /dev/null; then
        print_error "Node.js 未安装"
        echo "请从 https://nodejs.org/ 下载安装"
        exit 1
    fi
    
    NODE_VERSION=$(node -v)
    print_success "Node.js 已安装: $NODE_VERSION"
    
    if ! command -v npm &> /dev/null; then
        print_error "npm 未安装"
        exit 1
    fi
    
    NPM_VERSION=$(npm -v)
    print_success "npm 已安装: $NPM_VERSION"
}

# 进入项目目录
enter_project() {
    print_header "进入项目目录"
    
    if [ ! -f "package.json" ]; then
        print_error "package.json 不存在！"
        echo "请确保在项目根目录运行此脚本"
        exit 1
    fi
    
    PROJECT_NAME=$(grep '"name"' package.json | head -1 | cut -d'"' -f4)
    print_success "项目: $PROJECT_NAME"
}

# 安装依赖
install_dependencies() {
    print_header "安装依赖"
    
    if [ -d "node_modules" ]; then
        print_warning "node_modules 已存在，跳过安装"
        return
    fi
    
    echo "正在下载依赖... (可能需要 2-5 分钟)"
    npm install
    
    if [ $? -eq 0 ]; then
        print_success "依赖安装完成"
    else
        print_error "依赖安装失败"
        exit 1
    fi
}

# 备份原文件
backup_files() {
    print_header "备份原文件"
    
    if [ -f "src/App.vue" ] && [ ! -f "src/App.vue.backup" ]; then
        cp src/App.vue src/App.vue.backup
        print_success "备份 src/App.vue"
    fi
    
    if [ -f "src/config.js" ] && [ ! -f "src/config.js.backup" ]; then
        cp src/config.js src/config.js.backup
        print_success "备份 src/config.js"
    fi
}

# 检查新文件
check_new_files() {
    print_header "检查更新文件"
    
    if [ -f "App.vue" ]; then
        cp App.vue src/App.vue
        print_success "已复制 App.vue 到 src/"
    else
        print_warning "App.vue 未找到（可选）"
    fi
    
    if [ -f "config.js" ]; then
        cp config.js src/config.js
        print_success "已复制 config.js 到 src/"
    else
        print_warning "config.js 未找到（可选）"
    fi
}

# 启动开发服务器
start_dev_server() {
    print_header "启动开发服务器"
    
    echo -e "${YELLOW}"
    echo "=========================================="
    echo "✨ 服务器启动成功！"
    echo "=========================================="
    echo ""
    echo "📱 本地访问: http://localhost:5173/"
    echo ""
    echo "💡 提示："
    echo "  • 按 'h' 查看帮助"
    echo "  • 按 'q' 停止服务器"
    echo "  • 修改代码后自动刷新（HMR）"
    echo ""
    echo "🔗 确保后端也在运行:"
    echo "  python app.py (在另一个终端)"
    echo ""
    echo "=========================================="
    echo -e "${NC}"
    
    npm run dev
}

# 清理函数（Ctrl+C 时执行）
cleanup() {
    echo ""
    print_warning "服务器已停止"
    exit 0
}

# 捕获 Ctrl+C
trap cleanup SIGINT SIGTERM

# ========================================
# 主程序
# ========================================

main() {
    detect_system
    print_header "GeneTi-Maid Frontend 一键启动"
    echo "系统: $OS"
    echo ""
    
    check_nodejs
    enter_project
    backup_files
    check_new_files
    
    # 只在第一次运行时安装依赖
    if [ ! -d "node_modules" ]; then
        install_dependencies
    else
        print_success "node_modules 已存在，跳过安装"
    fi
    
    start_dev_server
}

# 运行主程序
main "$@"
