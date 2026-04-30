# ============================================================
# prompts_rules.py - 修复版（零硬编码）
#
# 修复内容：
# 1. SubQuerySchedulerRules 添加了 {question}, {sparql_query}, {ttl_info} 变量
# 2. 移除所有硬编码的数据库映射，让LLM从TTL动态学习
# ============================================================

# ============================================================
# QueryPlanner - 查询分解规则（保持不变）
# ============================================================
QueryPlannerRules = """
你是查询分解专家，将复杂问题分解为依赖链式子查询。

## 分解原则
1. **识别依赖**：后续查询依赖前面结果
2. **合并同类**：同类查询合并为一个（多个微生物的相同属性）
3. **保持简洁**：每个子查询对应一个具体信息需求
4. **避免冗余**：不添加"机制"、"如何影响"等解释性查询
5. **方向语义守恒**：分解时必须保留原问题中的方向词，不能改写成相反方向。

## 方向语义守恒（极重要）
- 原问题说“抑制、减少、降低、下降、下调”这些微生物时，后续基因子查询必须写成“减少/抑制这些微生物”，不能写成“增加/促进这些微生物”。
- 原问题说“促进、增加、提高、上升、上调”这些微生物时，后续基因子查询必须写成“增加/促进这些微生物”，不能写成“减少/抑制这些微生物”。
- 第一阶段的“食物/药物使微生物丰度上升/下降”只描述筛选微生物集合；第二阶段的“基因增加/减少这些微生物”必须以第二阶段原文动词为准，不能被第一阶段方向覆盖。
- 如果原问题是“丰度上升的微生物 + 抑制这些微生物生长的基因”，正确分解是：
  1. [依赖: 无] 某干预导致丰度上升的微生物
  2. [依赖: 1] 能够抑制/减少这些微生物生长的基因
- 如果原问题是“丰度上升的微生物 + 促进这些微生物生长的基因”，正确分解是：
  1. [依赖: 无] 某干预导致丰度上升的微生物
  2. [依赖: 1] 能够促进/增加这些微生物生长的基因

## 典型模式
**3步链（最常见）**：
问题：微生物A相关？受哪些基因调控？基因的通路？
分解：
1. [依赖: 无] 微生物A是否相关
2. [依赖: 1] 哪些基因调控这些微生物
3. [依赖: 2] 这些基因参与什么通路

**4步链（食物/药物）**：
问题：食物X增加哪些微生物？基因调控？通路？
分解：
1. [依赖: 无] 食物X增加哪些微生物
2. [依赖: 1] 哪些基因调控这些微生物
3. [依赖: 2] 基因参与什么通路

**方向混合链（不要混淆两个阶段的方向）**：
问题：干预X导致丰度上升的小鼠微生物，能够抑制这些微生物生长的基因及通路？
分解：
1. [依赖: 无] 干预X导致丰度上升的小鼠微生物
2. [依赖: 1] 能够抑制这些微生物生长的基因
3. [依赖: 2] 这些基因参与什么通路

**指定通路筛选链（不能合并基因和通路）**：
问题：条件X下哪些微生物相关？调控这些微生物的基因中，哪些参与了指定KEGG通路？
分解：
1. [依赖: 无] 条件X下相关的微生物
2. [依赖: 1] 调控这些微生物的基因
3. [依赖: 2] 检查指定KEGG通路是否在这些基因的代谢通路中

注意：即使原问题列出很多 hsa/mmu 通路编号，也不能把第2步直接写成“参与指定通路的基因”。必须先得到调控这些微生物的基因集合，再在第3步用指定通路筛选这些基因。

## 输出格式
X. [依赖: Y] 子查询内容

**要求**：
- 第一个必须是[依赖: 无]
- 只输出"子查询列表："及内容
- 无任何额外解释

问题：{question}

子查询列表：
"""

# ============================================================
# SparQLGenerator - SPARQL生成规则（保持不变）
# ============================================================
SparQLGeneratorRules = """
你是SPARQL生成器，将自然语言转换为SPARQL。

输入：
- 子问题：{sub_question}
- 本体：{ontology[classes]}, {ontology[properties]}, {ontology[example_triples]}
- 依赖：{dependencies}

## 核心规则

### 1. SELECT变量（最重要）
**原则：只SELECT问题直接询问的实体，主体第一列**

| 问题模式 | SELECT（主体第一列） | 说明 |
|---------|---------------------|------|
| "哪些基因..." | ?gene_symbol ?microbiota_name | 基因是主体 |
| "哪些微生物..." | ?microbiota_name | 只返回微生物名 |
| "微生物是否相关" | ?microbiota_name | 只返回微生物名 |
| "微生物相关（带p值）" | ?microbiota_name ?pvalue | 需要p值时才包含 |
| "基因参与什么通路" | ?pathway_name ?gene_symbol | 通路是主体 |
| "微生物产生的代谢物" | ?metabolite_name ?microbiota_name | 代谢物是主体 |
| "代谢物和哪些基因有关" | ?gene_symbol ?metabolite_name | 基因是主体 |
| "食物增加哪些微生物" | ?microbiota_name | **只返回微生物，不返回食物** |
| "药物增加哪些微生物" | ?microbiota_name | **只返回微生物，不返回药物** |

⚠️ **关键**：食物/药物查询时，问题是"哪些微生物"，所以只返回微生物名，不返回食物名或药物名！

### 2. 有效变量
microbiota_name, gene_symbol, pathway_name, food_name, drug_name, metabolite_name, pvalue, condition

### 3. 关系映射（严格遵守）

**Neo4j关系：**
| 问题特征 | 关系 |
|---------|------|
| 明确p值（"p<0.02", "pvalue在..."） | ont:has_phenotype_association + ont:pvalue |
| "相关"无p值 | ont:correlatedwith_feed_efficiency |
| "提高效率" | ont:increases_feed_efficiency |
| "产生代谢物" | ont:generates_metabolite |

**MySQL(newgutmgene)关系：**
| 问题特征 | 关系 |
|---------|------|
| 基因"调控"微生物 | ont:regulates_microbiota_abundance |
| 基因"增加"微生物 | ont:increases_microbiota_abundance |
| 基因"减少"微生物 | ont:decreases_microbiota_abundance |
| 微生物"影响"基因 | ont:changes_gene_expression_by_microbiota |

方向词必须按语义选择具体关系：
- "增加"、"促进"、"促生长"、"提高数量"、"上调丰度" → ont:increases_microbiota_abundance
- "减少"、"抑制"、"降低数量"、"下调丰度"、"抑制生长" → ont:decreases_microbiota_abundance
- 只有问题真正没有方向，只说"调控/影响"时，才使用 ont:regulates_microbiota_abundance

方向选择必须以当前子问题的基因动作动词为准：
- 当前子问题问“能够抑制/减少这些微生物的基因”，必须使用 `ont:decreases_microbiota_abundance`。
- 当前子问题问“能够促进/增加这些微生物的基因”，必须使用 `ont:increases_microbiota_abundance`。
- 上游子问题里的“微生物丰度上升/下降”只用于确定 `<<SUBQUERY_X>>` 的微生物集合，不决定当前基因关系方向。
- 禁止因为上游是“丰度上升的微生物”就在当前基因查询中使用 `increases_microbiota_abundance`；当前基因查询是否 increase/decrease 只看当前子问题。

**MySQL(gutmdisorder)关系：**
| 问题特征 | 关系 |
|---------|------|
| 食物"增加"微生物 | ont:increases_microbiota_abundance_by_food |
| 食物"减少"微生物 | ont:decreases_microbiota_abundance_by_food |
| 药物"增加"微生物 | ont:increases_microbiota_abundance_by_drug |
| 药物"减少"微生物 | ont:decreases_microbiota_abundance_by_drug |

食物/药物导致微生物丰度变化时，如果问题限定宿主，也必须在源头查询中加入宿主过滤：
- 食物查询：使用 `?food ont:host_type ?host_type .` 并添加对应 `FILTER`
- 药物查询：使用 `?drug ont:host_type ?host_type .` 并添加对应 `FILTER`
- 不能只在后续基因查询中加宿主；第一步微生物集合如果没有宿主过滤，会把上游集合放大，导致后续全部过宽。

干预名称抽取规则：
- 对“在X干预下”“给X食物/药物”“使用药物X”等表达，`X` 是完整干预名称。
- 不要把 `phenolic compounds from red wine and coffee` 拆成 `red wine` 和 `coffee`；应保留完整短语作为 `food_name` 或 `drug_name`。
- 只有问题明确说“分别查询red wine和coffee”或用列表方式枚举多个独立干预时，才使用 `IN (...)`。

**PostgreSQL关系：**
| 问题特征 | 关系 |
|---------|------|
| "参与通路"（KEGG） | ont:participates_in_pathway |

### 4. 决策树

**步骤1：判断p值（最关键！）**

⚠️ **关键警告**：
- "显著相关"、"显著"、"关联性显著"、"最为显著" ≠ p值！
- 这些是口语化表达，表示"重要的相关"，不是统计学p值
- **只有**明确出现这些词才用has_phenotype_association：
  * "p值"、"pvalue"、"p<"、"p>"、"p="
  * "pvalue在X-Y之间"
  * "显著性p"、"统计显著性"

判断规则：
- 有明确p值统计术语 → has_phenotype_association + pvalue
- 说"相关"、"显著相关"、"关联"（无p值术语） → correlatedwith_feed_efficiency
- 说"提高效率" → increases_feed_efficiency
- 说"生猪饲养效率提高会导致/引起哪些微生物数量增加" → increases_feed_efficiency
- 上一句这种“效率提高导致微生物增加”不是“显著相关”查询，不能使用 correlatedwith_feed_efficiency。

### 4.1 pvalue + condition 的关联查询（极重要）
- 当问题是“与生猪饲养效率相关”并且同时给出 `Pvalue` / `condition` 时，使用 `has_phenotype_association` 关联对象即可。
- 不要额外生成 `?phenotype ont:phenotype_name ?phenotype_name` 或 `FILTER (?phenotype_name IN (...))`，除非问题明确给出某个具体 phenotype 字段值。
- 原因：`has_phenotype_association` 已经表示微生物与表型关联；实际 Neo4j 的 phenotype 名称可能是数据源原始值，不能凭自然语言自行猜测。

正确示例：
```sparql
SELECT DISTINCT ?microbiota_name ?pvalue
WHERE {{
  ?microbiota rdf:type ont:MicrobiotaName .
  ?microbiota ont:microbiota_name ?microbiota_name .
  ?microbiota ont:has_phenotype_association ?association .
  ?association rdf:type ont:PhenotypeAssociation .
  ?association ont:pvalue ?pvalue .
  ?association ont:condition ?condition .
  FILTER (?pvalue >= 0.2)
  FILTER (?pvalue <= 0.21)
  FILTER (?condition = "Fattening, Unmedicated feed formula / Antibiotics and zinc oxide")
}}
```

错误示例：
```sparql
?association ont:associated_with_phenotype ?phenotype .
?phenotype ont:phenotype_name ?phenotype_name .
FILTER (?phenotype_name IN ("FeedEfficiency", "feed efficiency", "生猪饲养效率"))
```

**步骤2：判断主体**
- 查询基因 → gene_symbol第一列
- 查询微生物 → microbiota_name第一列
- 查询通路 → pathway_name第一列
- 查询代谢物 → metabolite_name第一列

**步骤3：选择关系**
- 参考上面映射表

### 5. 类型声明模板
```sparql
?microbiota rdf:type ont:MicrobiotaName .
?microbiota ont:microbiota_name ?microbiota_name .

?gene rdf:type ont:Gene .
?gene ont:gene_symbol ?gene_symbol .

?pathway rdf:type ont:KEGGPathway .
?pathway ont:pathway_name ?pathway_name .

?metabolite rdf:type ont:Metabolite .
?metabolite ont:metabolite_name ?metabolite_name .

?food rdf:type ont:Food .
?food ont:food_name ?food_name .

?drug rdf:type ont:Drug .
?drug ont:drug_name ?drug_name .
```

### 6. KEGG通路处理（重要！）

⚠️ **KEGG通路只用标号，不用完整名称**

**规则**：
- 数据库中pathway_name字段只存储通路标号（如"hsa04060"）
- 如果问题给出完整名称，必须提取标号
- 提取方法：取空格前的部分

**示例**：
```
用户输入："hsa04062 Chemokine signaling pathway"
提取标号："hsa04062"

用户输入："mmu04010 MAPK signaling pathway"
提取标号："mmu04010"

用户输入："hsa01521 EGFR tyrosine kinase inhibitor resistance"
提取标号："hsa01521"
```

**正确的FILTER**：
```sparql
FILTER (?pathway_name IN ("hsa04062", "mmu04010", "hsa01521"))
```

**错误的FILTER**：
```sparql
❌ FILTER (?pathway_name IN ("hsa04062 Chemokine signaling pathway", ...))
```

### 7. 语法限制
- **禁用**：CONTAINS、REGEX等函数
- **必须**：FILTER用于限制条件
- **占位符**：FILTER (?var IN (<<SUBQUERY_X>>))

### 7.5 依赖约束继承（极重要）
- 当当前子查询依赖上游子查询时，必须继承原始问题和上游子查询中的上下文约束。
- 必须优先继承：宿主类型、干预条件、实验条件、pvalue范围、变化方向。
- 宿主类型不是固定写死的值，必须由自然语言判断：
  - 如果原始问题/上游问题描述的是人类、人、人源、人类宿主等语义，`host_type` 取该语义对应的数据库值。
  - 如果原始问题/上游问题描述的是小鼠、鼠、mouse、murine 等语义，`host_type` 取该语义对应的数据库值。
  - 只能根据问题语义和上游SPARQL继承，不能因为样例中出现某个宿主就固定套用该宿主。
- 继承方式：
  1. 通过 `FILTER (?var IN (<<SUBQUERY_X>>))` 继承实体集合；
  2. 同时保留上游约束对应的过滤条件，不得只保留占位符而丢失上下文；
  3. 如果当前查询涉及基因-微生物关系，并且原始问题或上游问题限定了宿主类型，必须加入 `?gene ont:host_type ?host_type .` 和对应 `FILTER`；
  4. 如果当前查询是食物/药物/疾病导致微生物丰度变化，并且原始问题限定了宿主类型，第一步源头查询也必须显式加入对应实体的 `ont:host_type` 过滤。
- 如果问题没有明确要求放宽范围，不允许去掉上述约束。
- `<<SUBQUERY_X>>` 只代表上游返回的实体值，不会自动携带宿主、方向、condition、pvalue等条件。
- 不要凭固定词表猜测约束值；必须从原始问题、当前子问题、依赖子问题描述、依赖SPARQL中抽取约束并传递。

依赖子查询生成前必须自检：
- 原问题/上游是否限定宿主类型？如果是，下游 gene-microbiota 查询必须显式写 `ont:host_type`。
- 当前是否是第一步食物/药物/疾病影响微生物丰度查询？如果原问题限定宿主，第一步也必须显式写 `ont:host_type`。
- 宿主约束必须和自然语言一致：人类问题不能写成小鼠，小鼠问题不能写成人类。
- 当前子问题是否有"增加/促进/减少/抑制"方向？如果是，必须使用具体的 increases/decreases 谓词，不要退化成 regulates。
- 上游是否有 condition/pvalue 等实验条件？如果当前查询仍在同一批实体语境下，不得无故丢失。
- 当前是否是"这些基因/相关基因的代谢通路"或"检查指定通路是否在相关基因通路中"？如果依赖上游基因集合，必须写 `FILTER (?gene_symbol IN (<<SUBQUERY_X>>))`。指定 `?pathway_name` 过滤只能作为额外条件，不能替代上游 gene 约束。

### 7.6 依赖继承典型示例（必须遵守）
上游子查询1问题：在人类宿主中，`soluble corn fiber` 导致丰度上升的微生物
上游关键约束：`host_type = "human"`，`food_name = "soluble corn fiber"`，`Alteration = "increase"`

下游子查询2问题：在人类宿主中，能减少这些微生物数量的基因表达

错误写法（会导致结果爆炸）：
```sparql
SELECT ?gene_symbol ?microbiota_name
WHERE {{
  ?gene ont:gene_symbol ?gene_symbol .
  ?gene ont:decreases_microbiota_abundance ?microbiota .
  ?microbiota ont:microbiota_name ?microbiota_name .
  FILTER (?microbiota_name IN (<<SUBQUERY_1>>))
}}
```

正确写法（必须保留上下文）：
```sparql
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
```
说明：依赖占位符只传“实体集合”，不会自动传宿主/干预条件，必须在当前子查询显式保留。

对称正确示例（增加/促进也必须保留宿主）：
```sparql
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
```
说明："增加/促进这些微生物"必须使用 `ont:increases_microbiota_abundance`，同时继承宿主约束。

小鼠宿主继承示例（值必须随自然语言改变，不要照抄human）：
上游子查询1问题：在小鼠肠道中，某个药物导致丰度上升的微生物
下游子查询2问题：能够促进这些微生物群生长的关键基因
```sparql
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
```
说明：这里使用 `"mouse"` 是因为问题语义是小鼠；如果问题语义是人类，则应使用人类对应值。宿主值必须由问题语义决定。

指定通路检查也必须保留上游基因示例：
上游子查询2问题：这些微生物的调控基因
当前子查询3问题：检查指定代谢通路是否在相关基因的代谢通路中
```sparql
SELECT DISTINCT ?gene_symbol ?pathway_name
WHERE {{
  ?gene rdf:type ont:Gene .
  ?gene ont:gene_symbol ?gene_symbol .
  ?gene ont:participates_in_pathway ?pathway .
  ?pathway rdf:type ont:KEGGPathway .
  ?pathway ont:pathway_name ?pathway_name .
  FILTER (?gene_symbol IN (<<SUBQUERY_2>>))
  FILTER (?pathway_name IN ("hsa04060", "hsa04062"))
}}
```
说明：`?pathway_name` 只是在上游基因的通路中做筛选；如果漏掉 `?gene_symbol IN (<<SUBQUERY_2>>)`，会变成查询全库所有属于这些通路的基因，结果会严重过宽。

源头查询也必须保留宿主示例（小鼠食物干预）：
上游子查询1问题：在某个食物干预下丰度显著上升的小鼠肠道微生物群
```sparql
SELECT DISTINCT ?microbiota_name
WHERE {{
  ?food rdf:type ont:Food .
  ?food ont:food_name ?food_name .
  ?food ont:increases_microbiota_abundance_by_food ?microbiota .
  ?food ont:host_type ?host_type .
  ?microbiota rdf:type ont:MicrobiotaName .
  ?microbiota ont:microbiota_name ?microbiota_name .
  FILTER (?food_name = "根据问题抽取的完整食物名")
  FILTER (?host_type = "mouse")
}}
```
说明：第一步如果漏掉宿主，会把人类和小鼠微生物混在一起，后续 `<<SUBQUERY_1>>` 会过大。

源头查询也必须保留宿主示例（小鼠药物干预）：
```sparql
SELECT DISTINCT ?microbiota_name
WHERE {{
  ?drug rdf:type ont:Drug .
  ?drug ont:drug_name ?drug_name .
  ?drug ont:increases_microbiota_abundance_by_drug ?microbiota .
  ?drug ont:host_type ?host_type .
  ?microbiota rdf:type ont:MicrobiotaName .
  ?microbiota ont:microbiota_name ?microbiota_name .
  FILTER (?drug_name = "根据问题抽取的完整药物名")
  FILTER (?host_type = "mouse")
}}
```

### 8. 前缀
```sparql
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX ont: <http://www.semanticweb.org/ontologies/integrated_gut_microbiota_ontology#>
```

## 输出
只返回SPARQL查询，无其他文字，不含```标记
"""

# ============================================================
# 🔧 SubQueryScheduler - 数据库路由规则（关键修复！）
#
# 修复内容：
# 1. 添加了 {question}, {sparql_query}, {ttl_info} 变量
# 2. 移除硬编码的映射表，让LLM从TTL动态学习
# ============================================================
SubQuerySchedulerRules = """
你是数据库路由专家。根据SPARQL中的谓词（关系）和TTL映射信息选择正确的数据库。

## 输入信息

### 自然语言问题
{question}

### SPARQL查询
```sparql
{sparql_query}
```

### 数据库TTL映射信息
{ttl_info}

## 决策规则

1. **分析SPARQL中使用的谓词（ont:xxx）**
   - 找出WHERE子句中所有 ont:xxx 形式的谓词/关系

2. **查看TTL映射信息**
   - 每个数据库的TTL定义了它包含哪些谓词
   - 找到包含该谓词的数据库

3. **做出选择**
   - 选择包含SPARQL中谓词的数据库

## 输出格式

只输出一个数据库名称，不要有任何解释。
根据TTL信息中显示的可用数据库名称输出。

你的选择："""

# ============================================================
# SPARQLRepair - SPARQL修复规则（保持不变）
# ============================================================
SPARQLRepairRules = """
你是SPARQL修复专家。

输入：
- 原始问题：{natural_language_query}
- 当前SPARQL：{sparql_query}
- 检测问题：{detected_issues}
- 本体：{ontology_content}
- 依赖：{dependencies}

## 修复规则

### 1. 变量修正（最高优先级）
| 错误 | 正确 |
|-----|------|
| ?efficiency | 删除（不存在） |
| ?microbiota | ?microbiota_name |
| ?gene | ?gene_symbol |
| ?pathway | ?pathway_name |
| ?food | ?food_name |
| ?drug | ?drug_name |
| ?metabolite | ?metabolite_name |

### 2. 变量顺序（主体第一列）
| 问题 | 正确顺序 |
|------|---------|
| "哪些基因..." | ?gene_symbol第一列 |
| "哪些微生物..." | ?microbiota_name第一列 |
| "基因的通路" | ?pathway_name第一列 |
| "食物增加哪些微生物" | ?microbiota_name（只返回微生物）|

### 3. 食物/药物查询修正
⚠️ **重要**：食物/药物查询只返回微生物名
```sparql
错误：SELECT ?microbiota_name ?food_name
正确：SELECT ?microbiota_name
```

### 4. 类名修正
| 错误 | 正确 |
|-----|------|
| ont:Microbiota | ont:MicrobiotaName |
| ont:GeneSymbol | ont:Gene |

### 5. 缺少类型声明
必须包含：
```sparql
?gene rdf:type ont:Gene .
?gene ont:gene_symbol ?gene_symbol .
```

### 6. 关系选择
| 情况 | 正确关系 |
|------|---------|
| "相关"无p值 | correlatedwith_feed_efficiency |
| "p<0.05" | has_phenotype_association + pvalue |

### 7. KEGG通路
- 只用标号（"hsa04060"）

### 8. 占位符
- 保留<<SUBQUERY_n>>不变

## 输出
只返回修复后的SPARQL，无解释，不含markdown标记
"""

# ============================================================
# QueryRepair - 通用修复规则（保持不变）
# ============================================================
QueryRepairRules = """
SPARQL修复专家。

输入：
- 原始问题：{natural_language_query}
- SPARQL：{sparql_query}
- 问题：{detected_issues}
- 本体：{ontology_content}

重要前缀：
PREFIX ont: <http://www.semanticweb.org/ontologies/integrated_gut_microbiota_ontology#>

## 快速修复
✗ ?efficiency → 删除
✗ ?microbiota → ✓ ?microbiota_name
✗ ?gene → ✓ ?gene_symbol
✗ ont:Microbiota → ✓ ont:MicrobiotaName

"哪些基因..." → ?gene_symbol第一列
"哪些微生物..." → ?microbiota_name第一列
"食物增加哪些微生物" → 只返回?microbiota_name（不返回food_name）

"相关"无p值 → correlatedwith_feed_efficiency
"p<0.05" → has_phenotype_association + pvalue

## 输出
只返回修复后的SPARQL
"""

# ============================================================
# SemanticConsistency - 语义一致性检查（保持不变）
# ============================================================
QueryCheckerRules = """
语义一致性检查专家。

输入：
- 本体：{ontology_info}
- 自然语言：{natural_language_query}
- SELECT变量：{select_variables}

## 检查要点
1. 自然语言期望返回什么？
2. SELECT是否完全匹配？
3. 是否有多余或缺少的变量？

## SELECT标准
| 问题 | 应返回 |
|------|--------|
| "哪些基因..." | ?gene_symbol ?microbiota_name |
| "微生物是否相关" | ?microbiota_name |
| "微生物相关（带p值）" | ?microbiota_name ?pvalue |
| "基因参与通路" | ?pathway_name ?gene_symbol |
| "食物增加哪些微生物" | ?microbiota_name（只返回微生物）|

## 输出
状态: [CONSISTENT/INCONSISTENT]
分析: [详细分析]
建议: [修改建议]
"""

ResultAggregation_template = """
生物信息学数据分析助手。

任务：
- 子问题：{sub_question}
- 查询：{converted_queries}
- 结果：{query_results}
- 联合汇总表：{merged_table}

## 输出格式

**结果统计**:
- 总记录数：X条（说明联合汇总表和子查询明细的关系）
- 涉及实体：按微生物、基因、代谢通路分别概括

**关键发现**:
- 用专业生物医学语言概括“微生物 → 调控基因 → 代谢通路”的链式发现
- 如果某个上游实体没有下游基因或通路，明确说明“未在当前数据源中检索到下游证据”
- 不要把未被下游支持的微生物说成已经存在完整机制链

**生物学意义**:
- 结合宿主-肠道微生物互作、基因调控、免疫/凋亡/代谢信号通路等角度解释
- 说明这是基于当前数据库证据的关联性发现，不要过度推断因果机制

要求：语言专业、准确、层次清晰；优先引用联合汇总表中的实体；避免冗余和凭空扩展。
"""
