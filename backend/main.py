
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional
from pathlib import Path
from datetime import datetime
import pandas as pd
import numpy as np
import joblib
import json
import uuid
import math

# ============================================================
# APP
# ============================================================

app = FastAPI(
    title="ReviveAI",
    description="AI Revenue Recovery Platform",
    version="1.0.0"
)

# ============================================================
# CORS
# ============================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
         "https://reviveai-1-k55n.onrender.com",
         "http://localhost:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================
# PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

MODEL_DIR = BASE_DIR / "model"
DATA_DIR = BASE_DIR / "data"

MODEL_DIR.mkdir(exist_ok=True)
DATA_DIR.mkdir(exist_ok=True)

PREPROCESSOR_PATH = MODEL_DIR / "reviveai_preprocessor.pkl"
MODEL_JSON_PATH = MODEL_DIR / "reviveai_xgboost.json"
MODEL_PKL_PATH = MODEL_DIR / "reviveai_xgboost_model.pkl"

DATA_PATH = DATA_DIR / "recovery_outcomes.csv"

# ============================================================
# GLOBAL OBJECTS
# ============================================================

preprocessor = None
xgb_model = None
recovery_df = None

# Only live decisions are stored here.
audit_log = []

# ============================================================
# REQUIRED MODEL FEATURES
# ============================================================

FEATURE_COLUMNS = [
    "amount",
    "failure_type",
    "attempt_number",
    "total_orders",
    "total_spend",
    "avg_order_value",
    "customer_tenure_days",
    "cancelled_orders",
    "cancellation_rate",
]

# ============================================================
# REQUEST SCHEMA
# ============================================================

class RecoveryRequest(BaseModel):

    transaction_id: Optional[str] = None

    amount: float = Field(..., gt=0)

    failure_type: str

    total_orders: int = Field(default=1, ge=0)

    customer_tenure_days: int = Field(default=30, ge=0)

    cancelled_orders: int = Field(default=0, ge=0)

    retry_count: int = Field(default=1, ge=0)

    total_spend: Optional[float] = None

    avg_order_value: Optional[float] = None

    attempt_number: Optional[int] = None


# ============================================================
# UTILITY FUNCTIONS
# ============================================================

def safe_float(value, default=0.0):
    """
    Convert any value to a finite float.
    Prevents NaN / Infinity from entering the API.
    """

    try:
        value = float(value)

        if not math.isfinite(value):
            return float(default)

        return value

    except Exception:
        return float(default)


def clean_probability(value):
    """
    Guarantees probability is always between 0 and 1.
    """

    value = safe_float(value, 0.5)

    if value < 0:
        value = 0

    if value > 1:
        value = 1

    return round(value, 4)


def clean_failure_type(value):
    """
    Normalize failure type.
    """

    if value is None:
        return "UNKNOWN"

    value = str(value).strip().upper()

    if not value:
        return "UNKNOWN"

    return value


def generate_transaction_id():
    return f"TXN_DEMO_{int(datetime.now().timestamp() * 1000)}"


# ============================================================
# POLICY ENGINE
# ============================================================

def policy_engine(
    probability,
    failure_type,
    retry_count,
    amount
):
    """
    Deterministic recovery policy.

    The ML model predicts recovery probability.
    The policy engine decides what action is allowed.

    This keeps ML prediction and business decision separate.
    """

    probability = clean_probability(probability)

    failure_type = clean_failure_type(failure_type)

    retry_count = int(max(0, retry_count))

    # --------------------------------------------------------
    # HARD SAFETY RULES
    # --------------------------------------------------------

    # Too many retries -> human review
    if retry_count >= 3:
        return {
            "action": "ESCALATE",
            "decision": "HUMAN REVIEW",
            "reason": "Maximum automatic retry limit reached.",
            "customer_message": (
                "We could not safely complete your payment automatically. "
                "Our support team will review it."
            )
        }

    # Card expired -> update card
    if failure_type == "CARD_EXPIRED":
        if probability >= 0.55:
            return {
                "action": "UPDATE_CARD",
                "decision": "AUTOMATED",
                "reason": (
                    "Payment method appears expired; customer should "
                    "update card details."
                ),
                "customer_message": (
                    "Your payment method appears to have expired. "
                    "Please update your payment details."
                )
            }

        return {
            "action": "ESCALATE",
            "decision": "HUMAN REVIEW",
            "reason": "Expired payment method with low recovery probability.",
            "customer_message": (
                "We could not safely complete your payment automatically. "
                "Our support team will review it."
            )
        }

    # --------------------------------------------------------
    # TEMPORARY PAYMENT FAILURES
    # --------------------------------------------------------

    if failure_type in ["NETWORK_ERROR", "TIMEOUT"]:

        if probability >= 0.80:
            return {
                "action": "RETRY",
                "decision": "AUTOMATED",
                "reason": (
                    "High recovery probability and temporary payment failure."
                ),
                "customer_message": (
                    f"Your payment of ₹{amount:,.2f} encountered a temporary "
                    "issue. We will safely retry it."
                )
            }

        if probability >= 0.60:
            return {
                "action": "PAYMENT_LINK",
                "decision": "AUTOMATED",
                "reason": (
                    "Moderate recovery probability; payment link provides "
                    "a safer alternative."
                ),
                "customer_message": (
                    "Your payment could not be completed. "
                    "Please use the secure payment link to complete it."
                )
            }

        return {
            "action": "ESCALATE",
            "decision": "HUMAN REVIEW",
            "reason": "Low recovery probability for temporary payment failure.",
            "customer_message": (
                "We could not safely complete your payment automatically. "
                "Our support team will review it."
            )
        }

    # --------------------------------------------------------
    # INSUFFICIENT FUNDS
    # --------------------------------------------------------

    if failure_type == "INSUFFICIENT_FUNDS":

        if probability >= 0.65:
            return {
                "action": "PAYMENT_LINK",
                "decision": "AUTOMATED",
                "reason": (
                    "Customer has a reasonable recovery probability; "
                    "payment link is preferred over repeated retries."
                ),
                "customer_message": (
                    "Your payment could not be completed. "
                    "Please use the secure payment link when convenient."
                )
            }

        if probability >= 0.45:
            return {
                "action": "REMINDER",
                "decision": "AUTOMATED",
                "reason": (
                    "Moderate recovery probability; reminder avoids "
                    "aggressive retry behavior."
                ),
                "customer_message": (
                    "Your payment is still pending. "
                    "Please complete it when you are ready."
                )
            }

        return {
            "action": "ESCALATE",
            "decision": "HUMAN REVIEW",
            "reason": "Low recovery probability.",
            "customer_message": (
                "We could not safely complete your payment automatically. "
                "Our support team will review it."
            )
        }

    # --------------------------------------------------------
    # LIMIT EXCEEDED
    # --------------------------------------------------------

    if failure_type == "LIMIT_EXCEEDED":

        if probability >= 0.70:
            return {
                "action": "PAYMENT_LINK",
                "decision": "AUTOMATED",
                "reason": (
                    "Alternative payment flow is preferable to retrying "
                    "a limit-related failure."
                ),
                "customer_message": (
                    "Your payment could not be completed using the current "
                    "method. Please use the secure payment link."
                )
            }

        return {
            "action": "ESCALATE",
            "decision": "HUMAN REVIEW",
            "reason": "Payment limit issue requires review.",
            "customer_message": (
                "We could not safely complete your payment automatically. "
                "Our support team will review it."
            )
        }

    # --------------------------------------------------------
    # UNKNOWN FAILURE
    # --------------------------------------------------------

    if probability >= 0.75:
        return {
            "action": "PAYMENT_LINK",
            "decision": "AUTOMATED",
            "reason": (
                "Recovery probability is sufficiently high for a "
                "low-risk alternative payment flow."
            ),
            "customer_message": (
                "Your payment could not be completed. "
                "Please use the secure payment link."
            )
        }

    return {
        "action": "ESCALATE",
        "decision": "HUMAN REVIEW",
        "reason": "Failure type requires manual review.",
        "customer_message": (
            "We could not safely complete your payment automatically. "
            "Our support team will review it."
        )
    }


# ============================================================
# MODEL LOADING
# ============================================================

def load_models():

    global preprocessor
    global xgb_model

    # --------------------------------------------------------
    # PREPROCESSOR
    # --------------------------------------------------------

    if PREPROCESSOR_PATH.exists():

        try:

            preprocessor = joblib.load(PREPROCESSOR_PATH)

            print("✅ ReviveAI preprocessor loaded successfully")

        except Exception as e:

            print("❌ Failed to load preprocessor")
            print("Error:", e)

            preprocessor = None

    else:

        print(
            f"⚠️ Preprocessor not found:\n"
            f"{PREPROCESSOR_PATH}"
        )

    # --------------------------------------------------------
    # XGBOOST
    # --------------------------------------------------------

    # First preference: native XGBoost JSON
    if MODEL_JSON_PATH.exists():

        try:

            from xgboost import XGBClassifier

            model = XGBClassifier()

            model.load_model(str(MODEL_JSON_PATH))

            xgb_model = model

            print("✅ ReviveAI XGBoost JSON model loaded successfully")

            return

        except Exception as e:

            print("⚠️ JSON XGBoost model could not be loaded")
            print("Error:", e)

    # Second preference: joblib
    if MODEL_PKL_PATH.exists():

        try:

            xgb_model = joblib.load(MODEL_PKL_PATH)

            print("✅ ReviveAI XGBoost PKL model loaded successfully")

            return

        except Exception as e:

            print("⚠️ PKL XGBoost model could not be loaded")
            print("Error:", e)

    print("⚠️ XGBoost model unavailable.")

    print("Expected one of:")
    print(MODEL_JSON_PATH)
    print(MODEL_PKL_PATH)


# ============================================================
# DATASET LOADING
# ============================================================

def load_dataset():

    global recovery_df

    if not DATA_PATH.exists():

        print(
            f"⚠️ Recovery dataset not found:\n"
            f"{DATA_PATH}"
        )

        recovery_df = pd.DataFrame()

        return

    try:

        recovery_df = pd.read_csv(DATA_PATH)

        print(
            f"✅ Recovery dataset loaded: "
            f"{len(recovery_df)} records"
        )

    except Exception as e:

        print("❌ Failed to load recovery dataset")
        print("Error:", e)

        recovery_df = pd.DataFrame()


# Load at startup
load_models()
load_dataset()


# ============================================================
# MODEL PREDICTION
# ============================================================

def predict_recovery_probability(data: dict):

    """
    Predict recovery probability.

    If ML model is unavailable or produces an invalid value,
    use a deterministic fallback score.

    IMPORTANT:
    Never return NaN.
    """

    # --------------------------------------------------------
    # ML MODEL
    # --------------------------------------------------------

    if xgb_model is not None:

        try:

            input_df = pd.DataFrame(
                [{
                    column: data.get(column)
                    for column in FEATURE_COLUMNS
                }]
            )

            # Preprocessor exists
            if preprocessor is not None:

                transformed = preprocessor.transform(input_df)

                probability = xgb_model.predict_proba(
                    transformed
                )[0][1]

            else:

                probability = xgb_model.predict_proba(
                    input_df
                )[0][1]

            probability = clean_probability(probability)

            return probability, "XGBoost"

        except Exception as e:

            print("⚠️ Model prediction failed")
            print("Error:", e)

    # --------------------------------------------------------
    # FALLBACK SCORE
    # --------------------------------------------------------

    failure_type = clean_failure_type(
        data.get("failure_type")
    )

    retry_count = int(
        data.get("attempt_number", 1)
    )

    probability = 0.60

    if failure_type == "NETWORK_ERROR":
        probability = 0.78

    elif failure_type == "TIMEOUT":
        probability = 0.72

    elif failure_type == "INSUFFICIENT_FUNDS":
        probability = 0.65

    elif failure_type == "CARD_EXPIRED":
        probability = 0.62

    elif failure_type == "LIMIT_EXCEEDED":
        probability = 0.48

    # Customer history adjustment
    total_orders = safe_float(
        data.get("total_orders"),
        1
    )

    cancelled_orders = safe_float(
        data.get("cancelled_orders"),
        0
    )

    if total_orders > 0:

        cancellation_rate = (
            cancelled_orders / total_orders
        )

        if cancellation_rate < 0.20:
            probability += 0.05

        elif cancellation_rate > 0.50:
            probability -= 0.10

    # Retry penalty
    if retry_count >= 2:
        probability -= 0.05

    probability = clean_probability(probability)

    return probability, "Policy fallback"


# ============================================================
# HEALTH
# ============================================================

@app.get("/health")
def health():

    return {
        "status": "healthy",
        "service": "ReviveAI",
        "model_loaded": xgb_model is not None,
        "preprocessor_loaded": preprocessor is not None,
        "dataset_loaded": recovery_df is not None
        and not recovery_df.empty,
        "dataset_records": (
            int(len(recovery_df))
            if recovery_df is not None
            else 0
        ),
    }


# ============================================================
# ROOT
# ============================================================

@app.get("/")
def root():

    return {
        "name": "ReviveAI",
        "description": "AI Revenue Recovery Platform",
        "status": "online",
        "model": (
            "XGBoost"
            if xgb_model is not None
            else "Policy fallback"
        ),
        "endpoints": [
            "/health",
            "/metrics",
            "/audit",
            "/recover",
            "/analytics",
            "/docs",
        ],
    }


# ============================================================
# METRICS
# ============================================================

@app.get("/metrics")
def get_metrics():

    """
    Metrics are based ONLY on live recovery decisions
    made through /recover.

    Dataset size is reported separately.
    """

    total_transactions = len(audit_log)

    automatic_actions = sum(
        1
        for record in audit_log
        if record["decision"] == "AUTOMATED"
    )

    escalations = sum(
        1
        for record in audit_log
        if record["decision"] == "HUMAN REVIEW"
    )

    revenue_at_risk = sum(
        safe_float(record["amount"])
        for record in audit_log
    )

    revenue_recovered = sum(
        safe_float(record.get("amount_recovered", 0))
        for record in audit_log
    )

    if revenue_at_risk > 0:

        recovery_rate = (
            revenue_recovered /
            revenue_at_risk
        ) * 100

    else:

        recovery_rate = 0.0

    if total_transactions > 0:

        automation_rate = (
            automatic_actions /
            total_transactions
        ) * 100

    else:

        automation_rate = 0.0

    action_distribution = {}

    for record in audit_log:

        action = record["action"]

        action_distribution[action] = (
            action_distribution.get(action, 0) + 1
        )

    return {
        "total_transactions": total_transactions,

        "automatic_actions": automatic_actions,

        "escalations": escalations,

        "automation_rate": round(
            automation_rate,
            2
        ),

        "revenue_at_risk": round(
            revenue_at_risk,
            2
        ),

        "revenue_recovered": round(
            revenue_recovered,
            2
        ),

        "recovery_rate": round(
            recovery_rate,
            2
        ),

        "action_distribution": action_distribution,

        "dataset_records": (
            int(len(recovery_df))
            if recovery_df is not None
            else 0
        ),
    }


# ============================================================
# RECOVER
# ============================================================

@app.post("/recover")
def recover(request: RecoveryRequest):

    """
    Main ReviveAI agent endpoint.

    Flow:

    Input
       ↓
    Feature preparation
       ↓
    XGBoost prediction
       ↓
    Policy Engine
       ↓
    Recovery action
       ↓
    Audit trail
    """

    # --------------------------------------------------------
    # TRANSACTION ID
    # --------------------------------------------------------

    transaction_id = (
        request.transaction_id
        if request.transaction_id
        else generate_transaction_id()
    )

    # --------------------------------------------------------
    # FAILURE TYPE
    # --------------------------------------------------------

    failure_type = clean_failure_type(
        request.failure_type
    )

    # --------------------------------------------------------
    # ATTEMPT NUMBER
    # --------------------------------------------------------

    if request.attempt_number is not None:

        attempt_number = max(
            1,
            int(request.attempt_number)
        )

    else:

        attempt_number = (
            int(request.retry_count) + 1
        )

    # --------------------------------------------------------
    # CUSTOMER FEATURES
    # --------------------------------------------------------

    total_orders = max(
        0,
        int(request.total_orders)
    )

    cancelled_orders = max(
        0,
        int(request.cancelled_orders)
    )

    if request.total_spend is not None:

        total_spend = max(
            0,
            safe_float(request.total_spend)
        )

    else:

        total_spend = (
            float(total_orders)
            * float(request.amount)
        )

    if request.avg_order_value is not None:

        avg_order_value = max(
            0,
            safe_float(request.avg_order_value)
        )

    elif total_orders > 0:

        avg_order_value = (
            total_spend /
            total_orders
        )

    else:

        avg_order_value = float(
            request.amount
        )

    if total_orders > 0:

        cancellation_rate = (
            cancelled_orders /
            total_orders
        )

    else:

        cancellation_rate = 0.0

    cancellation_rate = clean_probability(
        cancellation_rate
    )

    # --------------------------------------------------------
    # MODEL INPUT
    # --------------------------------------------------------

    model_input = {

        "amount": safe_float(
            request.amount
        ),

        "failure_type": failure_type,

        "attempt_number": attempt_number,

        "total_orders": total_orders,

        "total_spend": total_spend,

        "avg_order_value": avg_order_value,

        "customer_tenure_days": max(
            0,
            int(request.customer_tenure_days)
        ),

        "cancelled_orders": cancelled_orders,

        "cancellation_rate": cancellation_rate,
    }

    # --------------------------------------------------------
    # PREDICTION
    # --------------------------------------------------------

    probability, prediction_source = (
        predict_recovery_probability(
            model_input
        )
    )

    probability = clean_probability(
        probability
    )

    # --------------------------------------------------------
    # POLICY
    # --------------------------------------------------------

    policy = policy_engine(
        probability=probability,
        failure_type=failure_type,
        retry_count=int(request.retry_count),
        amount=float(request.amount),
    )

    action = policy["action"]

    decision = policy["decision"]

    # --------------------------------------------------------
    # SIMULATED RECOVERY
    # --------------------------------------------------------

    # This is intentionally conservative.
    #
    # In a real system, this field would only become non-zero
    # after an actual payment provider confirms recovery.
    #
    # For the hackathon demo we simulate a bounded recovery
    # outcome for automated actions.

    amount_recovered = 0.0

    if decision == "AUTOMATED":

        # Simulated expected recovery value.
        amount_recovered = (
            float(request.amount)
            * probability
        )

        amount_recovered = round(
            amount_recovered,
            2
        )

    recovery_status = (
        "Approved"
        if decision == "AUTOMATED"
        else "Escalated"
    )

    # --------------------------------------------------------
    # AUDIT RECORD
    # --------------------------------------------------------

    audit_record = {

        "transaction_id": transaction_id,

        "timestamp": datetime.now().isoformat(),

        "amount": round(
            float(request.amount),
            2
        ),

        "failure_type": failure_type,

        "attempt_number": attempt_number,

        "total_orders": total_orders,

        "customer_tenure_days": int(
            request.customer_tenure_days
        ),

        "cancelled_orders": cancelled_orders,

        "retry_count": int(
            request.retry_count
        ),

        "recovery_probability": probability,

        "probability_percent": round(
            probability * 100,
            1
        ),

        "action": action,

        "decision": decision,

        "status": recovery_status,

        "reason": policy["reason"],

        "customer_message": policy[
            "customer_message"
        ],

        "amount_recovered": amount_recovered,

        "prediction_source": prediction_source,
    }

    # --------------------------------------------------------
    # SAVE EXACTLY ONE AUDIT RECORD
    # --------------------------------------------------------

    audit_log.append(
        audit_record
    )

    # --------------------------------------------------------
    # RESPONSE
    # --------------------------------------------------------

    return {

        "success": True,

        "transaction_id": transaction_id,

        "amount": round(
            float(request.amount),
            2
        ),

        "failure_type": failure_type,

        "recovery_probability": probability,

        "recovery_probability_percent": round(
            probability * 100,
            1
        ),

        "action": action,

        "decision": decision,

        "status": recovery_status,

        "reason": policy["reason"],

        "customer_message": policy[
            "customer_message"
        ],

        "amount_recovered": amount_recovered,

        "prediction_source": prediction_source,

        "audit_recorded": True,
    }


# ============================================================
# AUDIT
# ============================================================

@app.get("/audit")
def get_audit():

    """
    Returns live recovery decision history.

    Most recent decisions appear first.
    """

    return {
        "count": len(audit_log),
        "records": list(
            reversed(audit_log)
        )
    }


# ============================================================
# ANALYTICS
# ============================================================

@app.get("/analytics")
def get_analytics():

    """
    Analytics calculated from live decisions.
    """

    if not audit_log:

        return {
            "total_transactions": 0,
            "revenue_at_risk": 0.0,
            "revenue_recovered": 0.0,
            "recovery_rate": 0.0,
            "actions": []
        }

    df = pd.DataFrame(
        audit_log
    )

    grouped = []

    for action, group in df.groupby(
        "action"
    ):

        transactions = len(group)

        revenue_at_risk = group[
            "amount"
        ].apply(
            safe_float
        ).sum()

        revenue_recovered = group[
            "amount_recovered"
        ].apply(
            safe_float
        ).sum()

        if revenue_at_risk > 0:

            recovery_rate = (
                revenue_recovered /
                revenue_at_risk
            ) * 100

        else:

            recovery_rate = 0.0

        grouped.append({

            "action": action,

            "transactions": int(
                transactions
            ),

            "recovery_rate": round(
                recovery_rate,
                2
            ),

            "revenue_recovered": round(
                revenue_recovered,
                2
            )
        })

    total_risk = df[
        "amount"
    ].apply(
        safe_float
    ).sum()

    total_recovered = df[
        "amount_recovered"
    ].apply(
        safe_float
    ).sum()

    overall_rate = (
        (
            total_recovered /
            total_risk
        ) * 100
        if total_risk > 0
        else 0
    )

    return {

        "total_transactions": len(df),

        "revenue_at_risk": round(
            total_risk,
            2
        ),

        "revenue_recovered": round(
            total_recovered,
            2
        ),

        "recovery_rate": round(
            overall_rate,
            2
        ),

        "actions": grouped,
    }


# ============================================================
# CLEAR AUDIT
# ============================================================

@app.delete("/audit")
def clear_audit():

    """
    Clears live audit decisions.

    Dataset is NOT modified.
    """

    audit_log.clear()

    return {
        "success": True,
        "message": "Live audit trail cleared."
    }


# ============================================================
# RUN DIRECTLY
# ============================================================

if __name__ == "__main__":

    import uvicorn

    uvicorn.run(
        "main:app",
        host="127.0.0.1",
        port=8000,
        reload=True
    )
