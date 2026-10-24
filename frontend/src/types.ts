export type Evidence = {
  source: string;
  excerpt: string;
  citation: string;
  score: number;
};
export type Source = {
  title: string;
  url: string;
  publication_date?: string;
  retrieved_at: string;
};
export type Report = {
  commerce?: { primary: any; selection: string; datasets: any[] };
  research_status?: { status: string; detail?: string };
  connector_status?: {
    tool: string;
    status: string;
    retrieved_at?: string;
    detail?: string;
  }[];
  operations?: any;
  knowledge_scope?: string;
  provider_status?: string;
  strategy_fallback?: string;
  strategy_engine?: string;
  recommendations?: Recommendation[];
  market_sources?: Source[];
  recommendation_kind?: string;
  facts: {
    period: string;
    visits: number;
    paid: number;
    conversion: number;
    source: string;
  }[];
  evidence: Evidence[];
  hypothesis: string;
  plan: string;
  success_metric: string;
  market_research: string;
};
export type Run = {
  chat_result?: {mode?: string; classification?: string; usage?: {provider?: string; model?: string}};
  engine?: string;
  execution_result?: {
    tool: string;
    status: string;
    verified_task_count: number;
    executed_at: string;
    external_effect: string;
  };
  id: string;
  state: string;
  events: { stage: string; detail: string }[];
  report: Report | null;
  artifact?: string;
  output?: string;
  error?: string;
};
export type Message = {
  sources?: Source[];
  role: string;
  text: string;
  execution?: string;
  report?: Report;
};
export type Convo = {
  id: string;
  title: string;
  goal: string;
  business_id?: string;
  project_id?: string;
  created_at?: string;
  files: {
    id: string;
    name: string;
    import?: { kind: string; dataset_id: string };
  }[];
  messages: Message[];
};
export type Business = {
  id: string;
  name: string;
  product: string;
  goal: string;
};

export type Recommendation = {
  id: string;
  title: string;
  rationale: string;
  evidence: string[];
  impact: number;
  confidence: number;
  effort: number;
  priority_score: number;
  expected_benefit: string;
  risks: string[];
  rollback: string;
  tasks: string[];
  measurement_period_days: number;
};
