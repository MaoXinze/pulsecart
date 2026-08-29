import { defHttp } from '/@/utils/http/axios';

const API = '/api/v1';
const silentSuccess = { successMessageMode: 'none' as const };

export type SentimentLabel = 'positive' | 'neutral' | 'negative';
export type ReviewTaskStatus = 'pending' | 'approved' | 'verified' | 'rejected';
export type IssueStatus = 'open' | 'in_progress' | 'pending_validation' | 'closed';

export interface DatasetReport {
  dataset_version: string;
  source_filename: string;
  received_rows: number;
  valid_rows: number;
  rejected_rows: number;
  rejection_reasons: Record<string, number>;
}

export interface DatasetItem {
  dataset_version: string;
  source_filename: string;
  status: string;
  file_sha256: string;
  received_rows: number;
  valid_rows: number;
  rejected_rows: number;
  rejection_reasons: Record<string, number>;
  created_at?: string;
}

export interface ReviewTask {
  task_id: string;
  dataset_version: string;
  review_id: string;
  sampling_group: string;
  sampling_reason: string;
  assigned_role: string;
  review_status: ReviewTaskStatus;
  model_version?: string;
  system_sentiment?: SentimentLabel;
  system_aspects: string[];
  system_confidence?: number;
  reviewer_sentiment?: SentimentLabel;
  reviewer_aspects: string[];
  reviewer_note: string;
  reviewer_id?: string;
  reviewed_at?: string;
  review?: {
    product_id: string;
    category_id?: string;
    review_text: string;
    reviewed_at: string;
    channel?: string;
    rating?: number;
    product_version?: string;
  };
}

export interface AnalysisRun {
  id: string;
  dataset_version: string;
  model_version: string;
  status: string;
  source_kind: 'human_reviewed';
  metrics: Record<string, unknown>;
  error_message?: string;
  created_at?: string;
}

export interface ProductIssue {
  id: string;
  dataset_version: string;
  title: string;
  aspect: string;
  severity: 'low' | 'medium' | 'high' | 'critical';
  status: IssueStatus;
  description: string;
  source_review_ids: string[];
  owner_user_id?: string;
  resolution_note?: string;
  created_at?: string;
  updated_at?: string;
}

export function bootstrapDemo() {
  return defHttp.post<{ dataset_version: string; report: DatasetReport; reused: boolean; review_tasks_inserted: number }>(
    {
      url: `${API}/demo/bootstrap`,
    },
    silentSuccess
  );
}

export function getDatasets() {
  return defHttp.get<DatasetItem[]>({ url: `${API}/datasets` }, silentSuccess);
}

export function uploadDataset(file: File, fieldMapping?: Record<string, string>) {
  const form = new FormData();
  form.append('file', file);
  if (fieldMapping) form.append('field_mapping', JSON.stringify(fieldMapping));
  return defHttp.request<{ dataset_version: string; report: DatasetReport; reused: boolean }>(
    {
      url: `${API}/datasets/imports`,
      method: 'POST',
      data: form,
      headers: { 'Content-Type': 'multipart/form-data' },
    },
    silentSuccess
  );
}

export function getReviewTasks(params: { status?: ReviewTaskStatus; dataset_version?: string; limit?: number } = {}) {
  return defHttp.get<ReviewTask[]>({ url: `${API}/review-tasks`, params }, silentSuccess);
}

export function updateReviewTask(
  taskId: string,
  payload: {
    review_status: ReviewTaskStatus;
    reviewer_sentiment?: SentimentLabel;
    reviewer_aspects: string[];
    reviewer_note: string;
  }
) {
  return defHttp.request<ReviewTask>({ url: `${API}/review-tasks/${encodeURIComponent(taskId)}`, method: 'PATCH', data: payload }, silentSuccess);
}

export function getAnalysisRuns(datasetVersion?: string) {
  return defHttp.get<AnalysisRun[]>(
    { url: `${API}/analysis-runs`, params: datasetVersion ? { dataset_version: datasetVersion } : {} },
    silentSuccess
  );
}

export function createAnalysisRun(datasetVersion: string, modelVersion: string) {
  return defHttp.post<AnalysisRun>(
    {
      url: `${API}/analysis-runs`,
      data: { dataset_version: datasetVersion, model_version: modelVersion, source_kind: 'human_reviewed' },
    },
    silentSuccess
  );
}

export function syncAnalysisRun(runId: string) {
  return defHttp.post<AnalysisRun>({ url: `${API}/analysis-runs/${encodeURIComponent(runId)}/sync` }, silentSuccess);
}

export function getIssues(params: { dataset_version?: string; status?: IssueStatus } = {}) {
  return defHttp.get<ProductIssue[]>({ url: `${API}/issues`, params }, silentSuccess);
}

export function createIssue(payload: {
  dataset_version: string;
  title: string;
  aspect: string;
  severity: ProductIssue['severity'];
  description: string;
  source_review_ids: string[];
}) {
  return defHttp.post<ProductIssue>({ url: `${API}/issues`, data: payload }, silentSuccess);
}

export function updateIssue(issueId: string, payload: { status: IssueStatus; resolution_note: string; owner_user_id?: string }) {
  return defHttp.request<ProductIssue>({ url: `${API}/issues/${encodeURIComponent(issueId)}`, method: 'PATCH', data: payload }, silentSuccess);
}
