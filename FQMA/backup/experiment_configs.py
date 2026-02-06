#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
实验配置文件和便捷运行脚本
可以通过修改这个文件来调整实验参数
"""

from evaluation_framework import ExperimentConfig, ExperimentType, ExperimentRunner
from datetime import datetime
import argparse
import json


class ExperimentSuite:
    """实验套件 - 预定义的实验配置集合"""

    @staticmethod
    def get_parameter_tuning_experiments():
        """参数调优实验"""
        return [
            # 温度参数实验
            ExperimentConfig(
                experiment_name="temp_0.1",
                experiment_type=ExperimentType.PARAMETER_TUNING,
                temperature=0.1,
                max_queries=10
            ),
            ExperimentConfig(
                experiment_name="temp_0.3",
                experiment_type=ExperimentType.PARAMETER_TUNING,
                temperature=0.3,
                max_queries=10
            ),
            ExperimentConfig(
                experiment_name="temp_0.7",
                experiment_type=ExperimentType.PARAMETER_TUNING,
                temperature=0.7,
                max_queries=10
            ),

            # 评分权重实验
            ExperimentConfig(
                experiment_name="high_ontology_weight",
                experiment_type=ExperimentType.PARAMETER_TUNING,
                ontology_consistency_weight=0.7,
                syntax_compliance_weight=0.2,
                complexity_metric_weight=0.1,
                max_queries=10
            ),
            ExperimentConfig(
                experiment_name="high_syntax_weight",
                experiment_type=ExperimentType.PARAMETER_TUNING,
                ontology_consistency_weight=0.2,
                syntax_compliance_weight=0.7,
                complexity_metric_weight=0.1,
                max_queries=10
            ),

            # 修复器参数实验
            ExperimentConfig(
                experiment_name="strict_repair",
                experiment_type=ExperimentType.PARAMETER_TUNING,
                min_score=95,
                max_attempts=3,
                max_queries=10
            ),
            ExperimentConfig(
                experiment_name="loose_repair",
                experiment_type=ExperimentType.PARAMETER_TUNING,
                min_score=80,
                max_attempts=8,
                max_queries=10
            ),
        ]

    @staticmethod
    def get_ontology_experiments():
        """本体对比实验"""
        return [
            ExperimentConfig(
                experiment_name="with_ontology",
                experiment_type=ExperimentType.ONTOLOGY_COMPARISON,
                use_ontology=True,
                max_queries=10
            ),
            ExperimentConfig(
                experiment_name="without_ontology",
                experiment_type=ExperimentType.ONTOLOGY_COMPARISON,
                use_ontology=False,
                max_queries=10
            ),
        ]

    @staticmethod
    def get_repair_experiments():
        """修复器对比实验"""
        return [
            ExperimentConfig(
                experiment_name="with_repair",
                experiment_type=ExperimentType.REPAIR_COMPARISON,
                use_repair=True,
                max_queries=10
            ),
            ExperimentConfig(
                experiment_name="without_repair",
                experiment_type=ExperimentType.REPAIR_COMPARISON,
                use_repair=False,
                max_queries=10
            ),
        ]

    @staticmethod
    def get_llm_experiments():
        """LLM对比实验"""
        experiments = []

        # DeepSeek实验
        experiments.append(ExperimentConfig(
            experiment_name="deepseek_llm",
            experiment_type=ExperimentType.LLM_COMPARISON,
            llm_type="deepseek",
            max_queries=10
        ))

        # 如果有其他LLM的API密钥，可以添加
        try:
            import os
            if os.environ.get('DASHSCOPE_API_KEY'):
                experiments.append(ExperimentConfig(
                    experiment_name="qwen_llm",
                    experiment_type=ExperimentType.LLM_COMPARISON,
                    llm_type="qwen",
                    max_queries=10
                ))
        except:
            pass

        return experiments

    @staticmethod
    def get_prompt_experiments():
        """Prompt对比实验"""
        return [
            ExperimentConfig(
                experiment_name="zero_shot",
                experiment_type=ExperimentType.PROMPT_COMPARISON,
                prompt_type="zero_shot",
                max_queries=10
            ),
            ExperimentConfig(
                experiment_name="few_shot",
                experiment_type=ExperimentType.PROMPT_COMPARISON,
                prompt_type="few_shot",
                max_queries=10
            ),
            ExperimentConfig(
                experiment_name="many_shot",
                experiment_type=ExperimentType.PROMPT_COMPARISON,
                prompt_type="many_shot",
                max_queries=10
            ),
            ExperimentConfig(
                experiment_name="full_prompt",
                experiment_type=ExperimentType.PROMPT_COMPARISON,
                prompt_type="full",
                max_queries=10
            ),
        ]

    @staticmethod
    def get_comprehensive_experiments():
        """综合对比实验（较少数量的查询）"""
        return [
            # 基线
            ExperimentConfig(
                experiment_name="baseline",
                temperature=0.15,
                use_ontology=True,
                use_repair=True,
                prompt_type="full",
                max_queries=5
            ),

            # 最优配置测试
            ExperimentConfig(
                experiment_name="optimized",
                temperature=0.1,
                use_ontology=True,
                use_repair=True,
                prompt_type="many_shot",
                min_score=85,
                max_attempts=5,
                ontology_consistency_weight=0.6,
                syntax_compliance_weight=0.3,
                complexity_metric_weight=0.1,
                max_queries=5
            ),

            # 最简配置测试
            ExperimentConfig(
                experiment_name="minimal",
                temperature=0.5,
                use_ontology=False,
                use_repair=False,
                prompt_type="zero_shot",
                max_queries=5
            ),
        ]


def run_experiment_suite(suite_name: str, max_queries: int = None):
    """运行实验套件"""

    # 获取实验配置
    suite_mapping = {
        'parameter': ExperimentSuite.get_parameter_tuning_experiments,
        'ontology': ExperimentSuite.get_ontology_experiments,
        'repair': ExperimentSuite.get_repair_experiments,
        'llm': ExperimentSuite.get_llm_experiments,
        'prompt': ExperimentSuite.get_prompt_experiments,
        'comprehensive': ExperimentSuite.get_comprehensive_experiments,
    }

    if suite_name not in suite_mapping:
        print(f"未知的实验套件: {suite_name}")
        print(f"可用的套件: {list(suite_mapping.keys())}")
        return

    experiments = suite_mapping[suite_name]()

    # 如果指定了最大查询数，更新所有实验配置
    if max_queries:
        for exp in experiments:
            exp.max_queries = max_queries

    print(f"开始运行实验套件: {suite_name}")
    print(f"实验数量: {len(experiments)}")
    print(f"每个实验的查询数量: {experiments[0].max_queries if experiments else 'N/A'}")
    print("-" * 60)

    # 运行实验
    runner = ExperimentRunner()
    results = []

    for i, config in enumerate(experiments, 1):
        print(f"\n[{i}/{len(experiments)}] 运行实验: {config.experiment_name}")
        try:
            result = runner.run_experiment(config)
            results.append(result)
            print(f"✓ 实验完成 - 成功率: {result.success_rate:.1%}, F1: {result.f1_score:.3f}")
        except Exception as e:
            print(f"✗ 实验失败: {e}")

    # 生成报告
    if results:
        print("\n" + "=" * 60)
        print("生成实验报告...")

        report = runner.generate_report(results)

        # 保存报告
        filename = runner.save_report(report, suite_name)

        print(f"报告已保存: {filename}")

        # 显示简要结果
        print("\n简要结果:")
        print("-" * 60)
        for result in results:
            print(f"{result.config.experiment_name:20} | "
                  f"F1: {result.f1_score:.3f} | "
                  f"成功率: {result.success_rate:.1%} | "
                  f"时间: {result.avg_time_per_query:.1f}s")

        # 显示最佳实验
        if report["summary"]["best_experiment"]:
            print(f"\n🏆 最佳实验: {report['summary']['best_experiment']}")

    return results


def run_custom_experiment():
    """运行自定义实验"""
    print("自定义实验配置:")
    print("请根据提示输入参数，直接回车使用默认值")

    # 基本配置
    name = input("实验名称 [custom]: ") or "custom"
    llm_type = input("LLM类型 (deepseek/qwen) [deepseek]: ") or "deepseek"
    temperature = float(input("温度 (0.0-1.0) [0.15]: ") or "0.15")
    max_queries = int(input("最大查询数 [10]: ") or "10")

    # 组件开关
    use_ontology = input("使用本体? (y/n) [y]: ").lower() != 'n'
    use_repair = input("使用修复器? (y/n) [y]: ").lower() != 'n'

    # Prompt类型
    prompt_type = input("Prompt类型 (zero_shot/few_shot/many_shot/full) [full]: ") or "full"

    # 创建配置
    config = ExperimentConfig(
        experiment_name=name,
        llm_type=llm_type,
        temperature=temperature,
        use_ontology=use_ontology,
        use_repair=use_repair,
        prompt_type=prompt_type,
        max_queries=max_queries
    )

    # 运行实验
    print(f"\n开始运行自定义实验: {name}")
    runner = ExperimentRunner()

    try:
        result = runner.run_experiment(config)

        # 显示结果
        print("\n实验完成!")
        print(f"成功率: {result.success_rate:.1%}")
        print(f"F1分数: {result.f1_score:.3f}")
        print(f"平均查询时间: {result.avg_time_per_query:.2f}秒")

        # 保存报告
        report = runner.generate_report([result])
        filename = runner.save_report(report, "custom")

        print(f"详细报告已保存: {filename}")

    except Exception as e:
        print(f"实验失败: {e}")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='运行系统评估实验')
    parser.add_argument('--suite', type=str,
                        choices=['parameter', 'ontology', 'repair', 'llm', 'prompt', 'comprehensive'],
                        help='选择实验套件')
    parser.add_argument('--max-queries', type=int, default=None,
                        help='每个实验的最大查询数量')
    parser.add_argument('--custom', action='store_true',
                        help='运行自定义实验')
    parser.add_argument('--list', action='store_true',
                        help='列出所有可用的实验套件')

    args = parser.parse_args()

    if args.list:
        print("可用的实验套件:")
        print("- parameter: 参数调优实验（温度、权重等）")
        print("- ontology: 本体对比实验（有无本体）")
        print("- repair: 修复器对比实验（有无修复器）")
        print("- llm: LLM对比实验（不同模型）")
        print("- prompt: Prompt对比实验（零样本、少样本等）")
        print("- comprehensive: 综合对比实验（少量查询的全面测试）")
        return

    if args.custom:
        run_custom_experiment()
    elif args.suite:
        run_experiment_suite(args.suite, args.max_queries)
    else:
        # 默认运行综合实验
        print("未指定实验套件，运行综合实验...")
        run_experiment_suite('comprehensive', args.max_queries)


if __name__ == "__main__":
    # 如果直接运行脚本，提供交互式菜单
    if len(__import__('sys').argv) == 1:
        print("系统评估实验框架")
        print("=" * 50)
        print("1. 参数调优实验")
        print("2. 本体对比实验")
        print("3. 修复器对比实验")
        print("4. LLM对比实验")
        print("5. Prompt对比实验")
        print("6. 综合对比实验")
        print("7. 自定义实验")
        print("0. 退出")

        while True:
            choice = input("\n请选择实验类型 (0-7): ").strip()

            if choice == '0':
                break
            elif choice == '1':
                max_queries = input("查询数量 [10]: ") or "10"
                run_experiment_suite('parameter', int(max_queries))
                break
            elif choice == '2':
                max_queries = input("查询数量 [10]: ") or "10"
                run_experiment_suite('ontology', int(max_queries))
                break
            elif choice == '3':
                max_queries = input("查询数量 [10]: ") or "10"
                run_experiment_suite('repair', int(max_queries))
                break
            elif choice == '4':
                max_queries = input("查询数量 [10]: ") or "10"
                run_experiment_suite('llm', int(max_queries))
                break
            elif choice == '5':
                max_queries = input("查询数量 [10]: ") or "10"
                run_experiment_suite('prompt', int(max_queries))
                break
            elif choice == '6':
                max_queries = input("查询数量 [5]: ") or "5"
                run_experiment_suite('comprehensive', int(max_queries))
                break
            elif choice == '7':
                run_custom_experiment()
                break
            else:
                print("无效选择，请重新输入")
    else:
        main()