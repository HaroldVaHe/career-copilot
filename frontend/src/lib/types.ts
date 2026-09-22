/** Espejo de los esquemas Pydantic del backend (backend/app/schemas). */

export type Severity = "critical" | "warning" | "info";

export interface ContactInfo {
  full_name: string;
  headline: string;
  email: string;
  phone: string;
  location: string;
  linkedin: string;
  github: string;
  portfolio: string;
}

export interface ExperienceItem {
  company: string;
  role: string;
  location: string;
  start_date: string;
  end_date: string;
  is_current: boolean;
  bullets: string[];
  technologies: string[];
}

export interface EducationItem {
  institution: string;
  degree: string;
  field_of_study: string;
  start_date: string;
  end_date: string;
  notes: string;
}

export interface SkillSet {
  languages: string[];
  frameworks: string[];
  databases: string[];
  cloud_devops: string[];
  tools: string[];
  soft_skills: string[];
  other: string[];
}

export interface ResumeData {
  contact: ContactInfo;
  summary: string;
  experience: ExperienceItem[];
  education: EducationItem[];
  skills: SkillSet;
  certifications: { name: string; issuer: string; date: string; credential_url: string }[];
  projects: { name: string; description: string; technologies: string[]; url: string }[];
  languages: { language: string; level: string }[];
  total_years_experience: number;
  detected_seniority: string;
}

export interface AtsFinding {
  severity: Severity;
  area: string;
  message: string;
  fix: string;
}

export interface BulletRewrite {
  experience_index: number;
  bullet_index: number;
  original: string;
  suggestion: string;
  rationale: string;
  invented_facts: boolean;
}

export interface AtsReport {
  overall_score: number;
  breakdown: {
    technical_relevance: number;
    clarity_format: number;
    achievement_quantification: number;
    skill_coverage: number;
    ats_parseability: number;
  };
  findings: AtsFinding[];
  rewrites: BulletRewrite[];
  keyword_density: Record<string, number>;
  missing_sections: string[];
  strengths: string[];
  quick_wins: string[];
}

export interface ResumeSummary {
  id: number;
  label: string;
  target_role: string | null;
  source_filename: string | null;
  ats_score: number | null;
  is_primary: boolean;
  parent_id: number | null;
  tailored_for_job_id: number | null;
  created_at: string;
  updated_at: string;
}

export interface Resume extends ResumeSummary {
  parsed: ResumeData;
  ats_report: AtsReport | null;
  raw_text: string;
}

export interface Job {
  id: number;
  source: string;
  external_id: string | null;
  url: string | null;
  title: string;
  company: string;
  location: string | null;
  country: string | null;
  remote_type: string;
  seniority: string | null;
  employment_type: string | null;
  salary_min: number | null;
  salary_max: number | null;
  salary_currency: string | null;
  salary_period: string | null;
  description_raw: string;
  requirements: JobRequirements;
  tags: string[];
  posted_at: string | null;
  created_at: string | null;
}

export interface JobRequirements {
  hard_skills?: { name: string; required: boolean; years: number }[];
  soft_skills?: string[];
  responsibilities?: string[];
  must_have?: string[];
  nice_to_have?: string[];
  education_required?: string;
  years_experience?: number;
  seniority?: string;
  languages?: string[];
  benefits?: string[];
  red_flags?: string[];
}

export interface MatchAnalysis {
  verdict: string;
  strongest_arguments: string[];
  gaps: string[];
  gap_mitigation: string[];
  keywords_to_add: string[];
  estimated_fit: number;
}

export interface MatchResult {
  job_id: number;
  resume_id: number;
  score: number;
  semantic_score: number;
  skill_score: number;
  seniority_score: number;
  matched_skills: string[];
  missing_skills: string[];
  analysis: MatchAnalysis | null;
}

export interface JobWithMatch {
  job: Job;
  match: MatchResult | null;
}

export interface SearchResponse {
  total: number;
  results: JobWithMatch[];
  resume_id: number | null;
}

export type ApplicationStatus =
  | "saved"
  | "applied"
  | "recruiter_contact"
  | "technical_test"
  | "final_interview"
  | "offer"
  | "rejected"
  | "withdrawn";

export interface Task {
  id: number;
  title: string;
  detail: string;
  category: string;
  done: boolean;
  due_at: string | null;
  order_index: number;
}

export interface Application {
  id: number;
  job_id: number;
  resume_id: number | null;
  status: ApplicationStatus;
  board_order: number;
  notes: string;
  cover_letter: string | null;
  applied_at: string | null;
  next_action_at: string | null;
  salary_expectation: string | null;
  contact_name: string | null;
  contact_url: string | null;
  created_at: string;
  updated_at: string;
  job: Job | null;
  tasks: Task[];
  match_score: number | null;
}

export interface BoardColumn {
  status: ApplicationStatus;
  label: string;
  applications: Application[];
}

export interface Board {
  columns: BoardColumn[];
  stats: {
    total: number;
    applied: number;
    interviews: number;
    offers: number;
    rejected: number;
    response_rate: number;
    offer_rate: number;
    overdue_tasks: number;
  };
}

export interface DiffLine {
  kind: "equal" | "insert" | "delete";
  text: string;
}

export interface BulletDiff {
  experience_index: number;
  bullet_index: number;
  company: string;
  role: string;
  original: string;
  suggestion: string;
  rationale: string;
  invented_facts: boolean;
  words: DiffLine[];
}

export interface TailorResponse {
  resume_id: number;
  job_id: number | null;
  summary_before: string;
  summary_after: string;
  summary_diff: DiffLine[];
  bullet_diffs: BulletDiff[];
  added_keywords: string[];
  warnings: string[];
}

export interface CompanyIntel {
  company_name: string;
  summary: string;
  industry: string;
  size: string;
  headquarters: string;
  founded: string;
  funding_stage: string;
  culture_notes: string[];
  tech_stack: string[];
  products: string[];
  recent_news: { title: string; summary: string; url: string; date: string }[];
  talking_points: string[];
  questions_to_ask: string[];
  sources: string[];
  confidence: string;
}

export interface InterviewIntel {
  company_name: string;
  role: string;
  stages: {
    order: number;
    name: string;
    format: string;
    duration: string;
    focus: string;
    how_to_prepare: string[];
  }[];
  assessment_types: string[];
  common_questions: { question: string; type: string; why_asked: string }[];
  technical_topics: string[];
  difficulty: string;
  typical_duration: string;
  tips: string[];
  sources: string[];
  confidence: string;
}

export interface SalaryBenchmark {
  role: string;
  location: string;
  currency: string;
  period: string;
  p25: number;
  p50: number;
  p75: number;
  reasoning: string;
  negotiation_script: string[];
  leverage_points: string[];
  sources: string[];
  confidence: string;
}

export interface JobBrief {
  job_id: number;
  company: CompanyIntel | null;
  interview: InterviewIntel | null;
  salary: SalaryBenchmark | null;
  match: MatchResult | null;
  errors: string[];
}

export interface CoverLetter {
  subject: string;
  body: string;
  highlighted_projects: string[];
  word_count: number;
}

export interface AnswerFeedback {
  score: number;
  strengths: string[];
  improvements: string[];
  missing_points: string[];
  star_compliance: string;
  model_answer: string;
}

export interface InterviewReply {
  feedback: AnswerFeedback;
  next_question: string;
  question_type: string;
  is_final: boolean;
}

export interface InterviewSession {
  id: number;
  job_id: number | null;
  resume_id: number | null;
  mode: string;
  transcript: {
    role: string;
    content: string;
    question_type?: string;
    feedback?: AnswerFeedback;
  }[];
  summary: Record<string, unknown> | null;
  finished: boolean;
  created_at: string;
}

export interface InterviewSummary {
  overall_score: number;
  technical_score: number;
  communication_score: number;
  verdict: string;
  top_strengths: string[];
  priority_improvements: string[];
  study_plan: string[];
}

export interface QAEntry {
  id: number;
  question: string;
  answer: string;
  tags: string[];
  times_used: number;
  created_at: string;
}

export interface Health {
  status: string;
  database: boolean;
  llm: { configured: boolean; model: string; effort: string };
  embeddings: { provider: string; dim: number };
  job_sources: string[];
}
