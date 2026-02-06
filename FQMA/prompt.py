# import prompts.much_shot,prompts.without_ontology_shot,prompts.few_shot,prompts.zero_shot
# from config import prompt_mode, is_ontology
#
# if(prompt_mode == 'much_shot'):
#     QueryPlanner_template = prompts.much_shot.QueryPlanner_template
#     if(is_ontology == True):
#         SparQLGenerator_template = prompts.much_shot.SparQLGenerator_template
#         SubQueryScheduler_template = prompts.much_shot.SubQueryScheduler_template
#     else:
#         SparQLGenerator_template = prompts.without_ontology_shot.SparQLGenerator_template
#         SubQueryScheduler_template = prompts.without_ontology_shot.SubQueryScheduler_template
#     QueryRepairer_template = prompts.much_shot.QueryRepairer_template
#     ResultAggregation_template = prompts.much_shot.ResultAggregation_template
# elif(prompt_mode == 'few_shot'):
#     QueryPlanner_template = prompts.few_shot.QueryPlanner_template
#     SparQLGenerator_template = prompts.few_shot.SparQLGenerator_template
#     SubQueryScheduler_template = prompts.few_shot.SubQueryScheduler_template
#     QueryRepairer_template = prompts.few_shot.QueryRepairer_template
#     ResultAggregation_template = prompts.few_shot.ResultAggregation_template
# elif(prompt_mode == 'zero_shot'):
#     QueryPlanner_template = prompts.zero_shot.QueryPlanner_template
#     SparQLGenerator_template = prompts.zero_shot.SparQLGenerator_template
#     SubQueryScheduler_template = prompts.zero_shot.SubQueryScheduler_template
#     QueryRepairer_template = prompts.zero_shot.QueryRepairer_template
#     ResultAggregation_template = prompts.zero_shot.ResultAggregation_template