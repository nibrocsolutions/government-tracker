const ORG_DEFAULT = "new-hanover-county";
const DISPLAY_TZ = "America/New_York";
const PALETTE = ["#0a4548", "#0f6a6a", "#7eb8b0", "#c4a574", "#c45c3e", "#3a5260", "#2f7d6d", "#8b6b3f"];

let charts = {
  exp: null,
  rev: null,
  change: null,
  topic: null,
};

let chartRenderToken = 0;
let chartsReady = false;

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

function chartDefaults() {
  return {
    responsive: true,
    maintainAspectRatio: false,
    animation: chartsReady ? false : { duration: 450 },
    resizeDelay: 100,
    plugins: {
      legend: {
        labels: {
          boxWidth: 12,
          font: { family: "'Source Sans 3', sans-serif", size: 12 },
          color: "#3a5260",
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
          position: window.matchMedia("(max-width: 860px)").matches ? "bottom" : "right",
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
          ticks: { maxRotation: 45, minRotation: 0, color: "#3a5260" },
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

function scheduleChartRender(budget, mentions) {
  const token = ++chartRenderToken;
  // Wait for layout to settle so Chart.js measures stable container sizes.
  requestAnimationFrame(() => {
    requestAnimationFrame(() => {
      if (token !== chartRenderToken) return;
      renderBudgetCharts(budget);
      renderTopicChart(mentions || []);
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

function renderBudgetLinks(links) {
  const body = $("budget-links-body");
  if (!links.length) {
    body.innerHTML = `<tr><td colspan="7" class="empty">No budget-linked stories yet—try Refresh sources.</td></tr>`;
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
          <td><a href="${escapeHtml(row.story_url)}" target="_blank" rel="noopener">${escapeHtml(row.story_title)}</a></td>
          <td class="amount">${escapeHtml(mentioned)}</td>
          <td>${escapeHtml(source)}</td>
          <td>${escapeHtml(relevance)}</td>
          <td>${formatDate(row.published_at)}</td>
        </tr>`;
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
  renderSources(data.sources || []);
  scheduleChartRender(budget, data.topic_mentions || []);

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
    Object.values(charts).forEach((chart) => {
      if (chart) chart.resize();
    });
  });
}

boot().catch((err) => {
  $("status-line").textContent = err.message;
});
