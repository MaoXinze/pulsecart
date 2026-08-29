<template>

  <div class="sentiment-analyze p-4">

    <AiStatusBanner />



    <PipelineOverview />



    <a-row :gutter="16">

      <a-col :xs="24" :xl="16">

        <a-card :bordered="false">

          <a-tabs v-model:activeKey="activeTab">

            <a-tab-pane key="single" tab="单条分析">

              <a-textarea

                v-model:value="text"

                :rows="5"

                :maxlength="1000"

                show-count

                placeholder="粘贴或输入一条商品评论，例如：物流很快，但是包装有点简陋"

                @keydown.ctrl.enter="handleAnalyze"

              />

              <div class="mt-4 flex flex-wrap gap-3">

                <a-button type="primary" :loading="loading" @click="handleAnalyze">分析</a-button>

                <a-button @click="fillSample">填入示例</a-button>

                <a-button @click="reset">清空</a-button>

                <span class="self-center text-gray-400 text-sm">Ctrl + Enter 快捷分析</span>

              </div>

            </a-tab-pane>



            <a-tab-pane key="batch" tab="批量对比">

              <a-textarea

                v-model:value="batchText"

                :rows="6"

                placeholder="每行一条评论，最多 10 条。适合对比多条评价的情感差异。"

              />

              <div class="mt-4">

                <a-button type="primary" :loading="batchLoading" @click="handleBatchAnalyze">批量分析</a-button>

              </div>

            </a-tab-pane>

          </a-tabs>

        </a-card>



        <a-card v-if="result && activeTab === 'single'" class="mt-4" title="分析结果" :bordered="false">

          <template #extra>

            <a-space>

              <a-tag v-if="result.active_model" color="blue">{{ result.active_model }} 推理</a-tag>

              <SourceBadge :source="result.source" />

              <span v-if="result.latency_ms != null" class="text-gray-400 text-sm">{{ result.latency_ms }} ms</span>

            </a-space>

          </template>



          <div v-if="result.entities?.length" class="mb-4">

            <div class="mb-2 text-gray-500">属性实体识别（BIO NER 高亮）</div>

            <AspectHighlight :text="text" :entities="result.entities" />

          </div>



          <a-row :gutter="16">

            <a-col :xs="24" :md="8">

              <Gauge

                :chartData="{ name: result.sentiment.label_text, value: Math.round(result.sentiment.prob * 100) }"

                height="220px"

                :seriesColor="result.sentiment.label === 1 ? '#52c41a' : '#ff4d4f'"

              />

              <div class="text-center text-gray-500 -mt-2">情感置信度</div>

            </a-col>

            <a-col :xs="24" :md="16">

              <div class="mb-2 text-gray-500">关键词权重（KeyBERT）</div>

              <Bar :chartData="keywordChartData" height="220px" seriesColor="#1890ff" />

            </a-col>

          </a-row>



          <div class="mt-4">

            <div class="mb-2 text-gray-500">属性情感雷达</div>

            <Radar v-if="aspectRadarData.length" :chartData="aspectRadarData" height="280px" />

            <a-empty v-else description="未识别到属性维度" />

          </div>



          <div class="mt-4">

            <div class="mb-2 text-gray-500">属性明细</div>

            <a-table

              :columns="aspectColumns"

              :data-source="result.aspects"

              :pagination="false"

              row-key="aspect"

              size="middle"

            />

          </div>

        </a-card>



        <a-card v-if="batchResults.length && activeTab === 'batch'" class="mt-4" title="批量对比结果" :bordered="false">

          <template #extra>

            <span v-if="batchAvgLatency != null" class="text-gray-400 text-sm">平均 {{ batchAvgLatency }} ms</span>

          </template>

          <a-table

            :columns="batchColumns"

            :data-source="batchResults"

            :pagination="false"

            :row-key="batchRowKey"

            size="middle"

            :expand-column-width="48"

          >

            <template #expandedRowRender="{ record }">

              <div class="px-2 py-1">

                <div class="mb-2 text-gray-500">关键词</div>

                <a-space wrap>

                  <a-tag v-for="kw in record.keywords" :key="kw.word" color="blue">

                    {{ kw.word }} ({{ kw.score.toFixed(2) }})

                  </a-tag>

                </a-space>

                <div class="mt-3 mb-2 text-gray-500">属性情感</div>

                <a-space wrap>

                  <a-tag

                    v-for="asp in record.aspects"

                    :key="asp.aspect"

                    :color="asp.polarity === 1 ? 'success' : 'error'"

                  >

                    {{ asp.aspect }} · {{ asp.polarity_text }}

                  </a-tag>

                </a-space>

              </div>

            </template>

          </a-table>

        </a-card>

      </a-col>



      <a-col :xs="24" :xl="8">

        <a-card title="最近分析" :bordered="false">

          <template #extra>

            <a-button v-if="history.length" type="link" size="small" @click="clearHistory">清空</a-button>

          </template>

          <a-list v-if="history.length" :data-source="history" size="small">

            <template #renderItem="{ item }">

              <a-list-item>

                <a-list-item-meta>

                  <template #title>

                    <a-tag :color="item.sentiment.label === 1 ? 'success' : 'error'" class="mr-2">

                      {{ item.sentiment.label_text }}

                    </a-tag>

                    <span class="text-gray-600">{{ item.text_preview || item.text.slice(0, 24) }}</span>

                  </template>

                  <template #description>

                    {{ formatTime(item.analyzed_at) }}

                  </template>

                </a-list-item-meta>

                <template #actions>

                  <a @click="restoreHistory(item)">复用</a>

                  <a @click="removeEntry(item.id)">删除</a>

                </template>

              </a-list-item>

            </template>

          </a-list>

          <a-empty v-else description="分析后将在此保留最近 12 条记录" />

        </a-card>



        <a-card class="mt-4" title="能力导航" :bordered="false" size="small">

          <a-space direction="vertical" class="w-full">

            <a-button block @click="goTo('/sentiment/models')">三模型对比链</a-button>

            <a-button block @click="goTo('/sentiment/keywords')">KeyBERT vs TF-IDF</a-button>

            <a-button block @click="goTo('/sentiment/pros-cons')">优缺点 Top10</a-button>

            <a-button block @click="goTo('/sentiment/dashboard')">评价看板</a-button>

            <a-button block type="primary" @click="goTo('/pulsecart/operations')">商品体验问题闭环</a-button>

          </a-space>

        </a-card>

      </a-col>

    </a-row>

  </div>

</template>



<script lang="ts" setup>

  import { computed, ref } from 'vue';

  import { useRouter } from 'vue-router';

  import { message } from 'ant-design-vue';

  import Bar from '/@/components/chart/Bar.vue';

  import Gauge from '/@/components/chart/Gauge.vue';

  import Radar from '/@/components/chart/Radar.vue';

  import AiStatusBanner from '../components/AiStatusBanner.vue';

  import AspectHighlight from '../components/AspectHighlight.vue';

  import PipelineOverview from '../components/PipelineOverview.vue';

  import SourceBadge from '../components/SourceBadge.vue';

  import { useReviewHistory } from '../hooks/useReviewHistory';

  import { analyzeBatch, analyzeReview, type AnalyzeResult } from '../review.api';



  const SAMPLE = '物流很快，但是包装有点简陋，性价比还可以';



  const router = useRouter();

  const activeTab = ref('single');

  const text = ref('');

  const batchText = ref('');

  const loading = ref(false);

  const batchLoading = ref(false);

  const result = ref<AnalyzeResult | null>(null);

  const batchResults = ref<AnalyzeResult[]>([]);

  const batchAvgLatency = ref<number | null>(null);



  const { history, addEntry, removeEntry, clearHistory } = useReviewHistory();



  const aspectColumns = [

    { title: '属性', dataIndex: 'aspect', key: 'aspect' },

    {

      title: '情感',

      dataIndex: 'polarity_text',

      key: 'polarity_text',

    },

    {

      title: '置信度',

      dataIndex: 'prob',

      key: 'prob',

      customRender: ({ text: v }: { text: number }) => `${(v * 100).toFixed(1)}%`,

    },

  ];



  const batchColumns = [

    { title: '评论摘要', dataIndex: 'text_preview', key: 'text_preview', ellipsis: true },

    { title: '情感', dataIndex: ['sentiment', 'label_text'], key: 'label_text' },

    {

      title: '置信度',

      dataIndex: ['sentiment', 'prob'],

      key: 'prob',

      customRender: ({ text: v }: { text: number }) => `${(v * 100).toFixed(1)}%`,

    },

    {

      title: '属性数',

      key: 'aspect_count',

      customRender: ({ record }: { record: AnalyzeResult }) => record.aspects?.length ?? 0,

    },

    { title: '来源', dataIndex: 'source', key: 'source' },

    {

      title: '耗时',

      dataIndex: 'latency_ms',

      key: 'latency_ms',

      customRender: ({ text: v }: { text?: number }) => (v != null ? `${v} ms` : '—'),

    },

  ];



  const keywordChartData = computed(() =>

    (result.value?.keywords || []).map((item) => ({ name: item.word, value: item.score }))

  );



  const aspectRadarData = computed(() =>

    (result.value?.aspects || []).map((item) => ({

      name: item.aspect,

      max: 100,

      type: '属性情感',

      value: Math.round(item.prob * 100),

    }))

  );



  function batchRowKey(_record: AnalyzeResult, index: number) {

    return index;

  }



  function formatTime(iso: string) {

    const d = new Date(iso);

    return Number.isNaN(d.getTime()) ? iso : d.toLocaleString();

  }



  function goTo(path: string) {

    router.push(path);

  }



  async function handleAnalyze() {

    const value = text.value.trim();

    if (!value) {

      message.warning('请先输入评论文本');

      return;

    }

    loading.value = true;

    try {

      result.value = await analyzeReview({ text: value, top_n: 8 });

      addEntry(value, result.value);

    } finally {

      loading.value = false;

    }

  }



  async function handleBatchAnalyze() {

    const texts = batchText.value

      .split('\n')

      .map((line) => line.trim())

      .filter(Boolean);

    if (!texts.length) {

      message.warning('请至少输入一行评论');

      return;

    }

    if (texts.length > 10) {

      message.warning('批量分析最多 10 条');

      return;

    }

    batchLoading.value = true;

    try {

      const res = await analyzeBatch({ texts, top_n: 5 });

      batchResults.value = res.items;

      batchAvgLatency.value = res.avg_latency_ms ?? null;

    } finally {

      batchLoading.value = false;

    }

  }



  function fillSample() {

    text.value = SAMPLE;

  }



  function reset() {

    text.value = '';

    result.value = null;

  }



  function restoreHistory(item: { text: string }) {

    text.value = item.text;

    activeTab.value = 'single';

    handleAnalyze();

  }

</script>

