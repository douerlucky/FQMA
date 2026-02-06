#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RODI数据集专用示例列表 - 修复版 v3

🔥🔥🔥 核心修复 🔥🔥🔥
1. 添加依赖实体类型推断的示例
2. 添加关系桥接的示例（从会议找作者需要先找论文）
3. 修复摘要查询的谓词方向问题
4. 添加更多边界情况的示例

规则定义请参考 prompts_rules.py
"""

# ============================================================
# QueryPlanner 示例 - 查询分解
# ============================================================
QueryPlannerSamplesList = [
    # 示例1：【重要】带数量限制的查询分解 - 必须保留LIMIT
    """
## 示例1：
**问题**：查询ID为3的作者所著的前10篇论文，这些论文的摘要和标题

**分解**：
1. [依赖: 无] 查询ID为3的作者所著的前10篇论文
2. [依赖: 1] 查询这些论文的摘要
3. [依赖: 1] 查询这些论文的标题

**⚠️ 注意**：子查询1保留了"前10篇"，这样SPARQL生成时会添加LIMIT 10
""",

    # 示例2：查询会议的投稿论文及审稿意见
    """
## 示例2：
**问题**：查找会议ID=7的前5篇投稿论文，以及这些论文的审稿意见

**分解**：
1. [依赖: 无] 查询提交到会议ID=7的前5篇论文
2. [依赖: 1] 查询这些论文的审稿意见

**⚠️ 注意**：子查询1保留了"前5篇"
""",

    # 示例3：【🔥重要】从会议找作者 - 需要桥接
    """
## 示例3：
**问题**：查找位置为Benguela举办的会议上发表论文的作者，获取姓名

**分解**：
1. [依赖: 无] 查找位置为Benguela举办的会议
2. [依赖: 1] 查找在这些会议上发表论文的作者
3. [依赖: 2] 获取这些作者的姓名

**🔥 关键说明**：
- 子查询1返回的是**会议ID**
- 子查询2必须通过 会议→论文→作者 的路径查找
- 子查询2的SPARQL需要先用is_submitted_at关联到会议，再找作者
""",

    # 示例4：查询论文的作者数量（聚合查询）
    """
## 示例4：
**问题**：查找ID为3的作者的所有论文，查询每篇论文的作者数量

**分解**：
1. [依赖: 无] 查询ID为3的作者发表的所有论文
2. [依赖: 1] 统计每篇论文的作者数量
""",

    # 示例5：查询委员会的成员数量（聚合查询）
    """
## 示例5：
**问题**：查询ID为1000的委员会的成员数量

**分解**：
1. [依赖: 无] 统计ID为1000的委员会的成员数量
""",

    # 示例6：复杂查询 - 会议论文的完整信息
    """
## 示例6：
**问题**：查找会议ID=7的所有投稿论文，这些论文的审稿意见是什么，每篇论文的标题和对应的会议是什么

**分解**：
1. [依赖: 无] 查询提交到会议ID=7的所有论文
2. [依赖: 1] 查询这些论文的审稿意见
3. [依赖: 1] 查询这些论文的标题和对应的会议信息
"""
]

# ============================================================
# SparQLGenerator 示例 - SPARQL生成
# ============================================================
SparQLGeneratorSamplesList = [
    """
## 示例1：查询作者的前N篇论文（带LIMIT）
**子问题**：查询ID为3的作者所著的前10篇论文

**SPARQL**：
```sparql
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX conf: <http://conference#>

SELECT ?paper
WHERE {{
  ?person rdf:type conf:Person .
  ?person conf:contributes ?paper .
  ?paper rdf:type conf:Paper .
  FILTER (?person = 3)
}}
LIMIT 10
```

**说明**：
- ⚠️ 问题中"前10篇论文" → 必须添加 LIMIT 10
- 使用 conf:contributes 表示"作者发表论文"关系（正确谓词！）
- 方向：Person -> Paper
- 数字ID过滤：FILTER (?person = 3)（正确用法！）
- LIMIT子句**必须**放在查询最后
""",

    # 示例2：按位置查询会议
    """
## 示例2：按位置查询会议
**子问题**：查找位置为Benguela举办的会议

**SPARQL**：
```sparql
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX conf: <http://conference#>

SELECT ?conference
WHERE {{
  ?conference rdf:type conf:Conference_volume .
  ?conference conf:has_a_location ?location .
  FILTER (?location = "Benguela")
}}
```

**说明**：
- 使用 conf:has_a_location 查询会议地点
- 字符串过滤：FILTER (?location = "Benguela")
- 返回会议ID（?conference）
- 🔥 注意：这个查询返回的是**会议ID**，后续子查询需要据此判断实体类型
""",

    # 示例3：🔥🔥🔥【极其重要】从会议找作者 - 关系桥接示例
    """
## 示例3：🔥【极其重要】从会议找作者（关系桥接）
**子问题**：查找在这些会议上发表论文的作者
**依赖**：<<SUBQUERY_1>> 是**会议**实体列表（不是论文！）

**SPARQL**：
```sparql
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX conf: <http://conference#>

SELECT ?person
WHERE {{
  ?paper rdf:type conf:Paper .
  ?paper conf:is_submitted_at ?conference .
  ?paper conf:has_authors ?person .
  ?person rdf:type conf:Person .
  FILTER (?conference IN (<<SUBQUERY_1>>))
}}
```

**🔥🔥🔥 极其重要的说明 🔥🔥🔥**：
- ⚠️ 依赖的子查询1返回的是**会议ID**，不是论文ID！
- ⚠️ 必须通过 `conf:is_submitted_at` 先关联到会议
- ⚠️ FILTER必须过滤 `?conference`（会议变量），不是 `?paper`！
- ⚠️ 路径：Paper --is_submitted_at--> Conference_volume

**❌ 常见错误（必须避免）：**
```sparql
# ❌ 错误：把会议ID当成论文ID来过滤！
SELECT ?person WHERE {{
  ?paper conf:has_authors ?person .
  FILTER (?paper IN (<<SUBQUERY_1>>))  # ❌ 这是错误的！SUBQUERY_1返回的是会议ID！
}}
```

**正确的关系桥接流程**：
1. 识别上一个子查询返回的实体类型：会议（Conference_volume）
2. 确定当前查询的目标实体类型：作者（Person）
3. 找到关系路径：Conference_volume <-[is_submitted_at]- Paper -[has_authors]-> Person
4. 构建SPARQL：先关联Paper到Conference，再从Paper找Person
""",

    # 示例4：【重要】带LIMIT的会议论文查询
    """
## 示例4：查询会议的前N篇投稿论文（带LIMIT）
**子问题**：查询提交到会议ID=7的前5篇论文

**SPARQL**：
```sparql
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX conf: <http://conference#>

SELECT ?paper
WHERE {{
  ?paper rdf:type conf:Paper .
  ?paper conf:is_submitted_at ?conference .
  ?conference rdf:type conf:Conference_volume .
  FILTER (?conference = 7)
}}
LIMIT 5
```

**说明**：
- ⚠️ 问题中"前5篇论文" → 必须添加 LIMIT 5
- 使用 conf:is_submitted_at 表示"论文提交到会议"（正确谓词！）
- 方向：Paper -> Conference_volume
- 会议类名是 Conference_volume，不是 Conference
- 识别关键词：前N、N条、N篇、N个 → 必须添加LIMIT
""",

    # 示例5：查询论文的标题和会议ID（数据属性）
    """
## 示例5：查询论文的标题和会议ID
**子问题**：查询这些论文的标题和提交的会议ID
**依赖**：<<SUBQUERY_1>> 是论文实体列表

**SPARQL**：
```sparql
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX conf: <http://conference#>

SELECT ?paper ?title ?conference_id
WHERE {{
  ?paper rdf:type conf:Paper .
  ?paper conf:has_a_paper_title ?title .
  ?paper conf:is_submitted_at ?conference_id .
  FILTER (?paper IN (<<SUBQUERY_1>>))
}}
```

**说明**：
- ⚠️ 使用 conf:has_a_paper_title 查询标题，不是 has_title
- ⚠️ 使用 conf:is_submitted_at 查询提交的会议ID
- ⚠️ SELECT必须包含主体变量 ?paper
- 占位符在FILTER中：FILTER (?paper IN (<<SUBQUERY_1>>))
- 🔥 查询会议ID时，直接用 ?conference_id 变量，不需要额外的类型声明
""",

    # 示例6：【重要】查询审稿意见（MySQL关系）
    """
## 示例6：查询论文的审稿意见
**子问题**：查询这些论文的审稿意见
**依赖**：<<SUBQUERY_1>> 是论文实体列表

**SPARQL**：
```sparql
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX conf: <http://conference#>

SELECT ?paper ?review ?detailed_comments
WHERE {{
  ?review rdf:type conf:Review .
  ?review conf:reviews ?paper .
  ?review conf:has_detailed_comments ?detailed_comments .
  FILTER (?paper IN (<<SUBQUERY_1>>))
}}
```

**说明**：
- conf:reviews 是 Review -> Paper 的关系
- ⚠️ 使用 conf:has_detailed_comments 获取审稿意见内容
- ⚠️ SELECT必须包含主体变量 ?review
- 这个查询应该路由到 MySQL（因为 has_detailed_comments 在 MySQL）
""",

    # 示例7：统计每篇论文的作者数量（聚合查询）
    """
## 示例7：统计每篇论文的作者数量
**子问题**：统计每篇论文的作者数量
**依赖**：<<SUBQUERY_1>> 是论文实体列表

**SPARQL**：
```sparql
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX conf: <http://conference#>

SELECT ?paper (COUNT(?person) AS ?author_count)
WHERE {{
  ?paper rdf:type conf:Paper .
  ?paper conf:has_authors ?person .
  ?person rdf:type conf:Person .
  FILTER (?paper IN (<<SUBQUERY_1>>))
}}
GROUP BY ?paper
```

**说明**：
- 使用 COUNT 函数统计作者数量
- ⚠️ 使用 conf:has_authors 表示"论文的作者"（Paper -> Person）
- 必须有 GROUP BY 子句
- 分组变量 ?paper 同时出现在 SELECT 和 GROUP BY 中
""",

    # 示例8：🔥【重要】查询委员会成员及其姓名（按名称过滤+返回属性）
    """
## 示例8：查询委员会成员及其姓名（🔥重要示例）
**子问题**：查找'YSWC 2015 Program Committee'委员会的所有成员，返回他们的ID和姓名

**SPARQL**：
```sparql
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX conf: <http://conference#>

SELECT ?person ?first_name ?last_name
WHERE {{
  ?committee rdf:type conf:Committee .
  ?committee conf:has_a_name "YSWC 2015 Program Committee" .
  ?committee conf:has_members ?person .
  ?person rdf:type conf:Person .
  ?person conf:has_the_first_name ?first_name .
  ?person conf:has_the_last_name ?last_name .
}}
```

**🔥 关键说明**：
- 按名称过滤委员会：`?committee conf:has_a_name "委员会名称" .`
- ⚠️ 问题要求"返回姓名" → **必须**添加姓名三元组：
  - `?person conf:has_the_first_name ?first_name .`
  - `?person conf:has_the_last_name ?last_name .`
- ⚠️ SELECT必须包含所有要返回的变量：`?person ?first_name ?last_name`
- 使用 conf:has_members 关系（Committee -> Person）
""",

    # 示例9：查询人员的姓名和邮箱
    """
## 示例9：查询人员的姓名和邮箱
**子问题**：查询这些人员的姓名和邮箱
**依赖**：<<SUBQUERY_1>> 是人员实体列表

**SPARQL**：
```sparql
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX conf: <http://conference#>

SELECT ?person ?first_name ?last_name ?email
WHERE {{
  ?person rdf:type conf:Person .
  ?person conf:has_the_first_name ?first_name .
  ?person conf:has_the_last_name ?last_name .
  ?person conf:has_an_email ?email .
  FILTER (?person IN (<<SUBQUERY_1>>))
}}
```

**说明**：
- ⚠️ 使用 conf:has_the_first_name 和 conf:has_the_last_name 获取姓名
- ⚠️ 使用 conf:has_an_email 获取邮箱（在MySQL中）
- ⚠️ SELECT必须包含主体变量 ?person
""",

    # 示例10：【🔥极其重要】查询摘要文本 - 必须使用 is_the_1th_part_of
    """
## 示例10：查询论文的摘要文本（🔥必须使用正确的谓词方向）
**子问题**：查询这些论文的摘要
**依赖**：<<SUBQUERY_1>> 是论文实体列表

**SPARQL**：
```sparql
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX conf: <http://conference#>

SELECT ?abstract ?abstract_text
WHERE {{
  ?abstract rdf:type conf:Abstract .
  ?abstract conf:is_the_1th_part_of ?paper .
  ?abstract conf:has_text ?abstract_text .
  FILTER (?paper IN (<<SUBQUERY_1>>))
}}
```

**🔥🔥🔥 极其重要的说明 🔥🔥🔥**：
- ⚠️ **必须**使用 conf:is_the_1th_part_of 表示摘要属于论文（Abstract -> Paper方向）
- ⚠️ **绝对禁止**使用 conf:has_an_abstract（Paper -> Abstract方向），因为：
  - has_an_abstract 列在 PostgreSQL 的 Paper 表中
  - has_text 列在 MySQL 的 Abstract 表中
  - 混用会导致跨库错误！
- ⚠️ 使用 conf:has_text 获取摘要文本
- ⚠️ SELECT必须包含主体变量 ?abstract
- 注意是 1th 不是 1st（这是数据库的实际列名）

**❌ 错误示例（会导致跨库错误）：**
```sparql
# ❌ 错误：不要使用 has_an_abstract！
SELECT ?abstract ?abstract_text
WHERE {{
  ?paper conf:has_an_abstract ?abstract .  # ❌ 这个谓词在PostgreSQL
  ?abstract conf:has_text ?abstract_text .  # ❌ 这个谓词在MySQL，跨库了！
}}
```
""",

    # 示例11：获取作者姓名（从人员ID列表）
    """
## 示例11：获取作者姓名
**子问题**：获取这些作者的姓名
**依赖**：<<SUBQUERY_2>> 是人员实体列表

**SPARQL**：
```sparql
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX conf: <http://conference#>

SELECT ?person ?first_name ?last_name
WHERE {{
  ?person rdf:type conf:Person .
  ?person conf:has_the_first_name ?first_name .
  ?person conf:has_the_last_name ?last_name .
  FILTER (?person IN (<<SUBQUERY_2>>))
}}
```

**说明**：
- 依赖的是人员ID列表，直接过滤 ?person
- 使用正确的姓名谓词
- 返回姓名作为属性值
""",

    # 示例12：【重要】依赖实体类型判断示例
    """
## 示例12：🔥 依赖实体类型判断示例

**场景**：当子查询有依赖时，如何判断依赖的实体类型

**判断方法**：
1. 查看依赖子查询的自然语言描述
2. 识别关键词：
   - "会议"、"Conference"、"位置为X" → Conference_volume
   - "论文"、"Paper"、"投稿" → Paper
   - "作者"、"人员"、"成员" → Person
   - "委员会"、"Committee" → Committee

**示例场景**：
- 子查询1："查找位置为Benguela的会议" → 返回 Conference_volume
- 子查询2："查找这些会议上的论文作者" → 需要桥接！

**子查询2的正确SPARQL**：
```sparql
SELECT ?person WHERE {{
  ?paper rdf:type conf:Paper .
  ?paper conf:is_submitted_at ?conference .  # 桥接到会议
  ?paper conf:has_authors ?person .
  ?person rdf:type conf:Person .
  FILTER (?conference IN (<<SUBQUERY_1>>))  # 过滤会议ID
}}
```

**❌ 错误的SPARQL（实体类型混淆）**：
```sparql
SELECT ?person WHERE {{
  ?paper conf:has_authors ?person .
  FILTER (?paper IN (<<SUBQUERY_1>>))  # ❌ 错误！SUBQUERY_1返回的是会议ID，不是论文ID！
}}
```
"""
]

# ============================================================
# SPARQLRepair 示例 - SPARQL语法修复
# ============================================================
SPARQLRepairSampleList = [
    # 示例1：【重要】谓词名称修复
    """
## 修复示例1：谓词名称错误
**问题**：查询会议ID=7的投稿论文

**错误**：
```sparql
SELECT ?paper
WHERE {{
  ?paper conf:submitted_to ?conference .
  FILTER (?conference = 7)
}}
```

**问题**：使用了错误的谓词名称 submitted_to

**修复后**：
```sparql
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX conf: <http://conference#>

SELECT ?paper
WHERE {{
  ?paper rdf:type conf:Paper .
  ?paper conf:is_submitted_at ?conference .
  ?conference rdf:type conf:Conference_volume .
  FILTER (?conference = 7)
}}
```

**关键**：submitted_to → is_submitted_at
""",

    # 示例2：🔥🔥🔥【极重要】依赖实体类型错误修复
    """
## 修复示例2：🔥🔥🔥 依赖实体类型错误（极其重要）
**问题**：查找在这些会议上发表论文的作者
**依赖**：<<SUBQUERY_1>> 返回的是**会议ID**

**错误**：
```sparql
SELECT ?person
WHERE {{
  ?paper conf:has_authors ?person .
  FILTER (?paper IN (<<SUBQUERY_1>>))
}}
```

**问题**：把会议ID当成了论文ID来过滤！

**修复后**：
```sparql
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX conf: <http://conference#>

SELECT ?person
WHERE {{
  ?paper rdf:type conf:Paper .
  ?paper conf:is_submitted_at ?conference .
  ?paper conf:has_authors ?person .
  ?person rdf:type conf:Person .
  FILTER (?conference IN (<<SUBQUERY_1>>))
}}
```

**关键修复**：
1. 添加 `?paper conf:is_submitted_at ?conference` 建立论文到会议的关联
2. 将 FILTER 从 `?paper` 改为 `?conference`
3. 这样才能正确过滤会议ID
""",

    # 示例3：🔥【极重要】摘要查询谓词方向修复
    """
## 修复示例3：摘要查询谓词方向错误（🔥必须修复）
**问题**：查询论文的摘要

**错误**：
```sparql
SELECT ?abstract ?abstract_text
WHERE {{
  ?paper conf:has_an_abstract ?abstract .
  ?abstract conf:has_text ?abstract_text .
  FILTER (?paper IN (<<SUBQUERY_1>>))
}}
```

**问题**：使用了错误的谓词方向 has_an_abstract（会导致跨库错误）

**修复后**：
```sparql
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX conf: <http://conference#>

SELECT ?abstract ?abstract_text
WHERE {{
  ?abstract rdf:type conf:Abstract .
  ?abstract conf:is_the_1th_part_of ?paper .
  ?abstract conf:has_text ?abstract_text .
  FILTER (?paper IN (<<SUBQUERY_1>>))
}}
```

**关键**：has_an_abstract → is_the_1th_part_of（必须从Abstract出发！）
**原因**：
- has_an_abstract 在 PostgreSQL 的 Paper 表
- has_text 在 MySQL 的 Abstract 表
- 必须使用 is_the_1th_part_of 才能在同一数据库（MySQL）完成查询
""",

    # 示例4：缺少聚合函数修复
    """
## 修复示例4：缺少COUNT函数
**问题**：统计每篇论文的作者数量

**错误**：
```sparql
SELECT ?paper ?person
WHERE {{
  ?paper conf:has_authors ?person .
}}
```

**问题**：需要统计数量但没有使用COUNT

**修复后**：
```sparql
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX conf: <http://conference#>

SELECT ?paper (COUNT(?person) AS ?author_count)
WHERE {{
  ?paper rdf:type conf:Paper .
  ?paper conf:has_authors ?person .
  ?person rdf:type conf:Person .
}}
GROUP BY ?paper
```
""",

    # 示例5：错误的前缀修复
    """
## 修复示例5：使用了错误的前缀
**错误**：
```sparql
PREFIX ont: <http://www.semanticweb.org/ontologies/...>
SELECT ?paper
WHERE {{
  ?person ont:contributes ?paper .
}}
```

**问题**：RODI使用conf:前缀，不是ont:

**修复后**：
```sparql
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX conf: <http://conference#>

SELECT ?paper
WHERE {{
  ?person rdf:type conf:Person .
  ?person conf:contributes ?paper .
  ?paper rdf:type conf:Paper .
}}
```
""",

    # 示例6：关系方向错误修复
    """
## 修复示例6：关系方向不正确
**问题**：查询委员会的成员

**错误**：
```sparql
SELECT ?person
WHERE {{
  ?committee conf:was_a_member_of ?person .
  FILTER (?committee = 1000)
}}
```

**问题**：was_a_member_of是Person->Committee，方向反了

**修复后**：
```sparql
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX conf: <http://conference#>

SELECT ?person
WHERE {{
  ?committee rdf:type conf:Committee .
  ?committee conf:has_members ?person .
  ?person rdf:type conf:Person .
  FILTER (?committee = 1000)
}}
```
"""
]