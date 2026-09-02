import { useEffect, useState } from "react";
import axios from "axios";

import {
  TrendingUp,
  Activity,
  AlertTriangle,
  CheckCircle,
  RefreshCw,
  CreditCard,
  Bell,
  ShieldAlert,
  IndianRupee,
  BarChart3,
  Clock,
} from "lucide-react";

import "./App.css";

// ============================================================
// API CONFIGURATION
// ============================================================

// Local development:
// VITE_API_URL=http://127.0.0.1:8000

// Production:
// VITE_API_URL=https://reviveai-g1p3.onrender.com

const API_URL =
  import.meta.env.VITE_API_URL ||
  "http://127.0.0.1:8000";

// ============================================================
// API
// ============================================================

const getMetrics = async () => {
  const response = await axios.get(`${API_URL}/metrics`);
  return response.data;
};

const getAudit = async () => {
  const response = await axios.get(`${API_URL}/audit`);
  return response.data;
};

// ============================================================
// APP
// ============================================================

function App() {
  const [metrics, setMetrics] = useState(null);
  const [audit, setAudit] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);

  // ==========================================================
  // FORM
  // ==========================================================

  const [form, setForm] = useState({
    transaction_id: "TXN_DEMO",
    amount: 15000,
    failure_type: "NETWORK_ERROR",
    attempt_number: 1,
    total_orders: 12,
    total_spend: 4367.67,
    avg_order_value: 363.97,
    customer_tenure_days: 362,
    cancelled_orders: 2,
    cancellation_rate: 0.1667,
    retry_count: 0,
  });

  // ==========================================================
  // LOAD METRICS
  // ==========================================================

  const loadMetrics = async () => {
    try {
      const data = await getMetrics();

      setMetrics(data);
      setError("");
    } catch (err) {
      console.error("Metrics error:", err);

      setError(
        "Unable to load dashboard metrics. Please check the backend."
      );
    }
  };

  // ==========================================================
  // LOAD AUDIT
  // ==========================================================

  const loadAudit = async () => {
    try {
      const data = await getAudit();

      setAudit(data.records || []);
    } catch (err) {
      console.error("Audit error:", err);
    }
  };

  // ==========================================================
  // INITIAL LOAD
  // ==========================================================

  useEffect(() => {
    loadMetrics();
    loadAudit();
  }, []);

  // ==========================================================
  // FORM CHANGE
  // ==========================================================

  const handleChange = (e) => {
    const { name, value } = e.target;

    const numericFields = [
      "amount",
      "attempt_number",
      "total_orders",
      "total_spend",
      "avg_order_value",
      "customer_tenure_days",
      "cancelled_orders",
      "cancellation_rate",
      "retry_count",
    ];

    setForm((previous) => ({
      ...previous,
      [name]: numericFields.includes(name)
        ? Number(value)
        : value,
    }));
  };

  // ==========================================================
  // RECOVERY AGENT
  // ==========================================================

  const runRecovery = async () => {
    setLoading(true);
    setResult(null);
    setError("");

    try {
      // Generate unique transaction ID
      const transactionId = `TXN_${Date.now()}_${Math.random()
        .toString(36)
        .substring(2, 7)
        .toUpperCase()}`;

      const requestData = {
        ...form,
        transaction_id: transactionId,
      };

      const response = await axios.post(
        `${API_URL}/recover`,
        requestData
      );

      setResult(response.data);

      // Refresh dashboard after recovery decision
      await Promise.all([
        loadMetrics(),
        loadAudit(),
      ]);
    } catch (err) {
      console.error("Recovery error:", err);

      setError(
        err.response?.data?.detail ||
          "Unable to connect to ReviveAI backend."
      );
    } finally {
      setLoading(false);
    }
  };

  // ==========================================================
  // SAFE NUMBER
  // ==========================================================

  const safeNumber = (value, fallback = 0) => {
    const num = Number(value);

    return Number.isFinite(num) ? num : fallback;
  };

  // ==========================================================
  // SAFE PROBABILITY
  // ==========================================================

  const getProbability = (value) => {
    const probability = safeNumber(value);

    return Math.min(Math.max(probability, 0), 1);
  };

  // ==========================================================
  // FORMAT CURRENCY
  // ==========================================================

  const currency = (value) => {
    return new Intl.NumberFormat("en-IN", {
      style: "currency",
      currency: "INR",
      maximumFractionDigits: 2,
    }).format(safeNumber(value));
  };

  // ==========================================================
  // FORMAT NUMBER
  // ==========================================================

  const number = (value) => {
    return new Intl.NumberFormat("en-IN").format(
      safeNumber(value)
    );
  };

  // ==========================================================
  // ACTION ICON
  // ==========================================================

  const actionIcon = (action) => {
    switch (action) {
      case "RETRY":
        return <RefreshCw size={16} />;

      case "PAYMENT_LINK":
        return <CreditCard size={16} />;

      case "UPDATE_CARD":
        return <CreditCard size={16} />;

      case "REMINDER":
        return <Bell size={16} />;

      case "ESCALATE":
        return <ShieldAlert size={16} />;

      default:
        return <Activity size={16} />;
    }
  };

  // ==========================================================
  // ACTION NAME
  // ==========================================================

  const formatAction = (action) => {
    return String(action || "").replaceAll("_", " ");
  };

  // ==========================================================
  // RECOVERY RATE
  // ==========================================================

  const recoveryRate = safeNumber(
    metrics?.recovery_rate
  );

  // ==========================================================
  // AUTOMATION RATE
  // ==========================================================

  const automationRate = safeNumber(
    metrics?.automation_rate,
    metrics?.total_transactions > 0
      ? (safeNumber(metrics.automatic_actions) /
          safeNumber(metrics.total_transactions)) *
          100
      : 0
  );

  // ==========================================================
  // ACTION ANALYTICS
  // ==========================================================

  const actionAnalytics =
    metrics?.action_analytics || {};

  // ==========================================================
  // MAX REVENUE FOR BAR
  // ==========================================================

  const maxRevenue = Math.max(
    ...Object.values(actionAnalytics).map((item) =>
      safeNumber(item?.revenue_recovered)
    ),
    1
  );

  // ==========================================================
  // CURRENT RESULT PROBABILITY
  // ==========================================================

  const resultProbability = getProbability(
    result?.recovery_probability
  );

  // ==========================================================
  // RENDER
  // ==========================================================

  return (
    <div className="app">

      {/* =====================================================
          SIDEBAR
      ====================================================== */}

      <aside className="sidebar">

        <div className="brand">

          <div className="brand-icon">
            R
          </div>

          <div>
            <h2>ReviveAI</h2>

            <span>
              Revenue Recovery
            </span>
          </div>

        </div>

        <nav>

          <div className="nav-item active">
            Dashboard
          </div>

          <div className="nav-item">
            Recovery Agent
          </div>

          <div className="nav-item">
            Audit Trail
          </div>

          <div className="nav-item">
            Analytics
          </div>

        </nav>

        <div className="sidebar-bottom">

          <div className="ai-status">

            <span className="status-dot"></span>

            <div>

              <strong>
                AI Agent Online
              </strong>

              <small>
                XGBoost + Policy Engine
              </small>

            </div>

          </div>

        </div>

      </aside>

      {/* =====================================================
          MAIN
      ====================================================== */}

      <main className="main">

        {/* ===================================================
            HEADER
        ==================================================== */}

        <header className="header">

          <div>

            <h1>
              Revenue Recovery Dashboard
            </h1>

            <p>
              Monitor AI-driven recovery decisions
              and recovered revenue.
            </p>

          </div>

          <div className="live-badge">

            <span></span>

            LIVE

          </div>

        </header>

        {/* ===================================================
            ERROR
        ==================================================== */}

        {error && (

          <div className="error-banner">

            <AlertTriangle size={18} />

            {error}

          </div>

        )}

        {/* ===================================================
            REVENUE KPI CARDS
        ==================================================== */}

        <section className="kpi-grid">

          {/* Revenue At Risk */}

          <div className="kpi-card">

            <div className="kpi-icon">
              <IndianRupee />
            </div>

            <div>

              <span>
                Revenue at Risk
              </span>

              <strong>
                {currency(
                  metrics?.revenue_at_risk
                )}
              </strong>

              <small>
                Payment value at risk
              </small>

            </div>

          </div>

          {/* Revenue Recovered */}

          <div className="kpi-card">

            <div className="kpi-icon">
              <TrendingUp />
            </div>

            <div>

              <span>
                Revenue Recovered
              </span>

              <strong>
                {currency(
                  metrics?.revenue_recovered
                )}
              </strong>

              <small>
                Estimated recovered value
              </small>

            </div>

          </div>

          {/* Recovery Rate */}

          <div className="kpi-card">

            <div className="kpi-icon">
              <BarChart3 />
            </div>

            <div>

              <span>
                Recovery Rate
              </span>

              <strong>
                {recoveryRate.toFixed(2)}%
              </strong>

              <small>
                Revenue recovery performance
              </small>

            </div>

          </div>

          {/* Transactions */}

          <div className="kpi-card">

            <div className="kpi-icon">
              <Activity />
            </div>

            <div>

              <span>
                Transactions
              </span>

              <strong>
                {number(
                  metrics?.total_transactions
                )}
              </strong>

              <small>
                Transactions processed
              </small>

            </div>

          </div>

          {/* Automatic Actions */}

          <div className="kpi-card">

            <div className="kpi-icon">
              <CheckCircle />
            </div>

            <div>

              <span>
                Automatic Actions
              </span>

              <strong>
                {number(
                  metrics?.automatic_actions
                )}
              </strong>

              <small>
                AI handled
              </small>

            </div>

          </div>

          {/* Escalations */}

          <div className="kpi-card warning">

            <div className="kpi-icon">
              <AlertTriangle />
            </div>

            <div>

              <span>
                Escalations
              </span>

              <strong>
                {number(
                  metrics?.escalations
                )}
              </strong>

              <small>
                Human review required
              </small>

            </div>

          </div>

        </section>

        {/* ===================================================
            AUTOMATION BANNER
        ==================================================== */}

        <section className="automation-banner">

          <div>

            <div className="automation-title">

              <CheckCircle size={20} />

              AI Automation Rate

            </div>

            <p>
              ReviveAI automatically handles
              eligible recovery decisions while
              escalating risky transactions.
            </p>

          </div>

          <div className="automation-value">

            {automationRate.toFixed(1)}%

          </div>

          <div className="automation-detail">

            {number(
              metrics?.automatic_actions
            )}

            {" "}of{" "}

            {number(
              metrics?.total_transactions
            )}

            {" "}decisions automated

          </div>

        </section>

        {/* ===================================================
            CONTENT GRID
        ==================================================== */}

        <section className="content-grid">

          {/* =================================================
              RECOVERY AGENT
          ================================================== */}

          <div className="panel simulator">

            <div className="panel-header">

              <div>

                <h2>
                  Recovery Agent
                </h2>

                <p>
                  Analyze a failed payment
                </p>

              </div>

              <div className="ai-badge">
                AI
              </div>

            </div>

            {/* FORM */}

            <div className="form-grid">

              {/* Amount */}

              <div className="form-group">

                <label>
                  Amount (₹)
                </label>

                <input
                  type="number"
                  name="amount"
                  value={form.amount}
                  onChange={handleChange}
                  min="1"
                />

              </div>

              {/* Failure */}

              <div className="form-group">

                <label>
                  Failure Type
                </label>

                <select
                  name="failure_type"
                  value={form.failure_type}
                  onChange={handleChange}
                >

                  <option>
                    NETWORK_ERROR
                  </option>

                  <option>
                    TIMEOUT
                  </option>

                  <option>
                    INSUFFICIENT_FUNDS
                  </option>

                  <option>
                    CARD_EXPIRED
                  </option>

                  <option>
                    LIMIT_EXCEEDED
                  </option>

                </select>

              </div>

              {/* Total Orders */}

              <div className="form-group">

                <label>
                  Total Orders
                </label>

                <input
                  type="number"
                  name="total_orders"
                  value={form.total_orders}
                  onChange={handleChange}
                  min="0"
                />

              </div>

              {/* Customer Tenure */}

              <div className="form-group">

                <label>
                  Customer Tenure (days)
                </label>

                <input
                  type="number"
                  name="customer_tenure_days"
                  value={
                    form.customer_tenure_days
                  }
                  onChange={handleChange}
                  min="0"
                />

              </div>

              {/* Cancelled Orders */}

              <div className="form-group">

                <label>
                  Cancelled Orders
                </label>

                <input
                  type="number"
                  name="cancelled_orders"
                  value={
                    form.cancelled_orders
                  }
                  onChange={handleChange}
                  min="0"
                />

              </div>

              {/* Retry Count */}

              <div className="form-group">

                <label>
                  Retry Count
                </label>

                <input
                  type="number"
                  name="retry_count"
                  value={form.retry_count}
                  onChange={handleChange}
                  min="0"
                />

              </div>

            </div>

            {/* BUTTON */}

            <button
              className="recover-button"
              onClick={runRecovery}
              disabled={loading}
            >

              {loading ? (

                <>
                  <RefreshCw
                    size={18}
                    className="spin"
                  />

                  Analyzing...
                </>

              ) : (

                <>
                  Analyze & Recover
                </>

              )}

            </button>

            {/* =================================================
                RESULT
            ================================================== */}

            {result && (

              <div className="result-card">

                <div className="result-top">

                  <div>

                    <span>
                      Recovery Probability
                    </span>

                    <strong>
                      {(resultProbability * 100).toFixed(1)}%
                    </strong>

                  </div>

                  <div className="result-action">

                    {actionIcon(
                      result.action ||
                      result.recommended_action
                    )}

                    {formatAction(
                      result.action ||
                      result.recommended_action
                    )}

                  </div>

                </div>

                {/* Probability Bar */}

                <div className="probability-bar">

                  <div
                    style={{
                      width: `${resultProbability * 100}%`,
                    }}
                  />

                </div>

                {/* Decision */}

                <div className="decision">

                  <strong>
                    Why this action?
                  </strong>

                  <p>
                    {result.reason ||
                      "Policy engine selected this action based on the predicted recovery probability and payment failure type."}
                  </p>

                </div>

                {/* Policy */}

                <div className="policy-result">

                  <div>

                    <span>
                      Policy Decision
                    </span>

                    <strong>
                      {result.approved === true ||
                      result.decision === "AUTOMATED"
                        ? "AUTOMATED"
                        : "HUMAN REVIEW"}
                    </strong>

                  </div>

                  <div>

                    {result.approved === true ||
                    result.decision === "AUTOMATED" ? (

                      <CheckCircle size={18} />

                    ) : (

                      <AlertTriangle size={18} />

                    )}

                  </div>

                </div>

                {/* Customer Message */}

                <div className="customer-message">

                  <span>
                    Customer Message
                  </span>

                  <p>
                    {result.customer_message}
                  </p>

                </div>

                {/* Expected Recovery */}

                {result.amount_recovered !==
                  undefined && (

                  <div className="customer-message">

                    <span>
                      Estimated Recovery
                    </span>

                    <p>
                      {currency(
                        result.amount_recovered
                      )}
                    </p>

                  </div>

                )}

                {/* Audit */}

                <div className="audit-success">

                  <CheckCircle size={16} />

                  Decision recorded in audit trail

                </div>

              </div>

            )}

          </div>

          {/* =================================================
              RECOVERY ACTIONS
          ================================================== */}

          <div className="panel">

            <div className="panel-header">

              <div>

                <h2>
                  Recovery Actions
                </h2>

                <p>
                  Agent decision distribution
                </p>

              </div>

              <BarChart3 size={20} />

            </div>

            <div className="actions-list">

              {metrics?.action_distribution &&
                Object.entries(
                  metrics.action_distribution
                )
                  .sort(
                    ([, a], [, b]) =>
                      Number(b) - Number(a)
                  )
                  .map(
                    ([action, count]) => {

                      const total =
                        safeNumber(
                          metrics.total_transactions,
                          1
                        ) || 1;

                      const percentage =
                        (safeNumber(count) /
                          total) *
                        100;

                      return (

                        <div
                          className="action-row"
                          key={action}
                        >

                          <div className="action-name">

                            {actionIcon(action)}

                            <span>
                              {formatAction(action)}
                            </span>

                          </div>

                          <div className="action-progress">

                            <div>

                              <span
                                style={{
                                  width: `${Math.min(
                                    percentage,
                                    100
                                  )}%`,
                                }}
                              />

                            </div>

                          </div>

                          <strong>
                            {number(count)}
                          </strong>

                        </div>

                      );
                    }
                  )}

            </div>

            {/* Exceptions */}

            <div className="exception-box">

              <AlertTriangle size={20} />

              <div>

                <strong>

                  {number(
                    metrics?.escalations
                  )}

                  {" "}exceptions

                </strong>

                <p>
                  Automatically escalated
                  for human review.
                </p>

              </div>

            </div>

          </div>

        </section>

        {/* ===================================================
            ANALYTICS
        ==================================================== */}

        <section className="panel analytics-panel">

          <div className="panel-header">

            <div>

              <h2>
                Recovery Analytics
              </h2>

              <p>
                Revenue recovered by intervention
              </p>

            </div>

            <TrendingUp size={22} />

          </div>

          <div className="analytics-content">

            {/* BAR CHART */}

            <div className="revenue-chart">

              {Object.entries(
                actionAnalytics
              )
                .sort(
                  ([, a], [, b]) =>
                    safeNumber(
                      b?.revenue_recovered
                    ) -
                    safeNumber(
                      a?.revenue_recovered
                    )
                )
                .map(
                  ([action, data]) => {

                    const recovered =
                      safeNumber(
                        data?.revenue_recovered
                      );

                    const width =
                      (recovered /
                        maxRevenue) *
                      100;

                    return (

                      <div
                        className="chart-row"
                        key={action}
                      >

                        <div className="chart-label">

                          {actionIcon(action)}

                          <span>
                            {formatAction(action)}
                          </span>

                        </div>

                        <div className="chart-bar">

                          <span
                            style={{
                              width: `${Math.max(
                                width,
                                recovered > 0
                                  ? 2
                                  : 0
                              )}%`,
                            }}
                          />

                        </div>

                        <strong>
                          {currency(recovered)}
                        </strong>

                      </div>

                    );
                  }
                )}

            </div>

            {/* ANALYTICS TABLE */}

            <div className="analytics-table">

              <div className="analytics-table-header">

                <span>
                  Action
                </span>

                <span>
                  Transactions
                </span>

                <span>
                  Recovery Rate
                </span>

                <span>
                  Revenue Recovered
                </span>

              </div>

              {Object.entries(
                actionAnalytics
              ).map(
                ([action, data]) => (

                  <div
                    className="analytics-table-row"
                    key={action}
                  >

                    <span className="action-name">

                      {actionIcon(action)}

                      {formatAction(action)}

                    </span>

                    <span>
                      {number(
                        data?.transactions
                      )}
                    </span>

                    <span>
                      {safeNumber(
                        data?.recovery_rate
                      ).toFixed(2)}%
                    </span>

                    <strong>
                      {currency(
                        data?.revenue_recovered
                      )}
                    </strong>

                  </div>

                )
              )}

            </div>

          </div>

        </section>

        {/* ===================================================
            AUDIT TRAIL
        ==================================================== */}

        <section className="panel audit-panel">

          <div className="panel-header">

            <div>

              <h2>
                Recent Recovery Decisions
              </h2>

              <p>
                Complete AI decision audit trail
              </p>

            </div>

            <Clock size={20} />

          </div>

          <div className="table-container">

            <table>

              <thead>

                <tr>

                  <th>
                    Transaction
                  </th>

                  <th>
                    Amount
                  </th>

                  <th>
                    Failure
                  </th>

                  <th>
                    Probability
                  </th>

                  <th>
                    Action
                  </th>

                  <th>
                    Status
                  </th>

                </tr>

              </thead>

              <tbody>

                {audit
                  .slice()
                  .reverse()
                  .slice(0, 10)
                  .map(
                    (item, index) => {

                      const probability =
                        getProbability(
                          item.recovery_probability
                        );

                      const approved =
                        item.approved === true ||
                        item.approved === "True" ||
                        item.approved === "true" ||
                        item.decision ===
                          "AUTOMATED";

                      return (

                        <tr
                          key={`${item.transaction_id}-${item.timestamp || index}`}
                        >

                          <td className="transaction">

                            {item.transaction_id}

                          </td>

                          <td>

                            {currency(
                              item.amount
                            )}

                          </td>

                          <td>

                            {item.failure_type}

                          </td>

                          <td>

                            <span className="probability">

                              {(probability * 100).toFixed(
                                1
                              )}%

                            </span>

                          </td>

                          <td>

                            <span className="action-pill">

                              {actionIcon(
                                item.action ||
                                  item.recommended_action
                              )}

                              {formatAction(
                                item.action ||
                                  item.recommended_action
                              )}

                            </span>

                          </td>

                          <td>

                            {approved ? (

                              <span className="status-approved">

                                <CheckCircle
                                  size={14}
                                />

                                Approved

                              </span>

                            ) : (

                              <span className="status-escalated">

                                <AlertTriangle
                                  size={14}
                                />

                                Escalated

                              </span>

                            )}

                          </td>

                        </tr>

                      );
                    }
                  )}

              </tbody>

            </table>

            {audit.length === 0 && (

              <div className="empty-state">

                <Activity size={24} />

                <p>
                  No recovery decisions yet.
                </p>

              </div>

            )}

          </div>

        </section>

        {/* ===================================================
            FOOTER
        ==================================================== */}

        <footer>

          ReviveAI • AI Revenue Recovery Platform
          • XGBoost + Policy Engine

        </footer>

      </main>

    </div>
  );
}

export default App;