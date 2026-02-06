import json
from typing import List, Dict, Any


def validate_element(element: Dict[str, Any]) -> List[str]:
    """验证单个元素是否符合指定格式，返回错误信息列表"""
    errors = []

    # 检查顶级字段
    required_top_fields = ["id", "question", "answer"]
    for field in required_top_fields:
        if field not in element:
            errors.append(f"缺少顶级字段: {field}")

    # 检查id字段
    if "id" in element:
        id_val = element["id"]
        if not isinstance(id_val, str):
            errors.append(f"id字段应为字符串类型，实际为: {type(id_val).__name__}")

    # 检查question字段
    if "question" in element:
        question_val = element["question"]
        if not isinstance(question_val, str):
            errors.append(f"question字段应为字符串类型，实际为: {type(question_val).__name__}")

    # 检查answer字段
    if "answer" in element:
        answer_val = element["answer"]
        if not isinstance(answer_val, dict):
            errors.append(f"answer字段应为字典类型，实际为: {type(answer_val).__name__}")
        else:
            # 检查answer中的query字段（如query_1, query_2等）
            query_keys = [k for k in answer_val.keys() if k.startswith("query_")]
            if not query_keys:
                errors.append("answer中缺少query_*格式的字段")

            for query_key in query_keys:
                query = answer_val[query_key]
                if not isinstance(query, dict):
                    errors.append(f"{query_key}应为字典类型，实际为: {type(query).__name__}")
                    continue

                # 检查每个query的必填字段
                required_query_fields = ["description", "results"]
                for field in required_query_fields:
                    if field not in query:
                        errors.append(f"{query_key}缺少字段: {field}")

                # 检查description
                if "description" in query:
                    desc_val = query["description"]
                    if not isinstance(desc_val, str):
                        errors.append(f"{query_key}的description应为字符串类型，实际为: {type(desc_val).__name__}")

                # 检查results
                if "results" in query:
                    results_val = query["results"]
                    if not isinstance(results_val, list):
                        errors.append(f"{query_key}的results应为列表类型，实际为: {type(results_val).__name__}")
                    else:
                        # 检查results中的每个元素是否为列表
                        for i, item in enumerate(results_val):
                            if not isinstance(item, list):
                                errors.append(
                                    f"{query_key}的results第{i + 1}个元素应为列表类型，实际为: {type(item).__name__}")

                # 检查查询语句字段（cypher_query或sql_query必选其一）
                query_types = ["cypher_query", "sql_query"]
                has_query = any(qt in query for qt in query_types)
                if not has_query:
                    errors.append(f"{query_key}缺少cypher_query或sql_query字段")
                else:
                    # 检查查询语句类型
                    for qt in query_types:
                        if qt in query:
                            q_val = query[qt]
                            if not isinstance(q_val, str):
                                errors.append(f"{query_key}的{qt}应为字符串类型，实际为: {type(q_val).__name__}")

    return errors


def validate_file(file_path: str) -> bool:
    """验证文件中所有元素是否符合格式，返回验证结果"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        if not isinstance(data, list):
            print("文件内容应为列表类型")
            return False

        all_valid = True
        for i, element in enumerate(data):
            print(f"验证第{i + 1}个元素...")
            errors = validate_element(element)
            if errors:
                all_valid = False
                print(f"发现错误:")
                for err in errors:
                    print(f"- {err}")
            else:
                print("验证通过")
            print("---")

        return all_valid

    except json.JSONDecodeError:
        print("文件不是有效的JSON格式")
        return False
    except FileNotFoundError:
        print(f"文件不存在: {file_path}")
        return False
    except Exception as e:
        print(f"验证过程出错: {str(e)}")
        return False


if __name__ == "__main__":
    # 直接在代码中指定文件路径
    file_path = "rodi_query2.json"  # 这里填写了你的文件路径
    if validate_file(file_path):
        print("所有元素均符合格式要求")
        exit(0)
    else:
        print("存在不符合格式要求的元素")
        exit(1)