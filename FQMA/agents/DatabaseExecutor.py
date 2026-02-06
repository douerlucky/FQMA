from neo4j import GraphDatabase
import pymysql
import psycopg2
from psycopg2.extras import RealDictCursor


class Neo4jQueryExecutor:
    def __init__(self, uri, user, password):
        # 创建数据库驱动
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self):
        # 关闭驱动
        self.driver.close()

    def execute_query(self, converted_query):
        with self.driver.session() as session:
            result = session.run(converted_query)
            # 返回所有记录中所有字段拼成列表
            return [record.values() for record in result]


class MySQLQueryExecutor:
    def __init__(self, host, user, password, database, port=3306):
        # 创建数据库连接
        self.connection = pymysql.connect(
            host=host,
            user=user,
            password=password,
            database=database,
            port=port,
            charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor  # 使用字典游标便于处理
        )

    def close(self):
        # 关闭数据库连接
        if self.connection:
            self.connection.close()

    def execute_query(self, sql_query):
        try:
            with self.connection.cursor() as cursor:
                # 执行SQL查询
                cursor.execute(sql_query)
                # 获取所有结果
                results = cursor.fetchall()

                # 转换为列表格式，保持与Neo4j执行器的输出一致
                if results:
                    # 如果是字典游标，提取值为列表
                    if isinstance(results[0], dict):
                        return [list(record.values()) for record in results]
                    else:
                        # 如果是元组，直接转换为列表
                        return [list(record) for record in results]
                else:
                    return []

        except Exception as e:
            print(f"执行MySQL查询时出错: {e}")
            return []

    def execute_query_with_columns(self, sql_query):
        """
        执行查询并返回包含列名的结果

        返回:
            dict: {'columns': [列名列表], 'data': [数据列表]}
        """
        try:
            with self.connection.cursor() as cursor:
                cursor.execute(sql_query)
                results = cursor.fetchall()

                if results:
                    if isinstance(results[0], dict):
                        # 字典游标
                        columns = list(results[0].keys())
                        data = [list(record.values()) for record in results]
                    else:
                        # 元组游标
                        columns = [desc[0] for desc in cursor.description]
                        data = [list(record) for record in results]

                    return {
                        'columns': columns,
                        'data': data
                    }
                else:
                    return {'columns': [], 'data': []}

        except Exception as e:
            print(f"执行MySQL查询时出错: {e}")
            return {'columns': [], 'data': []}


class PostgreQueryExecutor:
    def __init__(self, host, user, password, database, port=5432):
        # 创建数据库连接
        self.connection = psycopg2.connect(
            host=host,
            user=user,
            password=password,
            database=database,
            port=port
        )

    def close(self):
        # 关闭数据库连接
        if self.connection:
            self.connection.close()

    def execute_query(self, sql_query):
        try:
            with self.connection.cursor(cursor_factory=RealDictCursor) as cursor:
                # 执行SQL查询
                cursor.execute(sql_query)
                # 获取所有结果
                results = cursor.fetchall()

                # 转换为列表格式，保持与其他执行器的输出一致
                if results:
                    return [list(record.values()) for record in results]
                else:
                    return []

        except Exception as e:
            print(f"执行PostgreSQL查询时出错: {e}")
            return []

    def execute_query_with_columns(self, sql_query):
        """
        执行查询并返回包含列名的结果

        返回:
            dict: {'columns': [列名列表], 'data': [数据列表]}
        """
        try:
            with self.connection.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(sql_query)
                results = cursor.fetchall()

                if results:
                    columns = list(results[0].keys())
                    data = [list(record.values()) for record in results]

                    return {
                        'columns': columns,
                        'data': data
                    }
                else:
                    return {'columns': [], 'data': []}

        except Exception as e:
            print(f"执行PostgreSQL查询时出错: {e}")
            return {'columns': [], 'data': []}


# 使用示例
if __name__ == "__main__":
    # Neo4j 示例
    print("=== Neo4j 查询示例 ===")
    neo4j_uri = "bolt://localhost:7687"
    neo4j_user = "neo4j"
    neo4j_password = "akie0126"

    neo4j_executor = Neo4jQueryExecutor(neo4j_uri, neo4j_user, neo4j_password)

    neo4j_query = "MATCH (s:MicrobiotaName)-[r:increase]->(o {name:'FE'}) RETURN s.name"
    neo4j_result = neo4j_executor.execute_query(neo4j_query)

    print("Neo4j查询结果:")
    print(neo4j_result)

    neo4j_executor.close()

    print("\n" + "=" * 50 + "\n")

    # MySQL 示例
    print("=== MySQL 查询示例 ===")
    mysql_host = "localhost"
    mysql_user = "root"
    mysql_password = "1234"
    mysql_database = "none"
    mysql_port = 3306

    mysql_executor = MySQLQueryExecutor(
        host=mysql_host,
        user=mysql_user,
        password=mysql_password,
        database=mysql_database,
        port=mysql_port
    )

    # 基本查询示例
    mysql_query = "SELECT gene_symbol, relationship FROM has_expression_change_results_by_microbiota WHERE relationship IN ('Lactobacillus', 'Bifidobacterium') LIMIT 10"
    mysql_result = mysql_executor.execute_query(mysql_query)

    print("MySQL查询结果:")
    print(mysql_result)

    # 带列名的查询示例
    mysql_result_with_columns = mysql_executor.execute_query_with_columns(mysql_query)
    print("\nMySQL查询结果(带列名):")
    print("列名:", mysql_result_with_columns['columns'])
    print("数据:", mysql_result_with_columns['data'])

    mysql_executor.close()

    print("\n" + "=" * 50 + "\n")

    # PostgreSQL 示例
    print("=== PostgreSQL 查询示例 ===")
    postgres_host = "localhost"
    postgres_user = "postgres"
    postgres_password = "1234"
    postgres_database = "kegg"
    postgres_port = 5432

    postgres_executor = PostgreQueryExecutor(
        host=postgres_host,
        user=postgres_user,
        password=postgres_password,
        database=postgres_database,
        port=postgres_port
    )

    # 基本查询示例
    postgres_query = """select gene_symbol,pathway
from "kegg"
where gene_symbol in ('IL22','MAPK14','Tjp1','Arg1')"""
    postgres_result = postgres_executor.execute_query(postgres_query)

    print("PostgreSQL查询结果:")
    print(postgres_result)

    # 带列名的查询示例
    postgres_result_with_columns = postgres_executor.execute_query_with_columns(postgres_query)
    print("\nPostgreSQL查询结果(带列名):")
    print("列名:", postgres_result_with_columns['columns'])
    print("数据:", postgres_result_with_columns['data'])

    postgres_executor.close()