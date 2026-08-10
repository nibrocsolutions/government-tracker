const ORG_DEFAULT = "new-hanover-county";
const DISPLAY_TZ = "America/New_York";
const PALETTE = ["#0a4548", "#0f6a6a", "#7eb8b0", "#c4a574", "#c45c3e", "#3a5260", "#2f7d6d", "#8b6b3f"];

let charts = {
  exp: null,
  rev: null,
  change: null,
  topic: null,
  history: null,
};

let chartRenderToken = 0;
let chartsReady = false;
let lastDashboard = null;
let wasMobileLayout = typeof window !== "undefined" ? window.matchMedia("(max-width: 720px)").matches : false;

const money = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  maximumFractionDigits: 0,
});

const moneyCompact = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  notation: "compact",
  maximumFractionDigits: 1,
});

function $(id) {
  return document.getElementById(id);
}

function destroyChart(key) {
  if (key && charts[key]) {
    charts[key].destroy();
    charts[key] = null;
  }
}

function resetCanvas(id, chartKey) {
  destroyChart(chartKey);
  const old = $(id);
  if (!old || !old.parentNode) return null;
  const next = document.createElement("canvas");
  next.id = old.id;
  if (old.getAttribute("aria-label")) {
    next.setAttribute("aria-label", old.getAttribute("aria-label"));
  }
  old.parentNode.replaceChild(next, old);
  return next;
}

function parseUtcDate(value) {
  if (!value) return null;
  if (value instanceof Date) return Number.isNaN(value.getTime()) ? null : value;
  let raw = String(value).trim().replace(" ", "T");
  if (!/(?:Z|[+-]\d{2}:?\d{2})$/i.test(raw)) {
    raw += "Z";
  }
  const d = new Date(raw);
  return Number.isNaN(d.getTime()) ? null : d;
}

function formatDate(value) {
  const d = parseUtcDate(value);
  if (!d) return "—";
  return (
    d.toLocaleString("en-US", {
      timeZone: DISPLAY_TZ,
      month: "short",
      day: "numeric",
      year: "numeric",
      hour: "numeric",
      minute: "2-digit",
    }) + " ET"
  );
}

function escapeHtml(text) {
  return String(text)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function isMobileLayout() {
  return window.matchMedia("(max-width: 720px)").matches;
}

function chartDefaults() {
  const mobile = isMobileLayout();
  return {
    responsive: true,
    maintainAspectRatio: false,
    animation: chartsReady ? false : { duration: mobile ? 0 : 450 },
    resizeDelay: 100,
    plugins: {
      legend: {
        labels: {
          boxWidth: mobile ? 10 : 12,
          boxHeight: mobile ? 10 : 12,
          font: { family: "'Source Sans 3', sans-serif", size: mobile ? 11 : 12 },
          color: "#3a5260",
          padding: mobile ? 10 : 12,
        },
      },
    },
  };
}

function renderStories(targetId, stories, emptyText) {
  const el = $(targetId);
  if (!stories.length) {
    el.innerHTML = `<li class="empty">${escapeHtml(emptyText)}</li>`;
    return;
  }
  el.innerHTML = stories
    .map((story) => {
      const topics = (story.topics || "")
        .split(",")
        .map((t) => t.trim())
        .filter(Boolean)
        .map((t) => `<span class="topic-chip">${escapeHtml(t)}</span>`)
        .join("");
      const sourceName = story.source?.name || (story.is_official ? "Official" : "News");
      const relevance =
        story.budget_relevance > 0
          ? `<span class="relevance">${Math.round(story.budget_relevance * 100)}% budget relevance</span>`
          : "";
      return `
        <li class="story-item">
          <a href="${escapeHtml(story.url)}" target="_blank" rel="noopener">${escapeHtml(story.title)}</a>
          <div class="story-meta">
            <span>${escapeHtml(sourceName)}</span>
            <span>${formatDate(story.published_at || story.collected_at)}</span>
            ${relevance}
            ${topics}
          </div>
          ${story.summary ? `<p class="story-summary">${escapeHtml(story.summary)}</p>` : ""}
        </li>`;
    })
    .join("");
}

function doughnutConfig(labels, values) {
  const defaults = chartDefaults();
  return {
    type: "doughnut",
    data: {
      labels,
      datasets: [
        {
          data: values,
          backgroundColor: labels.map((_, i) => PALETTE[i % PALETTE.length]),
          borderWidth: 0,
          hoverOffset: 4,
        },
      ],
    },
    options: {
      ...defaults,
      plugins: {
        ...defaults.plugins,
        legend: {
          ...defaults.plugins.legend,
          position: isMobileLayout() ? "bottom" : "right",
        },
        tooltip: {
          callbacks: {
            label: (ctx) => {
              const total = ctx.dataset.data.reduce((a, b) => a + b, 0);
              const pct = total ? ((ctx.parsed / total) * 100).toFixed(1) : 0;
              return ` ${money.format(ctx.parsed)} (${pct}%)`;
            },
          },
        },
      },
    },
  };
}

function renderBudgetCharts(budget) {
  const expCanvas = resetCanvas("exp-chart", "exp");
  const revCanvas = resetCanvas("rev-chart", "rev");
  const changeCanvas = resetCanvas("change-chart", "change");
  if (!budget || !expCanvas || !revCanvas || !changeCanvas) return;

  const items = budget.line_items || [];
  const expenditures = items
    .filter((i) => i.category === "expenditure")
    .sort((a, b) => a.sort_order - b.sort_order);
  const revenues = items
    .filter((i) => i.category === "revenue")
    .sort((a, b) => a.sort_order - b.sort_order);

  charts.exp = new Chart(
    expCanvas,
    doughnutConfig(
      expenditures.map((i) => i.function_name),
      expenditures.map((i) => i.amount)
    )
  );
  charts.rev = new Chart(
    revCanvas,
    doughnutConfig(
      revenues.map((i) => i.function_name),
      revenues.map((i) => i.amount)
    )
  );

  const defaults = chartDefaults();
  charts.change = new Chart(changeCanvas, {
    type: "bar",
    data: {
      labels: expenditures.map((i) => i.function_name),
      datasets: [
        {
          label: "% change vs prior revised",
          data: expenditures.map((i) => i.pct_change ?? 0),
          backgroundColor: expenditures.map((i) =>
            (i.pct_change ?? 0) >= 0 ? "rgba(15, 106, 106, 0.75)" : "rgba(196, 92, 62, 0.8)"
          ),
          borderRadius: 8,
        },
      ],
    },
    options: {
      ...defaults,
      scales: {
        x: {
          ticks: {
            maxRotation: isMobileLayout() ? 60 : 45,
            minRotation: isMobileLayout() ? 30 : 0,
            color: "#3a5260",
            font: { size: isMobileLayout() ? 10 : 12 },
          },
          grid: { display: false },
        },
        y: {
          ticks: {
            callback: (v) => `${v}%`,
            color: "#3a5260",
          },
          grid: { color: "rgba(19,37,47,0.08)" },
        },
      },
      plugins: {
        ...defaults.plugins,
        legend: { display: false },
        tooltip: {
          callbacks: {
            afterLabel: (ctx) => {
              const item = expenditures[ctx.dataIndex];
              return [
                `Adopted: ${money.format(item.amount)}`,
                item.prior_amount != null ? `Prior: ${money.format(item.prior_amount)}` : "",
              ].filter(Boolean);
            },
          },
        },
      },
    },
  });
}

function renderTopicChart(mentions) {
  const canvas = resetCanvas("topic-chart", "topic");
  if (!canvas || !mentions.length) return;

  const defaults = chartDefaults();
  charts.topic = new Chart(canvas, {
    type: "bar",
    data: {
      labels: mentions.map((m) => m.topic),
      datasets: [
        {
          label: "Story mentions",
          data: mentions.map((m) => m.story_count),
          backgroundColor: "rgba(10, 69, 72, 0.8)",
          borderRadius: 8,
          yAxisID: "y",
        },
        {
          label: "Budget share %",
          data: mentions.map((m) => m.budget_share ?? 0),
          backgroundColor: "rgba(196, 165, 116, 0.85)",
          borderRadius: 8,
          yAxisID: "y1",
        },
      ],
    },
    options: {
      ...defaults,
      scales: {
        y: {
          position: "left",
          title: { display: true, text: "Stories", color: "#3a5260" },
          ticks: { precision: 0, color: "#3a5260" },
          grid: { color: "rgba(19,37,47,0.08)" },
        },
        y1: {
          position: "right",
          title: { display: true, text: "Budget %", color: "#3a5260" },
          grid: { drawOnChartArea: false },
          ticks: {
            callback: (v) => `${v}%`,
            color: "#3a5260",
          },
        },
        x: {
          ticks: { color: "#3a5260" },
          grid: { display: false },
        },
      },
      plugins: {
        ...defaults.plugins,
        tooltip: {
          callbacks: {
            afterBody: (items) => {
              const idx = items[0].dataIndex;
              const m = mentions[idx];
              return m.budget_amount != null ? `Budget: ${money.format(m.budget_amount)}` : "";
            },
          },
        },
      },
    },
  });
}

function scheduleChartRender(budget, mentions, history) {
  const token = ++chartRenderToken;
  // Wait for layout to settle so Chart.js measures stable container sizes.
  requestAnimationFrame(() => {
    requestAnimationFrame(() => {
      if (token !== chartRenderToken) return;
      renderBudgetCharts(budget);
      renderTopicChart(mentions || []);
      renderHistoryChart(history || []);
      chartsReady = true;
      // Force one stable resize after fonts/layout settle.
      requestAnimationFrame(() => {
        if (token !== chartRenderToken) return;
        Object.values(charts).forEach((chart) => {
          if (chart) chart.resize();
        });
      });
    });
  });
}

function renderHistoryChart(history) {
  const canvas = resetCanvas("history-chart", "history");
  if (!canvas || !history.length) return;
  const defaults = chartDefaults();
  charts.history = new Chart(canvas, {
    type: "bar",
    data: {
      labels: history.map((h) => h.fiscal_year),
      datasets: [
        {
          type: "bar",
          label: "General Fund adopted ($)",
          data: history.map((h) => h.total_expenditures),
          backgroundColor: "rgba(10, 69, 72, 0.75)",
          borderRadius: 8,
          yAxisID: "y",
        },
        {
          type: "bar",
          label: "Fund balance used ($)",
          data: history.map((h) => h.reserve_draw || 0),
          backgroundColor: "rgba(196, 165, 116, 0.85)",
          borderRadius: 8,
          yAxisID: "y",
        },
        {
          type: "line",
          label: "Tax rate (¢)",
          data: history.map((h) => h.tax_rate_cents ?? null),
          borderColor: "#c45c3e",
          backgroundColor: "#c45c3e",
          yAxisID: "y1",
          tension: 0.25,
        },
      ],
    },
    options: {
      ...defaults,
      scales: {
        y: {
          position: "left",
          title: { display: true, text: "Dollars", color: "#3a5260" },
          ticks: {
            callback: (v) => moneyCompact.format(v),
            color: "#3a5260",
          },
          grid: { color: "rgba(19,37,47,0.08)" },
        },
        y1: {
          position: "right",
          title: { display: true, text: "Tax rate ¢", color: "#3a5260" },
          grid: { drawOnChartArea: false },
          ticks: { color: "#3a5260" },
        },
        x: {
          ticks: { color: "#3a5260" },
          grid: { display: false },
        },
      },
    },
  });
}

function renderFiscalBalance(balance) {
  const panel = $("fiscal-balance-panel");
  if (!balance) {
    panel.hidden = true;
    return;
  }
  panel.hidden = false;
  const pill = $("balance-status-pill");
  pill.textContent = balance.headline;
  pill.className = "status-pill";
  if (balance.status === "balanced_with_reserves") pill.classList.add("is-reserves");
  if (balance.status === "deficit") pill.classList.add("is-deficit");
  $("balance-headline").textContent = balance.headline;
  $("balance-detail").textContent = balance.detail;
  const coverage =
    balance.recurring_revenue_coverage != null
      ? `${balance.recurring_revenue_coverage}%`
      : "—";
  $("balance-metrics").innerHTML = `
    <div class="balance-metric">
      <span>Adopted gap</span>
      <strong>${escapeHtml(money.format(balance.adopted_gap || 0))}</strong>
    </div>
    <div class="balance-metric">
      <span>Reserve draw</span>
      <strong>${escapeHtml(money.format(balance.reserve_draw || 0))}</strong>
    </div>
    <div class="balance-metric">
      <span>Recurring revenue coverage</span>
      <strong>${escapeHtml(coverage)}</strong>
    </div>`;
}

function yoyClass(pctChange) {
  if (pctChange == null || Number.isNaN(pctChange)) return "";
  if (pctChange > 0) return "is-up";
  if (pctChange < 0) return "is-down";
  return "";
}

function formatYoy(pctChange) {
  if (pctChange == null || Number.isNaN(pctChange)) return "—";
  return `${pctChange > 0 ? "+" : ""}${Number(pctChange).toFixed(1)}%`;
}

function renderDestinationCards(items, total, listedTotal, listedShare, listedYoy, listedYoyPct) {
  const mobile = $("destinations-mobile");
  if (!mobile) return;
  if (!items.length) {
    mobile.innerHTML = `<li class="empty">Department destinations not loaded yet.</li>`;
    return;
  }

  const maxShare = Math.max(
    ...items.map((item) => (total ? (item.amount / total) * 100 : 0)),
    total ? (listedTotal / total) * 100 : 0,
    1
  );

  const cards = items.map((item, index) => {
    const sharePct = total ? (item.amount / total) * 100 : 0;
    const barWidth = Math.max(4, (sharePct / maxShare) * 100);
    const yoy = formatYoy(item.pct_change);
    return `
      <li class="destination-card">
        <div class="destination-card-top">
          <span class="destination-rank">${index + 1}</span>
          <h3 class="destination-name">${escapeHtml(item.function_name)}</h3>
          <span class="destination-yoy ${yoyClass(item.pct_change)}">${escapeHtml(yoy)}</span>
        </div>
        <p class="destination-amount">${escapeHtml(money.format(item.amount))}</p>
        <div class="destination-share-row">
          <span>Share of General Fund</span>
          <span>${escapeHtml(sharePct.toFixed(1))}%</span>
        </div>
        <div class="destination-bar" aria-hidden="true"><span style="width:${barWidth.toFixed(1)}%"></span></div>
      </li>`;
  });

  const totalBar = total ? Math.max(4, ((listedTotal / total) * 100 / maxShare) * 100) : 4;
  cards.push(`
    <li class="destination-card is-total">
      <div class="destination-card-top">
        <span class="destination-rank">Total</span>
        <h3 class="destination-name">Listed destinations</h3>
        <span class="destination-yoy ${yoyClass(listedYoyPct)}">${escapeHtml(listedYoy)}</span>
      </div>
      <p class="destination-amount">${escapeHtml(money.format(listedTotal))}</p>
      <div class="destination-share-row">
        <span>Share of General Fund</span>
        <span>${escapeHtml(listedShare)}</span>
      </div>
      <div class="destination-bar" aria-hidden="true"><span style="width:${totalBar.toFixed(1)}%"></span></div>
    </li>`);

  mobile.innerHTML = cards.join("");
}

function renderDestinations(items, total) {
  const body = $("destinations-body");
  if (!items.length) {
    body.innerHTML = `<tr><td colspan="4" class="empty">Department destinations not loaded yet.</td></tr>`;
    renderDestinationCards([], total, 0, "—", "—", null);
    return;
  }
  const rows = items.map((item) => {
    const share = total ? ((item.amount / total) * 100).toFixed(1) + "%" : "—";
    const yoy = formatYoy(item.pct_change);
    return `
      <tr>
        <td class="category">${escapeHtml(item.function_name)}</td>
        <td class="amount">${escapeHtml(money.format(item.amount))}</td>
        <td class="amount">${escapeHtml(share)}</td>
        <td>${escapeHtml(yoy)}</td>
      </tr>`;
  });

  const listedTotal = items.reduce((sum, item) => sum + (item.amount || 0), 0);
  const listedPrior = items.reduce(
    (sum, item) => sum + (item.prior_amount != null ? item.prior_amount : 0),
    0
  );
  const hasPriors = items.some((item) => item.prior_amount != null);
  const listedShare = total ? ((listedTotal / total) * 100).toFixed(1) + "%" : "—";
  let listedYoyPct = null;
  let listedYoy = "—";
  if (hasPriors && listedPrior > 0) {
    listedYoyPct = ((listedTotal - listedPrior) / listedPrior) * 100;
    listedYoy = formatYoy(listedYoyPct);
  }

  rows.push(`
    <tr class="totals-row">
      <td class="category">Total (listed destinations)</td>
      <td class="amount">${escapeHtml(money.format(listedTotal))}</td>
      <td class="amount">${escapeHtml(listedShare)}</td>
      <td>${escapeHtml(listedYoy)}</td>
    </tr>`);

  body.innerHTML = rows.join("");
  renderDestinationCards(items, total, listedTotal, listedShare, listedYoy, listedYoyPct);
}

function renderResources(resources) {
  const el = $("resource-list");
  if (!resources.length) {
    el.innerHTML = `<li class="empty">No transparency resources configured.</li>`;
    return;
  }
  const categoryLabel = {
    public_records: "Public records",
    budget_documents: "Budget documents",
    spending_tools: "Spending tools",
    contacts: "Contacts",
    oversight: "Oversight",
    audited_results: "Audited results",
  };
  el.innerHTML = resources
    .map(
      (r) => `
      <li class="resource-item">
        <a href="${escapeHtml(r.url)}" target="_blank" rel="noopener">${escapeHtml(r.name)}</a>
        <div class="story-meta"><span class="topic-chip">${escapeHtml(
          categoryLabel[r.category] || r.category
        )}</span></div>
        ${r.description ? `<p>${escapeHtml(r.description)}</p>` : ""}
      </li>`
    )
    .join("");
}

function renderBudgetLinks(links) {
  const body = $("budget-links-body");
  const mobile = $("budget-links-mobile");
  if (!links.length) {
    body.innerHTML = `<tr><td colspan="7" class="empty">No budget-linked stories yet—try Refresh sources.</td></tr>`;
    if (mobile) {
      mobile.innerHTML = `<li class="empty">No budget-linked stories yet—try Refresh sources.</li>`;
    }
    return;
  }

  body.innerHTML = links
    .map((row) => {
      const amount =
        row.budget_amount != null
          ? `${money.format(row.budget_amount)}${
              row.budget_share != null ? ` (${row.budget_share}%)` : ""
            }`
          : "—";
      const mentioned = row.mentioned_money || "—";
      const source = row.source_name || (row.is_official ? "Official" : "News");
      const relevance =
        row.budget_relevance > 0 ? `${Math.round(row.budget_relevance * 100)}%` : "—";
      return `
        <tr>
          <td class="category">${escapeHtml(row.budget_category)}</td>
          <td class="amount">${escapeHtml(amount)}</td>
          <td>
            <a class="story-table-link" href="${escapeHtml(row.story_url)}" target="_blank" rel="noopener">
              ${escapeHtml(row.story_title)}
              <span class="story-table-link-hint">Open story ↗</span>
            </a>
          </td>
          <td class="amount">${escapeHtml(mentioned)}</td>
          <td>${escapeHtml(source)}</td>
          <td>${escapeHtml(relevance)}</td>
          <td>${formatDate(row.published_at)}</td>
        </tr>`;
    })
    .join("");

  if (!mobile) return;
  mobile.innerHTML = links
    .map((row) => {
      const amount =
        row.budget_amount != null
          ? `${money.format(row.budget_amount)}${
              row.budget_share != null ? ` · ${row.budget_share}% of GF` : ""
            }`
          : "Budget amount unavailable";
      const mentioned = row.mentioned_money || "None found";
      const source = row.source_name || (row.is_official ? "Official" : "News");
      const relevance =
        row.budget_relevance > 0 ? `${Math.round(row.budget_relevance * 100)}%` : "—";
      return `
        <li class="news-link-card">
          <div class="news-link-card-top">
            <span class="topic-chip">${escapeHtml(row.budget_category)}</span>
            <span class="topic-chip">${escapeHtml(source)}</span>
          </div>
          <h3 class="news-link-title">${escapeHtml(row.story_title)}</h3>
          <div class="news-link-meta">
            <div><strong>Adopted:</strong> ${escapeHtml(amount)}</div>
            <div><strong>Mentioned $:</strong> ${escapeHtml(mentioned)}</div>
            <div><strong>Relevance:</strong> ${escapeHtml(relevance)} · ${formatDate(row.published_at)}</div>
          </div>
          <a class="news-link-open" href="${escapeHtml(row.story_url)}" target="_blank" rel="noopener">
            Open story
          </a>
        </li>`;
    })
    .join("");
}

function renderOfficialStories(stories) {
  const panel = $("official-stories-panel");
  const grid = $("stories-grid");
  if (!stories.length) {
    panel.hidden = true;
    panel.setAttribute("aria-hidden", "true");
    grid.classList.add("single-column");
    $("official-stories").innerHTML = "";
    return;
  }
  panel.hidden = false;
  panel.removeAttribute("aria-hidden");
  grid.classList.remove("single-column");
  renderStories("official-stories", stories, "No official stories yet.");
}

function renderSources(sources) {
  const el = $("source-list");
  el.innerHTML = sources
    .map(
      (s) => `
      <li class="source-item">
        <div>
          <a href="${escapeHtml(s.url)}" target="_blank" rel="noopener">${escapeHtml(s.name)}</a>
          <div class="story-meta"><span>${escapeHtml(s.source_type)}</span></div>
        </div>
        <span>${s.last_collected_at ? `Last pull ${formatDate(s.last_collected_at)}` : "Not collected yet"}</span>
      </li>`
    )
    .join("");
}

async function loadOrganizations() {
  const orgs = await fetch("/api/organizations").then((r) => r.json());
  const select = $("org-select");
  select.innerHTML = orgs
    .map((o) => `<option value="${escapeHtml(o.slug)}">${escapeHtml(o.short_name)}</option>`)
    .join("");
  const preferred = orgs.find((o) => o.slug === ORG_DEFAULT) || orgs[0];
  if (preferred) select.value = preferred.slug;
  return preferred?.slug || ORG_DEFAULT;
}

async function loadDashboard(slug) {
  $("status-line").textContent = "Loading dashboard…";
  const data = await fetch(`/api/organizations/${slug}/dashboard`).then((r) => {
    if (!r.ok) throw new Error("Failed to load dashboard");
    return r.json();
  });

  const org = data.organization;
  const budget = data.current_budget;
  lastDashboard = data;
  $("org-tagline").textContent = org.description || `Tracking ${org.name}.`;

  if (budget) {
    $("stat-budget").textContent = moneyCompact.format(budget.total_expenditures);
    $("stat-fy").textContent = budget.label;
    $("stat-tax").textContent = budget.tax_rate_cents != null ? `${budget.tax_rate_cents}¢` : "—";
    $("budget-notes").textContent = budget.notes || "";
    const link = $("budget-source-link");
    if (budget.source_url) {
      link.href = budget.source_url;
      link.hidden = false;
    } else {
      link.hidden = true;
    }
  } else {
    $("stat-budget").textContent = "—";
    $("stat-tax").textContent = "—";
    $("budget-notes").textContent = "No budget loaded for this organization yet.";
  }

  const storyCount =
    (data.official_stories?.length || 0) + (data.external_stories?.length || 0) ||
    data.recent_stories?.length ||
    0;
  $("stat-stories").textContent = String(data.recent_stories?.length || storyCount);
  $("stat-collected").textContent = data.last_collection
    ? `Last collection ${formatDate(data.last_collection)}`
    : "Run refresh to pull live sources";

  // Render DOM content first, then charts after layout is stable.
  renderOfficialStories(data.official_stories || []);
  renderStories("external-stories", data.external_stories || [], "No external coverage yet—try Refresh sources.");
  const budgetStories = (data.recent_stories || [])
    .filter((s) => s.budget_relevance > 0)
    .sort((a, b) => b.budget_relevance - a.budget_relevance);
  renderStories("budget-stories", budgetStories, "No budget-tagged stories yet.");
  renderBudgetLinks(data.budget_story_links || []);
  renderFiscalBalance(data.fiscal_balance);
  renderDestinations(data.top_destinations || [], budget?.total_expenditures || 0);
  renderResources(data.transparency_resources || []);
  renderSources(data.sources || []);
  scheduleChartRender(budget, data.topic_mentions || [], data.budget_history || []);

  document.body.classList.add("is-ready");
  $("status-line").textContent = `Showing ${org.short_name}`;
}

async function refreshSources() {
  const btn = $("refresh-btn");
  btn.disabled = true;
  btn.textContent = "Collecting…";
  $("status-line").textContent = "Pulling official pages and news feeds…";
  try {
    const result = await fetch("/api/collect", { method: "POST" }).then((r) => r.json());
    $("status-line").textContent = result.message || `Added ${result.stories_added} stories`;
    await loadDashboard($("org-select").value);
  } catch (err) {
    $("status-line").textContent = `Collection failed: ${err.message}`;
  } finally {
    btn.disabled = false;
    btn.textContent = "Refresh sources";
  }
}

async function boot() {
  const slug = await loadOrganizations();
  await loadDashboard(slug);
  $("org-select").addEventListener("change", (e) => loadDashboard(e.target.value));
  $("refresh-btn").addEventListener("click", refreshSources);
  window.addEventListener("resize", () => {
    const nowMobile = isMobileLayout();
    if (nowMobile !== wasMobileLayout && lastDashboard) {
      wasMobileLayout = nowMobile;
      scheduleChartRender(
        lastDashboard.current_budget,
        lastDashboard.topic_mentions || [],
        lastDashboard.budget_history || []
      );
      return;
    }
    wasMobileLayout = nowMobile;
    Object.values(charts).forEach((chart) => {
      if (chart) chart.resize();
    });
  });
}

boot().catch((err) => {
  $("status-line").textContent = err.message;
});
