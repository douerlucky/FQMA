import json


def extract_queries(json_file):
    """
    提取JSON文件中的id, question, cypher_query和sql_query
    """
    # 读取JSON文件
    with open(json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # 存储提取的结果
    extracted_data = []

    # 遍历每个条目
    for item in data:
        extracted_item = {
            'id': item.get('id'),
            'question': item.get('question'),
            'cypher_query': item.get('answer', {}).get('query_1', {}).get('cypher_query'),
            'sql_query_2': item.get('answer', {}).get('query_2', {}).get('sql_query'),
            'sql_query_3': item.get('answer', {}).get('query_3', {}).get('sql_query')
        }
        extracted_data.append(extracted_item)

    return extracted_data


def save_to_json(data, output_file):
    """保存为JSON文件"""
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def save_to_csv(data, output_file):
    """保存为CSV文件"""
    import csv

    with open(output_file, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['id', 'question', 'cypher_query', 'sql_query_2', 'sql_query_3'])
        writer.writeheader()
        writer.writerows(data)


# 使用示例
if __name__ == '__main__':
    # 输入文件路径
    input_file = 'pig_microbiota_query_backup2.json'

    # 提取数据
    extracted_data = extract_queries(input_file)

    # 保存为JSON
    save_to_json(extracted_data, 'output.json')

    # 或保存为CSV
    save_to_csv(extracted_data, 'output.csv')

    # 打印结果
    for item in extracted_data:
        print(f"ID: {item['id']}")
        print(f"Question: {item['question']}")
        print(f"Cypher Query: {item['cypher_query']}")
        print(f"SQL Query 2: {item['sql_query_2']}")
        print(f"SQL Query 3: {item['sql_query_3']}")
        print("-" * 80)