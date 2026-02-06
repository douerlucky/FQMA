from rdflib.plugins.sparql.parser import parseQuery

sparql_query = """
PREFIX foaf: <http://xmlns.com/foaf/0.1/>
SELECT ?name ?age
WHERE {
    ?person foaf:name ?name .
    ?person foaf:age ?age .
    FILTER (?age > ?SUBQUERY1)
}
"""

parsed = parseQuery(sparql_query)
print(parsed)
