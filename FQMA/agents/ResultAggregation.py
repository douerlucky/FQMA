import re
import csv
import io
import json
from langchain_core.prompts import PromptTemplate
from typing import List, Dict, Any, Tuple
import config
import importlib
import samples_exp.prompt_grad

class ResultAggregation:
    def __init__(self, llm):
        self.llm = llm
        # 🔥 修复：每次__init__动态加载，不用模块级缓存变量
        try:
            prompts_module = importlib.import_module(f"samples_exp.{config.CURRENT_DATASET}.prompts_rules")
            _,_,_,_,_,cur_prompt = samples_exp.prompt_grad.get_templates()
            template = cur_prompt
        except (ImportError, AttributeError) as e:
            print(f"⚠️ 无法导入ResultAggregation_template: {e}")
            template = None
        self.aggregation_prompt = PromptTemplate(
            input_variables=["sub_question", "converted_queries", "query_results", "merged_table"],
            template=template
        )
        self.context_prompt = PromptTemplate(
            input_variables=["question"],
            template="""你是肠道微生物联邦查询系统中的表格上下文字段抽取器。
请从用户自然语言问题中抽取适合补充到“联合汇总表”的全局上下文字段。

要求：
1. 只抽取问题中明确出现或可以直接归纳出的全局查询条件，不要抽取查询结果实体。
2. 字段名使用简短中文，例如：宿主、疾病、饮食、药物、实验条件、Pvalue范围、微生物丰度变化、微生物调控方向。
3. 如果问题提到“人类宿主/小鼠宿主”，宿主值分别写为“人类宿主/小鼠宿主”。
4. 如果问题提到疾病、饮食、药物、实验条件，请放入对应字段；保留英文专有名词和括号中文解释。
5. “丰度显著上升/下降”抽取为“微生物丰度变化”，值要带主语，例如“肠道微生物群显著上升”。
6. “促进/抑制/减少/增加这些微生物群”抽取为“微生物调控方向”，例如“宿主基因促进微生物群生长”“宿主基因抑制微生物群生长”“宿主基因减少微生物群数量”。
7. 只返回 JSON 对象，不要 Markdown，不要解释。

示例：
问题：在人类宿主中，在药物Vitamin A（维他命A）干预下丰度显著上升的肠道微生物群，分析能够抑制这些微生物群生长的关键基因，并进一步阐明这些基因参与的主要代谢通路。
返回：{{"宿主":"人类宿主","药物":"Vitamin A（维他命A）","微生物丰度变化":"肠道微生物群显著上升","微生物调控方向":"宿主基因抑制微生物群生长"}}

问题：{question}
返回："""
        )

    def extract_return_fields(self, query_list: List[str], results: Dict[int, List[Any]] = None) -> Dict[
        int, List[str]]:
        result = {}
        for idx, query in enumerate(query_list, 1):
            fields = []
            query = query.strip()

            if "RETURN" in query.upper():
                fields = self._extract_neo4j_fields(query)
            elif "SELECT" in query.upper():
                fields = self._extract_sql_fields(query)

            # 用实际结果校正列数
            if results and idx in results:
                actual_data = results[idx]
                if actual_data:
                    first_row = actual_data[0]
                    actual_col_count = len(first_row) if isinstance(first_row, (list, tuple)) else 1
                    # 字段数不够时补充
                    while len(fields) < actual_col_count:
                        fields.append(f"column_{len(fields) + 1}")
                    # 字段数过多时截断
                    fields = fields[:actual_col_count]

            if not fields:
                fields = ["column_1", "column_2"]

            result[idx] = fields
            print(f"查询 {idx} 提取的字段: {fields}")

        return result

    def _extract_neo4j_fields(self, query: str) -> List[str]:
        """
        提取Neo4j查询的返回字段
        """
        fields = []

        return_pattern = r'RETURN\s+(.*?)(?:$|\s+ORDER|\s+LIMIT)'
        return_match = re.search(return_pattern, query, re.IGNORECASE | re.DOTALL)
        if return_match:
            return_content = return_match.group(1).strip()
            items = [item.strip() for item in return_content.split(',')]
            for item in items:
                alias_match = re.search(r'\s+as\s+([`"\w]+)$', item, re.IGNORECASE)
                if alias_match:
                    fields.append(alias_match.group(1).strip('`"'))
                elif '.' in item:
                    fields.append(item.split('.')[-1].strip('`"'))
                elif item:
                    fields.append(item.strip('`"'))

        # 如果没有找到 as 别名，尝试提取属性名
        if not fields:
            # 匹配 RETURN node.property 的模式
            prop_pattern = r'RETURN\s+[\w\.]+\.(\w+)'
            prop_matches = re.findall(prop_pattern, query, re.IGNORECASE)
            fields.extend(prop_matches)

        # 如果还是没有，尝试简单的 RETURN 模式
        return fields

    def _extract_sql_fields(self, query: str) -> List[str]:
        """
        提取SQL查询的字段名（改进版）
        """
        fields = []

        # 改进的SELECT字段提取正则表达式
        # 匹配 SELECT [DISTINCT] ... FROM
        select_pattern = r'SELECT\s+(?:DISTINCT\s+)?(.*?)\s+FROM'
        select_match = re.search(select_pattern, query, re.IGNORECASE | re.DOTALL)

        if select_match:
            select_content = select_match.group(1).strip()
            print(f"提取的SELECT内容: {select_content}")

            # 分割字段（考虑逗号分隔）
            field_items = [item.strip() for item in select_content.split(',')]

            for item in field_items:
                item = item.strip()
                if not item:
                    continue

                # 处理 AS 别名
                if ' as ' in item.lower():
                    # 提取 AS 后面的别名
                    alias = item.lower().split(' as ')[-1].strip()
                    fields.append(alias)
                elif '.' in item:
                    # 提取表前缀后的字段名（如 hecrbm.gene_symbol -> gene_symbol）
                    field_name = item.split('.')[-1].strip()
                    fields.append(field_name)
                else:
                    # 直接使用字段名
                    fields.append(item)

        return fields

    def table_generate(self, queries: List[str], results: Dict[int, List[Any]]) -> str:
        detected_attr = self.extract_return_fields(queries, results)  # 传入results
        tables = ""
        for key, field_names in detected_attr.items():
            if not field_names:
                continue
            headers = " | ".join(field_names)
            separator = " | ".join(["---"] * len(field_names))
            result_data = results.get(key, [])
            rows = ""
            for row_data in result_data:
                if isinstance(row_data, (list, tuple)):
                    row_values = list(row_data[:len(field_names)])
                    while len(row_values) < len(field_names):
                        row_values.append("")
                    row_str = " | ".join(map(str, row_values))
                else:
                    row_str = str(row_data)
                rows += f"| {row_str} |\n"  # ← 关键修复
            markdown_table = f"### 查询 {key} 的结果\n\n| {headers} |\n| {separator} |\n{rows}\n"
            tables += markdown_table
        return tables

    def merged_table_generate(
        self,
        sub_question: str,
        queries: List[str],
        results: Dict[int, List[Any]],
    ) -> Tuple[str, str]:
        """生成跨子查询联合汇总表，并同步返回CSV。"""
        detected_attr = self.extract_return_fields(queries, results)
        row_maps_by_query = self._rows_to_dicts(detected_attr, results)
        merged_rows = self._merge_query_rows(row_maps_by_query)

        if not merged_rows:
            return "", ""

        context_fields = self.extract_context_fields(sub_question)
        if context_fields:
            merged_rows = [self._with_context_fields(row, context_fields) for row in merged_rows]

        display_rows = [self._to_display_row(row) for row in merged_rows]
        display_rows = self._filter_display_rows_for_summary(display_rows)
        headers = self._ordered_headers(display_rows)
        markdown = self._to_markdown_table(headers, display_rows)
        csv_text = self._to_csv(headers, display_rows)
        return markdown, csv_text

    def extract_context_fields(self, question: str) -> Dict[str, str]:
        """从用户问题中抽取适合补充到联合汇总表的全局上下文字段。"""
        context_fields = {}
        try:
            prompt = self.context_prompt.format(question=question)
            response = self.llm.invoke(prompt)
            raw_text = getattr(response, "content", str(response)).strip()
            parsed = self._parse_context_json(raw_text)
            if isinstance(parsed, dict):
                context_fields = self._sanitize_context_fields(parsed)
        except Exception as e:
            print(f"⚠️ LLM上下文字段抽取失败，使用规则兜底: {e}")

        fallback_fields = self._rule_extract_context_fields(question)
        for key, value in fallback_fields.items():
            context_fields.setdefault(key, value)

        print(f"联合汇总表上下文字段: {context_fields}")
        return context_fields

    def _parse_context_json(self, raw_text: str) -> Dict[str, Any]:
        text = raw_text.strip()
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if match:
            text = match.group(0)
        return json.loads(text)

    def _sanitize_context_fields(self, fields: Dict[str, Any]) -> Dict[str, str]:
        sanitized = {}
        for key, value in fields.items():
            clean_key = str(key).strip()
            clean_value = str(value).strip()
            if not clean_key or not clean_value or clean_value.lower() in {"null", "none", "无", "未知"}:
                continue
            clean_key = self._canonical_context_header(clean_key)
            clean_value = self._canonical_context_value(clean_key, clean_value)
            if clean_key in {"microbiota_name", "gene_symbol", "pathway", "pathway_name", "metabolite_name"}:
                continue
            sanitized[clean_key] = clean_value
        return sanitized

    def _canonical_context_header(self, header: str) -> str:
        mapping = {
            "丰度变化": "微生物丰度变化",
            "生物群变化": "微生物调控方向",
            "微生物群变化": "微生物调控方向",
            "调控方向": "微生物调控方向",
            "基因调控方向": "微生物调控方向",
        }
        return mapping.get(header, header)

    def _canonical_context_value(self, header: str, value: str) -> str:
        if header == "微生物丰度变化":
            if "下降" in value or "降低" in value or "减少" in value:
                return "肠道微生物群显著下降"
            if "上升" in value or "升高" in value or "增加" in value:
                return "肠道微生物群显著上升"
        if header == "微生物调控方向":
            if "抑制" in value or "减少" in value:
                return "宿主基因抑制微生物群生长"
            if "促进" in value or "增加" in value:
                return "宿主基因促进微生物群生长"
            if "调控" in value:
                return "宿主基因调控微生物群生长"
        return value

    def _rule_extract_context_fields(self, question: str) -> Dict[str, str]:
        fields = {}

        if re.search(r"人类宿主|人类|human", question, re.IGNORECASE):
            fields["宿主"] = "人类宿主"
        elif re.search(r"小鼠宿主|小鼠|mouse|murine", question, re.IGNORECASE):
            fields["宿主"] = "小鼠宿主"
        elif re.search(r"生猪|猪|swine", question, re.IGNORECASE):
            fields["宿主"] = "生猪"

        intervention_patterns = [
            ("药物", r"(?:药物|drug)\s*([A-Za-z0-9][A-Za-z0-9\s_\\/\-+.']*(?:（[^）]+）)?)"),
            ("饮食", r"(?:饮食|食物|food)\s*([A-Za-z0-9][A-Za-z0-9\s_\\/\-+.']*(?:（[^）]+）)?)"),
            ("疾病", r"(?:疾病|disease)\s*([A-Za-z0-9][A-Za-z0-9\s_\\/\-+.']*(?:（[^）]+）)?)"),
            ("药物", r"([A-Za-z0-9][A-Za-z0-9\s_\\/\-+.']*(?:（[^）]+）)?)\s*(?:药物|drug)\s*(?:干预|处理)?"),
            ("饮食", r"([A-Za-z0-9][A-Za-z0-9\s_\\/\-+.']*(?:（[^）]+）)?)\s*(?:饮食|食物|food)\s*(?:干预|摄入|处理)?"),
            ("疾病", r"([A-Za-z0-9][A-Za-z0-9\s_\\/\-+.']*(?:（[^）]+）)?)\s*(?:疾病)?状态"),
        ]
        for field_name, pattern in intervention_patterns:
            match = re.search(pattern, question, re.IGNORECASE)
            if match:
                value = self._clean_context_value(match.group(1))
                if value:
                    fields[field_name] = value

        condition_match = re.search(r"在\s*[“\"]?([^“”\"]+?Antibiotics and zinc oxide[^“”\"]*?)[”\"]?\s*条件下", question, re.IGNORECASE)
        if condition_match:
            fields["实验条件"] = condition_match.group(1).strip(" ：:;；\"'“”")

        pvalue_match = re.search(r"P\s*value|Pvalue|P值", question, re.IGNORECASE)
        if pvalue_match:
            range_match = re.search(r"(?:位于|落在|在)\s*([0-9.]+)\s*(?:到|至|–|-)\s*([0-9.]+)", question)
            if range_match:
                fields["Pvalue范围"] = f"{range_match.group(1)}–{range_match.group(2)}"

        if re.search(r"丰度.{0,8}(显著)?上升|丰度.{0,8}升高|丰度.{0,8}增加", question):
            fields["微生物丰度变化"] = "肠道微生物群显著上升"
        elif re.search(r"丰度.{0,8}(显著)?下降|丰度.{0,8}降低|丰度.{0,8}减少", question):
            fields["微生物丰度变化"] = "肠道微生物群显著下降"

        if re.search(r"抑制.{0,12}(微生物|菌群)|减少这些微生物|减少.{0,12}(微生物|菌群)|宿主基因抑制|基因抑制", question):
            fields["微生物调控方向"] = "宿主基因抑制微生物群生长"
        elif re.search(r"促进.{0,12}(微生物|菌群)|增加这些微生物|促进这些微生物|宿主基因促进|基因促进", question):
            fields["微生物调控方向"] = "宿主基因促进微生物群生长"
        elif re.search(r"调控.{0,12}(微生物|菌群)", question):
            fields["微生物调控方向"] = "宿主基因调控微生物群生长"

        return fields

    def _clean_context_value(self, value: str) -> str:
        value = re.split(r"(?:干预|状态|条件|下|后|，|,|。|\?)", value.strip())[0].strip()
        return value.strip(" ：:;；\"'“”")

    def _with_context_fields(self, row: Dict[str, Any], context_fields: Dict[str, str]) -> Dict[str, Any]:
        merged = {}
        for key, value in context_fields.items():
            merged[key] = value
        merged.update(row)
        return merged

    def _to_display_row(self, row: Dict[str, Any]) -> Dict[str, Any]:
        display_row = {}
        for key, value in row.items():
            display_key = self._display_header(key)
            if display_key not in display_row or display_row[display_key] in ("", None):
                display_row[display_key] = value
            elif self._normalize_value(display_row[display_key]) != self._normalize_value(value):
                display_row[f"{display_key}补充信息"] = value
        return display_row

    def _filter_display_rows_for_summary(self, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """联合汇总表优先展示完整证据链，避免上游孤立实体造成空白行。"""
        if not rows:
            return rows

        critical_headers = [
            header for header in ["肠道微生物群", "关键基因", "主要代谢通路"]
            if any(header in row for row in rows)
        ]
        if len(critical_headers) < 2:
            return rows

        complete_rows = [
            row for row in rows
            if all(str(row.get(header, "")).strip() for header in critical_headers)
        ]
        return complete_rows or rows

    def _display_header(self, header: str) -> str:
        clean_header = self._clean_header(header)
        normalized = clean_header.lower()
        normalized = re.sub(r"\s+", "", normalized)
        mapping = {
            "microbiota_name": "肠道微生物群",
            "microbiotaname": "肠道微生物群",
            "microbiota": "肠道微生物群",
            "relationship": "肠道微生物群",
            "gene_symbol": "关键基因",
            "genesymbol": "关键基因",
            "gene": "关键基因",
            "pathway": "主要代谢通路",
            "pathway_name": "主要代谢通路",
            "pathwayname": "主要代谢通路",
            "metabolite_name": "相关代谢物",
            "metabolitename": "相关代谢物",
            "metabolite": "相关代谢物",
            "pvalue": "Pvalue",
            "p_value": "Pvalue",
            "condition": "实验条件",
            "host_type": "宿主",
            "hosttype": "宿主",
            "alteration": "微生物丰度变化",
        }
        return mapping.get(normalized, clean_header)

    def _rows_to_dicts(
        self,
        detected_attr: Dict[int, List[str]],
        results: Dict[int, List[Any]],
    ) -> Dict[int, List[Dict[str, Any]]]:
        row_maps_by_query = {}
        for query_idx, field_names in detected_attr.items():
            rows = []
            for row_data in results.get(query_idx, []):
                values = list(row_data) if isinstance(row_data, (list, tuple)) else [row_data]
                row = {}
                for field_name, value in zip(field_names, values):
                    clean_name = self._clean_header(field_name)
                    row[clean_name] = value
                rows.append(row)
            row_maps_by_query[query_idx] = rows
        return row_maps_by_query

    def _merge_query_rows(self, row_maps_by_query: Dict[int, List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
        rows1 = row_maps_by_query.get(1, [])
        rows2 = row_maps_by_query.get(2, [])
        rows3 = row_maps_by_query.get(3, [])

        if not rows1 and not rows2 and not rows3:
            return []

        if rows1 and rows2:
            merged = self._join_rows(rows1, rows2)
        else:
            merged = [self._prefixed_row(1, row) for row in rows1] or [self._prefixed_row(2, row) for row in rows2]

        if rows3:
            merged = self._join_rows(merged, rows3)

        return merged

    def _join_rows(self, left_rows: List[Dict[str, Any]], right_rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        joined = []
        for left in left_rows:
            matches = [right for right in right_rows if self._rows_related(left, right)]
            if matches:
                for right in matches:
                    joined.append(self._combine_rows(left, right))
            else:
                joined.append(dict(left))

        left_keys = {self._normalize_value(value) for row in left_rows for value in row.values()}
        for right in right_rows:
            right_values = {self._normalize_value(value) for value in right.values()}
            if not left_keys.intersection(right_values):
                joined.append(self._combine_rows({}, right))

        return self._deduplicate_rows(joined)

    def _rows_related(self, left: Dict[str, Any], right: Dict[str, Any]) -> bool:
        left_values = {self._normalize_value(value) for value in left.values() if value not in (None, "")}
        right_values = {self._normalize_value(value) for value in right.values() if value not in (None, "")}
        return bool(left_values.intersection(right_values))

    def _combine_rows(self, left: Dict[str, Any], right: Dict[str, Any]) -> Dict[str, Any]:
        combined = dict(left)
        for key, value in right.items():
            clean_key = self._clean_header(key)
            if clean_key not in combined or combined[clean_key] in ("", None):
                combined[clean_key] = value
            elif self._normalize_value(combined[clean_key]) == self._normalize_value(value):
                continue
            else:
                combined[f"{clean_key}_detail"] = value
        return combined

    def _prefixed_row(self, query_idx: int, row: Dict[str, Any]) -> Dict[str, Any]:
        return {self._clean_header(key): value for key, value in row.items()}

    def _ordered_headers(self, rows: List[Dict[str, Any]]) -> List[str]:
        preferred = [
            "宿主",
            "疾病",
            "饮食",
            "药物",
            "实验条件",
            "Pvalue范围",
            "微生物丰度变化",
            "肠道微生物群",
            "微生物调控方向",
            "关键基因",
            "主要代谢通路",
            "相关代谢物",
            "Pvalue",
        ]
        headers = []
        all_keys = []
        for row in rows:
            for key in row:
                if key not in all_keys:
                    all_keys.append(key)
        for key in preferred:
            if key in all_keys:
                headers.append(key)
        for key in all_keys:
            if key not in headers:
                headers.append(key)
        return headers

    def _to_markdown_table(self, headers: List[str], rows: List[Dict[str, Any]]) -> str:
        title = "### 联合汇总表\n\n"
        header_line = "| " + " | ".join(headers) + " |"
        separator = "| " + " | ".join(["---"] * len(headers)) + " |"
        body = []
        for row in rows:
            body.append("| " + " | ".join(self._format_cell(row.get(header, "")) for header in headers) + " |")
        return title + "\n".join([header_line, separator] + body) + "\n\n"

    def _to_csv(self, headers: List[str], rows: List[Dict[str, Any]]) -> str:
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(headers)
        for row in rows:
            writer.writerow([row.get(header, "") for header in headers])
        return output.getvalue()

    def _deduplicate_rows(self, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        seen = set()
        unique_rows = []
        for row in rows:
            key = tuple((field, self._normalize_value(value)) for field, value in sorted(row.items()))
            if key in seen:
                continue
            seen.add(key)
            unique_rows.append(row)
        return unique_rows

    def _clean_header(self, header: str) -> str:
        return str(header).strip().strip('"`')

    def _format_cell(self, value: Any) -> str:
        return str(value).replace("|", "\\|").replace("\n", "<br>")

    def _normalize_value(self, value: Any) -> str:
        return str(value).strip().lower()

    def generate_explanations(
        self,
        sub_question: str,
        queries: List[str],
        results: Dict[int, List[Any]],
        merged_table: str = "",
    ) -> str:
        """
        生成查询结果的整体分析和解释
        """
        # 准备数据
        converted_queries = "\n".join([f"查询 {i + 1}: {query}" for i, query in enumerate(queries)])
        query_results = "\n".join([f"查询 {key} 结果: {results[key]}" for key in results])

        # 使用模板生成提示
        prompt = self.aggregation_prompt.format(
            sub_question=sub_question,
            converted_queries=converted_queries,
            query_results=query_results,
            merged_table=merged_table or "无联合汇总表"
        )

        # 调用模型生成解释
        result = self.llm.invoke(prompt)
        return result.content

    def process(self, sub_question: str, queries: List[str], results: Dict[int, List[Any]]) -> tuple:
        """
        主方法：生成表格并让模型生成整体的分析和建议

        返回:
            tuple: (tables, explanation, merged_table, merged_csv)
        """
        print("=== 开始处理结果聚合 ===")
        print(f"子问题: {sub_question}")
        print(f"查询数量: {len(queries)}")
        print(f"结果数量: {len(results)}")

        # 先生成跨子查询汇总表，再保留每个子查询的原始明细表。
        merged_table, merged_csv = self.merged_table_generate(sub_question, queries, results)
        tables = self.table_generate(queries, results).strip()

        # 生成整体分析和建议
        explanation = self.generate_explanations(sub_question, queries, results, merged_table)

        print("=== 结果聚合完成 ===")

        return tables, explanation, merged_table, merged_csv


def main():
    """测试修复后的结果聚合器"""

    # 测试数据
    test_queries = [
        """SELECT DISTINCT hecrbm.gene_symbol, hecrbm.relationship
FROM relationship.has_expression_change_results_by_microbiota hecrbm
JOIN newgutmgene.gut_microbiota_gene_change_results gmgcr 
ON hecrbm.`index` = gmgcr.`index`
WHERE gmgcr.Alteration = 'increase' AND hecrbm.relationship IN ('Cellulosilyticum', 'Leeia', 'Subdoligranulu', 'Rothia', 'Methanobrevibacter', 'Bacteroides', 'Lactobacillus', 'Oscillibacter', 'Ruminococcaceae')""",

        """SELECT gene_symbol, pathway
FROM kegg
WHERE gene_symbol IN ('IL22', 'MAPK14', 'Tjp1', 'Arg1')""",

        """MATCH (microbiota:MicrobiotaName)-[:increase]->(feed_efficiency:FE)
RETURN microbiota.name as microbiota_name"""
    ]

    test_results = {
        1: [
            ['IL22', 'Lactobacillus'],
            ['MAPK14', 'Lactobacillus'],
            ['BAX', 'Bacteroides'],
            ['CASP3', 'Bacteroides'],
            ['Tjp1', 'Lactobacillus'],
            ['Nr1h4', 'Bacteroides'],
            ['Fgf15', 'Bacteroides'],
            ['Fgfr4', 'Bacteroides'],
            ['Fas', 'Bacteroides'],
            ['Arg1', 'Lactobacillus']
        ],
        2: [
            ['IL22', 'hsa04060 Cytokine-cytokine receptor interaction'],
            ['MAPK14', 'hsa04010 MAPK signaling pathway'],
            ['Tjp1', 'mmu04530 Tight junction'],
            ['Arg1', 'mmu00330 Arginine and proline metabolism']
        ],
        3: [
            ['Lactobacillus'],
            ['Bacteroides'],
            ['Bifidobacterium']
        ]
    }

    # 创建修复后的聚合器
    aggregator = ResultAggregation(config.model)

    # 测试字段提取
    print("=== 测试字段提取 ===")
    extracted_fields = aggregator.extract_return_fields(test_queries)
    for query_id, fields in extracted_fields.items():
        print(f"查询 {query_id} 的字段: {fields}")

    print("\n=== 测试表格生成 ===")

    # 处理结果
    sub_question = "哪些基因的表达能够增加特定微生物的数量，这些基因参与哪些通路？"
    tables, explanation = aggregator.process(sub_question, test_queries, test_results)

    print("\n生成的表格:")
    print(tables)

    print("\n生成的解释:")
    print(explanation)


if __name__ == '__main__':
    main()
