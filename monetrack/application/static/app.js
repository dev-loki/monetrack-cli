// MonetRack Dashboard Controller

document.addEventListener("DOMContentLoaded", () => {
  // --- State & Constants ---
  const API_BASE = ""; // relative paths to FastAPI backend
  let currentTab = "overview";
  let assetsData = [];
  let summaryData = {};

  // Charts cache
  let donutChart = null;
  let barChart = null;

  // --- Element Selectors ---
  const tabLinks = document.querySelectorAll(".sidebar-nav .nav-link");
  const tabPanes = document.querySelectorAll(".tab-pane");
  const pageTitle = document.getElementById("page-title");

  // Modals
  const quickLogBtn = document.getElementById("btn-quick-log");
  const quickActionModal = document.getElementById("modal-quick-action");
  const modalCloseBtn = document.getElementById("modal-close-btn");
  const modalInvestBtn = document.getElementById("btn-modal-invest");
  const modalSnapshotBtn = document.getElementById("btn-modal-snapshot");

  // Forms
  const formAddAsset = document.getElementById("form-add-asset");
  const formAddTransaction = document.getElementById("form-add-transaction");
  const formAddSnapshot = document.getElementById("form-add-snapshot");

  // Dropdowns
  const selectTxAsset = document.getElementById("tx-asset-id");
  const selectSnapAsset = document.getElementById("snap-asset-id");

  // --- Tab Routing ---
  function switchTab(tabId) {
    currentTab = tabId;

    // Update active nav link
    tabLinks.forEach(link => {
      if (link.getAttribute("data-tab") === tabId) {
        link.classList.add("active");
      } else {
        link.classList.remove("active");
      }
    });

    // Update visible tab pane
    tabPanes.forEach(pane => {
      if (pane.id === `tab-${tabId}`) {
        pane.classList.add("active");
      } else {
        pane.classList.remove("active");
      }
    });

    // Update Header Page Title
    const titleMap = {
      overview: "Portfolio Overview",
      assets: "Asset Allocations",
      transactions: "Transactions Log",
      snapshots: "Valuation Snapshots"
    };
    pageTitle.textContent = titleMap[tabId] || "Dashboard";

    // Refresh view specific data
    refreshData();
  }

  tabLinks.forEach(link => {
    link.addEventListener("click", () => {
      switchTab(link.getAttribute("data-tab"));
    });
  });

  // --- Modal Controllers ---
  function openModal(modalEl) {
    modalEl.classList.add("active");
  }

  function closeModal(modalEl) {
    modalEl.classList.remove("active");
  }

  quickLogBtn.addEventListener("click", () => openModal(quickActionModal));
  modalCloseBtn.addEventListener("click", () => closeModal(quickActionModal));

  // Close modal when clicking outside content area
  quickActionModal.addEventListener("click", (e) => {
    if (e.target === quickActionModal) {
      closeModal(quickActionModal);
    }
  });

  modalInvestBtn.addEventListener("click", () => {
    closeModal(quickActionModal);
    switchTab("transactions");
  });

  modalSnapshotBtn.addEventListener("click", () => {
    closeModal(quickActionModal);
    switchTab("snapshots");
  });

  // --- Toast Notifications ---
  function showToast(message, type = "success") {
    const container = document.getElementById("toast-container");
    const toast = document.createElement("div");
    toast.className = `toast toast-${type}`;

    const iconClass = type === "success" ? "fa-circle-check" : "fa-circle-exclamation";
    toast.innerHTML = `
      <i class="fa-solid ${iconClass}"></i>
      <span>${message}</span>
    `;

    container.appendChild(toast);

    // Slide out and remove toast
    setTimeout(() => {
      toast.style.opacity = "0";
      setTimeout(() => toast.remove(), 300);
    }, 4000);
  }

  // --- Data Fetching and UI Rendering ---
  async function refreshData() {
    try {
      await fetchAssets();
      await fetchSummary();

      if (currentTab === "overview") {
        renderMetrics();
        renderOverviewTable();
        renderCharts();
      } else if (currentTab === "assets") {
        renderAssetsList();
      } else if (currentTab === "transactions") {
        await fetchTransactions();
      } else if (currentTab === "snapshots") {
        await fetchSnapshots();
      }

      // Keep asset dropdowns up-to-date
      populateAssetDropdowns();

    } catch (err) {
      console.error("Error refreshing data:", err);
      showToast("Failed to fetch fresh data from backend", "danger");
    }
  }

  async function fetchSummary() {
    const res = await fetch(`${API_BASE}/api/summary`);
    if (!res.ok) throw new Error("Could not fetch summary data");
    summaryData = await res.json();
  }

  async function fetchAssets() {
    const res = await fetch(`${API_BASE}/api/assets`);
    if (!res.ok) throw new Error("Could not fetch assets");
    assetsData = await res.json();
  }

  async function fetchTransactions() {
    const res = await fetch(`${API_BASE}/api/transactions`);
    if (!res.ok) throw new Error("Could not fetch transactions");
    const txs = await res.json();
    renderTransactionsTable(txs);
  }

  async function fetchSnapshots() {
    const res = await fetch(`${API_BASE}/api/snapshots`);
    if (!res.ok) throw new Error("Could not fetch snapshots");
    const snaps = await res.json();
    renderSnapshotsTable(snaps);
  }

  // --- UI Renderers ---
  function renderMetrics() {
    document.getElementById("val-net-invested").textContent = formatCurrency(summaryData.net_invested);
    document.getElementById("val-current-value").textContent = formatCurrency(summaryData.current_value);

    const earnEl = document.getElementById("val-earnings");
    earnEl.textContent = formatCurrency(summaryData.earnings, true);

    const profitIcon = document.getElementById("profit-icon");
    if (summaryData.earnings >= 0) {
      earnEl.className = "metric-value text-green";
      profitIcon.className = "fa-solid fa-arrow-trend-up text-green";
    } else {
      earnEl.className = "metric-value text-danger";
      profitIcon.className = "fa-solid fa-arrow-trend-down text-danger";
    }

    const roiEl = document.getElementById("val-roi");
    roiEl.textContent = `${summaryData.roi >= 0 ? "+" : ""}${summaryData.roi.toFixed(2)} %`;
    roiEl.className = summaryData.roi >= 0 ? "metric-value text-green" : "metric-value text-danger";
  }

  function renderOverviewTable() {
    const tbody = document.querySelector("#table-overview-assets tbody");
    tbody.innerHTML = "";

    if (assetsData.length === 0) {
      tbody.innerHTML = `
        <tr>
          <td colspan="6" style="text-align: center; color: var(--text-muted); padding: 30px;">
            No assets registered yet. Go to the Assets tab to add your first asset!
          </td>
        </tr>
      `;
      return;
    }

    assetsData.forEach(asset => {
      const tr = document.createElement("tr");

      const earnColor = asset.stats.earnings >= 0 ? "text-green" : "text-danger";
      const roiColor = asset.stats.roi >= 0 ? "text-green" : "text-danger";

      tr.innerHTML = `
        <td style="font-weight: 600;">${asset.name}</td>
        <td><span class="asset-badge badge-${asset.type}">${asset.type}</span></td>
        <td>${formatCurrency(asset.stats.net_invested)}</td>
        <td>${formatCurrency(asset.stats.current_value)}</td>
        <td class="${earnColor}" style="font-weight: 500;">${formatCurrency(asset.stats.earnings, true)}</td>
        <td class="${roiColor}" style="font-weight: 600;">${asset.stats.roi >= 0 ? "+" : ""}${asset.stats.roi.toFixed(2)}%</td>
      `;
      tbody.appendChild(tr);
    });
  }

  function renderAssetsList() {
    const list = document.getElementById("list-assets");
    list.innerHTML = "";

    if (assetsData.length === 0) {
      list.innerHTML = `
        <div style="text-align: center; color: var(--text-muted); padding: 40px;">
          No assets registered yet. Fill out the form on the right to start tracking.
        </div>
      `;
      return;
    }

    assetsData.forEach(asset => {
      const card = document.createElement("div");
      card.className = "asset-item glass-card";

      let codesStr = "";
      if (asset.isin) codesStr += `ISIN: ${asset.isin}`;
      if (asset.wkn) codesStr += (codesStr ? " | " : "") + `WKN: ${asset.wkn}`;

      card.innerHTML = `
        <div class="asset-details">
          <div class="asset-name-row">
            <h4>${asset.name}</h4>
            <span class="asset-badge badge-${asset.type}">${asset.type}</span>
          </div>
          ${codesStr ? `<div class="asset-codes">${codesStr}</div>` : ""}
          <div class="asset-comment-desc">${asset.comment || "No description / comments logged."}</div>
        </div>
        <button class="btn btn-danger btn-delete-asset" data-id="${asset.id}" data-name="${asset.name}">
          <i class="fa-solid fa-trash-can"></i> Delete
        </button>
      `;

      list.appendChild(card);
    });

    // Add delete event listeners
    document.querySelectorAll(".btn-delete-asset").forEach(btn => {
      btn.addEventListener("click", async (e) => {
        const assetId = btn.getAttribute("data-id");
        const assetName = btn.getAttribute("data-name");

        if (confirm(`Are you sure you want to permanently delete the asset "${assetName}" and all its transaction history/valuation snapshots?`)) {
          try {
            const res = await fetch(`${API_BASE}/api/assets/${assetId}`, { method: "DELETE" });
            if (!res.ok) throw new Error("Could not delete asset");
            showToast(`Asset "${assetName}" successfully deleted!`);
            refreshData();
          } catch (err) {
            showToast("Failed to delete asset", "danger");
          }
        }
      });
    });
  }

  function renderTransactionsTable(txs) {
    const tbody = document.querySelector("#table-transactions tbody");
    tbody.innerHTML = "";

    if (txs.length === 0) {
      tbody.innerHTML = `
        <tr>
          <td colspan="5" style="text-align: center; color: var(--text-muted); padding: 30px;">
            No transactions logged yet. Fill out the form on the right to record your first transaction!
          </td>
        </tr>
      `;
      return;
    }

    // Build asset ID map
    const assetMap = {};
    assetsData.forEach(a => assetMap[a.id] = a.name);

    txs.forEach(tx => {
      const tr = document.createElement("tr");
      const isInvest = tx.type === "invest";
      const badgeClass = isInvest ? "badge-crypto" : "badge-danger";
      const amtColor = isInvest ? "text-green" : "text-danger";

      tr.innerHTML = `
        <td>${tx.timestamp}</td>
        <td style="font-weight: 500;">${assetMap[tx.asset_id] || `Asset ID ${tx.asset_id}`}</td>
        <td><span class="asset-badge ${badgeClass}">${tx.type}</span></td>
        <td class="${amtColor}" style="font-weight: 600;">${isInvest ? "+" : "-"}${tx.amount.toFixed(2)} €</td>
        <td>${tx.comment || "-"}</td>
      `;
      tbody.appendChild(tr);
    });
  }

  function renderSnapshotsTable(snaps) {
    const tbody = document.querySelector("#table-snapshots tbody");
    tbody.innerHTML = "";

    if (snaps.length === 0) {
      tbody.innerHTML = `
        <tr>
          <td colspan="4" style="text-align: center; color: var(--text-muted); padding: 30px;">
            No valuation snapshots logged yet. Fill out the form on the right to record your first valuation!
          </td>
        </tr>
      `;
      return;
    }

    // Build asset ID map
    const assetMap = {};
    assetsData.forEach(a => assetMap[a.id] = a.name);

    snaps.forEach(snap => {
      const tr = document.createElement("tr");

      tr.innerHTML = `
        <td>${snap.timestamp}</td>
        <td style="font-weight: 500;">${assetMap[snap.asset_id] || `Asset ID ${snap.asset_id}`}</td>
        <td style="font-weight: 600;">${snap.value.toFixed(2)} €</td>
        <td>${snap.comment || "-"}</td>
      `;
      tbody.appendChild(tr);
    });
  }

  function populateAssetDropdowns() {
    const populate = (selectEl) => {
      const selectedValue = selectEl.value;
      selectEl.innerHTML = "";

      if (assetsData.length === 0) {
        selectEl.innerHTML = `<option value="" disabled selected>No assets available</option>`;
        return;
      }

      assetsData.forEach(asset => {
        const opt = document.createElement("option");
        opt.value = asset.id;
        opt.textContent = asset.name;
        selectEl.appendChild(opt);
      });

      // Restore previously selected value if possible
      if (selectedValue && selectEl.querySelector(`option[value="${selectedValue}"]`)) {
        selectEl.value = selectedValue;
      }
    };

    populate(selectTxAsset);
    populate(selectSnapAsset);
  }

  // --- Chart.js Rendering ---
  function renderCharts() {
    renderDonutChart();
    renderBarChart();
  }

  function renderDonutChart() {
    const ctx = document.getElementById("donut-allocation").getContext("2d");

    // Destroy previous instance
    if (donutChart) donutChart.destroy();

    const activeAssets = assetsData.filter(a => a.stats.current_value > 0);

    if (activeAssets.length === 0) {
      // Display empty state on canvas
      ctx.clearRect(0, 0, 400, 400);
      ctx.fillStyle = "#64748b";
      ctx.textAlign = "center";
      ctx.font = "14px Inter";
      ctx.fillText("No valuation data to chart", 150, 125);
      return;
    }

    const labels = activeAssets.map(a => a.name);
    const data = activeAssets.map(a => a.stats.current_value);

    const colors = [
      "#6366f1", // indigo
      "#3b82f6", // blue
      "#10b981", // green
      "#f59e0b", // amber
      "#ec4899", // pink
      "#8b5cf6", // purple
      "#14b8a6", // teal
    ];

    donutChart = new Chart(ctx, {
      type: "doughnut",
      data: {
        labels: labels,
        datasets: [{
          data: data,
          backgroundColor: colors.slice(0, labels.length),
          borderWidth: 2,
          borderColor: "#161c2f"
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            position: "bottom",
            labels: {
              color: "#94a3b8",
              font: { family: "Inter", size: 11 }
            }
          }
        }
      }
    });
  }

  function renderBarChart() {
    const ctx = document.getElementById("bar-performance").getContext("2d");

    if (barChart) barChart.destroy();

    if (assetsData.length === 0) {
      ctx.clearRect(0, 0, 400, 400);
      ctx.fillStyle = "#64748b";
      ctx.textAlign = "center";
      ctx.font = "14px Inter";
      ctx.fillText("No asset data to chart", 150, 125);
      return;
    }

    const labels = assetsData.map(a => a.name);
    const netInvested = assetsData.map(a => a.stats.net_invested);
    const currentVal = assetsData.map(a => a.stats.current_value);

    barChart = new Chart(ctx, {
      type: "bar",
      data: {
        labels: labels,
        datasets: [
          {
            label: "Net Invested",
            data: netInvested,
            backgroundColor: "rgba(99, 102, 241, 0.8)",
            borderRadius: 4
          },
          {
            label: "Current Value",
            data: currentVal,
            backgroundColor: "rgba(16, 185, 129, 0.8)",
            borderRadius: 4
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          x: {
            grid: { display: false },
            ticks: { color: "#94a3b8", font: { family: "Inter", size: 10 } }
          },
          y: {
            grid: { color: "rgba(255, 255, 255, 0.05)" },
            ticks: { color: "#94a3b8", font: { family: "Inter", size: 10 } }
          }
        },
        plugins: {
          legend: {
            position: "top",
            labels: {
              color: "#94a3b8",
              font: { family: "Inter", size: 11 }
            }
          }
        }
      }
    });
  }

  // --- Form Submissions ---

  formAddAsset.addEventListener("submit", async (e) => {
    e.preventDefault();
    const payload = {
      name: document.getElementById("asset-name").value.trim(),
      type: document.getElementById("asset-type").value,
      isin: document.getElementById("asset-isin").value.trim() || null,
      wkn: document.getElementById("asset-wkn").value.trim() || null,
      comment: document.getElementById("asset-comment").value.trim() || null
    };

    try {
      const res = await fetch(`${API_BASE}/api/assets`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Failed to create asset");
      }

      showToast("Asset successfully registered!");
      formAddAsset.reset();
      refreshData();
    } catch (err) {
      showToast(err.message, "danger");
    }
  });

  formAddTransaction.addEventListener("submit", async (e) => {
    e.preventDefault();
    const payload = {
      asset_id: parseInt(document.getElementById("tx-asset-id").value),
      type: document.getElementById("tx-type").value,
      amount: parseFloat(document.getElementById("tx-amount").value),
      timestamp: document.getElementById("tx-date").value,
      comment: document.getElementById("tx-comment").value.trim() || null
    };

    try {
      const res = await fetch(`${API_BASE}/api/transactions`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Failed to log transaction");
      }

      showToast("Transaction successfully recorded!");
      // Reset amount & comment
      document.getElementById("tx-amount").value = "";
      document.getElementById("tx-comment").value = "";
      refreshData();
    } catch (err) {
      showToast(err.message, "danger");
    }
  });

  formAddSnapshot.addEventListener("submit", async (e) => {
    e.preventDefault();
    const payload = {
      asset_id: parseInt(document.getElementById("snap-asset-id").value),
      value: parseFloat(document.getElementById("snap-value").value),
      timestamp: document.getElementById("snap-date").value,
      comment: document.getElementById("snap-comment").value.trim() || null
    };

    try {
      const res = await fetch(`${API_BASE}/api/snapshots`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Failed to log snapshot");
      }

      showToast("Valuation snapshot successfully recorded!");
      // Reset value & comment
      document.getElementById("snap-value").value = "";
      document.getElementById("snap-comment").value = "";
      refreshData();
    } catch (err) {
      showToast(err.message, "danger");
    }
  });

  // --- Helper Helpers ---
  function formatCurrency(value, withSign = false) {
    const sign = withSign && value >= 0 ? "+" : "";
    return `${sign}${value.toLocaleString("de-DE", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} €`;
  }

  // Set today's date on date inputs
  const todayStr = new Date().toISOString().split("T")[0];
  document.getElementById("tx-date").value = todayStr;
  document.getElementById("snap-date").value = todayStr;

  // --- Initial App Load ---
  refreshData();
});
