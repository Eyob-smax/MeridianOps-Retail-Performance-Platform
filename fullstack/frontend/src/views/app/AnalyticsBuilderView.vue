<template>
  <section>
    <h1>Analytics Builder</h1>
    <p>Create dashboard layouts visually, then link widget filters for drill-through behavior.</p>

    <section class="panel">
      <h2>Create Dashboard</h2>
      <div class="form-grid">
        <input v-model="name" placeholder="Dashboard name" />
        <input v-model="description" placeholder="Description" />
        <input v-model="storeIds" placeholder="Store IDs (comma separated)" />
      </div>

      <h3>Drag Canvas (12-column)</h3>
      <p class="hint">Drag a widget card and drop it onto a slot to set its x/y position.</p>
      <div class="builder-canvas" @dragover.prevent>
        <div
          v-for="slot in canvasSlots"
          :key="`slot-${slot.x}-${slot.y}`"
          class="canvas-slot"
          @dragover.prevent
          @drop.prevent="onDropToSlot(slot.x, slot.y)"
        >
          {{ slot.x }},{{ slot.y }}
        </div>
      </div>

      <div class="builder-widget-list">
        <article
          v-for="widget in widgets"
          :key="widget.id"
          class="builder-widget"
          draggable="true"
          @dragstart="onDragStart(widget.id)"
        >
          <header class="builder-widget-header">
            <strong>{{ widget.title }}</strong>
            <span>({{ widget.x }},{{ widget.y }}) {{ widget.w }}x{{ widget.h }}</span>
          </header>

          <div class="form-grid">
            <input v-model="widget.title" placeholder="Widget title" />
            <select v-model="widget.kind">
              <option value="kpi">kpi</option>
              <option value="trend">trend</option>
              <option value="breakdown">breakdown</option>
              <option value="table">table</option>
            </select>
            <select v-model="widget.metric">
              <option value="revenue">revenue</option>
              <option value="orders">orders</option>
              <option value="refunds">refunds</option>
              <option value="gross_margin">gross_margin</option>
            </select>
            <select v-model="widget.dimension">
              <option :value="null">none</option>
              <option value="store">store</option>
              <option value="date">date</option>
            </select>
          </div>

          <div class="form-grid">
            <input v-model.number="widget.w" type="number" min="1" max="12" placeholder="width" />
            <input v-model.number="widget.h" type="number" min="1" max="12" placeholder="height" />
            <button class="btn btn-small" type="button" @click="addFilter(widget.id)">+ Filter</button>
            <button class="btn btn-small" type="button" @click="removeWidget(widget.id)">Remove</button>
          </div>

          <div class="builder-filters" v-if="widget.filters && widget.filters.length > 0">
            <div v-for="(filter, index) in widget.filters" :key="`${widget.id}-f-${index}`" class="form-grid">
              <input v-model="filter.key" placeholder="filter key" />
              <select v-model="filter.operator">
                <option value="eq">eq</option>
                <option value="in">in</option>
                <option value="gte">gte</option>
                <option value="lte">lte</option>
                <option value="between">between</option>
              </select>
              <input v-model="filter.value" placeholder="value" />
              <button class="btn btn-small" type="button" @click="removeFilter(widget.id, index)">
                Drop
              </button>
            </div>
          </div>
        </article>
      </div>

      <h3>Filter Linking</h3>
      <div class="form-grid">
        <select v-model="linkEditor.sourceWidgetId">
          <option value="">Source widget</option>
          <option v-for="widget in widgets" :key="`source-${widget.id}`" :value="widget.id">{{ widget.title }}</option>
        </select>
        <input v-model="linkEditor.sourceFilterKey" placeholder="source filter key" />
        <select v-model="linkEditor.targetWidgetId">
          <option value="">Target widget</option>
          <option v-for="widget in widgets" :key="`target-${widget.id}`" :value="widget.id">{{ widget.title }}</option>
        </select>
        <input v-model="linkEditor.targetFilterKey" placeholder="target filter key" />
      </div>
      <div class="inline-actions">
        <button class="btn btn-small" type="button" @click="addLink">Add Link</button>
        <button class="btn btn-small" type="button" @click="addWidget">+ Widget</button>
      </div>

      <table class="data-table" v-if="activeLinks.length > 0">
        <thead>
          <tr>
            <th>Source Widget</th>
            <th>Source Filter</th>
            <th>Target Filter</th>
            <th>Action</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in activeLinks" :key="`link-${row.widgetId}-${row.linkIndex}`">
            <td>{{ row.widgetTitle }}</td>
            <td>{{ row.link.source_filter_key }}</td>
            <td>{{ row.link.target_filter_key }}</td>
            <td>
              <button class="btn btn-small" type="button" @click="removeLink(row.widgetId, row.linkIndex)">
                Remove
              </button>
            </td>
          </tr>
        </tbody>
      </table>

      <button class="btn" @click="onCreate">Create Dashboard</button>
      <p v-if="createdId">Created dashboard ID: {{ createdId }}</p>
    </section>

    <section class="panel">
      <h2>Recent Dashboards</h2>
      <button class="btn" @click="refreshDashboards">Refresh</button>
      <table class="data-table" v-if="dashboards.length > 0">
        <thead>
          <tr>
            <th>ID</th>
            <th>Name</th>
            <th>Widgets</th>
            <th>Stores</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in dashboards" :key="row.id">
            <td>{{ row.id }}</td>
            <td>{{ row.name }}</td>
            <td>{{ row.widget_count }}</td>
            <td>{{ row.allowed_store_ids.join(", ") }}</td>
          </tr>
        </tbody>
      </table>
    </section>

    <p v-if="errorMessage" class="error">{{ errorMessage }}</p>
  </section>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";

import {
  createDashboard,
  listDashboards,
  type DashboardSummary,
  type DashboardWidget,
} from "@/services/analytics";
import { useUiStore } from "@/stores/ui";
import { notifyError } from "@/utils/feedback";

const ui = useUiStore();

const name = ref("Regional Builder Dashboard");
const description = ref("Store and date linked KPI board");
const storeIds = ref("101,102,103");
const createdId = ref<number | null>(null);
const errorMessage = ref("");
const dashboards = ref<DashboardSummary[]>([]);
const draggingWidgetId = ref<string | null>(null);

const widgets = ref<DashboardWidget[]>([
  {
    id: "kpi-revenue",
    kind: "kpi",
    title: "Revenue",
    metric: "revenue",
    dimension: null,
    x: 0,
    y: 0,
    w: 4,
    h: 2,
    filters: [{ key: "store_id", operator: "in", value: "101,102" }],
    links: [],
  },
  {
    id: "trend-orders",
    kind: "trend",
    title: "Orders Trend",
    metric: "orders",
    dimension: "date",
    x: 4,
    y: 0,
    w: 8,
    h: 3,
    filters: [{ key: "business_date", operator: "between", value: "2026-01-01,2026-12-31" }],
    links: [],
  },
]);

const linkEditor = ref({
  sourceWidgetId: "",
  sourceFilterKey: "",
  targetWidgetId: "",
  targetFilterKey: "",
});

const canvasSlots = computed(() => {
  const slots: Array<{ x: number; y: number }> = [];
  for (let y = 0; y < 4; y += 1) {
    for (let x = 0; x < 12; x += 1) {
      slots.push({ x, y });
    }
  }
  return slots;
});

const activeLinks = computed(() => {
  const rows: Array<{
    widgetId: string;
    widgetTitle: string;
    linkIndex: number;
    link: { source_filter_key: string; target_filter_key: string };
  }> = [];
  for (const widget of widgets.value) {
    const links = widget.links ?? [];
    for (let i = 0; i < links.length; i += 1) {
      rows.push({
        widgetId: widget.id,
        widgetTitle: widget.title,
        linkIndex: i,
        link: links[i],
      });
    }
  }
  return rows;
});

function onDragStart(widgetId: string) {
  draggingWidgetId.value = widgetId;
}

function onDropToSlot(x: number, y: number) {
  if (!draggingWidgetId.value) return;
  const row = widgets.value.find((widget) => widget.id === draggingWidgetId.value);
  if (!row) return;
  row.x = x;
  row.y = y;
  draggingWidgetId.value = null;
}

function addWidget() {
  widgets.value.push({
    id: `widget-${Date.now()}`,
    kind: "kpi",
    title: "New Widget",
    metric: "revenue",
    dimension: null,
    x: 0,
    y: 0,
    w: 4,
    h: 2,
    filters: [],
    links: [],
  });
}

function removeWidget(widgetId: string) {
  widgets.value = widgets.value.filter((widget) => widget.id !== widgetId);
}

function addFilter(widgetId: string) {
  const row = widgets.value.find((widget) => widget.id === widgetId);
  if (!row) return;
  if (!row.filters) row.filters = [];
  row.filters.push({ key: "", operator: "eq", value: "" });
}

function removeFilter(widgetId: string, index: number) {
  const row = widgets.value.find((widget) => widget.id === widgetId);
  if (!row?.filters) return;
  row.filters.splice(index, 1);
}

function addLink() {
  const source = widgets.value.find((widget) => widget.id === linkEditor.value.sourceWidgetId);
  const target = widgets.value.find((widget) => widget.id === linkEditor.value.targetWidgetId);
  if (!source || !target) {
    errorMessage.value = "Choose source and target widgets for link binding.";
    return;
  }
  const sourceKey = linkEditor.value.sourceFilterKey.trim();
  const targetKey = linkEditor.value.targetFilterKey.trim();
  if (!sourceKey || !targetKey) {
    errorMessage.value = "Source and target filter keys are required.";
    return;
  }
  if (!source.links) source.links = [];
  source.links.push({
    source_filter_key: sourceKey,
    target_filter_key: `${target.id}:${targetKey}`,
  });
  linkEditor.value = { sourceWidgetId: "", sourceFilterKey: "", targetWidgetId: "", targetFilterKey: "" };
  errorMessage.value = "";
}

function removeLink(widgetId: string, index: number) {
  const row = widgets.value.find((widget) => widget.id === widgetId);
  if (!row?.links) return;
  row.links.splice(index, 1);
}

async function onCreate() {
  try {
    errorMessage.value = "";
    const allowedStoreIds = storeIds.value
      .split(",")
      .map((v) => Number(v.trim()))
      .filter((v) => Number.isFinite(v) && v > 0);

    const dashboard = await createDashboard({
      name: name.value,
      description: description.value,
      widgets: widgets.value,
      allowed_store_ids: allowedStoreIds,
    });
    createdId.value = dashboard.id;
    await refreshDashboards();
    ui.success("Created", `Dashboard ${dashboard.id} created and list refreshed.`);
  } catch (error) {
    errorMessage.value = notifyError(error, "Dashboard creation failed.");
  }
}

async function refreshDashboards() {
  dashboards.value = await listDashboards();
}

refreshDashboards().catch(() => {
  // Best-effort initial load.
});
</script>
