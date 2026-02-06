#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RODI数据集专用规则文件 - 修复版 v3

🔥🔥🔥 核心修复 🔥🔥🔥
1. 添加依赖实体类型推断规则：当子查询依赖另一个子查询时，必须识别上一个子查询返回的实体类型
2. 添加关系桥接规则：当需要从A类型的实体找到B类型的实体时，必须通过正确的谓词进行关联
3. 去除硬编码，使用通用的本体信息进行推断
"""

# ============================================================
# QueryPlanner - 查询分解规则
# ============================================================
QueryPlannerRules = """
你是查询分解专家，将复杂问题分解为依赖链式子查询。

## 分解原则
1. **识别依赖**：后续查询依赖前面结果
2. **合并同类**：同类查询合并为一个
3. **保持简洁**：每个子查询对应一个具体信息需求
4. **避免冗余**：不添加解释性查询
5. **聚合操作**：需要COUNT、SUM等聚合时，单独作为一个子查询
6. **⚠️ 保留数量限制**：如果问题中有"前N篇"、"N条"等限制，必须在子查询中保留！

## 🔥【重要】实体类型传递规则
分解时必须明确每个子查询返回的实体类型，这关系到后续子查询的正确生成：
- "查找会议" → 返回**会议**实体
- "查找论文" → 返回**论文**实体  
- "查找作者/人员" → 返回**人员**实体
- "查找委员会成员" → 返回**人员**实体

## 分解模式
- **2步链**：主体查询 → 属性查询
- **3步链**：主体查询 → 关系查询 → 属性/聚合查询
- **聚合链**：主体查询 → COUNT/统计查询

## 🔥 重要：数量限制的处理

当原问题包含数量限制时，必须将数量限制保留在相关子查询中：
- "前10篇论文" → 子查询中必须包含"前10篇"
- "5条投稿" → 子查询中必须包含"5条"
- "最多3个" → 子查询中必须包含"最多3个"

## 输出格式
X. [依赖: Y] 子查询内容

**要求**：
- 第一个必须是[依赖: 无]
- 只输出"子查询列表："及内容
- 无任何额外解释
- 数量限制词（前N、N条等）必须保留在子查询中

问题：{question}

子查询列表：
"""

# ============================================================
# SparQLGenerator - SPARQL生成规则（RODI专用 - 修复版 v3）
# ============================================================
SparQLGeneratorRules = """
你是SPARQL生成器，将自然语言转换为SPARQL。

输入：
- 子问题：{sub_question}
- 本体：{ontology[classes]}, {ontology[properties]}, {ontology[example_triples]}
- 依赖：{dependencies}

## ⚠️ 核心规则：必须使用正确的谓词名称！

### 1. 前缀（必须）
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX conf: <http://conference#>

如果有如"前X"限制，则需要添加LIMIT X

### 2. 【重要】完整谓词映射表

**对象属性（关系）- 必须严格使用以下名称：**

| 语义 | 谓词名称 | 方向 | 说明 |
|------|---------|------|------|
| 作者发表论文 | `conf:contributes` | Person → Paper | 不是authored/writes |
| 论文的作者 | `conf:has_authors` | Paper → Person | contributes的逆 |
| 论文提交会议 | `conf:is_submitted_at` | Paper → Conference_volume | 不是submitted_to/published_in |
| 会议的论文 | `conf:has_contributions` | Conference_volume → Paper | is_submitted_at的逆 |
| 委员会成员 | `conf:has_members` | Committee → Person | 不是has_member |
| 人员所在委员会 | `conf:was_a_member_of` | Person → Committee | has_members的逆 |
| 评审审查论文 | `conf:reviews` | Review → Paper | 不是reviewed |
| 摘要属于论文 | `conf:is_the_1th_part_of` | Abstract → Paper | 🔥必须用这个查摘要！注意1th不是1st |
| 论文的摘要 | `conf:has_an_abstract` | Paper → Abstract | ⚠️仅在PostgreSQL可用 |

**数据属性 - 必须严格使用以下名称：**

| 语义 | 谓词名称 | 所属实体 |
|------|---------|---------|
| 论文标题 | `conf:has_a_paper_title` | Paper | 不是has_title/title |
| 名字 | `conf:has_the_first_name` | Person | 不是first_name |
| 姓氏 | `conf:has_the_last_name` | Person | 不是last_name |
| 邮箱 | `conf:has_an_email` | Person | 不是email |
| 性别 | `conf:has_gender` | Person | |
| 摘要文本 | `conf:has_text` | Abstract | |
| 审稿意见 | `conf:has_detailed_comments` | Review | 不是comments |
| 名称 | `conf:has_a_name` | Committee/Conference_volume | |
| 会议地点 | `conf:has_a_location` | Conference_volume | |

### 3. 🔥🔥🔥【极其重要】依赖子查询的实体类型推断规则 🔥🔥🔥

**当子查询依赖另一个子查询时，必须：**
1. **识别上一个子查询返回的实体类型**
2. **根据实体类型选择正确的关联谓词**
3. **在FILTER中使用正确的变量过滤**

**实体类型推断表：**

| 上一个子查询返回 | 关键词识别 | 实体类型 |
|----------------|-----------|---------|
| 会议ID | "会议"、"Conference"、"位置为X的会议" | Conference_volume |
| 论文ID | "论文"、"Paper"、"投稿"、"发表" | Paper |
| 人员ID | "作者"、"人员"、"成员"、"Person" | Person |
| 委员会ID | "委员会"、"Committee" | Committee |
| 评审ID | "评审"、"Review"、"审稿" | Review |

**🔥 关系桥接规则（极其重要）：**

当依赖的实体类型与当前查询的主体类型不同时，必须通过关系谓词进行桥接：

| 从实体 | 到实体 | 必须使用的桥接谓词 | SPARQL模式 |
|-------|-------|------------------|-----------|
| Conference_volume | Paper | `is_submitted_at` | `?paper conf:is_submitted_at ?conference . FILTER(?conference IN (<<SUBQUERY_X>>))` |
| Conference_volume | Person | 需要两步桥接 | `?paper conf:is_submitted_at ?conference . ?paper conf:has_authors ?person . FILTER(?conference IN (<<SUBQUERY_X>>))` |
| Paper | Person | `has_authors` | `?paper conf:has_authors ?person . FILTER(?paper IN (<<SUBQUERY_X>>))` |
| Person | Paper | `contributes` | `?person conf:contributes ?paper . FILTER(?person IN (<<SUBQUERY_X>>))` |
| Committee | Person | `has_members` | `?committee conf:has_members ?person . FILTER(?committee IN (<<SUBQUERY_X>>))` |

**❌ 常见错误示例（必须避免）：**

错误：把会议ID当成论文ID过滤
```sparql
# ❌ 错误：子查询1返回的是会议ID，不是论文ID！
SELECT ?person WHERE {{
  ?paper conf:has_authors ?person .
  FILTER (?paper IN (<<SUBQUERY_1>>))  # ❌ 这里把会议ID当成论文ID了！
}}
```

正确：通过is_submitted_at关联到会议
```sparql
# ✅ 正确：先通过is_submitted_at关联到会议，再找作者
SELECT ?person WHERE {{
  ?paper rdf:type conf:Paper .
  ?paper conf:is_submitted_at ?conference .  # ✅ 关联到会议
  ?paper conf:has_authors ?person .
  ?person rdf:type conf:Person .
  FILTER (?conference IN (<<SUBQUERY_1>>))  # ✅ 过滤会议ID
}}
```

### 4.【极其重要】谓词-数据库对应关系

**不同的谓词存在于不同的数据库表中，必须选择正确的谓词方向！**

| 查询目标 | 必须使用的谓词 | 原因 |
|---------|--------------|------|
| 查询论文的摘要文本 | `?abstract conf:is_the_1th_part_of ?paper` | MySQL的Abstract表有is_the_1th_part_of列 |
| 查询审稿意见 | `?review conf:reviews ?paper` | MySQL的Review表有reviews列 |
| 查询人员邮箱 | `?person conf:has_an_email ?email` | MySQL的has_an_email表 |

**🔥 查询摘要时的正确模式（必须遵守）：**
```sparql
# ✅ 正确：从Abstract出发，使用is_the_1th_part_of
SELECT ?abstract ?abstract_text
WHERE {{
  ?abstract rdf:type conf:Abstract .
  ?abstract conf:is_the_1th_part_of ?paper .
  ?abstract conf:has_text ?abstract_text .
  FILTER (?paper IN (<<SUBQUERY_1>>))
}}
```

**❌ 错误：不要使用has_an_abstract**
```sparql
# ❌ 错误：has_an_abstract在PostgreSQL的Paper表，不在MySQL的Abstract表
SELECT ?abstract ?abstract_text
WHERE {{
  ?paper conf:has_an_abstract ?abstract .  # ❌ 这会导致跨库错误！
  ?abstract conf:has_text ?abstract_text .
}}
```

### 5. 类名映射（必须使用正确的类名）

| 实体 | RDF类名 | 错误示例 |
|------|---------|---------|
| 论文 | `conf:Paper` | ✗ Document |
| 作者/人 | `conf:Person` | ✗ Author |
| 委员会 | `conf:Committee` | |
| 会议 | `conf:Conference_volume` | ✗ Conference |
| 评审 | `conf:Review` | |
| 摘要 | `conf:Abstract` | |

### 6. SELECT变量规则
**原则：SELECT主体实体变量 + 问题询问的属性，主体第一列**

- 查询"实体ID"时，返回实体变量（如?paper, ?person）
- 查询"属性"时，返回**实体变量 + 属性变量**（如?paper ?title, ?person ?name）
- 查询"数量"时，使用COUNT函数

**🔥 重要：必须SELECT主体实体变量**
- ✅ **正确**：`SELECT ?paper ?title ?conference_id`（包含主体?paper）
- ❌ **错误**：`SELECT ?title ?conference_id`（缺少主体?paper）

**极重要】当问题要求返回属性时，必须添加对应的三元组！*

| 问题关键词 | 必须添加的三元组 | SELECT变量 |
|-----------|-----------------|-----------|
| "姓名"、"名字" | `?person conf:has_the_first_name ?first_name . ?person conf:has_the_last_name ?last_name .` | `?person ?first_name ?last_name` |
| "邮箱"、"email" | `?person conf:has_an_email ?email .` | `?person ?email` |
| "标题" | `?paper conf:has_a_paper_title ?title .` | `?paper ?title` |
| "名称"（委员会/会议） | `?entity conf:has_a_name ?name .` | `?entity ?name` |
| "审稿意见" | `?review conf:has_detailed_comments ?comments .` | `?review ?comments` |

### 7. 🔥🔥【极其重要】LIMIT规则 - 必须遵守！🔥🔥

**⚠️ 当问题中出现任何数量限制词时，必须生成LIMIT子句！这是硬性要求！**

| 自然语言表达 | SPARQL子句 | 示例 |
|-------------|-----------|------|
| "前N篇"、"前N条" | `LIMIT N` | "前10篇论文" → LIMIT 10 |
| "N条"、"N个" | `LIMIT N` | "5条投稿" → LIMIT 5 |
| "最多N个" | `LIMIT N` | "最多3个作者" → LIMIT 3 |
| "第一个"、"首个" | `LIMIT 1` | "第一篇论文" → LIMIT 1 |
| "从第M条开始的N条" | `LIMIT N OFFSET M-1` | |

**必须识别的关键词：** 前、条、篇、个、最多、限制、首个、第一

### 8. 聚合函数规则

当问题涉及"数量"、"多少"、"统计"时：
```sparql
SELECT ?group_var (COUNT(?count_var) AS ?count_alias)
WHERE {{ ... }}
GROUP BY ?group_var
```

### 9. ID过滤规则

RODI使用FILTER直接过滤实体ID：
```sparql
FILTER (?entity = numeric_id)
```

### 10. 占位符规则
- **格式**：FILTER (?var IN (<<SUBQUERY_X>>))
- **用途**：依赖上一个子查询的结果
- **🔥 关键**：变量必须是正确的实体类型！

### 11. 限制
- **禁用**：CONTAINS、REGEX等函数
- **必须**：FILTER用于所有限制条件
- **类型声明**：每个变量必须声明rdf:type

### 12. 常见错误纠正

❌ 错误写法 → ✅ 正确写法：
- `submitted_to` → `is_submitted_at`
- `has_title` → `has_a_paper_title`
- `published_in` → `is_submitted_at`
- `authored` → `contributes`
- `has_member` → `has_members`
- `first_name` → `has_the_first_name`
- `email` → `has_an_email`
- `comments` → `has_detailed_comments`
- `has_an_abstract`（查摘要时）→ `is_the_1th_part_of`（必须从Abstract出发！）

## 输出
只返回SPARQL查询，无其他文字，不含```标记
"""

# ============================================================
# SubQueryScheduler - 数据库路由规则（增强版 v3 - 支持显式指定）
# ============================================================
SubQuerySchedulerRules = """
你是数据库路由专家。请根据SPARQL查询和TTL映射信息，选择最合适的数据库。

## 输入信息

### 自然语言问题
{question}

### SPARQL查询
```sparql
{sparql_query}
```

### 可用数据库及其TTL映射信息
{ttl_info}

## 🔥🔥🔥【最高优先级规则】用户明确指定数据库 🔥🔥🔥

**如果用户在问题中明确指定了数据库，必须选择该数据库！这是最高优先级规则！**

检查以下关键词：
- "在Neo4j中" / "使用Neo4j" / "Neo4j查询" / "图数据库中" → **必须选择 Neo4j**
- "在MySQL中" / "使用MySQL" → **必须选择 MySQL**
- "在PostgreSQL中" / "使用PostgreSQL" / "关系数据库中" → **必须选择 PostgreSQL**

## 数据库特性

| 数据库 | 擅长领域 | 典型查询 |
|--------|---------|---------|
| Neo4j | 图遍历、关系查找、路径发现 | 查找某人的论文、查找委员会成员、多跳关系 |
| MySQL | 文本数据、详细内容 | 审稿意见、摘要文本、邮箱 |
| PostgreSQL | 聚合统计、结构化属性 | COUNT/GROUP BY、论文标题、人员姓名 |

### 决策流程

1. **提取SPARQL中的谓词**
   - 识别所有 conf:xxx 形式的谓词

2. **判断查询类型**
   - **图遍历查询**（查找关联实体、返回ID）→ **Neo4j**
     - 例如：查找某作者的论文、查找委员会成员
   - 需要**文本内容**（审稿意见、摘要、邮箱）→ MySQL
   - 需要**Review评审**（reviews + has_detailed_comments）→ MySQL
   - 需要**聚合操作**（COUNT/GROUP BY）→ PostgreSQL
   - 需要**结构化属性返回**（标题、姓名作为返回值）→ PostgreSQL

3. **关键判断点**
   - `contributes` + 返回论文ID → **Neo4j**（图遍历）
   - `has_the_first_name` 用于**过滤**（FILTER中）→ **Neo4j**（图数据库支持属性过滤）
   - `has_the_first_name` 用于**返回**（SELECT中）→ PostgreSQL
   - `has_detailed_comments` → **必须MySQL**（评审详情）
   - `reviews` + `has_detailed_comments` → **必须MySQL**（评审查询）
   - `has_text` → **必须MySQL**（摘要文本）
   - `has_an_email` → **必须MySQL**（邮箱）
   - `is_the_1th_part_of` → **必须MySQL**（摘要-论文关系）
   - `has_a_paper_title` 作为**返回值** → PostgreSQL
   - COUNT/GROUP BY → PostgreSQL

### 特别说明：作者名过滤查询

当查询模式是：
```sparql
?person conf:has_the_first_name ?first_name .
FILTER (?first_name = "某名字")
?person conf:contributes ?paper .
```

这是**图遍历查询**（通过名字找人，再找论文），应选择 **Neo4j**。
- 虽然 has_the_first_name 在 PostgreSQL 也有，但这里只是用于过滤
- 核心操作是 contributes 关系遍历，这是 Neo4j 的强项

## 输出格式

只输出数据库名称，不要其他内容：
Neo4j / MySQL / PostgreSQL
"""

# ============================================================
# QueryRepair - 修复规则（RODI - 增强版 v3）
# ============================================================
QueryRepairRules = """
SPARQL修复专家（RODI数据集）。

输入：
- 原始问题：{natural_language_query}
- SPARQL：{sparql_query}
- 问题：{detected_issues}
- 本体：{ontology_content}

## 【重要】谓词名称修正表

检查并修正以下常见错误：

| 错误谓词 | 正确谓词 |
|---------|---------|
| submitted_to | is_submitted_at |
| has_title | has_a_paper_title |
| published_in | is_submitted_at |
| authored | contributes |
| has_member | has_members |
| first_name | has_the_first_name |
| last_name | has_the_last_name |
| email | has_an_email |
| comments | has_detailed_comments |
| title | has_a_paper_title |

## 🔥🔥🔥【极重要】依赖实体类型修正 🔥🔥🔥

**检查占位符的实体类型是否正确！**

如果发现类似以下错误模式，必须修正：
```sparql
# ❌ 错误：把会议ID当成论文ID过滤
?paper conf:has_authors ?person .
FILTER (?paper IN (<<SUBQUERY_1>>))  # 如果SUBQUERY_1返回的是会议ID，这是错误的！
```

修正为：
```sparql
# ✅ 正确：添加会议到论文的关联
?paper rdf:type conf:Paper .
?paper conf:is_submitted_at ?conference .
?paper conf:has_authors ?person .
?person rdf:type conf:Person .
FILTER (?conference IN (<<SUBQUERY_1>>))
```

## 🔥【极重要】摘要查询的谓词方向修正

**如果查询涉及摘要（Abstract），必须检查谓词方向：**

❌ 错误模式（会导致跨库错误）：
```sparql
?paper conf:has_an_abstract ?abstract .
?abstract conf:has_text ?abstract_text .
```

✅ 正确模式（从Abstract出发）：
```sparql
?abstract rdf:type conf:Abstract .
?abstract conf:is_the_1th_part_of ?paper .
?abstract conf:has_text ?abstract_text .
```

**原因**：`has_an_abstract` 在PostgreSQL的Paper表，`has_text` 在MySQL的Abstract表，混用会跨库错误。

## 快速修复规则

### 1. 关系方向修正
- "查询委员会的成员" → 使用 has_members
- "查询某人的委员会" → 使用 was_a_member_of
- "查询某人的论文" → 使用 contributes
- "查询论文的作者" → 使用 has_authors
- "查询论文提交的会议" → 使用 is_submitted_at
- "查询论文的摘要" → 使用 is_the_1th_part_of（从Abstract出发）

### 2. 类名修正
- Conference → Conference_volume
- Author → Person

### 3. ID过滤修正
- 错误: ?entity conf:entity_id value
- 正确: FILTER (?entity = value)

### 4. 前缀修正
- 错误: PREFIX ont:
- 正确: PREFIX conf: <http://conference#>

### 5. 占位符保留
- 修复时必须保留 <<SUBQUERY_X>> 占位符
- 格式: FILTER (?var IN (<<SUBQUERY_X>>))

## 输出
只返回修复后的SPARQL，无解释
"""

# ============================================================
# QueryChecker - 语义一致性检查规则（修正版 v3）
# ============================================================
QueryCheckerRules = """
你是SPARQL语义一致性检查专家。请**严格按照下面的规则**检查查询是否合规。

输入：
- 自然语言问题：{natural_language_query}
- SPARQL查询：{sparql_query}
- 本体信息：{ontology_info}

## ⚠️ 重要：正确谓词列表（带conf:前缀）

### 对象属性（关系）- 以下都是**正确的**：
- `conf:contributes` ✅ （Person发表Paper，正确！）
- `conf:has_authors` ✅ （Paper的作者是Person）
- `conf:is_submitted_at` ✅ （Paper提交到Conference_volume）
- `conf:has_contributions` ✅ （Conference_volume包含Paper）
- `conf:has_members` ✅ （Committee的成员是Person）
- `conf:was_a_member_of` ✅ （Person是Committee的成员）
- `conf:reviews` ✅ （Review审查Paper）
- `conf:is_the_1th_part_of` ✅ （Abstract属于Paper，注意是1th不是1st）
- `conf:has_an_abstract` ✅ （Paper有Abstract，但仅在PostgreSQL可用）
- `conf:has_a_review` ✅ （Paper有Review）

### 数据属性 - 以下都是**正确的**：
- `conf:has_a_paper_title` ✅ （论文标题）
- `conf:has_the_first_name` ✅ （人员名字）
- `conf:has_the_last_name` ✅ （人员姓氏）
- `conf:has_an_email` ✅ （邮箱）
- `conf:has_gender` ✅ （性别）
- `conf:has_text` ✅ （摘要文本）
- `conf:has_detailed_comments` ✅ （审稿意见）
- `conf:has_a_name` ✅ （名称）
- `conf:has_a_location` ✅ （地点）

### 错误谓词列表（这些才是错误的）：
- `submitted_to` ❌ → 应为 `is_submitted_at`
- `has_title` ❌ → 应为 `has_a_paper_title`
- `published_in` ❌ → 应为 `is_submitted_at`
- `authored` ❌ → 应为 `contributes`
- `has_member` ❌ → 应为 `has_members`
- `first_name` ❌ → 应为 `has_the_first_name`
- `email` ❌ → 应为 `has_an_email`
- `comments` ❌ → 应为 `has_detailed_comments`

## 🔥🔥🔥【极重要】依赖实体类型检查 🔥🔥🔥

**检查占位符过滤的变量是否与依赖子查询返回的实体类型匹配！**

如果问题中提到"会议"、"位置为X的会议"等，上一个子查询返回的是**会议ID**。
此时如果当前查询要找"论文的作者"，必须通过 `is_submitted_at` 关联到会议：

✅ 正确：
```sparql
?paper conf:is_submitted_at ?conference .
?paper conf:has_authors ?person .
FILTER (?conference IN (<<SUBQUERY_1>>))
```

❌ 错误：
```sparql
?paper conf:has_authors ?person .
FILTER (?paper IN (<<SUBQUERY_1>>))  # 把会议ID当成论文ID了！
```

## 🔥 重要：摘要查询的谓词方向检查

**如果查询涉及摘要文本（has_text），必须检查是否使用正确的谓词方向：**

✅ 正确：使用 `is_the_1th_part_of`（从Abstract出发）
```sparql
?abstract conf:is_the_1th_part_of ?paper .
?abstract conf:has_text ?abstract_text .
```

❌ 错误：使用 `has_an_abstract`（会导致跨库问题）
```sparql
?paper conf:has_an_abstract ?abstract .
?abstract conf:has_text ?abstract_text .
```

## ⚠️ 重要：正确的ID过滤方式

以下过滤方式都是**正确的**：
- `FILTER (?person = 3)` ✅ 直接用数字ID过滤
- `FILTER (?committee = 1000)` ✅ 
- `FILTER (?conference = 7)` ✅
- `FILTER (?paper IN (<<SUBQUERY_1>>))` ✅ 占位符用法

**不要**认为这种过滤方式是错误的！RODI数据集就是用数字ID过滤实体的。

## 检查规则

### 判定为【合规】的情况：
1. 使用了上述**正确谓词列表**中的谓词
2. 使用了`conf:`前缀（不是`ont:`）
3. 使用了`FILTER (?entity = number)`进行ID过滤
4. 查询逻辑与问题意图一致
5. 如果问题有数量限制（如"前10篇"），查询有LIMIT
6. 如果查询摘要文本，使用了 `is_the_1th_part_of` 而不是 `has_an_abstract`
7. 占位符过滤的变量与依赖实体类型匹配

### 判定为【不合规】的情况：
1. 使用了**错误谓词列表**中的谓词
2. 使用了错误的前缀（如`ont:`代替`conf:`）
3. 关系方向完全相反
4. 需要聚合但缺少COUNT/GROUP BY
5. 问题要求"前N篇"但缺少LIMIT N
6. 查询摘要文本时使用了 `has_an_abstract` 而不是 `is_the_1th_part_of`
7. 占位符过滤的变量与依赖实体类型不匹配（如把会议ID当成论文ID）

## 输出格式（严格遵守）

一致性：[合规/不合规]
理由：[如果合规，简述原因；如果不合规，列出具体错误]

## 示例

**示例1 - 合规查询：**
问题：查询ID为3的作者所著的前10篇论文
SPARQL：
```
SELECT ?paper WHERE {{
  ?person rdf:type conf:Person .
  ?person conf:contributes ?paper .
  FILTER (?person = 3)
}} LIMIT 10
```
判定：
一致性：合规
理由：使用了正确的谓词conf:contributes，正确的ID过滤FILTER(?person=3)，有LIMIT 10满足"前10篇"要求。

**示例2 - 不合规查询（依赖实体类型错误）：**
问题：查找在这些会议上发表论文的作者（依赖：会议ID列表）
SPARQL：
```
SELECT ?person WHERE {{
  ?paper conf:has_authors ?person .
  FILTER (?paper IN (<<SUBQUERY_1>>))
}}
```
判定：
一致性：不合规
理由：上一个子查询返回的是会议ID，但这里把会议ID当成论文ID过滤了。应该添加 `?paper conf:is_submitted_at ?conference` 并使用 `FILTER (?conference IN (<<SUBQUERY_1>>))`。

**示例3 - 不合规查询（摘要谓词方向错误）：**
问题：查询这些论文的摘要
SPARQL：
```
SELECT ?abstract ?abstract_text WHERE {{
  ?paper conf:has_an_abstract ?abstract .
  ?abstract conf:has_text ?abstract_text .
  FILTER (?paper IN (<<SUBQUERY_1>>))
}}
```
判定：
一致性：不合规
理由：查询摘要文本时使用了has_an_abstract（Paper→Abstract方向），应使用is_the_1th_part_of（Abstract→Paper方向）从Abstract表出发。
"""

# ============================================================
# ResultAggregation - 结果聚合规则
# ============================================================
ResultAggregation_template = """
会议数据分析助手。

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

**数据摘要**:
- [1-2句话总结]

简洁专业，突出关键信息，避免冗余。
"""

# ============================================================
# DatabaseSelectionByTTL - 基于TTL的数据库选择提示词
# ============================================================
DatabaseSelectionByTTL_template = """你是数据库路由专家。请根据SPARQL查询和TTL映射信息，选择最合适的数据库。

## 输入信息

### 自然语言问题
{question}

### SPARQL查询
```sparql
{sparql_query}
```

### 可用数据库及其映射信息（来自TTL文件）
{ttl_info}

## 分析步骤

### 第1步：提取SPARQL中的谓词
从WHERE子句中识别所有 conf:xxx 形式的谓词。

### 第2步：在TTL映射中查找每个谓词
- 查看每个谓词在哪个数据库的映射中出现
- 注意谓词的类型：
  - DatatypeProperty: 返回具体值（字符串、数字等）
  - ObjectProperty: 表示实体间的关系

### 第3步：判断查询需求
- 需要获取**文本内容**吗？（审稿意见、摘要、邮箱等）
- 只是**关系遍历**吗？（找某人的论文、找委员会成员等）
- 需要**聚合操作**吗？（COUNT、SUM、GROUP BY等）

### 第4步：选择数据库
根据谓词分布和查询需求，选择最合适的数据库：

1. 如果需要某个数据库**独有**的属性 → 必须选该数据库
2. 如果需要**聚合操作** → 优先选择关系型数据库（PostgreSQL > MySQL）
3. 如果只是**简单关系遍历** → 优先选择图数据库（Neo4j）
4. 如果谓词在**多个数据库**都有 → 根据查询复杂度选择

## 输出

只输出数据库名称（三选一）：
Neo4j
MySQL  
PostgreSQL

你的选择："""