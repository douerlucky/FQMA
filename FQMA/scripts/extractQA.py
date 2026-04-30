import json


def extract_queries_from_json(file_path):
    """
    从JSON文件中提取问题和查询语句（不包含结果）

    Args:
        file_path (str): JSON文件路径

    Returns:
        list: 包含提取信息的列表
    """

    with open(file_path, 'r', encoding='utf-8') as file:
        data = json.load(file)

    extracted_data = []

    for item in data:
        extracted_item = {
            "id": item.get("id"),
            "question": item.get("question"),
            "queries": {}
        }

        answer = item.get("answer", {})

        # 提取query_1
        if "query_1" in answer:
            query_1 = answer["query_1"]
            extracted_item["queries"]["query_1"] = {
                "description": query_1.get("description"),
                "query_type": "cypher",
                "query": query_1.get("cypher_query")
            }

        # 提取query_2
        if "query_2" in answer:
            query_2 = answer["query_2"]
            extracted_item["queries"]["query_2"] = {
                "description": query_2.get("description"),
                "query_type": "sql",
                "query": query_2.get("sql_query")
            }

        # 提取query_3
        if "query_3" in answer:
            query_3 = answer["query_3"]
            extracted_item["queries"]["query_3"] = {
                "description": query_3.get("description"),
                "query_type": "sql",
                "query": query_3.get("sql_query")
            }

        extracted_data.append(extracted_item)

    return extracted_data


def save_extracted_data(extracted_data, output_file):
    """
    保存提取的数据到新的JSON文件

    Args:
        extracted_data (list): 提取的数据
        output_file (str): 输出文件路径
    """
    with open(output_file, 'w', encoding='utf-8') as file:
        json.dump(extracted_data, file, ensure_ascii=False, indent=2)


def print_queries_summary(extracted_data):
    """
    打印查询语句摘要

    Args:
        extracted_data (list): 提取的数据
    """
    for item in extracted_data:
        print(f"\n{'=' * 60}")
        print(f"ID: {item['id']}")
        print(f"问题: {item['question']}")
        print(f"{'=' * 60}")

        for query_key, query_info in item['queries'].items():
            print(f"\n{query_key.upper()}:")
            print(f"描述: {query_info['description']}")
            print(f"查询类型: {query_info['query_type'].upper()}")
            print(f"查询语句: {query_info['query']}")
            print("-" * 40)


# 主函数
def main():
    input_file = "pig_microbiota_query.json"
    output_file = "extracted_queries.json"

    try:
        # 提取查询信息
        extracted_data = extract_queries_from_json(input_file)

        # 保存到新文件
        save_extracted_data(extracted_data, output_file)

        # 打印摘要信息
        print_queries_summary(extracted_data)

        print(f"\n✅ 提取完成！查询信息已保存到 {output_file}")
        print(f"📊 共提取了 {len(extracted_data)} 个问题的查询信息")

    except FileNotFoundError:
        print(f"❌ 错误：找不到文件 {input_file}")
    except json.JSONDecodeError:
        print(f"❌ 错误：{input_file} 不是有效的JSON文件")
    except Exception as e:
        print(f"❌ 发生错误：{str(e)}")


if __name__ == "__main__":
    main()