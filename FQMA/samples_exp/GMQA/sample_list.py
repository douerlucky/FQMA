# ============================================================
# 核心样例 - 5个最有价值的样例（精简版）
# ============================================================

# ============ QueryPlanner - 5个样例 ============
QueryPlannerSamplesList = [
# 样例1：基础3步链（最常见模式）
"""示例1：基础3步依赖链
问题：Dorea，Eubacterium，Bacteroides中哪些微生物群对生猪饲养效率是显著相关的？这些微生物受哪些基因的调控？这些基因的代谢通路有哪些？
子查询列表：
1. [依赖: 无] Dorea，Eubacterium，Bacteroides中哪些微生物群对生猪饲养效率是显著相关的
2. [依赖: 1] 这些微生物受哪些基因的调控
3. [依赖: 2] 这些基因的代谢通路有哪些
""",

# 样例2：带p值和条件（易错点）
"""示例2：带p值条件查询
问题：哪些微生物群关联于生猪饲养效率，在"Fattening, Unmedicated feed formula / Antibiotics and zinc oxide"条件下Pvalue在0.2与0.21之间？这些微生物受哪些基因的调控？这些基因的代谢通路有哪些？
子查询列表：
1. [依赖: 无] 哪些微生物群关联于生猪饲养效率，在"Fattening, Unmedicated feed formula / Antibiotics and zinc oxide"条件下Pvalue在0.2与0.21之间
2. [依赖: 1] 这些微生物受哪些基因的调控
3. [依赖: 2] 这些基因的代谢通路有哪些
""",

# 样例3：食物4步链（新数据库）
"""示例3：食物影响微生物
问题：给ketogenic diet食物导致肠道微生物丰度上升的微生物有哪些？哪些基因的表达能够减少这些微生物的数量？这些基因的代谢通路是什么？
子查询列表：
1. [依赖: 无] 给ketogenic diet食物导致肠道微生物丰度上升的微生物有哪些
2. [依赖: 1] 哪些基因的表达能够减少这些微生物的数量
3. [依赖: 2] 这些基因的代谢通路是什么
""",

# 样例4：药物影响
"""示例4：药物影响微生物
问题：使用药物Metformin导致肠道微生物丰度上升的微生物有哪些？哪些基因的表达能够增加这些微生物群的数量？这些基因的代谢通路是什么？
子查询列表：
1. [依赖: 无] 使用药物Metformin导致肠道微生物丰度上升的微生物有哪些
2. [依赖: 1] 哪些基因的表达能够增加这些微生物群的数量
3. [依赖: 2] 这些基因的代谢通路是什么
""",

# 样例5：指定通路查询
"""示例5：指定通路查询
问题：Clostridium，Treponema中哪些微生物群对生猪饲养效率是显著相关的？哪些基因的表达能够增加这些微生物群的数量？hsa04060，hsa04062，mmu04010中哪些在这些基因的代谢通路里？
子查询列表：
1. [依赖: 无] Clostridium，Treponema中哪些微生物群对生猪饲养效率是显著相关的
2. [依赖: 1] 哪些基因的表达能够增加这些微生物群的数量
3. [依赖: 2] hsa04060，hsa04062，mmu04010中哪些在这些基因的代谢通路里
""",
"""
示例6（药物效应查询链）：
问题：哪些药物能够增加Bifidobacterium的丰度，这些微生物产生哪些代谢物，相关基因的表达如何调节？
子查询列表：
1. [依赖: 无] 哪些药物能够增加Bifidobacterium的丰度？
2. [依赖: 1] Bifidobacterium产生哪些代谢物？
3. [依赖: 2] 哪些基因的表达能够调节这些代谢物的产生？
""",
"""示例7：方向语义不能被上游方向带偏
问题：在药物Metformin干预下丰度显著上升的小鼠肠道微生物群，分析能够抑制这些微生物群生长的关键基因，并进一步阐明这些基因参与的主要代谢通路。
子查询列表：
1. [依赖: 无] 药物Metformin导致丰度显著上升的小鼠肠道微生物群
2. [依赖: 1] 能够抑制这些微生物群生长的关键基因
3. [依赖: 2] 这些基因参与的主要代谢通路
注意：第1步是“微生物丰度上升”，第2步是“基因抑制这些微生物”，两者方向不同，不能把第2步写成“增加/促进”。
"""
]

# ============ SparQLGenerator - 5个样例 ============
SparQLGeneratorSamplesList = [
# 样例1：微生物相关（无p值）- 最基础，最容易误判
"""示例1：微生物相关（无p值，注意"显著"不是p值！）
问题：Dorea，Eubacterium，Bacteroides中哪些微生物群对生猪饲养效率是显著相关的
关键：问题说"显著相关"，但没有提到"p值"、"pvalue"等统计术语！
      "显著相关"是口语化，表示"重要的相关"，不是统计显著性！
SPARQL：
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX ont: <http://www.semanticweb.org/ontologies/integrated_gut_microbiota_ontology#>

SELECT DISTINCT ?microbiota_name
WHERE {{
  ?microbiota rdf:type ont:MicrobiotaName .
  ?microbiota ont:microbiota_name ?microbiota_name .
  ?microbiota ont:correlatedwith_feed_efficiency ?efficiency .
  ?efficiency rdf:type ont:FeedEfficiency .
  FILTER (?microbiota_name IN ("Dorea", "Eubacterium", "Bacteroides"))
}}
注意：不查询pvalue，不使用has_phenotype_association！
""",

"""示例1B：饲养效率提高导致微生物增加（不是显著相关）
问题：生猪饲养效率的提高会导致哪些微生物群数量增加
关键：这里问的是“效率提高导致数量增加”，不是“哪些微生物显著相关”。
      必须使用 increases_feed_efficiency，不能使用 correlatedwith_feed_efficiency。
SPARQL：
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX ont: <http://www.semanticweb.org/ontologies/integrated_gut_microbiota_ontology#>

SELECT DISTINCT ?microbiota_name
WHERE {{
  ?microbiota rdf:type ont:MicrobiotaName .
  ?microbiota ont:microbiota_name ?microbiota_name .
  ?microbiota ont:increases_feed_efficiency ?efficiency .
  ?efficiency rdf:type ont:FeedEfficiency .
}}
注意：只要语义是“提高效率导致/对应微生物增加”，就用 increases_feed_efficiency。
""",

# 样例2：带p值查询 - 关键区分点
"""示例2：带p值条件查询（与"显著相关"对比）
问题：哪些微生物群关联于生猪饲养效率，在"Fattening, Unmedicated feed formula / Antibiotics and zinc oxide"条件下Pvalue在0.2与0.21之间
关键：问题明确提到"Pvalue在0.2与0.21之间"，这是统计术语！
      必须使用has_phenotype_association + pvalue
对比：如果问题只说"显著相关"而不提"pvalue"，则用correlatedwith_feed_efficiency
SPARQL：
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX ont: <http://www.semanticweb.org/ontologies/integrated_gut_microbiota_ontology#>

SELECT DISTINCT ?microbiota_name ?pvalue
WHERE {{
  ?microbiota rdf:type ont:MicrobiotaName .
  ?microbiota ont:microbiota_name ?microbiota_name .
  ?microbiota ont:has_phenotype_association ?association .
  ?association rdf:type ont:PhenotypeAssociation .
  ?association ont:pvalue ?pvalue .
  ?association ont:condition ?condition .
  FILTER (?pvalue >= 0.2 && ?pvalue <= 0.21)
  FILTER (?condition = "Fattening, Unmedicated feed formula / Antibiotics and zinc oxide")
}}
注意：只有明确提到"pvalue"、"p<"等统计术语时才这样写！
""",

# 样例3：食物增加微生物 - gutmdisorder数据库 ⚠️ 只返回微生物名！
"""示例3：食物增加微生物（关键：只返回微生物名，并按自然语言保留宿主！）
问题：在人类宿主中，给ketogenic diet食物导致肠道微生物丰度上升的微生物有哪些
⚠️ 最重要：问题问的是"哪些微生物"，所以只返回微生物名，不返回食物名！
⚠️ 如果问题限定宿主，第一步源头查询也必须写host_type，不能只在后续基因查询中写。
对应SQL：Select microbiota_name from gutmdisorder.food_gut_microbiota_change_results
SPARQL：
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX ont: <http://www.semanticweb.org/ontologies/integrated_gut_microbiota_ontology#>

SELECT ?microbiota_name
WHERE {{
  ?food rdf:type ont:Food .
  ?food ont:food_name ?food_name .
  ?food ont:increases_microbiota_abundance_by_food ?microbiota .
  ?food ont:host_type ?host_type .
  ?microbiota rdf:type ont:MicrobiotaName .
  ?microbiota ont:microbiota_name ?microbiota_name .
  FILTER (?food_name = "ketogenic diet")
  FILTER (?host_type = "human")
}}
注意：
1. 只SELECT ?microbiota_name，不SELECT ?food_name
2. 问题是"哪些微生物"，所以主体是微生物
3. 食物只是查询条件，不是返回结果
4. 原问题有人类宿主，所以第一步也必须保留host_type
""",

# 样例4：基因减少微生物 - 方向性
"""示例4：基因减少微生物（注意方向性）
问题：哪些基因的表达能够减少这些微生物的数量
依赖：<<SUBQUERY_1>>返回了微生物名称
关键：
1. 问"哪些基因"，所以gene_symbol是主体，第一列
2. "减少"微生物，用decreases_microbiota_abundance
SPARQL：
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX ont: <http://www.semanticweb.org/ontologies/integrated_gut_microbiota_ontology#>

SELECT ?gene_symbol ?microbiota_name
WHERE {{
  ?gene rdf:type ont:Gene .
  ?gene ont:gene_symbol ?gene_symbol .
  ?gene ont:decreases_microbiota_abundance ?microbiota .
  ?microbiota rdf:type ont:MicrobiotaName .
  ?microbiota ont:microbiota_name ?microbiota_name .
  FILTER (?microbiota_name IN (<<SUBQUERY_1>>))
}}
""",

# 样例5：指定通路查询（提取标号！）
"""示例5：查询指定KEGG通路（关键：提取标号！）
问题：hsa04062 Chemokine signaling pathway，hsa01521 EGFR tyrosine kinase inhibitor resistance，mmu04010 MAPK signaling pathway中哪些在这些基因的代谢通路里
依赖：<<SUBQUERY_2>>返回了基因符号
⚠️ 最关键：必须从完整名称中提取标号！
处理步骤：
1. 看到"hsa04062 Chemokine signaling pathway" → 提取"hsa04062"
2. 看到"hsa01521 EGFR tyrosine kinase inhibitor resistance" → 提取"hsa01521"
3. 看到"mmu04010 MAPK signaling pathway" → 提取"mmu04010"
4. 在FILTER中只使用标号
5. 指定通路只是额外筛选，不能丢掉上游基因约束；必须保留 FILTER (?gene_symbol IN (<<SUBQUERY_2>>))

SPARQL：
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX ont: <http://www.semanticweb.org/ontologies/integrated_gut_microbiota_ontology#>

SELECT DISTINCT ?pathway_name ?gene_symbol
WHERE {{
  ?gene rdf:type ont:Gene .
  ?gene ont:gene_symbol ?gene_symbol .
  ?gene ont:participates_in_pathway ?pathway .
  ?pathway rdf:type ont:KEGGPathway .
  ?pathway ont:pathway_name ?pathway_name .
  FILTER (?gene_symbol IN (<<SUBQUERY_2>>))
  FILTER (?pathway_name IN ("hsa04062", "hsa01521", "mmu04010"))
}}
注意：FILTER中只用标号，不用完整名称！
数据库中pathway_name字段只存储"hsa04062"这样的标号，不存储完整名称。
如果漏掉 FILTER (?gene_symbol IN (<<SUBQUERY_2>>))，会查出全库所有属于这些通路的基因，而不是“这些基因”的通路。
""",
"""示例6：依赖子查询必须继承宿主约束（减少/抑制方向）
问题：在人类宿主中，能够减少这些微生物数量的基因表达
依赖：<<SUBQUERY_1>> 返回了“在人类宿主 + soluble corn fiber + 丰度上升”得到的微生物
关键：
1. 不可以只写 FILTER (?microbiota_name IN (<<SUBQUERY_1>>))
2. 必须保留宿主约束（human）
3. 方向是“减少”，所以关系必须是 decreases_microbiota_abundance

SPARQL：
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX ont: <http://www.semanticweb.org/ontologies/integrated_gut_microbiota_ontology#>

SELECT ?gene_symbol ?microbiota_name
WHERE {{
  ?gene rdf:type ont:Gene .
  ?gene ont:gene_symbol ?gene_symbol .
  ?gene ont:decreases_microbiota_abundance ?microbiota .
  ?gene ont:host_type ?host_type .
  ?microbiota rdf:type ont:MicrobiotaName .
  ?microbiota ont:microbiota_name ?microbiota_name .
  FILTER (?microbiota_name IN (<<SUBQUERY_1>>))
  FILTER (?host_type = "human")
}}
注意：依赖占位符不会自动携带host，必须显式写FILTER约束。
""",
"""示例7：依赖子查询必须继承宿主约束（增加/促进方向）
问题：在人类宿主中，能够促进这些微生物群生长的关键基因
依赖：<<SUBQUERY_1>> 返回了“在人类宿主 + 某个干预条件 + 丰度上升”得到的微生物
关键：
1. "这些微生物"只通过占位符传递实体集合，不会自动传递host
2. 原问题限定了人类宿主，所以当前基因查询必须继续写host_type约束
3. "促进/增加"微生物，所以关系必须是 increases_microbiota_abundance
4. 不要退化成 regulates_microbiota_abundance，否则会丢失方向条件

SPARQL：
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX ont: <http://www.semanticweb.org/ontologies/integrated_gut_microbiota_ontology#>

SELECT ?gene_symbol ?microbiota_name
WHERE {{
  ?gene rdf:type ont:Gene .
  ?gene ont:gene_symbol ?gene_symbol .
  ?gene ont:increases_microbiota_abundance ?microbiota .
  ?gene ont:host_type ?host_type .
  ?microbiota rdf:type ont:MicrobiotaName .
  ?microbiota ont:microbiota_name ?microbiota_name .
  FILTER (?microbiota_name IN (<<SUBQUERY_1>>))
  FILTER (?host_type = "human")
}}
注意：只要原问题或上游子查询限定了宿主，依赖基因查询就必须显式保留host_type。
""",
"""示例8：小鼠宿主也必须继承host_type（不要照抄human）
问题：在小鼠肠道微生物群中，能够促进这些微生物群生长的关键基因
依赖：<<SUBQUERY_1>> 返回了“小鼠宿主 + 某个干预条件 + 丰度上升”得到的微生物
关键：
1. 宿主值必须根据自然语言判断；这里是小鼠，所以不是human
2. 下游基因查询必须继续写host_type约束
3. "促进/增加"微生物，所以关系必须是 increases_microbiota_abundance
4. 不可以只写 FILTER (?microbiota_name IN (<<SUBQUERY_1>>))

SPARQL：
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX ont: <http://www.semanticweb.org/ontologies/integrated_gut_microbiota_ontology#>

SELECT ?gene_symbol ?microbiota_name
WHERE {{
  ?gene rdf:type ont:Gene .
  ?gene ont:gene_symbol ?gene_symbol .
  ?gene ont:increases_microbiota_abundance ?microbiota .
  ?gene ont:host_type ?host_type .
  ?microbiota rdf:type ont:MicrobiotaName .
  ?microbiota ont:microbiota_name ?microbiota_name .
  FILTER (?microbiota_name IN (<<SUBQUERY_1>>))
  FILTER (?host_type = "mouse")
}}
注意：如果原问题是人类则使用人类对应host_type；如果原问题是小鼠则使用小鼠对应host_type。值来自自然语言语义，不是固定模板。
""",
"""示例9：上游丰度上升，但当前问抑制/减少时必须用decreases
问题：能够抑制这些微生物群生长的关键基因
依赖：<<SUBQUERY_1>> 返回了“某干预导致丰度上升的小鼠微生物”
关键：
1. 上游“丰度上升”只说明这些微生物如何被筛出来
2. 当前子问题问“抑制这些微生物”，所以基因关系必须是 decreases_microbiota_abundance
3. 原问题限定小鼠，所以继续保留host_type = mouse

SPARQL：
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX ont: <http://www.semanticweb.org/ontologies/integrated_gut_microbiota_ontology#>

SELECT ?gene_symbol ?microbiota_name
WHERE {{
  ?gene rdf:type ont:Gene .
  ?gene ont:gene_symbol ?gene_symbol .
  ?gene ont:decreases_microbiota_abundance ?microbiota .
  ?gene ont:host_type ?host_type .
  ?microbiota rdf:type ont:MicrobiotaName .
  ?microbiota ont:microbiota_name ?microbiota_name .
  FILTER (?microbiota_name IN (<<SUBQUERY_1>>))
  FILTER (?host_type = "mouse")
}}
注意：不要因为上游是“丰度上升”就把这里写成increases_microbiota_abundance。
""",
"""示例10：小鼠食物/药物干预的第一步也必须带host_type
问题：在resistant starch饮食干预下丰度显著上升的小鼠肠道微生物群
关键：
1. 这是第一步源头微生物集合查询，不是下游基因查询
2. 只返回microbiota_name
3. 原问题限定了小鼠，所以这里也必须写host_type = mouse
4. 如果这里漏host，<<SUBQUERY_1>>会包含其他宿主的微生物，后续Q2/Q3都会过宽

SPARQL：
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX ont: <http://www.semanticweb.org/ontologies/integrated_gut_microbiota_ontology#>

SELECT DISTINCT ?microbiota_name
WHERE {{
  ?food rdf:type ont:Food .
  ?food ont:food_name ?food_name .
  ?food ont:increases_microbiota_abundance_by_food ?microbiota .
  ?food ont:host_type ?host_type .
  ?microbiota rdf:type ont:MicrobiotaName .
  ?microbiota ont:microbiota_name ?microbiota_name .
  FILTER (?food_name = "resistant starch")
  FILTER (?host_type = "mouse")
}}
注意：宿主值来自自然语言“小鼠”，不是固定模板。
""",
"""示例11：完整干预名不能随便拆分
问题：在人类宿主中，在phenolic compounds from red wine and coffee干预下丰度显著上升的肠道微生物群
关键：
1. `phenolic compounds from red wine and coffee` 是完整干预名
2. 不要拆成 `red wine` 和 `coffee`
3. 原问题限定人类宿主，所以第一步也要保留host_type

SPARQL：
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX ont: <http://www.semanticweb.org/ontologies/integrated_gut_microbiota_ontology#>

SELECT DISTINCT ?microbiota_name
WHERE {{
  ?food rdf:type ont:Food .
  ?food ont:food_name ?food_name .
  ?food ont:increases_microbiota_abundance_by_food ?microbiota .
  ?food ont:host_type ?host_type .
  ?microbiota rdf:type ont:MicrobiotaName .
  ?microbiota ont:microbiota_name ?microbiota_name .
  FILTER (?food_name = "phenolic compounds from red wine and coffee")
  FILTER (?host_type = "human")
}}
注意：只有用户明确给出多个独立干预项时，才使用IN列表。
""",
"""
    示例12：药物减少微生物丰度查询
问题：哪些药物能够减少Clostridium、Bacteroides的丰度？
SPARQL：
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX ont: <http://www.semanticweb.org/ontologies/integrated_gut_microbiota_ontology#>

SELECT ?drug_name ?microbiota_name
WHERE {{
  ?drug rdf:type ont:Drug .
  ?drug ont:drug_name ?drug_name .
  ?drug ont:decreases_microbiota_abundance_by_drug ?microbiota .
  ?microbiota rdf:type ont:MicrobiotaName .
  ?microbiota ont:microbiota_name ?microbiota_name .
  FILTER (?microbiota_name IN ("Clostridium", "Bacteroides"))
}}
    """
]

# ============ SPARQLRepair - 5个核心修复模式 ============
SPARQLRepairSampleList = [
"""修复1：微生物相关（删除efficiency变量）
错误：SELECT ?microbiota_name ?efficiency
正确：SELECT DISTINCT ?microbiota_name
WHERE {{
  ?microbiota rdf:type ont:MicrobiotaName .
  ?microbiota ont:microbiota_name ?microbiota_name .
  ?microbiota ont:correlatedwith_feed_efficiency ?efficiency .
  ?efficiency rdf:type ont:FeedEfficiency .
}}
关键：efficiency只用于关系，不在SELECT中
""",

"""修复2：区分"显著相关"和"p值"（最常见误判！）
错误场景：问题说"关联性最为显著"，误认为需要p值
错误：SELECT ?microbiota_name ?pvalue
      WHERE {{ ?microbiota ont:has_phenotype_association ?association . }}
正确：SELECT DISTINCT ?microbiota_name
      WHERE {{ ?microbiota ont:correlatedwith_feed_efficiency ?efficiency . }}
关键：
- "显著相关"、"关联性显著"、"最为显著" = 口语化的"重要"
- 只有明确出现"pvalue"、"p<"等统计术语时才用PhenotypeAssociation
""",

"""修复3：食物查询只返回微生物名（重要！）
错误：SELECT ?microbiota_name ?food_name
正确：SELECT ?microbiota_name
关键：
- 问题是"哪些微生物"，所以只返回微生物名
- 食物只是查询条件，不是返回结果
- 对应SQL：Select microbiota_name from gutmdisorder...
""",

"""修复4：变量顺序（基因第一列）
错误：SELECT ?microbiota_name ?gene_symbol
正确：SELECT ?gene_symbol ?microbiota_name
关键：问"哪些基因"，基因是主体，必须第一列
""",

"""修复5：KEGG通路标号提取
错误：FILTER (?pathway_name IN ("hsa04062 Chemokine signaling pathway", "mmu04010 MAPK signaling pathway"))
正确：FILTER (?pathway_name IN ("hsa04062", "mmu04010"))
关键：
- 用户给出完整名称时，必须提取标号（空格前的部分）
- 数据库中只存储标号，不存储完整名称
- hsa04062 Chemokine signaling pathway → hsa04062
- mmu04010 MAPK signaling pathway → mmu04010
""",
"""
                       ### 微生物与表型的显著关联（带p值）：
```sparql
SELECT ?microbiota_name ?pvalue WHERE {{
  ?microbiota ont:has_phenotype_association ?association .
  ?association ont:pvalue ?pvalue .
  FILTER (?pvalue < 0.05)
}}
```""",
]
