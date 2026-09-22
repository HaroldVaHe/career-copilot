import type {
  Application,
  ApplicationStatus,
  AtsReport,
  Board,
  CompanyIntel,
  CoverLetter,
  Health,
  InterviewIntel,
  InterviewReply,
  InterviewSession,
  InterviewSummary,
  Job,
  JobBrief,
  MatchAnalysis,
  MatchResult,
  QAEntry,
  Resume,
  ResumeSummary,
  SalaryBenchmark,
  SearchResponse,
  TailorResponse,
  Task,
} from "./types";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const API = `${BASE}/api/v1`;

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly code?: string,
  ) {
    super(message);
  }

  /** Falta la API key de Anthropic: la UI ofrece ir a Ajustes en vez de un error seco. */
  get isLlmUnavailable() {
    return this.status === 503 || this.code === "llm_unavailable";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API}${path}`, {
      ...init,
      headers: {
        ...(init?.body instanceof FormData ? {} : { "Content-Type": "application/json" }),
        ...init?.headers,
      },
      cache: "no-store",
    });
  } catch {
    throw new ApiError(
      `No se pudo conectar con la API en ${BASE}. ¿Está arrancado el backend?`,
      0,
    );
  }

  if (res.status === 204) return undefined as T;

  const payload = await res.json().catch(() => null);
  if (!res.ok) {
    const detail =
      (payload && (payload.detail ?? payload.message)) || `Error ${res.status}`;
    throw new ApiError(
      typeof detail === "string" ? detail : JSON.stringify(detail),
      res.status,
      payload?.code,
    );
  }
  return payload as T;
}

const qs = (params: Record<string, unknown>) => {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== "") {
      search.set(key, String(value));
    }
  }
  const out = search.toString();
  return out ? `?${out}` : "";
};

export interface JobSearchQuery {
  q?: string;
  min_score?: number;
  remote_type?: string[];
  seniority?: string[];
  company?: string;
  salary_min?: number;
  required_skills?: string[];
  posted_within_days?: number;
  source?: string[];
  semantic?: string;
  limit?: number;
  offset?: number;
  sort?: "score" | "date" | "salary";
}

export const api = {
  health: () => request<Health>("/health"),
  stats: () =>
    request<{
      resumes: number;
      jobs_indexed: number;
      applications: number;
      best_resume_score: number | null;
    }>("/stats"),
  getPreferences: () => request<Record<string, string>>("/preferences"),
  setPreferences: (prefs: Record<string, string>) =>
    request<Record<string, string>>("/preferences", {
      method: "PUT",
      body: JSON.stringify(prefs),
    }),

  // --- CV ---
  listResumes: () => request<ResumeSummary[]>("/resumes"),
  getResume: (id: number) => request<Resume>(`/resumes/${id}`),
  uploadResume: (form: FormData) =>
    request<Resume>("/resumes", { method: "POST", body: form }),
  updateResume: (id: number, body: Record<string, unknown>) =>
    request<Resume>(`/resumes/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
  deleteResume: (id: number) => request<void>(`/resumes/${id}`, { method: "DELETE" }),
  reaudit: (id: number, useLlm = true) =>
    request<AtsReport>(`/resumes/${id}/audit${qs({ use_llm: useLlm })}`, { method: "POST" }),
  tailor: (body: {
    resume_id: number;
    job_id?: number;
    job_description?: string;
    inject_gaps?: boolean;
    tone?: string;
  }) => request<TailorResponse>("/resumes/tailor", { method: "POST", body: JSON.stringify(body) }),
  saveVariant: (body: Record<string, unknown>) =>
    request<Resume>("/resumes/variants", { method: "POST", body: JSON.stringify(body) }),

  // --- Vacantes ---
  sources: () => request<{ sources: string[]; note: string }>("/jobs/sources"),
  ingest: (body: { sources?: string[]; query?: string; limit?: number; analyze?: boolean }) =>
    request<{ results: { source: string; fetched?: number; created?: number; error?: string }[] }>(
      "/jobs/ingest",
      { method: "POST", body: JSON.stringify(body) },
    ),
  searchJobs: (body: JobSearchQuery, resumeId?: number) =>
    request<SearchResponse>(`/jobs/search${qs({ resume_id: resumeId })}`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  createJob: (body: Record<string, unknown>) =>
    request<Job>("/jobs", { method: "POST", body: JSON.stringify(body) }),
  getJob: (id: number) => request<Job>(`/jobs/${id}`),
  analyzeJob: (id: number) => request<Job>(`/jobs/${id}/analyze`, { method: "POST" }),
  deleteJob: (id: number) => request<void>(`/jobs/${id}`, { method: "DELETE" }),
  match: (jobId: number, opts: { resumeId?: number; deep?: boolean } = {}) =>
    request<MatchResult>(
      `/jobs/${jobId}/match${qs({ resume_id: opts.resumeId, deep: opts.deep })}`,
    ),
  deepAnalysis: (jobId: number, resumeId?: number) =>
    request<MatchAnalysis>(`/jobs/${jobId}/analysis${qs({ resume_id: resumeId })}`, {
      method: "POST",
    }),
  reindex: () => request<{ status: string }>("/jobs/reindex", { method: "POST" }),

  // --- Postulaciones ---
  board: () => request<Board>("/applications/board"),
  listApplications: () => request<Application[]>("/applications"),
  createApplication: (body: {
    job_id: number;
    resume_id?: number;
    status?: ApplicationStatus;
    notes?: string;
    generate_tasks?: boolean;
  }) => request<Application>("/applications", { method: "POST", body: JSON.stringify(body) }),
  getApplication: (id: number) => request<Application>(`/applications/${id}`),
  updateApplication: (id: number, body: Record<string, unknown>) =>
    request<Application>(`/applications/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
  deleteApplication: (id: number) =>
    request<void>(`/applications/${id}`, { method: "DELETE" }),
  addTask: (appId: number, body: { title: string; detail?: string; category?: string }) =>
    request<Task>(`/applications/${appId}/tasks`, { method: "POST", body: JSON.stringify(body) }),
  generateTasks: (appId: number, replace = false) =>
    request<Task[]>(`/applications/${appId}/tasks/generate${qs({ replace })}`, { method: "POST" }),
  updateTask: (taskId: number, body: Record<string, unknown>) =>
    request<Task>(`/applications/tasks/${taskId}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),
  deleteTask: (taskId: number) =>
    request<void>(`/applications/tasks/${taskId}`, { method: "DELETE" }),
  coverLetter: (appId: number, tone = "professional") =>
    request<CoverLetter>(`/applications/${appId}/cover-letter${qs({ tone })}`, { method: "POST" }),

  // --- Inteligencia ---
  companyIntel: (jobId: number, force = false) =>
    request<CompanyIntel>(`/intel/jobs/${jobId}/company${qs({ force })}`),
  interviewIntel: (jobId: number, force = false) =>
    request<InterviewIntel>(`/intel/jobs/${jobId}/interview${qs({ force })}`),
  salaryIntel: (jobId: number, resumeId?: number) =>
    request<SalaryBenchmark>(`/intel/jobs/${jobId}/salary${qs({ resume_id: resumeId })}`),
  brief: (jobId: number, resumeId?: number) =>
    request<JobBrief>(`/intel/jobs/${jobId}/brief${qs({ resume_id: resumeId })}`),

  // --- Entrevistas ---
  startInterview: (body: {
    job_id?: number;
    resume_id?: number;
    mode?: string;
    difficulty?: string;
    language?: string;
  }) =>
    request<{ session: InterviewSession; reply: InterviewReply }>("/interview/sessions", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  listInterviews: () => request<InterviewSession[]>("/interview/sessions"),
  getInterview: (id: number) => request<InterviewSession>(`/interview/sessions/${id}`),
  answerInterview: (id: number, answer: string) =>
    request<InterviewReply>(`/interview/sessions/${id}/answer`, {
      method: "POST",
      body: JSON.stringify({ answer }),
    }),
  finishInterview: (id: number) =>
    request<InterviewSummary>(`/interview/sessions/${id}/finish`, { method: "POST" }),
  listQa: (search?: string) => request<QAEntry[]>(`/interview/qa${qs({ search })}`),
  createQa: (body: { question: string; answer?: string; tags?: string[] }) =>
    request<QAEntry>("/interview/qa", { method: "POST", body: JSON.stringify(body) }),
  updateQa: (id: number, body: { question: string; answer: string; tags: string[] }) =>
    request<QAEntry>(`/interview/qa/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
  deleteQa: (id: number) => request<void>(`/interview/qa/${id}`, { method: "DELETE" }),
};
