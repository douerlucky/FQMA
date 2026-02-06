QueryPlannerSamplesList = ["""
示例1（单一查询链）：
问题：哪些基因与肥胖相关，这些基因编码的蛋白质有什么功能，以及它们参与哪些信号通路？
子查询列表：
1. [依赖: 无] 哪些基因与肥胖相关？
2. [依赖: 1] 这些与肥胖相关的基因编码的蛋白质有什么功能？
3. [依赖: 2] 这些蛋白质参与哪些信号通路？
""","""
示例2（合并同类查询）：
问题：哪些基因的表达能够增加Lactobacillus、Bacteroides、Ruminococcus的数量？
子查询列表：
1. [依赖: 无] 哪些基因的表达能够增加Lactobacillus、Bacteroides、Ruminococcus的数量？
""",
"""示例3（多实体合并查询）：
问题：IL-6、TNF-α、IL-1β这些炎症因子参与哪些信号通路？
子查询列表：
1. [依赖: 无] IL-6、TNF-α、IL-1β这些炎症因子参与哪些信号通路？
""",
"""
示例4（复杂查询链）：
问题：哪些微生物与炎症性肠病相关，这些微生物产生什么代谢物，这些代谢物如何影响宿主免疫？
子查询列表：
1. [依赖: 无] 哪些微生物与炎症性肠病相关？
2. [依赖: 1] 这些与炎症性肠病相关的微生物产生什么代谢物？
3. [依赖: 2] 这些代谢物如何影响宿主免疫？
""","""
示例5（合并条件相同的查询）：
问题：哪些微生物与生猪的饲养效率实验关联显著性p<0.02，哪些微生物与鸡的饲养效率实验关联显著性p<0.02？
子查询列表：
1. [依赖: 无] 哪些微生物与生猪和鸡的饲养效率实验关联显著性p<0.02？

- 如果出现代谢通路如"hsa04060 Cytokine-cytokine receptor interaction",只需要代谢通路代号即可,即"hsa04060"

""","""
示例6（食物对微生物影响查询）：
问题：ketogenic diet、high fat diet这些食物如何影响Bacteroides、Lactobacillus的丰度？
子查询列表：
1. [依赖: 无] ketogenic diet、high fat diet这些食物如何影响Bacteroides、Lactobacillus的丰度？
""","""
示例7（药物效应查询链）：
问题：哪些药物能够增加Bifidobacterium的丰度，这些微生物产生哪些代谢物，相关基因的表达如何调节？
子查询列表：
1. [依赖: 无] 哪些药物能够增加Bifidobacterium的丰度？
2. [依赖: 1] Bifidobacterium产生哪些代谢物？
3. [依赖: 2] 哪些基因的表达能够调节这些代谢物的产生？
""","""
示例8（基因调控微生物合并查询）：
问题：MAPK14、IL-6、TNF-α这些基因如何调控肠道微生物的丰度？
子查询列表：
1. [依赖: 无] MAPK14、IL-6、TNF-α这些基因如何调控肠道微生物的丰度？
""","""
示例9（疾病关联查询链）：
问题：哪些微生物与糖尿病相关，这些微生物受哪些基因调控，这些基因参与什么代谢通路？
子查询列表：
1. [依赖: 无] 哪些微生物与糖尿病相关？
2. [依赖: 1] 这些与糖尿病相关的微生物受哪些基因调控？
3. [依赖: 2] 这些调控基因参与什么代谢通路？
""","""
示例10（饲料效率提升查询）：
问题：哪些微生物能够提高饲料效率，影响这些微生物的食物和药物分别有哪些？
子查询列表：
1. [依赖: 无] 哪些微生物能够提高饲料效率？
2. [依赖: 1] 哪些食物能够增加这些微生物的丰度？
3. [依赖: 1] 哪些药物能够增加这些微生物的丰度？
"""]

SparQLGeneratorSamplesList = [
    """
    示例1：基因增加微生物丰度（基因在第一列）
问题：哪些基因的表达能够增加这些微生物的数量？
SPARQL：
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX ont: <http://www.semanticweb.org/ontologies/integrated_gut_microbiota_ontology#>

SELECT ?gene_symbol ?microbiota_name
WHERE {{
  ?gene rdf:type ont:Gene .
  ?gene ont:gene_symbol ?gene_symbol .
  ?gene ont:increases_microbiota_abundance ?microbiota .
  ?microbiota rdf:type ont:MicrobiotaName .
  ?microbiota ont:microbiota_name ?microbiota_name .
  FILTER (?microbiota_name IN (<<SUBQUERY_1>>))
}}
    """,
    """
    示例2：微生物和饲养效率相关（只返回微生物名）
问题：Dorea，Eubacterium，Bacteroides中哪些微生物群对生猪饲养效率是显著相关的？
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
注意，不用pvalue！
    """,
    """
    示例3：带p值和条件的表型关联查询
问题：哪些微生物群关联于生猪饲养效率，在"Fattening, Unmedicated feed formula / Antibiotics and zinc oxide"条件下的Pvalue在0.2与0.21之间？
SPARQL：
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX ont: <http://www.semanticweb.org/ontologies/integrated_gut_microbiota_ontology#>

SELECT DISTINCT ?microbiota_name ?pvalue
WHERE {{
  ?microbiota rdf:type ont:MicrobiotaName .
  ?microbiota ont:microbiota_name ?microbiota_name .
  ?microbiota ont:has_phenotype_association ?association .
  ?association rdf:type ont:PhenotypeAssociation .
  ?association ont:associated_with_phenotype ?phenotype .
  ?phenotype rdf:type ont:Phenotype .
  ?association ont:pvalue ?pvalue .
  ?association ont:condition ?condition .
  FILTER (?pvalue >= 0.2)
  FILTER (?pvalue <= 0.21)
  FILTER (?condition = "Fattening, Unmedicated feed formula / Antibiotics and zinc oxide")
}}
    """,
    """
    示例4：KEGG通路查询（只用通路标号）
问题：hsa04060 Cytokine-cytokine receptor interaction，mmu04010 MAPK signaling pathway中哪些在这些基因的代谢通路里？
SPARQL：
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX ont: <http://www.semanticweb.org/ontologies/integrated_gut_microbiota_ontology#>

SELECT DISTINCT ?pathway_name
WHERE {{
  ?gene rdf:type ont:Gene .
  ?gene ont:gene_symbol ?gene_symbol .
  ?gene ont:participates_in_pathway ?pathway .
  ?pathway rdf:type ont:KEGGPathway .
  ?pathway ont:pathway_name ?pathway_name .
  FILTER (?gene_symbol IN (<<SUBQUERY_2>>))
  FILTER (?pathway_name IN ("hsa04060", "mmu04010"))
}}
    """,
    """
    示例5：食物增加微生物丰度查询
问题：哪些食物能够增加Lactobacillus、Bifidobacterium的丰度？
SPARQL：
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX ont: <http://www.semanticweb.org/ontologies/integrated_gut_microbiota_ontology#>

SELECT ?food_name ?microbiota_name
WHERE {{
  ?food rdf:type ont:Food .
  ?food ont:food_name ?food_name .
  ?food ont:increases_microbiota_abundance_by_food ?microbiota .
  ?microbiota rdf:type ont:MicrobiotaName .
  ?microbiota ont:microbiota_name ?microbiota_name .
  FILTER (?microbiota_name IN ("Lactobacillus", "Bifidobacterium"))
}}
    """,
    """
    示例6：药物减少微生物丰度查询
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
    """,
    """
    示例7：微生物产生代谢物查询
问题：Lactobacillus、Bifidobacterium产生哪些代谢物？
SPARQL：
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX ont: <http://www.semanticweb.org/ontologies/integrated_gut_microbiota_ontology#>

SELECT  ?metabolite_name ?microbiota_name
WHERE {{
  ?microbiota rdf:type ont:MicrobiotaName .
  ?microbiota ont:microbiota_name ?microbiota_name .
  ?microbiota ont:generates_metabolite ?metabolite .
  ?metabolite rdf:type ont:Metabolite .
  ?metabolite ont:metabolite_name ?metabolite_name .
  FILTER (?microbiota_name IN ("Lactobacillus", "Bifidobacterium"))
}}
    """,
    """
    示例8：基因调控微生物关系查询（通用调控）
问题：哪些基因调控Bacteroides、Lactobacillus的丰度？
SPARQL：
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX ont: <http://www.semanticweb.org/ontologies/integrated_gut_microbiota_ontology#>

SELECT ?gene_symbol ?microbiota_name
WHERE {{
  ?gene rdf:type ont:Gene .
  ?gene ont:gene_symbol ?gene_symbol .
  ?gene ont:regulates_microbiota_abundance ?microbiota .
  ?microbiota rdf:type ont:MicrobiotaName .
  ?microbiota ont:microbiota_name ?microbiota_name .
  FILTER (?microbiota_name IN ("Bacteroides", "Lactobacillus"))
}}
    """,
    """
    示例9：微生物影响基因表达查询
问题：Clostridium、Lactobacillus如何影响基因表达？
SPARQL：
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX ont: <http://www.semanticweb.org/ontologies/integrated_gut_microbiota_ontology#>

SELECT ?microbiota_name ?gene_symbol
WHERE {{
  ?microbiota rdf:type ont:MicrobiotaName .
  ?microbiota ont:microbiota_name ?microbiota_name .
  ?microbiota ont:changes_gene_expression_by_microbiota ?gene .
  ?gene rdf:type ont:Gene .
  ?gene ont:gene_symbol ?gene_symbol .
  FILTER (?microbiota_name IN ("Clostridium", "Lactobacillus"))
}}
    """,
    """
    示例10：微生物提高饲料效率查询
问题：哪些微生物能够提高饲料效率？
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
    """
]

SPARQLRepairSampleList=[
    """
    ### 3. 特殊查询处理：
- **微生物与饲养效率相关（无p值要求）**：
  * SELECT只需要 ?microbiota_name
  * 不要查询任何efficiency相关变量
  * 正确示例：
    ```
    SELECT DISTINCT ?microbiota_name
    WHERE {{
      ?microbiota rdf:type ont:MicrobiotaName .
      ?microbiota ont:microbiota_name ?microbiota_name .
      ?microbiota ont:correlatedwith_feed_efficiency ?efficiency .
      ?efficiency rdf:type ont:FeedEfficiency .
      FILTER (?microbiota_name IN ("Dorea", "Eubacterium"))
    }}
    ```""",
    """
    - **带p值要求的查询**（才需要Association模式）：
  * 正确示例：
    ```
    SELECT DISTINCT ?microbiota_name ?pvalue
    WHERE {{
      ?microbiota rdf:type ont:MicrobiotaName .
      ?microbiota ont:microbiota_name ?microbiota_name .
      ?microbiota ont:has_phenotype_association ?association .
      ?association rdf:type ont:PhenotypeAssociation .
      ?association ont:associated_with_phenotype ?phenotype .
      ?phenotype rdf:type ont:Phenotype .
      ?association ont:pvalue ?pvalue .
      ?association ont:condition ?condition .
      FILTER (?pvalue >= 0.2)
      FILTER (?pvalue <= 0.21)
    }}
    ```
    """,
    """
    - **食物影响微生物丰度查询**：
  * 正确示例：
    ```
    SELECT ?food_name ?microbiota_name
    WHERE {{
      ?food rdf:type ont:Food .
      ?food ont:food_name ?food_name .
      ?food ont:increases_microbiota_abundance_by_food ?microbiota .
      ?microbiota rdf:type ont:MicrobiotaName .
      ?microbiota ont:microbiota_name ?microbiota_name .
      FILTER (?microbiota_name IN ("Lactobacillus", "Bifidobacterium"))
    }}
    ```
    """,
    """
    - **药物影响微生物丰度查询**：
  * 正确示例：
    ```
    SELECT ?drug_name ?microbiota_name
    WHERE {{
      ?drug rdf:type ont:Drug .
      ?drug ont:drug_name ?drug_name .
      ?drug ont:decreases_microbiota_abundance_by_drug ?microbiota .
      ?microbiota rdf:type ont:MicrobiotaName .
      ?microbiota ont:microbiota_name ?microbiota_name .
      FILTER (?microbiota_name IN ("Clostridium", "Bacteroides"))
    }}
    ```
    """,
    """
    - **微生物产生代谢物查询**：
  * 正确示例：
    ```
    SELECT ?microbiota_name ?metabolite_name
    WHERE {{
      ?microbiota rdf:type ont:MicrobiotaName .
      ?microbiota ont:microbiota_name ?microbiota_name .
      ?microbiota ont:generates_metabolite ?metabolite .
      ?metabolite rdf:type ont:Metabolite .
      ?metabolite ont:metabolite_name ?metabolite_name .
      FILTER (?microbiota_name IN ("Lactobacillus", "Bifidobacterium"))
    }}
    ```
    """,
    """
    - **基因调控微生物（减少丰度）查询**：
  * 正确示例：
    ```
    SELECT ?gene_symbol ?microbiota_name
    WHERE {{
      ?gene rdf:type ont:Gene .
      ?gene ont:gene_symbol ?gene_symbol .
      ?gene ont:decreases_microbiota_abundance ?microbiota .
      ?microbiota rdf:type ont:MicrobiotaName .
      ?microbiota ont:microbiota_name ?microbiota_name .
      FILTER (?microbiota_name IN ("Clostridium", "Bacteroides"))
    }}
    ```
    """,
    """
    - **微生物影响基因表达查询**：
  * 正确示例：
    ```
    SELECT ?microbiota_name ?gene_symbol
    WHERE {{
      ?microbiota rdf:type ont:MicrobiotaName .
      ?microbiota ont:microbiota_name ?microbiota_name .
      ?microbiota ont:changes_gene_expression_by_microbiota ?gene .
      ?gene rdf:type ont:Gene .
      ?gene ont:gene_symbol ?gene_symbol .
      FILTER (?microbiota_name IN ("Clostridium", "Lactobacillus"))
    }}
    ```
    """,
    """
    - **基因通用调控微生物查询**：
  * 正确示例：
    ```
    SELECT ?gene_symbol ?microbiota_name
    WHERE {{
      ?gene rdf:type ont:Gene .
      ?gene ont:gene_symbol ?gene_symbol .
      ?gene ont:regulates_microbiota_abundance ?microbiota .
      ?microbiota rdf:type ont:MicrobiotaName .
      ?microbiota ont:microbiota_name ?microbiota_name .
      FILTER (?microbiota_name IN ("Bacteroides", "Lactobacillus"))
    }}
    ```
    """,
    """
    - **微生物提高饲料效率查询**：
  * 正确示例：
    ```
    SELECT DISTINCT ?microbiota_name
    WHERE {{
      ?microbiota rdf:type ont:MicrobiotaName .
      ?microbiota ont:microbiota_name ?microbiota_name .
      ?microbiota ont:increases_feed_efficiency ?efficiency .
      ?efficiency rdf:type ont:FeedEfficiency .
    }}
    ```
    """,
    """
    - **疾病影响微生物丰度查询**：
  * 正确示例：
    ```
    SELECT ?disorder_name ?microbiota_name
    WHERE {{
      ?disorder rdf:type ont:Disorder .
      ?disorder ont:disorder_name ?disorder_name .
      ?disorder ont:changes_microbiota_abundance_by_disorder ?microbiota .
      ?microbiota rdf:type ont:MicrobiotaName .
      ?microbiota ont:microbiota_name ?microbiota_name .
      FILTER (?disorder_name IN ("diabetes", "obesity"))
    }}
    ```
    """
]

QueryRepairSampleList=["""
## 正确的查询模式示例：

### 查找微生物（只返回微生物名）：
```sparql
SELECT ?microbiota_name WHERE {{
  ?microbiota rdf:type ont:MicrobiotaName .
  ?microbiota ont:microbiota_name ?microbiota_name .
}}
```
""",
"""
### 查找基因（基因在第一列）：
```sparql
SELECT ?gene_symbol ?microbiota_name WHERE {{
  ?gene rdf:type ont:Gene .
  ?gene ont:gene_symbol ?gene_symbol .
  ?gene ont:increases_microbiota_abundance ?microbiota .
  ?microbiota rdf:type ont:MicrobiotaName .
  ?microbiota ont:microbiota_name ?microbiota_name .
}}
```
""",
"""
### 微生物与饲料效率关系（不要效率变量）：
```sparql
SELECT ?microbiota_name WHERE {{
  ?microbiota rdf:type ont:MicrobiotaName .
  ?microbiota ont:microbiota_name ?microbiota_name .
  ?microbiota ont:correlatedwith_feed_efficiency ?feed_efficiency .
  ?feed_efficiency rdf:type ont:FeedEfficiency .
}}
```""",
                       """
                       ### KEGG通路查询（只用通路标号）：
```sparql
SELECT ?pathway_name WHERE {{
  ?pathway rdf:type ont:KEGGPathway .
  ?pathway ont:pathway_name ?pathway_name .
  FILTER (?pathway_name IN ("hsa04060", "mmu04010"))
}}
```""",
                       """
                       ### 微生物与表型的显著关联（带p值）：
```sparql
SELECT ?microbiota_name ?pvalue WHERE {{
  ?microbiota ont:has_phenotype_association ?association .
  ?association ont:pvalue ?pvalue .
  FILTER (?pvalue < 0.05)
}}
```""",
                       """
                       ### 食物影响微生物丰度：
```sparql
SELECT ?food_name ?microbiota_name WHERE {{
  ?food rdf:type ont:Food .
  ?food ont:food_name ?food_name .
  ?food ont:increases_microbiota_abundance_by_food ?microbiota .
  ?microbiota rdf:type ont:MicrobiotaName .
  ?microbiota ont:microbiota_name ?microbiota_name .
}}
```""",
                       """
                       ### 药物影响微生物丰度：
```sparql
SELECT ?drug_name ?microbiota_name WHERE {{
  ?drug rdf:type ont:Drug .
  ?drug ont:drug_name ?drug_name .
  ?drug ont:decreases_microbiota_abundance_by_drug ?microbiota .
  ?microbiota rdf:type ont:MicrobiotaName .
  ?microbiota ont:microbiota_name ?microbiota_name .
}}
```""",
                       """
                       ### 微生物产生代谢物：
```sparql
SELECT ?microbiota_name ?metabolite_name WHERE {{
  ?microbiota rdf:type ont:MicrobiotaName .
  ?microbiota ont:microbiota_name ?microbiota_name .
  ?microbiota ont:generates_metabolite ?metabolite .
  ?metabolite rdf:type ont:Metabolite .
  ?metabolite ont:metabolite_name ?metabolite_name .
}}
```""",
                       """
                       ### 微生物影响基因表达：
```sparql
SELECT ?microbiota_name ?gene_symbol WHERE {{
  ?microbiota rdf:type ont:MicrobiotaName .
  ?microbiota ont:microbiota_name ?microbiota_name .
  ?microbiota ont:changes_gene_expression_by_microbiota ?gene .
  ?gene rdf:type ont:Gene .
  ?gene ont:gene_symbol ?gene_symbol .
}}
```""",
                       """
                       ### 疾病影响微生物：
```sparql
SELECT ?disorder_name ?microbiota_name WHERE {{
  ?disorder rdf:type ont:Disorder .
  ?disorder ont:disorder_name ?disorder_name .
  ?disorder ont:changes_microbiota_abundance_by_disorder ?microbiota .
  ?microbiota rdf:type ont:MicrobiotaName .
  ?microbiota ont:microbiota_name ?microbiota_name .
}}
```"""

]