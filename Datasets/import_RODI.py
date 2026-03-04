#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# 数据集根目录（含 RODI-Conf 文件夹的父目录）
DATA_ROOT = "./"

# MySQL 配置
MYSQL_HOST     = "localhost"
MYSQL_PORT     = 3306
MYSQL_USER     = "root"
MYSQL_PASSWORD = "pwd"    # MySQL密码

# PostgreSQL 配置
PG_HOST     = "localhost"
PG_PORT     = 5432
PG_USER     = "postgres"
PG_PASSWORD = "pwd"          # Postgre密码

# Neo4j 配置
NEO4J_URI      = "bolt://localhost:7687"
NEO4J_USER     = "neo4j"
NEO4J_PASSWORD = "pwd"    # Neo4j密码

# ════════════════════════════════════════════════════════════════
#  以下内容无需修改
# ════════════════════════════════════════════════════════════════

import os
import sys
import subprocess

RODI_DIR = os.path.join(DATA_ROOT, "RODI-Conf")

# 导入任务定义（数据库统一命名为 rodiConference）
MYSQL_TASKS = [
    {"file": "rodiConference_mysql.sql",    "database": "rodiConference"},
]
PG_TASKS = [
    {"file": "rodiConference_postgre.sql",  "database": "rodiConference"},
]
NEO4J_TASKS = [
    {"file": "rodi_neo4j.cypher"},
]

# ── 日志 ─────────────────────────────────────────────────────

def log(msg, level="INFO"):
    tag = {"INFO": "  ·", "OK": "  ✅", "SKIP": "  ⏭ ", "ERROR": "  ❌", "STEP": "\n  →"}
    print(f"{tag.get(level, '  ')} {msg}", flush=True)

# ── MySQL ─────────────────────────────────────────────────────

def _mysql_connect(database=None):
    try:
        import pymysql
    except ImportError:
        log("安装 pymysql ...", "INFO")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pymysql", "-q"])
        import pymysql
    kwargs = dict(host=MYSQL_HOST, port=MYSQL_PORT,
                  user=MYSQL_USER, password=MYSQL_PASSWORD, charset="utf8mb4")
    if database:
        kwargs["database"] = database
    return pymysql.connect(**kwargs)

def _mysql_db_has_tables(db):
    try:
        conn = _mysql_connect(db)
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema=%s", (db,)
            )
            count = cur.fetchone()[0]
        conn.close()
        return count > 0
    except Exception:
        return False

def import_mysql(task):
    db   = task["database"]
    path = os.path.join(RODI_DIR, task["file"])
    log(f"[MySQL] {task['file']}  →  数据库: {db}", "STEP")

    if not os.path.exists(path):
        log(f"文件不存在: {path}", "ERROR"); return False

    conn = _mysql_connect()
    with conn.cursor() as cur:
        cur.execute("SHOW DATABASES LIKE %s", (db,))
        db_exists = cur.fetchone() is not None
    conn.close()

    if db_exists and _mysql_db_has_tables(db):
        log(f"数据库 [{db}] 已存在且有数据，跳过", "SKIP"); return True

    if not db_exists:
        conn = _mysql_connect()
        with conn.cursor() as cur:
            cur.execute(f"CREATE DATABASE `{db}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
        conn.commit(); conn.close()
        log(f"数据库 [{db}] 已创建", "INFO")

    cmd = ["mysql", f"-h{MYSQL_HOST}", f"-P{MYSQL_PORT}",
           f"-u{MYSQL_USER}", f"-p{MYSQL_PASSWORD}", db]
    try:
        with open(path, "r", encoding="utf8") as f:
            r = subprocess.run(cmd, stdin=f, capture_output=True, text=True)
        if r.returncode != 0:
            log(f"导入失败:\n{r.stderr[:400]}", "ERROR"); return False
        log(f"导入成功: {task['file']}", "OK"); return True
    except FileNotFoundError:
        log("未找到 mysql 命令，请确保 MySQL 客户端已加入系统 PATH", "ERROR"); return False

# ── PostgreSQL ────────────────────────────────────────────────

def _pg_env():
    e = os.environ.copy()
    e["PGPASSWORD"] = PG_PASSWORD
    return e

def _pg_run(*args):
    base = ["psql", "-h", PG_HOST, "-p", str(PG_PORT), "-U", PG_USER]
    return subprocess.run(base + list(args), capture_output=True, text=True, env=_pg_env())

def _pg_db_exists(db):
    r = _pg_run("-tAc", f"SELECT 1 FROM pg_database WHERE datname='{db}'")
    return r.stdout.strip() == "1"

def _pg_has_tables(db):
    r = _pg_run("-d", db, "-tAc",
                "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public'")
    try: return int(r.stdout.strip()) > 0
    except Exception: return False

def import_pg(task):
    db   = task["database"]
    path = os.path.join(RODI_DIR, task["file"])
    log(f"[PostgreSQL] {task['file']}  →  数据库: {db}", "STEP")

    if not os.path.exists(path):
        log(f"文件不存在: {path}", "ERROR"); return False

    try:
        subprocess.run(["psql", "--version"], capture_output=True, check=True)
    except FileNotFoundError:
        log("未找到 psql 命令，请确保 PostgreSQL 客户端已加入系统 PATH", "ERROR"); return False

    if _pg_db_exists(db) and _pg_has_tables(db):
        log(f"数据库 [{db}] 已存在且有数据，跳过", "SKIP"); return True

    if not _pg_db_exists(db):
        r = _pg_run("-c", f'CREATE DATABASE "{db}"')
        if r.returncode != 0 and "already exists" not in r.stderr:
            log(f"创建数据库失败: {r.stderr[:200]}", "ERROR"); return False
        log(f"数据库 [{db}] 已创建", "INFO")

    r = subprocess.run(
        ["psql", "-h", PG_HOST, "-p", str(PG_PORT), "-U", PG_USER, "-d", db, "-f", path],
        capture_output=True, text=True, env=_pg_env()
    )
    if r.returncode != 0:
        log(f"导入失败:\n{r.stderr[:400]}", "ERROR"); return False
    log(f"导入成功: {task['file']}", "OK"); return True

# ── Neo4j ─────────────────────────────────────────────────────

def import_neo4j(task):
    path = os.path.join(RODI_DIR, task["file"])
    log(f"[Neo4j] {task['file']}", "STEP")

    if not os.path.exists(path):
        log(f"文件不存在: {path}", "ERROR"); return False

    try:
        from neo4j import GraphDatabase
    except ImportError:
        log("安装 neo4j 驱动 ...", "INFO")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "neo4j", "-q"])
        from neo4j import GraphDatabase

    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    try:
        with driver.session() as session:
            cnt = session.run("MATCH (n) RETURN count(n) AS c").single()["c"]
            if cnt > 0:
                log(f"Neo4j 已有 {cnt} 个节点，跳过导入", "SKIP"); return True

        with open(path, "r", encoding="utf8") as f:
            content = f.read()

        stmts, buf = [], []
        for line in content.splitlines():
            s = line.strip()
            if not s or s.startswith("//") or s.startswith("#"):
                continue
            buf.append(line)
            if s.endswith(";"):
                stmt = "\n".join(buf).rstrip(";").strip()
                if stmt:
                    stmts.append(stmt)
                buf = []

        log(f"共 {len(stmts)} 条语句，执行中...", "INFO")
        errors = 0
        with driver.session() as session:
            for i, stmt in enumerate(stmts, 1):
                try:
                    session.run(stmt)
                except Exception as e:
                    log(f"第 {i} 条失败（跳过）: {str(e)[:120]}", "ERROR")
                    errors += 1
                if i % 500 == 0:
                    log(f"进度: {i}/{len(stmts)}", "INFO")

        if errors:
            log(f"完成，但有 {errors} 条语句失败，请检查日志", "ERROR")
        else:
            log(f"导入成功: {task['file']}", "OK")
        return True
    finally:
        driver.close()

# ── 主程序 ────────────────────────────────────────────────────

def main():
    print()
    print("╔══════════════════════════════════════════╗")
    print("║     📄 RODI-Conf 数据集一键导入           ║")
    print("╚══════════════════════════════════════════╝")

    if not os.path.isdir(RODI_DIR):
        log(f"未找到数据目录: {RODI_DIR}", "ERROR")
        log("请检查脚本顶部 DATA_ROOT 配置", "ERROR")
        sys.exit(1)

    results = []

    print("\n── MySQL ────────────────────────────────────")
    for t in MYSQL_TASKS:
        results.append((t["file"], "MySQL", import_mysql(t)))

    print("\n── PostgreSQL ───────────────────────────────")
    for t in PG_TASKS:
        results.append((t["file"], "PostgreSQL", import_pg(t)))

    print("\n── Neo4j ────────────────────────────────────")
    for t in NEO4J_TASKS:
        results.append((t["file"], "Neo4j", import_neo4j(t)))

    print()
    print("╔══════════════════════════════════════════╗")
    print("║              导入结果汇总                  ║")
    print("╚══════════════════════════════════════════╝")
    all_ok = True
    for fname, dbtype, ok in results:
        mark = "✅" if ok else "❌"
        print(f"  {mark}  [{dbtype:12s}] {fname}")
        if not ok:
            all_ok = False
    print()
    if all_ok:
        print("  🎉 RODI-Conf 全部导入完成！\n")
    else:
        print("  ⚠️  部分导入失败，请检查上方错误信息。\n")

if __name__ == "__main__":
    main()
