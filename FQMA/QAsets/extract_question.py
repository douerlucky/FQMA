import json
import csv


def extract_questions(json_file):
    """
    提取JSON文件中的id和question

    Args:
        json_file: 输入的JSON文件路径

    Returns:
        list: 包含id和question的字典列表
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
            'question': item.get('question')
        }
        extracted_data.append(extracted_item)

    return extracted_data


def save_to_json(data, output_file):
    """
    保存为JSON文件

    Args:
        data: 要保存的数据
        output_file: 输出文件路径
    """
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"✅ 已保存到 JSON 文件: {output_file}")


def save_to_csv(data, output_file):
    """
    保存为CSV文件

    Args:
        data: 要保存的数据
        output_file: 输出文件路径
    """
    with open(output_file, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['id', 'question'])
        writer.writeheader()
        writer.writerows(data)
    print(f"✅ 已保存到 CSV 文件: {output_file}")


def save_to_txt(data, output_file):
    """
    保存为纯文本文件（每行一个问题）

    Args:
        data: 要保存的数据
        output_file: 输出文件路径
    """
    with open(output_file, 'w', encoding='utf-8') as f:
        for item in data:
            f.write(f"ID: {item['id']}\n")
            f.write(f"问题: {item['question']}\n")
            f.write("-" * 80 + "\n\n")
    print(f"✅ 已保存到 TXT 文件: {output_file}")


def print_statistics(data):
    """
    打印统计信息

    Args:
        data: 提取的数据
    """
    print("\n" + "=" * 80)
    print("📊 数据统计")
    print("=" * 80)
    print(f"总问题数: {len(data)}")

    # 统计问题长度
    question_lengths = [len(item['question']) for item in data]
    print(f"问题平均长度: {sum(question_lengths) / len(question_lengths):.1f} 字符")
    print(f"最短问题: {min(question_lengths)} 字符")
    print(f"最长问题: {max(question_lengths)} 字符")

    # 显示前3个问题作为示例
    print("\n📝 前3个问题示例:")
    print("-" * 80)
    for i, item in enumerate(data[:3], 1):
        print(f"{i}. [ID: {item['id']}] {item['question']}")
    print("=" * 80 + "\n")


# 使用示例
if __name__ == '__main__':
    # 输入文件路径
    input_file = 'pig_microbiota_query_backup2.json'

    print("🔍 开始提取问题...")
    print(f"📁 输入文件: {input_file}\n")

    try:
        # 提取数据
        extracted_data = extract_questions(input_file)

        # 打印统计信息
        print_statistics(extracted_data)

        # 保存为不同格式
        save_to_json(extracted_data, 'questions.json')
        save_to_csv(extracted_data, 'questions.csv')
        save_to_txt(extracted_data, 'questions.txt')

        print("\n✅ 所有文件已生成完成！")

    except FileNotFoundError:
        print(f"❌ 错误: 找不到文件 '{input_file}'")
        print("💡 提示: 请确保文件在当前目录下，或提供完整路径")
    except json.JSONDecodeError:
        print(f"❌ 错误: '{input_file}' 不是有效的JSON文件")
    except Exception as e:
        print(f"❌ 发生错误: {str(e)}")