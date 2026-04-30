import samples_exp.GMQA.sample_list as sample_list_gmqa
import samples_exp.RODI.sample_list as sample_list_rodi
import samples_exp.GMQA.prompts_rules as prompts_rules_gmqa
import samples_exp.RODI.prompts_rules as prompts_rules_rodi
import config


def get_templates():
    if config.CURRENT_DATASET == "GMQA":
        QueryPlanner_template = prompts_rules_gmqa.QueryPlannerRules
        SparQLGenerator_template = prompts_rules_gmqa.SparQLGeneratorRules
        QueryCheckerRules_template = prompts_rules_gmqa.QueryCheckerRules
        QueryRepairer_template = prompts_rules_gmqa.QueryRepairRules
        SubQueryScheduler_template = prompts_rules_gmqa.SubQuerySchedulerRules
        ResultAggregation_template = prompts_rules_gmqa.ResultAggregation_template
    elif config.CURRENT_DATASET == "RODI":
        QueryPlanner_template = prompts_rules_rodi.QueryPlannerRules
        SparQLGenerator_template = prompts_rules_rodi.SparQLGeneratorRules
        QueryCheckerRules_template = prompts_rules_gmqa.QueryCheckerRules
        QueryRepairer_template = prompts_rules_rodi.QueryRepairRules
        SubQueryScheduler_template = prompts_rules_rodi.SubQuerySchedulerRules
        ResultAggregation_template = prompts_rules_rodi.ResultAggregation_template



    if config.CURRENT_DATASET == "GMQA":
        for add_example in range(config.example_use):
            QueryPlanner_template += sample_list_gmqa.QueryPlannerSamplesList[add_example]
            SparQLGenerator_template += sample_list_gmqa.SparQLGeneratorSamplesList[add_example]
            QueryRepairer_template += sample_list_gmqa.SPARQLRepairSampleList[add_example]
    else:
        for add_example in range(config.example_use):
            QueryPlanner_template += sample_list_rodi.QueryPlannerSamplesList[add_example]
            SparQLGenerator_template += sample_list_rodi.SparQLGeneratorSamplesList[add_example]
            QueryRepairer_template += sample_list_rodi.SPARQLRepairSampleList[add_example]

    return QueryPlanner_template, SparQLGenerator_template, QueryCheckerRules_template,QueryRepairer_template,SubQueryScheduler_template,ResultAggregation_template