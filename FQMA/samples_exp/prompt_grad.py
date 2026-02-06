import samples_exp.GMQA.sample_list as sample_list_gmqa
import samples_exp.RODI.sample_list as sample_list_rodi
import samples_exp.GMQA.prompts_rules as prompts_rules
import samples_exp.RODI.prompts_rules as prompts_rules_rodi
from config import example_use
from config import CURRENT_DATASET

if CURRENT_DATASET == "GMQA":
    # GMQA 数据集使用 prompts_rules 和 sample_list
    QueryPlanner_template = prompts_rules.QueryPlannerRules
    SparQLGenerator_template = prompts_rules.SparQLGeneratorRules
    QueryCheckerRules_template = prompts_rules.QueryCheckerRules
    QueryRepairer_template = prompts_rules.QueryRepairRules
    SubQueryScheduler_template = prompts_rules.SubQuerySchedulerRules
    ResultAggregation_template = prompts_rules.ResultAggregation_template
    sample_list = sample_list_gmqa

elif CURRENT_DATASET == "RODI":
    # RODI 数据集使用 prompts_rules_rodi 和 sample_list_rodi
    QueryPlanner_template = prompts_rules_rodi.QueryPlannerRules
    SparQLGenerator_template = prompts_rules_rodi.SparQLGeneratorRules
    SubQueryScheduler_template = prompts_rules_rodi.SubQuerySchedulerRules
    QueryRepairer_template = prompts_rules_rodi.QueryRepairRules
    ResultAggregation_template = prompts_rules_rodi.ResultAggregation_template
    sample_list = sample_list_rodi

else:
    # 默认使用 GMQA 的规则
    print(f"⚠️ 警告: 未识别的数据集 '{CURRENT_DATASET}'，使用默认的 GMQA 规则")
    QueryPlanner_template = prompts_rules.QueryPlannerRules
    SparQLGenerator_template = prompts_rules.SparQLGeneratorRules
    SubQueryScheduler_template = prompts_rules.SubQuerySchedulerRules
    QueryRepairer_template = prompts_rules.QueryRepairRules
    ResultAggregation_template = prompts_rules.ResultAggregation_template
    sample_list = sample_list_gmqa

# 根据数据集动态加载对应的示例
for add_example in range(example_use):
    QueryPlanner_template += sample_list.QueryPlannerSamplesList[add_example]
    SparQLGenerator_template += sample_list.SparQLGeneratorSamplesList[add_example]
    QueryRepairer_template += sample_list.SPARQLRepairSampleList[add_example]