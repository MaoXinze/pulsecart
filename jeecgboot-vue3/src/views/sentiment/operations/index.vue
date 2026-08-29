<template>
  <main class="pulsecart-operations">
    <section class="workspace-header">
      <div>
        <div class="workspace-kicker">PULSECART / OPERATIONS</div>
        <h1>商品体验问题闭环</h1>
        <p>从评论证据到问题验证，在一个工作台完成审核、训练和处置。</p>
      </div>
      <div class="workspace-actions">
        <a-tooltip title="刷新工作台"
          ><a-button class="icon-button" :loading="isRefreshing" @click="refreshAll"><ReloadOutlined /></a-button
        ></a-tooltip>
        <a-upload :show-upload-list="false" accept=".csv" :before-upload="beforeUpload">
          <a-button :loading="loading.upload"><CloudUploadOutlined /> 导入 CSV</a-button>
        </a-upload>
        <a-button type="primary" :loading="loading.bootstrap" @click="handleBootstrap"><DatabaseOutlined /> 准备演示数据</a-button>
      </div>
    </section>

    <section class="dataset-band" :class="{ 'is-empty': !activeDataset }" :aria-busy="loading.datasets">
      <template v-if="activeDataset">
        <div class="dataset-band-title">
          <span class="dataset-icon"><DatabaseOutlined /></span>
          <div
            ><span>当前数据集</span><strong>{{ activeDataset.source_filename }}</strong></div
          >
        </div>
        <dl class="dataset-facts">
          <div
            ><dt>版本</dt><dd class="mono">{{ activeDataset.dataset_version }}</dd></div
          >
          <div
            ><dt>有效评论</dt><dd>{{ activeDataset.valid_rows.toLocaleString() }} 条</dd></div
          >
          <div
            ><dt>拒绝记录</dt><dd>{{ activeDataset.rejected_rows.toLocaleString() }} 条</dd></div
          >
          <div
            ><dt>训练状态</dt
            ><dd
              ><a-tag :color="trainingReady ? 'success' : 'gold'">{{ trainingReady ? '可创建运行' : `还需 ${remainingReviews} 条审核` }}</a-tag></dd
            ></div
          >
        </dl>
      </template>
      <a-empty v-else description="尚未导入数据集" :image-style="{ height: '36px' }" />
    </section>

    <a-row class="metric-grid" :gutter="[12, 12]">
      <a-col :xs="12" :sm="12" :lg="6"
        ><div class="metric-panel metric-dataset"
          ><span class="metric-icon"><DatabaseOutlined /></span><span class="metric-label">有效评论</span
          ><strong>{{ activeDataset?.valid_rows?.toLocaleString() || 0 }}</strong
          ><span class="metric-foot">当前数据集</span></div
        ></a-col
      >
      <a-col :xs="12" :sm="12" :lg="6"
        ><div class="metric-panel metric-review"
          ><span class="metric-icon"><CheckCircleOutlined /></span><span class="metric-label">已完成审核</span><strong>{{ reviewedTaskCount }}</strong
          ><a-progress :percent="reviewProgress" :show-info="false" :stroke-color="'#16805d'" size="small" /><span class="metric-foot"
            >{{ reviewedTaskCount }} / {{ totalTaskCount || 0 }} 条</span
          ></div
        ></a-col
      >
      <a-col :xs="12" :sm="12" :lg="6"
        ><div class="metric-panel metric-pending"
          ><span class="metric-icon"><FileSearchOutlined /></span><span class="metric-label">待审核任务</span><strong>{{ pendingTaskCount }}</strong
          ><span class="metric-foot">优先处理证据样本</span></div
        ></a-col
      >
      <a-col :xs="12" :sm="12" :lg="6"
        ><div class="metric-panel metric-issue"
          ><span class="metric-icon"><FlagOutlined /></span><span class="metric-label">待闭环问题</span><strong>{{ activeIssueCount }}</strong
          ><span class="metric-foot">{{ issues.length }} 张问题卡</span></div
        ></a-col
      >
    </a-row>

    <a-card title="人工审核队列" :bordered="false" class="workspace-card review-card" :loading="loading.tasks">
      <template #extra>
        <a-space>
          <a-select v-model:value="taskFilter" style="width: 128px" @change="loadTasks">
            <a-select-option value="">全部状态</a-select-option>
            <a-select-option value="pending">待审核</a-select-option>
            <a-select-option value="approved">已通过</a-select-option>
            <a-select-option value="verified">已复核</a-select-option>
            <a-select-option value="rejected">无效文本</a-select-option>
          </a-select>
          <a-button @click="loadTasks">刷新</a-button>
        </a-space>
      </template>
      <a-table
        class="workstream-table"
        :columns="taskColumns"
        :data-source="tasks"
        :pagination="{ pageSize: 10, showSizeChanger: false }"
        row-key="task_id"
        size="middle"
        :scroll="{ x: 980 }"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'review'">
            <div class="review-copy">{{ record.review?.review_text || '评论证据不存在' }}</div>
            <div class="review-meta"
              >{{ record.review?.product_id }} · {{ record.review?.channel || '未知渠道' }} · {{ record.review?.rating || '-' }} 星</div
            >
          </template>
          <template v-else-if="column.key === 'system'">
            <a-tag v-if="record.system_sentiment" :color="sentimentColor(record.system_sentiment)">{{
              sentimentLabel(record.system_sentiment)
            }}</a-tag>
            <span class="confidence-text">{{ confidenceText(record.system_confidence) }}</span>
          </template>
          <template v-else-if="column.key === 'status'">
            <a-tag :color="taskStatusColor(record.review_status)">{{ taskStatusLabel(record.review_status) }}</a-tag>
          </template>
          <template v-else-if="column.key === 'action'">
            <a-button size="small" type="link" @click="openReview(record)">审核</a-button>
          </template>
        </template>
      </a-table>
    </a-card>

    <a-row :gutter="[24, 24]" class="bottom-workstreams">
      <a-col :xs="24" :xl="11">
        <a-card title="分析运行" :bordered="false" class="workspace-card compact-card" :loading="loading.runs">
          <template #extra><a-button type="primary" :disabled="!activeDataset" @click="openRun">创建运行</a-button></template>
          <a-table class="workstream-table" :columns="runColumns" :data-source="runs" :pagination="false" row-key="id" size="small">
            <template #bodyCell="{ column, record }">
              <template v-if="column.key === 'status'"
                ><a-tag :color="runStatusColor(record.status)">{{ runStatusLabel(record.status) }}</a-tag></template
              >
              <template v-else-if="column.key === 'metrics'">{{ runMetricText(record) }}</template>
              <template v-else-if="column.key === 'created_at'">{{ formatTime(record.created_at) }}</template>
              <template v-else-if="column.key === 'action'">
                <a-button
                  v-if="['queued', 'running'].includes(record.status)"
                  size="small"
                  type="link"
                  :loading="syncingRunId === record.id"
                  @click="syncRun(record)"
                  >同步</a-button
                >
              </template>
            </template>
          </a-table>
        </a-card>
      </a-col>
      <a-col :xs="24" :xl="13">
        <a-card title="商品体验问题卡" :bordered="false" class="workspace-card compact-card" :loading="loading.issues">
          <template #extra><a-button type="primary" :disabled="!activeDataset" @click="openIssue">新建问题卡</a-button></template>
          <a-list class="issue-list" :data-source="issues" item-layout="horizontal">
            <template #renderItem="{ item }">
              <a-list-item>
                <a-list-item-meta :description="item.description || '尚未填写问题说明'">
                  <template #title
                    ><a-space :size="6" wrap
                      ><span>{{ item.title }}</span
                      ><a-tag :color="severityColor(item.severity)">{{ severityLabel(item.severity) }}</a-tag
                      ><a-tag>{{ issueStatusLabel(item.status) }}</a-tag></a-space
                    ></template
                  >
                  <template #avatar
                    ><a-avatar shape="square" :style="{ background: severityColor(item.severity) }">{{ item.aspect.slice(0, 1) }}</a-avatar></template
                  >
                </a-list-item-meta>
                <template #actions>
                  <a-button v-if="nextIssueStatus(item.status)" size="small" type="link" @click="openIssueUpdate(item)">{{
                    nextIssueLabel(item.status)
                  }}</a-button>
                </template>
              </a-list-item>
            </template>
          </a-list>
          <a-empty v-if="!issues.length" description="暂无问题卡。请从完成审核的评论中归因后创建。" />
        </a-card>
      </a-col>
    </a-row>

    <a-modal v-model:open="reviewOpen" title="审核评论" :confirm-loading="savingReview" @ok="saveReview">
      <div v-if="selectedTask" class="review-modal">
        <p class="review-evidence">{{ selectedTask.review?.review_text }}</p>
        <a-form layout="vertical">
          <a-form-item label="审核结论"
            ><a-select v-model:value="reviewForm.review_status"
              ><a-select-option value="approved">通过</a-select-option><a-select-option value="verified">复核通过</a-select-option
              ><a-select-option value="rejected">无效文本</a-select-option></a-select
            ></a-form-item
          >
          <a-form-item v-if="reviewForm.review_status !== 'rejected'" label="人工情感"
            ><a-radio-group v-model:value="reviewForm.reviewer_sentiment"
              ><a-radio-button value="positive">正向</a-radio-button><a-radio-button value="neutral">中性</a-radio-button
              ><a-radio-button value="negative">负向</a-radio-button></a-radio-group
            ></a-form-item
          >
          <a-form-item label="关联属性（逗号分隔）"
            ><a-input v-model:value="reviewForm.aspectText" placeholder="例如：续航, 充电, 噪音"
          /></a-form-item>
          <a-form-item label="审核说明"
            ><a-textarea
              v-model:value="reviewForm.reviewer_note"
              :rows="3"
              :placeholder="reviewForm.review_status === 'rejected' ? '标记无效文本时必填' : '可选，记录判断依据'"
          /></a-form-item>
        </a-form>
      </div>
    </a-modal>

    <a-modal v-model:open="runOpen" title="创建正式分析运行" :confirm-loading="savingRun" @ok="saveRun">
      <a-form layout="vertical"
        ><a-form-item label="数据集"><a-input :value="activeDataset?.dataset_version" disabled /></a-form-item
        ><a-form-item label="模型版本"><a-input v-model:value="runModelVersion" placeholder="baseline-tfidf-logreg-v1" /></a-form-item
      ></a-form>
    </a-modal>

    <a-modal v-model:open="issueOpen" :title="editingIssue ? '推进问题卡' : '创建商品体验问题卡'" :confirm-loading="savingIssue" @ok="saveIssue">
      <a-form layout="vertical">
        <template v-if="!editingIssue">
          <a-form-item label="问题标题"><a-input v-model:value="issueForm.title" /></a-form-item>
          <a-row :gutter="12"
            ><a-col :span="12"
              ><a-form-item label="体验属性"><a-input v-model:value="issueForm.aspect" placeholder="如：续航" /></a-form-item></a-col
            ><a-col :span="12"
              ><a-form-item label="严重度"
                ><a-select v-model:value="issueForm.severity"
                  ><a-select-option value="low">低</a-select-option><a-select-option value="medium">中</a-select-option
                  ><a-select-option value="high">高</a-select-option><a-select-option value="critical">紧急</a-select-option></a-select
                ></a-form-item
              ></a-col
            ></a-row
          >
          <a-form-item label="问题说明"><a-textarea v-model:value="issueForm.description" :rows="4" /></a-form-item>
          <a-form-item label="来源评论 ID（逗号分隔）"
            ><a-input v-model:value="issueForm.reviewIds" placeholder="可从审核队列复制 review_id"
          /></a-form-item>
        </template>
        <template v-else
          ><a-alert type="info" :message="`将状态推进到 ${nextIssueLabel(editingIssue.status)}`" show-icon /><a-form-item
            v-if="nextIssueStatus(editingIssue.status) === 'closed'"
            class="mt-4"
            label="关闭验证说明"
            ><a-textarea v-model:value="issueForm.resolution_note" :rows="4" placeholder="关闭前必须记录验证证据" /></a-form-item
        ></template>
      </a-form>
    </a-modal>
  </main>
</template>

<script lang="ts" setup>
  import { computed, onMounted, reactive, ref } from 'vue';
  import { message } from 'ant-design-vue';
  import {
    CheckCircleOutlined,
    CloudUploadOutlined,
    DatabaseOutlined,
    FileSearchOutlined,
    FlagOutlined,
    ReloadOutlined,
  } from '@ant-design/icons-vue';
  import {
    bootstrapDemo,
    createAnalysisRun,
    createIssue,
    getAnalysisRuns,
    getDatasets,
    getIssues,
    getReviewTasks,
    syncAnalysisRun,
    updateIssue,
    updateReviewTask,
    uploadDataset,
    type AnalysisRun,
    type DatasetItem,
    type IssueStatus,
    type ProductIssue,
    type ReviewTask,
    type ReviewTaskStatus,
    type SentimentLabel,
  } from '../pulsecart.api';

  const ACTION_NOTICE_KEY = 'pulsecart-action';
  const notifySuccess = (content: string) => message.success({ content, key: ACTION_NOTICE_KEY, duration: 2.5 });
  const notifyWarning = (content: string) => message.warning({ content, key: ACTION_NOTICE_KEY, duration: 2.5 });

  const datasets = ref<DatasetItem[]>([]);
  const tasks = ref<ReviewTask[]>([]);
  const summaryTasks = ref<ReviewTask[]>([]);
  const runs = ref<AnalysisRun[]>([]);
  const issues = ref<ProductIssue[]>([]);
  const taskFilter = ref<ReviewTaskStatus | ''>('pending');
  const loading = reactive({ datasets: false, tasks: false, runs: false, issues: false, bootstrap: false, upload: false });
  const reviewOpen = ref(false);
  const runOpen = ref(false);
  const issueOpen = ref(false);
  const savingReview = ref(false);
  const savingRun = ref(false);
  const savingIssue = ref(false);
  const syncingRunId = ref('');
  const selectedTask = ref<ReviewTask | null>(null);
  const editingIssue = ref<ProductIssue | null>(null);
  const runModelVersion = ref('baseline-tfidf-logreg-v1');
  const reviewForm = reactive({
    review_status: 'approved' as ReviewTaskStatus,
    reviewer_sentiment: 'negative' as SentimentLabel,
    aspectText: '',
    reviewer_note: '',
  });
  const issueForm = reactive({
    title: '',
    aspect: '',
    severity: 'medium' as ProductIssue['severity'],
    description: '',
    reviewIds: '',
    resolution_note: '',
  });
  const activeDataset = computed(() => datasets.value[0]);
  const totalTaskCount = computed(() => summaryTasks.value.length);
  const reviewedTaskCount = computed(() => summaryTasks.value.filter((item) => ['approved', 'verified'].includes(item.review_status)).length);
  const pendingTaskCount = computed(() => summaryTasks.value.filter((item) => item.review_status === 'pending').length);
  const reviewProgress = computed(() => (totalTaskCount.value ? Math.round((reviewedTaskCount.value / totalTaskCount.value) * 100) : 0));
  const trainingReady = computed(() => reviewedTaskCount.value >= 15);
  const remainingReviews = computed(() => Math.max(0, 15 - reviewedTaskCount.value));
  const activeIssueCount = computed(() => issues.value.filter((item) => item.status !== 'closed').length);
  const isRefreshing = computed(() => loading.datasets || loading.tasks || loading.runs || loading.issues);
  const taskColumns = [
    { title: '评论证据', key: 'review', width: 400 },
    { title: '抽样原因', dataIndex: 'sampling_reason', key: 'sampling_reason', width: 140 },
    { title: '模型判断', key: 'system', width: 150 },
    { title: '状态', key: 'status', width: 110 },
    { title: '操作', key: 'action', width: 70, fixed: 'right' },
  ];
  const runColumns = [
    { title: '模型版本', dataIndex: 'model_version', key: 'model_version' },
    { title: '状态', key: 'status', width: 88 },
    { title: '样本 / 指标', key: 'metrics', width: 130 },
    { title: '创建时间', key: 'created_at', width: 150 },
    { title: '操作', key: 'action', width: 64 },
  ];
  async function loadDatasets() {
    loading.datasets = true;
    try {
      datasets.value = await getDatasets();
    } finally {
      loading.datasets = false;
    }
  }
  async function loadTasks() {
    loading.tasks = true;
    try {
      tasks.value = await getReviewTasks({
        dataset_version: activeDataset.value?.dataset_version,
        status: taskFilter.value || undefined,
        limit: 100,
      });
    } finally {
      loading.tasks = false;
    }
  }
  async function loadTaskSummary() {
    summaryTasks.value = activeDataset.value ? await getReviewTasks({ dataset_version: activeDataset.value.dataset_version, limit: 300 }) : [];
  }
  async function loadRuns() {
    loading.runs = true;
    try {
      runs.value = await getAnalysisRuns(activeDataset.value?.dataset_version);
    } finally {
      loading.runs = false;
    }
  }
  async function loadIssues() {
    loading.issues = true;
    try {
      issues.value = await getIssues(activeDataset.value ? { dataset_version: activeDataset.value.dataset_version } : {});
    } finally {
      loading.issues = false;
    }
  }
  async function refreshAll() {
    await loadDatasets();
    await Promise.all([loadTasks(), loadTaskSummary(), loadRuns(), loadIssues()]);
  }
  async function handleBootstrap() {
    loading.bootstrap = true;
    try {
      const result = await bootstrapDemo();
      notifySuccess(`${result.report.valid_rows} 条合成评论和 ${result.review_tasks_inserted} 条审核任务已准备`);
      await refreshAll();
    } finally {
      loading.bootstrap = false;
    }
  }
  async function beforeUpload(file: File) {
    loading.upload = true;
    try {
      const response = await uploadDataset(file);
      notifySuccess(`数据集 ${response.dataset_version} 导入校验完成`);
      await refreshAll();
    } catch {
      /* The HTTP client provides the single request error message. */
    } finally {
      loading.upload = false;
    }
    return false;
  }
  function openReview(task: ReviewTask) {
    selectedTask.value = task;
    Object.assign(reviewForm, {
      review_status: task.review_status === 'rejected' ? 'rejected' : 'approved',
      reviewer_sentiment: task.reviewer_sentiment || task.system_sentiment || 'neutral',
      aspectText: task.reviewer_aspects?.join(', ') || task.system_aspects?.join(', ') || '',
      reviewer_note: task.reviewer_note || '',
    });
    reviewOpen.value = true;
  }
  async function saveReview() {
    if (!selectedTask.value) return;
    if (['approved', 'verified'].includes(reviewForm.review_status) && !reviewForm.reviewer_sentiment) {
      notifyWarning('请填写人工情感结论');
      return;
    }
    if (reviewForm.review_status === 'rejected' && !reviewForm.reviewer_note.trim()) {
      notifyWarning('标记无效文本时必须填写审核说明');
      return;
    }
    savingReview.value = true;
    try {
      await updateReviewTask(selectedTask.value.task_id, {
        review_status: reviewForm.review_status,
        reviewer_sentiment: reviewForm.review_status === 'rejected' ? undefined : reviewForm.reviewer_sentiment,
        reviewer_aspects: reviewForm.aspectText
          .split(/[,，]/)
          .map((item) => item.trim())
          .filter(Boolean),
        reviewer_note: reviewForm.reviewer_note,
      });
      reviewOpen.value = false;
      notifySuccess('审核结果已保存');
      await Promise.all([loadTasks(), loadTaskSummary(), loadRuns()]);
    } finally {
      savingReview.value = false;
    }
  }
  function openRun() {
    runOpen.value = true;
  }
  async function saveRun() {
    if (!activeDataset.value || !runModelVersion.value.trim()) {
      notifyWarning('请填写模型版本');
      return;
    }
    savingRun.value = true;
    try {
      await createAnalysisRun(activeDataset.value.dataset_version, runModelVersion.value.trim());
      runOpen.value = false;
      notifySuccess('分析运行已进入队列');
      await loadRuns();
    } finally {
      savingRun.value = false;
    }
  }
  async function syncRun(run: AnalysisRun) {
    syncingRunId.value = run.id;
    try {
      const updated = await syncAnalysisRun(run.id);
      notifySuccess(updated.status === 'succeeded' ? '训练结果已同步' : `训练状态已同步为 ${runStatusLabel(updated.status)}`);
      await loadRuns();
    } finally {
      syncingRunId.value = '';
    }
  }
  function openIssue() {
    editingIssue.value = null;
    Object.assign(issueForm, { title: '', aspect: '', severity: 'medium', description: '', reviewIds: '', resolution_note: '' });
    issueOpen.value = true;
  }
  function openIssueUpdate(item: ProductIssue) {
    editingIssue.value = item;
    issueForm.resolution_note = item.resolution_note || '';
    issueOpen.value = true;
  }
  async function saveIssue() {
    if (!activeDataset.value) return;
    savingIssue.value = true;
    try {
      if (editingIssue.value) {
        const status = nextIssueStatus(editingIssue.value.status);
        if (!status) return;
        if (status === 'closed' && !issueForm.resolution_note.trim()) {
          notifyWarning('关闭问题卡前必须填写验证说明');
          return;
        }
        await updateIssue(editingIssue.value.id, { status, resolution_note: issueForm.resolution_note });
      } else {
        if (!issueForm.title.trim() || !issueForm.aspect.trim()) {
          notifyWarning('请填写问题标题和体验属性');
          return;
        }
        await createIssue({
          dataset_version: activeDataset.value.dataset_version,
          title: issueForm.title.trim(),
          aspect: issueForm.aspect.trim(),
          severity: issueForm.severity,
          description: issueForm.description.trim(),
          source_review_ids: issueForm.reviewIds
            .split(/[,，]/)
            .map((item) => item.trim())
            .filter(Boolean),
        });
      }
      issueOpen.value = false;
      notifySuccess(editingIssue.value ? '问题卡状态已更新' : '问题卡已创建');
      await loadIssues();
    } finally {
      savingIssue.value = false;
    }
  }
  function runMetricText(run: AnalysisRun) {
    const training = run.metrics?.training as { metrics?: { macro_f1?: number } } | undefined;
    const macroF1 = training?.metrics?.macro_f1;
    return typeof macroF1 === 'number' ? `F1 ${macroF1.toFixed(3)}` : `已审核 ${Number(run.metrics?.reviewed_records || 0)} 条`;
  }
  const sentimentLabel = (value?: string) => ({ positive: '正向', neutral: '中性', negative: '负向' })[value || ''] || '-';
  const sentimentColor = (value?: string) => ({ positive: 'green', neutral: 'blue', negative: 'red' })[value || ''] || 'default';
  const confidenceText = (value?: number) => (value == null ? '' : `${Math.round(value * 100)}%`);
  const taskStatusLabel = (value: string) => ({ pending: '待审核', approved: '已通过', verified: '已复核', rejected: '无效文本' })[value] || value;
  const taskStatusColor = (value: string) => ({ pending: 'gold', approved: 'green', verified: 'cyan', rejected: 'red' })[value] || 'default';
  const runStatusLabel = (value: string) => ({ queued: '排队中', running: '执行中', succeeded: '已完成', failed: '失败' })[value] || value;
  const runStatusColor = (value: string) => ({ queued: 'gold', running: 'blue', succeeded: 'green', failed: 'red' })[value] || 'default';
  const severityLabel = (value: string) => ({ low: '低', medium: '中', high: '高', critical: '紧急' })[value] || value;
  const severityColor = (value: string) => ({ low: '#5f8d4e', medium: '#c68222', high: '#c64e33', critical: '#7c2637' })[value] || '#637382';
  const issueStatusLabel = (value: string) =>
    ({ open: '待处理', in_progress: '处理中', pending_validation: '待验证', closed: '已关闭' })[value] || value;
  const nextIssueStatus = (value: IssueStatus): IssueStatus | undefined =>
    ({ open: 'in_progress', in_progress: 'pending_validation', pending_validation: 'closed' })[value] as IssueStatus | undefined;
  const nextIssueLabel = (value: IssueStatus) => ({ open: '开始处理', in_progress: '提交验证', pending_validation: '验证关闭' })[value] || '';
  const formatTime = (value?: string) => (value ? new Date(value).toLocaleString('zh-CN', { hour12: false }) : '-');
  onMounted(refreshAll);
</script>

<style scoped lang="less">
  .pulsecart-operations {
    min-height: 100%;
    padding: 22px 24px 32px;
    color: #18232d;
    background: #f4f6f8;
  }

  .workspace-header {
    display: flex;
    align-items: flex-end;
    justify-content: space-between;
    gap: 20px;
    padding: 0 4px 20px;
    border-bottom: 1px solid #dbe3e9;
  }

  .workspace-kicker {
    margin-bottom: 8px;
    color: #60758a;
    font-size: 12px;
    font-weight: 700;
    line-height: 1;
  }

  .workspace-header h1 {
    margin: 0;
    color: #162733;
    font-size: 26px;
    font-weight: 700;
    line-height: 1.3;
    letter-spacing: 0;
  }

  .workspace-header p {
    margin: 6px 0 0;
    color: #66798a;
    font-size: 14px;
  }

  .workspace-actions {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
  }

  .icon-button {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 32px;
    min-width: 32px;
    padding: 0;
  }

  .dataset-band {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 28px;
    min-height: 84px;
    margin: 20px 0;
    padding: 16px 20px;
    background: #ffffff;
    border: 1px solid #dce5eb;
    border-radius: 6px;
  }

  .dataset-band.is-empty {
    justify-content: center;
  }

  .dataset-band-title {
    display: flex;
    align-items: center;
    gap: 12px;
    min-width: 215px;
  }

  .dataset-band-title span {
    display: block;
    margin-bottom: 2px;
    color: #6b7f8e;
    font-size: 12px;
  }

  .dataset-band-title strong {
    display: block;
    max-width: 280px;
    overflow: hidden;
    color: #1a2c38;
    font-size: 14px;
    line-height: 20px;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .dataset-icon,
  .metric-icon {
    display: inline-flex;
    align-items: center;
    justify-content: center;
  }

  .dataset-icon {
    width: 36px;
    height: 36px;
    color: #1d617f;
    font-size: 18px;
    background: #e7f1f6;
    border-radius: 6px;
  }

  .dataset-facts {
    display: grid;
    grid-template-columns: repeat(4, minmax(105px, 1fr));
    gap: 12px 28px;
    flex: 1;
    margin: 0;
  }

  .dataset-facts div {
    min-width: 0;
  }

  .dataset-facts dt {
    margin-bottom: 4px;
    color: #778794;
    font-size: 12px;
  }

  .dataset-facts dd {
    margin: 0;
    overflow: hidden;
    color: #263641;
    font-size: 14px;
    font-weight: 600;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .mono {
    font-family: Consolas, 'Courier New', monospace;
    font-size: 12px !important;
  }

  .metric-grid {
    margin-bottom: 26px;
  }

  .metric-panel {
    position: relative;
    display: flex;
    flex-direction: column;
    min-height: 142px;
    padding: 16px 18px 14px;
    overflow: hidden;
    background: #ffffff;
    border: 1px solid #dce5eb;
    border-radius: 6px;
  }

  .metric-panel::before {
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 3px;
    content: '';
  }

  .metric-dataset::before {
    background: #2f7899;
  }
  .metric-review::before {
    background: #16805d;
  }
  .metric-pending::before {
    background: #c68222;
  }
  .metric-issue::before {
    background: #c64e33;
  }

  .metric-icon {
    position: absolute;
    top: 15px;
    right: 16px;
    width: 30px;
    height: 30px;
    border-radius: 6px;
    font-size: 16px;
  }

  .metric-dataset .metric-icon {
    color: #1d617f;
    background: #e7f1f6;
  }
  .metric-review .metric-icon {
    color: #126848;
    background: #e7f5ee;
  }
  .metric-pending .metric-icon {
    color: #a3630f;
    background: #fff4df;
  }
  .metric-issue .metric-icon {
    color: #a83d27;
    background: #fbedeb;
  }

  .metric-label {
    color: #6e7d89;
    font-size: 13px;
  }

  .metric-panel strong {
    margin: 8px 0 2px;
    color: #1c2a34;
    font-size: 30px;
    font-weight: 700;
    line-height: 1.1;
  }

  .metric-panel :deep(.ant-progress) {
    margin-top: auto;
    margin-bottom: 8px;
  }

  .metric-foot {
    margin-top: auto;
    color: #7b8994;
    font-size: 12px;
  }

  .workspace-card {
    margin-bottom: 26px;
    overflow: hidden;
    border: 1px solid #dce5eb;
    border-radius: 6px;
    box-shadow: none;
  }

  .workspace-card :deep(.ant-card-head) {
    min-height: 60px;
    padding: 0 18px;
    background: #ffffff;
    border-bottom: 1px solid #dbe3e9;
  }

  .workspace-card :deep(.ant-card-head-title) {
    color: #1b2c37;
    font-size: 16px;
    font-weight: 700;
  }

  .workspace-card :deep(.ant-card-body) {
    padding: 0;
  }

  .review-card :deep(.ant-card-extra) {
    display: flex;
    align-items: center;
  }

  .workstream-table :deep(.ant-table) {
    border: 0;
    border-radius: 0;
  }

  .workstream-table :deep(.ant-table-thead > tr > th) {
    color: #687986;
    font-size: 12px;
    font-weight: 600;
    background: #f7f9fa;
  }

  .workstream-table :deep(.ant-table-tbody > tr > td) {
    color: #31414d;
  }

  .workstream-table :deep(.ant-table-tbody > tr:hover > td) {
    background: #f4f9fb !important;
  }

  .review-copy {
    max-width: 580px;
    color: #263540;
    line-height: 1.65;
  }

  .review-meta,
  .confidence-text {
    color: #7b8994;
    font-size: 12px;
  }

  .review-meta {
    margin-top: 4px;
  }

  .bottom-workstreams {
    margin-bottom: 0;
  }

  .compact-card {
    height: 100%;
    margin-bottom: 0;
  }

  .issue-list {
    min-height: 124px;
  }

  .issue-list :deep(.ant-list-item) {
    padding: 14px 16px;
  }

  .issue-list :deep(.ant-list-item-meta-title) {
    margin-bottom: 6px;
  }

  .issue-list :deep(.ant-list-item-meta-description) {
    color: #738390;
  }

  .issue-list :deep(.ant-avatar) {
    border-radius: 6px;
  }

  .review-evidence {
    padding: 13px 14px;
    color: #29404e;
    line-height: 1.7;
    background: #edf6fa;
    border-left: 3px solid #2f7899;
    border-radius: 0 4px 4px 0;
  }

  .review-modal :deep(.ant-form-item) {
    margin-bottom: 14px;
  }

  @media (max-width: 860px) {
    .pulsecart-operations {
      padding: 18px 14px 26px;
    }
    .workspace-header {
      align-items: flex-start;
      flex-direction: column;
    }
    .workspace-actions {
      width: 100%;
    }
    .dataset-band {
      align-items: flex-start;
      flex-direction: column;
      gap: 16px;
    }
    .dataset-facts {
      width: 100%;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 14px 20px;
    }
    .metric-panel {
      min-height: 132px;
    }
    .workspace-header h1 {
      font-size: 23px;
    }
  }

  @media (max-width: 480px) {
    .workspace-actions :deep(.ant-btn:not(.icon-button)) {
      flex: 1;
    }
    .metric-panel {
      padding: 15px 14px;
    }
    .metric-panel strong {
      font-size: 26px;
    }
    .dataset-facts {
      grid-template-columns: 1fr;
    }
    .review-copy {
      min-width: 260px;
    }
  }
</style>
