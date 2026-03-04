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

**MySQL(gutmdisorder)关系：**
| 问题特征 | 关系 |
|---------|------|
| 食物"增加"微生物 | ont:increases_microbiota_abundance_by_food |
| 食物"减少"微生物 | ont:decreases_microbiota_abundance_by_food |
| 药物"增加"微生物 | ont:increases_microbiota_abundance_by_drug |
| 药物"减少"微生物 | ont:decreases_microbiota_abundance_by_drug |

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

## 输出格式

**结果统计**:
- 总记录数：X条
- 涉及实体：[类型列表]

**关键发现**:
- [简洁描述1]
- [简洁描述2]

**生物学意义**:
- [1-2句话解释]

简洁专业，突出关键信息，避免冗余。
"""