const runtimeHost = window.location.hostname || 'localhost'
const runtimeProtocol = window.location.protocol === 'https:' ? 'https' : 'http'

export default {
  API_BASE_URL: import.meta.env.VITE_API_BASE_URL || `${runtimeProtocol}://${runtimeHost}:5001/api`,
  APP_NAME: 'FQMA',
  APP_VERSION: '1.0.0',

  DEFAULT_DATASET: 'GMQA',
  DATASETS: {
    GMQA: {
      name: 'GMQA',
      displayName: 'GMQA',
      label: 'An Ontology-based Federated Query Multi-Agent Framework',
      icon: '🧬',
      datasetJsonPath: '/GMQA.json',
      features: [
        'Supports federated querying based on virtual knowledge graphs',
        'Supports analysis of disease, diet, and drug effects on human and murine gut microbiota',
        'Supports association analysis between swine gut microbiota and feed efficiency'
      ],
      examples: [
        {
          text: 'Which regulatory genes and metabolic pathways are associated with Dorea, Eubacterium, and Bacteroides taxa that are significantly related to swine feed efficiency?',
          icon: '🐷'
        },
        {
          text: 'Under the Fattening, Unmedicated feed formula / Antibiotics and zinc oxide condition, which regulatory genes and metabolic pathways are associated with Eubacterium taxa related to swine feed efficiency with P values between 0.20 and 0.21?',
          icon: '🦠'
        },
        {
          text: 'In human hosts, which gut microbiota increase significantly after Vitamin A intervention, and which key genes may suppress their growth and participate in major metabolic pathways?',
          icon: '🍽️'
        },
        {
          text: 'In murine experiments, which gut microbiota increase after Isoliquiritigenin treatment, and which key genes and metabolic processes may support their growth?',
          icon: '💊'
        }
      ]
    },
    RODI: {
      name: 'RODI',
      displayName: 'RODI-C',
      label: 'RODI-C Conference-domain Federated Query Benchmark',
      icon: '📚',
      datasetJsonPath: '/rodi_query.json',
      features: [
        'Supports RODI-C conference-domain data querying',
        'Supports federated querying across MySQL, PostgreSQL, and Neo4j',
        'Supports retrieval over papers, authors, submissions, and conference relationships'
      ],
      examples: [
        {
          text: 'Retrieve the first 10 papers written by author ID 3, including their abstracts, titles, and submitted conference IDs from another database.',
          icon: '✍️'
        },
        {
          text: 'Retrieve the titles, abstracts, and author information for all papers submitted to conference ID 7.',
          icon: '📄'
        },
        {
          text: 'Find the papers associated with a given author and the conference information for those submissions.',
          icon: '🏛️'
        }
      ]
    }
  },

  ABOUT_PROJECT: {
    title: 'About FQMA',
    developers: `Authors: Feiyang Xue, Chaoying Zuo, Hongyu Wang, Jiwen Wang, Xuan Liu\nAdvisors: Ying Wang, Zaiwen Feng`,
    intro: 'FQMA is an ontology-based federated query multi-agent framework for heterogeneous data sources. It uses a domain ontology and virtual knowledge graph as a unified semantic layer, mapping MySQL, PostgreSQL, and Neo4j backends into consistent concepts, properties, and relationships. Given a natural-language question, FQMA orchestrates multiple agents with LangGraph to perform question decomposition, ontology-aware SPARQL generation, semantic checking and repair, database routing, query conversion, cross-database execution, and result aggregation.',
    problems: 'FQMA targets two major query scenarios: human and murine gut microbiota studies involving disease, diet, and drug effects, and swine gut microbiota studies related to feed efficiency. It also supports cross-entity, cross-relation, and cross-database retrieval over heterogeneous data sources.',
    innovations: 'The key contributions include an ontology-based unified semantic layer, ontology-constrained SPARQL generation to reduce hallucinated predicates and relations, semantic repair based on first-order logic rules and LLM-assisted judgment, LangGraph-based multi-agent orchestration, and the GMQA benchmark for validating federated query capability.',
    databases: 'FQMA uses Neo4j for graph relationships, MySQL for microbiota-phenotype and microbiota-gene associations, and PostgreSQL for KEGG gene-pathway knowledge.',
    datasetSources: 'The GMQA dataset integrates GutMDisorder, GutMGene, PGMKG, and KEGG. MySQL stores microbiota-phenotype and microbiota-gene associations, Neo4j stores swine gut microbiota and feed efficiency relationships, and PostgreSQL stores KEGG pathway knowledge.',
    qaCategories: 'Question-answer pairs are grouped into human/murine gut microbiota effect studies, including disease, diet, and drug effects, and swine gut microbiota studies focused on feed efficiency and host regulatory genes.',
    qaStats: [
      {
        category: 'Swine Feeding Efficiency',
        questions: 99,
        tables: 7,
        triples: 15,
        meanRows: 19.87,
        rowRange: '2–80',
        colRange: '5–8'
      },
      {
        category: 'Disease Effects, Human / Murine',
        questions: 88,
        tables: 7,
        triples: 17,
        meanRows: 47.00,
        rowRange: '3–170',
        colRange: '5–5'
      },
      {
        category: 'Food Effects, Human / Murine',
        questions: 67,
        tables: 7,
        triples: 17,
        meanRows: 45.06,
        rowRange: '3–168',
        colRange: '5–5'
      },
      {
        category: 'Drug Effects, Human / Murine',
        questions: 66,
        tables: 7,
        triples: 17,
        meanRows: 42.14,
        rowRange: '13–144',
        colRange: '5–5'
      },
      {
        category: 'Total',
        questions: 320,
        tables: 86,
        triples: 179,
        meanRows: 37.20,
        rowRange: '2–170',
        colRange: '5–8'
      }
    ],
    qaDetails: [
      {
        category: 'Disease Effects, Human / Murine',
        qty: 88,
        query: 'Under disease conditions, which human or murine gut microbiota change significantly, and which host genes and metabolic pathways may be associated with these changes?',
        sources: 'GutMDisorder, GutMGene, KEGG'
      },
      {
        category: 'Food Effects, Human / Murine',
        qty: 67,
        query: 'After a dietary intervention, which gut microbiota increase or decrease, and which host genes may regulate these microbiota through metabolic pathways?',
        sources: 'GutMDisorder, GutMGene, KEGG'
      },
      {
        category: 'Drug Effects, Human / Murine',
        qty: 66,
        query: 'Which gut microbiota change after drug intervention, and which host genes may promote or suppress these changes through metabolic pathways?',
        sources: 'GutMDisorder, GutMGene, KEGG'
      },
      {
        category: 'Swine Feeding Efficiency',
        qty: 99,
        query: 'Which gut microbiota are significantly associated with swine feed efficiency or feed conversion ratio, and which host genes and metabolic pathways may regulate them?',
        sources: 'PGMKG, GutMGene, KEGG'
      }
    ]
  },

  MAX_QUERY_LENGTH: 1000,
  QUERY_TIMEOUT: 60000,

  THEME: {
    primaryColor: '#6b46c1',
    secondaryColor: '#f0f0f0',
    errorColor: '#dc2626',
    successColor: '#10b981'
  }
}
