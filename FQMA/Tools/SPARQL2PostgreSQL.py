#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPARQL to PostgreSQL Converter
Fully driven by R2RML TTL mappings, no hardcoding.
"""

import re
from typing import Dict, List, Optional
from collections import defaultdict


class SparqlToPostgreSQLConverter:
    """SPARQL to SQL converter driven by TTL mappings."""

    def __init__(self, ttl_file_path: str):
        self.ttl_file_path = ttl_file_path

        # Core mapping structures
        self.class_to_table = {}
        self.property_to_column = {}
        self.property_to_table = {}
        self.object_properties = []
        self.table_columns = defaultdict(set)

        # Complex relation mappings (from SQL queries in TTL)
        self.complex_relation_mappings = {}

        self._parse_r2rml_mapping()

    def _parse_r2rml_mapping(self):
        """Parse R2RML TTL file."""
        try:
            with open(self.ttl_file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            mapping_sections = re.split(r'\n\s*<#', content)

            for section in mapping_sections:
                if not section.strip():
                    continue
                self._parse_mapping_section('<#' + section if not section.startswith('<#') else section)

            print(f"Parsed R2RML mapping:")
            print(f"  - {len(self.class_to_table)} class mappings")
            print(f"  - {len(self.property_to_column)} property mappings")
            print(f"  - {len(self.object_properties)} object properties")
            print(f"  - {len(self.complex_relation_mappings)} complex relation mappings")

        except Exception as e:
            print(f"Parse failed: {e}")
            raise

    def _parse_mapping_section(self, section: str):
        """Parse a single mapping section."""
        sql_match = re.search(r'rr:sqlQuery\s*"""(.*?)"""', section, re.DOTALL)

        if sql_match:
            sql_query = sql_match.group(1).strip()
            self._parse_complex_mapping(section, sql_query)
        else:
            table_name = self._extract_table_name(section)
            if not table_name:
                return

            self._parse_class_mapping(section, table_name)
            self._parse_datatype_properties(section, table_name)
            self._parse_object_properties(section, table_name)

    def _parse_complex_mapping(self, section: str, sql_query: str):
        """Parse complex mapping with SQL query."""
        pom_blocks = self._extract_predicate_object_maps(section)
        if not pom_blocks:
            return

        # Parse JOIN info from SQL
        join_info = self._parse_sql_joins(sql_query)

        # Get main table
        main_table = join_info.get('main_table')

        # Get subject template column
        subject_match = re.search(
            r'rr:subjectMap\s*\[\s*rr:template\s*"[^"]*\{(\w+)\}"',
            section
        )
        source_column = subject_match.group(1) if subject_match else None

        for pom_block in pom_blocks:
            pred_match = re.search(r'rr:predicate\s+(\w+):(\w+)', pom_block)
            if not pred_match:
                continue

            predicate_name = pred_match.group(2)

            is_datatype = bool(re.search(r'rr:column', pom_block))
            is_object = bool(re.search(r'rr:template', pom_block))

            if is_datatype and not is_object:
                column_match = re.search(r'rr:column\s+"([^"]+)"', pom_block)
                if column_match and main_table:
                    column_name = column_match.group(1)
                    if predicate_name not in self.property_to_column:
                        self.property_to_column[predicate_name] = column_name
                        self.property_to_table[predicate_name] = main_table
                        self.table_columns[main_table].add(column_name)
                continue

            if is_object:
                object_match = re.search(r'rr:template\s*"[^"]*\{(\w+)\}"', pom_block)
                target_column = object_match.group(1) if object_match else None

                mapping_info = {
                    'predicate': predicate_name,
                    'main_table': main_table,
                    'source_column': source_column,
                    'target_column': target_column,
                    'joins': join_info.get('joins', []),
                    'select_columns': join_info.get('select_columns', {}),
                    'sql_template': sql_query
                }

                self.complex_relation_mappings[predicate_name] = mapping_info

    def _parse_sql_joins(self, sql_query: str) -> Dict:
        """Parse all JOINs from SQL query."""
        result = {
            'main_table': None,
            'joins': [],
            'select_columns': {}
        }

        # Extract main table from FROM clause
        from_match = re.search(r'FROM\s+"(\w+)"', sql_query, re.IGNORECASE)
        if from_match:
            result['main_table'] = from_match.group(1)

        # Extract all JOINs - pattern: JOIN "table" ON "left_table"."left_col" = "right_table"."right_col"
        join_pattern = r'JOIN\s+"(\w+)"\s+ON\s+"(\w+)"\."(\w+)"\s*=\s*"(\w+)"\."(\w+)"'

        for match in re.finditer(join_pattern, sql_query, re.IGNORECASE):
            join_info = {
                'table': match.group(1),
                'left_table': match.group(2),
                'left_col': match.group(3),
                'right_table': match.group(4),
                'right_col': match.group(5)
            }
            result['joins'].append(join_info)

        # Extract SELECT columns with aliases
        select_match = re.search(r'SELECT\s+(.*?)\s+FROM', sql_query, re.IGNORECASE | re.DOTALL)
        if select_match:
            select_clause = select_match.group(1)
            alias_pattern = r'"(\w+)"\."(\w+)"\s+AS\s+(\w+)'
            for match in re.finditer(alias_pattern, select_clause, re.IGNORECASE):
                alias = match.group(3)
                result['select_columns'][alias] = {
                    'table': match.group(1),
                    'column': match.group(2)
                }

        return result

    def _extract_predicate_object_maps(self, content: str) -> List[str]:
        """Extract all predicateObjectMap blocks."""
        blocks = []
        pattern = r'rr:predicateObjectMap\s*\['

        for match in re.finditer(pattern, content):
            start = match.end() - 1
            end = self._find_matching_bracket(content, start)
            if end != -1:
                blocks.append(content[start + 1:end])

        return blocks

    def _find_matching_bracket(self, content: str, start_pos: int) -> int:
        """Find matching closing bracket."""
        if start_pos >= len(content) or content[start_pos] != '[':
            return -1

        depth = 0
        for i in range(start_pos, len(content)):
            if content[i] == '[':
                depth += 1
            elif content[i] == ']':
                depth -= 1
                if depth == 0:
                    return i
        return -1

    def _extract_table_name(self, section: str) -> Optional[str]:
        """Extract table name from mapping section."""
        match = re.search(r'rr:tableName\s+"([^"]+)"', section)
        if match:
            return match.group(1)
        return None

    def _parse_class_mapping(self, section: str, table_name: str):
        """Parse class to table mapping."""
        matches = re.finditer(r'rr:class\s+(\w+):(\w+)', section)
        for match in matches:
            class_name = match.group(2)
            self.class_to_table[class_name] = table_name

    def _parse_datatype_properties(self, section: str, table_name: str):
        """Parse datatype properties."""
        pom_blocks = self._extract_predicate_object_maps(section)

        for block in pom_blocks:
            pred_match = re.search(r'rr:predicate\s+(\w+):(\w+)', block)
            col_match = re.search(r'rr:column\s+"([^"]+)"', block)

            if pred_match and col_match:
                predicate_name = pred_match.group(2)
                column_name = col_match.group(1)

                self.property_to_column[predicate_name] = column_name
                self.property_to_table[predicate_name] = table_name
                self.table_columns[table_name].add(column_name)

    def _parse_object_properties(self, section: str, table_name: str):
        """Parse object properties."""
        pom_blocks = self._extract_predicate_object_maps(section)

        for block in pom_blocks:
            pred_match = re.search(r'rr:predicate\s+(\w+):(\w+)', block)
            template_match = re.search(r'rr:template\s+"([^"]+)"', block)

            if pred_match and template_match and 'rr:column' not in block:
                predicate_name = pred_match.group(2)
                template = template_match.group(1)

                target_match = re.search(r'#(\w+)_\{(\w+)\}', template)
                if target_match:
                    target_class = target_match.group(1)
                    fk_column = target_match.group(2)

                    self.object_properties.append({
                        'predicate': predicate_name,
                        'source_table': table_name,
                        'target_class': target_class,
                        'foreign_key': fk_column
                    })

    def convert(self, sparql_query: str) -> str:
        """Convert SPARQL to SQL."""
        try:
            parsed = self._parse_sparql_query(sparql_query)
            query_plan = self._analyze_query_pattern(parsed)
            sql = self._build_sql(parsed, query_plan)
            return sql
        except Exception as e:
            print(f"Conversion failed: {e}")
            import traceback
            traceback.print_exc()
            return ""

    def _parse_sparql_query(self, query: str) -> Dict:
        """Parse SPARQL query."""
        clean_query = re.sub(r'#.*', '', query)
        clean_query = ' '.join(clean_query.split())

        # SELECT clause
        select_match = re.search(r'SELECT\s+(DISTINCT\s+)?(.*?)\s+WHERE', clean_query, re.IGNORECASE)
        if not select_match:
            raise ValueError("Cannot parse SELECT clause")

        is_distinct = bool(select_match.group(1))
        select_clause = select_match.group(2).strip()

        # Parse variables and aggregations
        select_vars = []
        aggregations = []

        agg_pattern = r'\(?\s*(COUNT|SUM|AVG|MIN|MAX)\s*\(\s*(?:DISTINCT\s+)?\?(\w+)\s*\)\s*(?:AS\s+\?(\w+))?\s*\)?'
        for match in re.finditer(agg_pattern, select_clause, re.IGNORECASE):
            agg_func = match.group(1).upper()
            var_name = match.group(2)
            alias = match.group(3) if match.group(3) else f"{agg_func.lower()}_{var_name}"
            aggregations.append({'function': agg_func, 'variable': var_name, 'alias': alias})
            select_vars.append(alias)

        for match in re.finditer(r'\?(\w+)', select_clause):
            var = match.group(1)
            if var not in [a['variable'] for a in aggregations] and var not in [a['alias'] for a in aggregations]:
                if var not in select_vars:
                    select_vars.append(var)

        # WHERE clause
        where_match = re.search(r'WHERE\s*\{(.*?)\}', clean_query, re.DOTALL | re.IGNORECASE)
        if not where_match:
            raise ValueError("Cannot parse WHERE clause")

        where_body = where_match.group(1)

        # GROUP BY
        group_by_vars = []
        group_match = re.search(r'GROUP\s+BY\s+(.*?)(?:HAVING|ORDER|LIMIT|$)', clean_query, re.IGNORECASE)
        if group_match:
            group_by_vars = [v.strip('?') for v in re.findall(r'\?(\w+)', group_match.group(1))]

        # BIND
        bind_mappings = {}
        bind_pattern = r'BIND\s*\(\s*(?:STR\s*\(\s*)?\?(\w+)\s*(?:\))?\s+AS\s+\?(\w+)\s*\)'
        for match in re.finditer(bind_pattern, where_body, re.IGNORECASE):
            bind_mappings[match.group(2)] = match.group(1)
            where_body = where_body.replace(match.group(0), '')

        # FILTER
        filters = []
        filter_pattern = r'FILTER\s*\(((?:[^()]|\([^()]*\))*)\)'
        for match in re.finditer(filter_pattern, where_body, re.DOTALL):
            filters.append(match.group(1).strip())
            where_body = where_body.replace(match.group(0), '')

        # Triples
        triples = []
        statements = [s.strip() for s in re.split(r'\s*\.\s*', where_body) if s.strip()]

        for stmt in statements:
            parts = stmt.split(None, 2)
            if len(parts) >= 3:
                triples.append({
                    'subject': parts[0],
                    'predicate': parts[1],
                    'object': parts[2].rstrip('.')
                })

        return {
            'select_vars': select_vars,
            'is_distinct': is_distinct,
            'triples': triples,
            'filters': filters,
            'aggregations': aggregations,
            'group_by': group_by_vars,
            'bind_mappings': bind_mappings
        }

    def _analyze_query_pattern(self, parsed: Dict) -> Dict:
        """Analyze query pattern to determine tables and joins."""
        triples = parsed['triples']

        # Find variables used as subjects
        subject_vars = set()
        for triple in triples:
            if triple['subject'].startswith('?'):
                subj_var = triple['subject'].strip('?')
                if not self._is_type_predicate(triple['predicate']):
                    subject_vars.add(subj_var)

        # Find main table from type declaration
        main_table = None
        main_variable = None

        for triple in triples:
            if self._is_type_predicate(triple['predicate']):
                class_name = triple['object'].split(':')[-1]
                if class_name in self.class_to_table:
                    main_table = self.class_to_table[class_name]
                    main_variable = triple['subject'].strip('?')
                    break

        if not main_table:
            raise ValueError("Cannot determine main table (missing rdf:type)")

        # Build variable to column mapping
        var_to_column = {}
        var_to_entity_table = {}

        var_to_column[main_variable] = (main_table, 'ID')
        var_to_entity_table[main_variable] = main_table

        # Analyze triples
        joins = []
        complex_joins = []

        for triple in triples:
            if self._is_type_predicate(triple['predicate']):
                continue

            pred_name = triple['predicate'].split(':')[-1]
            subject_var = triple['subject'].strip('?')
            object_var = triple['object'].strip('?') if triple['object'].startswith('?') else None

            # Case 1: Complex relation mapping
            if pred_name in self.complex_relation_mappings:
                complex_mapping = self.complex_relation_mappings[pred_name]

                need_join = object_var and object_var in subject_vars

                if need_join:
                    complex_joins.append({
                        'predicate': pred_name,
                        'subject_var': subject_var,
                        'object_var': object_var,
                        'mapping': complex_mapping
                    })

                    joins_list = complex_mapping.get('joins', [])
                    if joins_list:
                        target_table = joins_list[-1]['table']
                        var_to_entity_table[object_var] = target_table
                        var_to_column[object_var] = (target_table, 'ID')
                else:
                    if object_var:
                        target_col = complex_mapping.get('target_column', pred_name)
                        var_to_column[object_var] = (main_table, target_col)

            # Case 2: Datatype property
            elif pred_name in self.property_to_column:
                column = self.property_to_column[pred_name]
                prop_table = self.property_to_table[pred_name]

                actual_table = prop_table
                if subject_var in var_to_entity_table:
                    entity_table = var_to_entity_table[subject_var]
                    if column in self.table_columns.get(entity_table, set()):
                        actual_table = entity_table

                if object_var:
                    var_to_column[object_var] = (actual_table, column)

            # Case 3: Simple object property
            else:
                for obj_prop in self.object_properties:
                    if obj_prop['predicate'] == pred_name:
                        target_class = obj_prop['target_class']
                        target_table = None

                        for cls, tbl in self.class_to_table.items():
                            if cls.lower() == target_class.lower():
                                target_table = tbl
                                break

                        if target_table and target_table != main_table:
                            need_join = object_var and object_var in subject_vars

                            if need_join:
                                joins.append({
                                    'table': target_table,
                                    'on_column': obj_prop['foreign_key'],
                                    'target_table': main_table
                                })
                                if object_var:
                                    var_to_column[object_var] = (target_table, 'ID')
                                    var_to_entity_table[object_var] = target_table
                            else:
                                if object_var:
                                    var_to_column[object_var] = (main_table, obj_prop['foreign_key'])
                        break

        return {
            'main_table': main_table,
            'main_variable': main_variable,
            'joins': joins,
            'var_to_column': var_to_column,
            'complex_joins': complex_joins,
            'var_to_entity_table': var_to_entity_table
        }

    def _is_type_predicate(self, predicate: str) -> bool:
        """Check if predicate is a type predicate."""
        return predicate == 'a' or predicate == 'rdf:type' or 'type' in predicate.lower()

    def _build_sql(self, parsed: Dict, plan: Dict) -> str:
        """Build SQL query."""
        aggregations = parsed.get('aggregations', [])
        has_aggregation = len(aggregations) > 0

        # SELECT clause
        select_items = []

        for agg in aggregations:
            agg_var = agg['variable']
            agg_func = agg['function']
            agg_alias = agg['alias']

            if agg_var in plan['var_to_column']:
                table, column = plan['var_to_column'][agg_var]
                select_items.append(f'{agg_func}("{table}"."{column}") AS {agg_alias}')
            else:
                select_items.append(f'{agg_func}(*) AS {agg_alias}')

        bind_mappings = parsed.get('bind_mappings', {})

        for var in parsed['select_vars']:
            if var in [a['alias'] for a in aggregations]:
                continue

            source_var = bind_mappings.get(var, var)

            if source_var in plan['var_to_column']:
                table, column = plan['var_to_column'][source_var]
                select_items.append(f'"{table}"."{column}"')
            else:
                # Try to find in complex mapping select columns
                found = False
                for cj in plan.get('complex_joins', []):
                    mapping = cj['mapping']
                    select_cols = mapping.get('select_columns', {})
                    for alias, info in select_cols.items():
                        if alias.lower() == source_var.lower() or source_var.lower() in alias.lower():
                            select_items.append(f'"{info["table"]}"."{info["column"]}"')
                            found = True
                            break
                    if found:
                        break

                if not found:
                    print(f"Warning: variable ?{var} has no column mapping")

        if not select_items:
            select_items = ['*']

        distinct = 'DISTINCT ' if parsed['is_distinct'] and not has_aggregation else ''
        sql_parts = [f"SELECT {distinct}{', '.join(select_items)}"]

        # FROM clause
        sql_parts.append(f'FROM "{plan["main_table"]}"')

        # Build JOINs - use full table names only, no aliases
        all_joins = []
        joins_seen = set()

        # Process complex joins from TTL
        for cj in plan.get('complex_joins', []):
            mapping = cj['mapping']
            joins_list = mapping.get('joins', [])

            for join_info in joins_list:
                join_table = join_info['table']
                left_table = join_info['left_table']
                left_col = join_info['left_col']
                right_table = join_info['right_table']
                right_col = join_info['right_col']

                join_key = (join_table, left_table, left_col, right_table, right_col)
                if join_key not in joins_seen:
                    # Use full table names, no aliases
                    all_joins.append({
                        'table': join_table,
                        'on': f'"{left_table}"."{left_col}" = "{right_table}"."{right_col}"'
                    })
                    joins_seen.add(join_key)

        # Process simple joins
        for join in plan.get('joins', []):
            join_table = join["table"]
            target_table = join["target_table"]
            on_col = join["on_column"]

            join_key = (join_table, target_table, on_col, join_table, 'ID')
            if join_key not in joins_seen:
                all_joins.append({
                    'table': join_table,
                    'on': f'"{target_table}"."{on_col}" = "{join_table}"."ID"'
                })
                joins_seen.add(join_key)

        # Generate JOIN clauses - no aliases
        for j in all_joins:
            sql_parts.append(f'JOIN "{j["table"]}" ON {j["on"]}')

        # WHERE clause
        where_conditions = self._build_where_conditions(parsed, plan)
        if where_conditions:
            sql_parts.append('WHERE ' + ' AND '.join(where_conditions))

        # GROUP BY clause
        if has_aggregation:
            group_columns = []
            group_by = parsed.get('group_by', [])
            if group_by:
                for var in group_by:
                    if var in plan['var_to_column']:
                        table, column = plan['var_to_column'][var]
                        group_columns.append(f'"{table}"."{column}"')
            else:
                for var in parsed['select_vars']:
                    if var not in [a['alias'] for a in aggregations]:
                        if var in plan['var_to_column']:
                            table, column = plan['var_to_column'][var]
                            group_columns.append(f'"{table}"."{column}"')

            if group_columns:
                sql_parts.append('GROUP BY ' + ', '.join(group_columns))

        return '\n'.join(sql_parts)

    def _build_where_conditions(self, parsed: Dict, plan: Dict) -> List[str]:
        """Build WHERE conditions."""
        conditions = []

        for filter_expr in parsed['filters']:
            # IN condition
            in_match = re.match(r'\?(\w+)\s+IN\s+\((.*?)\)', filter_expr, re.DOTALL)
            if in_match:
                var = in_match.group(1)
                values = in_match.group(2).strip()

                if var in plan['var_to_column']:
                    table, column = plan['var_to_column'][var]
                    conditions.append(f'"{table}"."{column}" IN ({values})')
                continue

            # Simple comparison
            compare_match = re.match(r'\?(\w+)\s*=\s*(\d+)', filter_expr)
            if compare_match:
                var = compare_match.group(1)
                value = compare_match.group(2)
                if var in plan['var_to_column']:
                    table, column = plan['var_to_column'][var]
                    conditions.append(f'"{table}"."{column}" = {value}')
                continue

        # Literal constraints from triples
        for triple in parsed['triples']:
            if self._is_type_predicate(triple['predicate']):
                continue

            if not triple['object'].startswith('?'):
                pred_name = triple['predicate'].split(':')[-1]
                if pred_name in self.property_to_column:
                    column = self.property_to_column[pred_name]
                    table = self.property_to_table[pred_name]
                    value = triple['object'].strip('"\'')
                    conditions.append(f'"{table}"."{column}" = \'{value}\'')

        return conditions


def main():
    """Test function."""
    import sys

    ttl_file = sys.argv[1] if len(sys.argv) > 1 else 'rodi_postgre.ttl'

    print("=" * 70)
    print("SPARQL to PostgreSQL Converter")
    print("=" * 70)

    converter = SparqlToPostgreSQLConverter(ttl_file)

    # Test query
    sparql = """
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
    PREFIX conf: <http://conference#>

    SELECT ?person ?first_name ?last_name ?gender ?committee_name
    WHERE {
      ?person rdf:type conf:Person .
      ?person conf:has_the_first_name ?first_name .
      ?person conf:has_the_last_name ?last_name .
      ?person conf:has_gender ?gender .
      ?person conf:was_a_member_of ?committee .
      ?committee rdf:type conf:Committee .
      ?committee conf:has_a_name ?committee_name .
      FILTER (?person IN (585, 584, 403, 313, 48))
    }
    """

    print("\nSPARQL:")
    print(sparql)
    print("\nSQL:")
    sql = converter.convert(sparql)
    print(sql)


if __name__ == "__main__":
    main()