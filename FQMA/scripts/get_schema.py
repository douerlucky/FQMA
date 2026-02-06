#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
多数据库Schema查询脚本
获取Neo4j、MySQL、PostgreSQL数据库的schema信息
"""

import pymysql
import psycopg2
from neo4j import GraphDatabase
import sys
from typing import Dict, List, Any


class DatabaseSchemaExtractor:
    def __init__(self):
        self.connections = {}

    def connect_neo4j(self, uri: str, username: str, password: str):
        """连接Neo4j数据库"""
        try:
            self.connections['neo4j'] = GraphDatabase.driver(uri, auth=(username, password))
            print("✓ Neo4j连接成功")
        except Exception as e:
            print(f"✗ Neo4j连接失败: {e}")
            return False
        return True

    def connect_mysql(self, host: str, port: int, username: str, password: str, database: str, connection_name: str):
        """连接MySQL数据库"""
        try:
            connection = pymysql.connect(
                host=host,
                port=port,
                user=username,
                password=password,
                database=database,
                charset='utf8mb4',
                cursorclass=pymysql.cursors.DictCursor
            )
            self.connections[connection_name] = connection
            print(f"✓ MySQL({connection_name})连接成功")
        except Exception as e:
            print(f"✗ MySQL({connection_name})连接失败: {e}")
            return False
        return True

    def connect_postgresql(self, host: str, port: int, username: str, password: str, database: str):
        """连接PostgreSQL数据库"""
        try:
            connection = psycopg2.connect(
                host=host,
                port=port,
                user=username,
                password=password,
                database=database
            )
            self.connections['postgresql'] = connection
            print("✓ PostgreSQL连接成功")
        except Exception as e:
            print(f"✗ PostgreSQL连接失败: {e}")
            return False
        return True

    def get_neo4j_schema(self):
        """获取Neo4j数据库schema"""
        print("\n" + "=" * 50)
        print("Neo4j pgmkg2 Schema")
        print("=" * 50)

        if 'neo4j' not in self.connections:
            print("Neo4j连接不存在")
            return

        try:
            with self.connections['neo4j'].session() as session:
                # 获取所有节点标签
                result = session.run("CALL db.labels()")
                labels = [record["label"] for record in result]
                print(f"节点标签 ({len(labels)}个):")
                for label in sorted(labels):
                    print(f"  - {label}")

                print()

                # 获取所有关系类型
                result = session.run("CALL db.relationshipTypes()")
                rel_types = [record["relationshipType"] for record in result]
                print(f"关系类型 ({len(rel_types)}个):")
                for rel_type in sorted(rel_types):
                    print(f"  - {rel_type}")

                print()

                # 获取每个标签的属性
                print("节点属性:")
                for label in sorted(labels)[:5]:  # 只显示前5个标签的详细信息
                    result = session.run(
                        f"MATCH (n:{label}) WITH DISTINCT keys(n) AS keys UNWIND keys AS key RETURN DISTINCT key LIMIT 20")
                    properties = [record["key"] for record in result]
                    print(f"  {label}:")
                    for prop in sorted(properties):
                        print(f"    - {prop}")
                    print()

        except Exception as e:
            print(f"获取Neo4j schema失败: {e}")

    def get_mysql_schema(self, connection_name: str, database_name: str):
        """获取MySQL数据库schema"""
        print("\n" + "=" * 50)
        print(f"MySQL {database_name} Schema")
        print("=" * 50)

        if connection_name not in self.connections:
            print(f"MySQL连接 {connection_name} 不存在")
            return

        try:
            connection = self.connections[connection_name]
            with connection.cursor() as cursor:
                # 获取所有表
                cursor.execute("SHOW TABLES")
                tables = [row[f'Tables_in_{database_name}'] for row in cursor.fetchall()]
                print(f"数据表 ({len(tables)}个):")
                for table in sorted(tables):
                    print(f"  - {table}")

                print()

                # 获取每个表的结构
                print("表结构:")
                for table in sorted(tables)[:10]:  # 只显示前10个表的详细信息
                    print(f"\n  表: {table}")
                    cursor.execute(f"DESCRIBE {table}")
                    columns = cursor.fetchall()
                    print("    字段:")
                    for col in columns:
                        null_info = "NULL" if col['Null'] == 'YES' else "NOT NULL"
                        key_info = f" [{col['Key']}]" if col['Key'] else ""
                        default_info = f" DEFAULT {col['Default']}" if col['Default'] is not None else ""
                        print(f"      {col['Field']}: {col['Type']} {null_info}{key_info}{default_info}")

        except Exception as e:
            print(f"获取MySQL schema失败: {e}")

    def get_postgresql_schema(self, database_name: str):
        """获取PostgreSQL数据库schema"""
        print("\n" + "=" * 50)
        print(f"PostgreSQL {database_name} Schema")
        print("=" * 50)

        if 'postgresql' not in self.connections:
            print("PostgreSQL连接不存在")
            return

        try:
            connection = self.connections['postgresql']
            cursor = connection.cursor()

            # 获取所有表
            cursor.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' 
                ORDER BY table_name
            """)
            tables = [row[0] for row in cursor.fetchall()]
            print(f"数据表 ({len(tables)}个):")
            for table in tables:
                print(f"  - {table}")

            print()

            # 获取每个表的结构
            print("表结构:")
            for table in tables[:10]:  # 只显示前10个表的详细信息
                print(f"\n  表: {table}")
                cursor.execute("""
                    SELECT column_name, data_type, is_nullable, column_default
                    FROM information_schema.columns 
                    WHERE table_name = %s AND table_schema = 'public'
                    ORDER BY ordinal_position
                """, (table,))
                columns = cursor.fetchall()
                print("    字段:")
                for col in columns:
                    null_info = "NULL" if col[2] == 'YES' else "NOT NULL"
                    default_info = f" DEFAULT {col[3]}" if col[3] is not None else ""
                    print(f"      {col[0]}: {col[1]} {null_info}{default_info}")

            cursor.close()

        except Exception as e:
            print(f"获取PostgreSQL schema失败: {e}")

    def close_connections(self):
        """关闭所有数据库连接"""
        for name, conn in self.connections.items():
            try:
                if name == 'neo4j':
                    conn.close()
                elif name == 'postgresql':
                    conn.close()
                else:  # MySQL connections
                    conn.close()
                print(f"✓ {name} 连接已关闭")
            except Exception as e:
                print(f"✗ 关闭 {name} 连接失败: {e}")


def main():
    """主函数"""
    print("数据库Schema提取工具")
    print("=" * 50)

    extractor = DatabaseSchemaExtractor()

    # 数据库连接配置
    # 请根据实际情况修改以下连接参数

    # Neo4j配置
    NEO4J_URI = "bolt://localhost:7687"
    NEO4J_USERNAME = "neo4j"
    NEO4J_PASSWORD = "akie0126"

    # MySQL配置
    MYSQL_HOST = "localhost"
    MYSQL_PORT = 3306
    MYSQL_USERNAME = "root"
    MYSQL_PASSWORD = "1234"

    # PostgreSQL配置
    POSTGRESQL_HOST = "localhost"
    POSTGRESQL_PORT = 5432
    POSTGRESQL_USERNAME = "postgres"
    POSTGRESQL_PASSWORD = "1234"

    try:
        # 连接各个数据库
        print("正在连接数据库...")

        # 连接Neo4j pgmkg2
        extractor.connect_neo4j(NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD)

        # 连接MySQL gutmgenenew
        extractor.connect_mysql(MYSQL_HOST, MYSQL_PORT, MYSQL_USERNAME, MYSQL_PASSWORD,
                                "newgutmgene", "newgutmgene")

        # 连接MySQL relationship
        extractor.connect_mysql(MYSQL_HOST, MYSQL_PORT, MYSQL_USERNAME, MYSQL_PASSWORD,
                                "relationship", "relationship")

        # 连接PostgreSQL kegg
        extractor.connect_postgresql(POSTGRESQL_HOST, POSTGRESQL_PORT, POSTGRESQL_USERNAME,
                                     POSTGRESQL_PASSWORD, "kegg")

        # 获取schema信息
        print("\n开始获取Schema信息...")

        # 获取Neo4j schema
        extractor.get_neo4j_schema()

        # 获取MySQL gutmgenenew schema
        extractor.get_mysql_schema("newgutmgene", "newgutmgene")

        # 获取MySQL relationship schema
        extractor.get_mysql_schema("relationship", "relationship")

        # 获取PostgreSQL kegg schema
        extractor.get_postgresql_schema("kegg")

        print("\n" + "=" * 50)
        print("Schema信息获取完成!")
        print("=" * 50)

    except KeyboardInterrupt:
        print("\n用户中断操作")
    except Exception as e:
        print(f"程序执行出错: {e}")
    finally:
        # 关闭所有连接
        print("\n正在关闭数据库连接...")
        extractor.close_connections()


if __name__ == "__main__":
    # 检查依赖包
    required_packages = ["pymysql", "psycopg2", "neo4j"]
    missing_packages = []

    for package in required_packages:
        try:
            __import__(package)
        except ImportError:
            missing_packages.append(package)

    if missing_packages:
        print("缺少以下依赖包，请先安装:")
        for package in missing_packages:
            print(f"  pip install {package}")
        sys.exit(1)

    main()