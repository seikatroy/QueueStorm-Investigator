from flask import Flask, request, jsonify
from dotenv import load_dotenv
import google.generativeai as genai
import os
import re
import json

load_dotenv()

app = Flask(__name__)

# =========================
# GEMINI
# =========================

GEMINI_ENABLED = False

try:
    api_key = os.getenv("GEMINI_API_KEY")

    if api_key:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-1.5-flash")
        GEMINI_ENABLED = True

except Exception:
    GEMINI_ENABLED = False


# =========================
# HEALTH
# =========================

@app.route("/")
def home():
    return "QueueStorm Investigator Running"


@app.route("/health")
def health():
    return jsonify({"status": "ok"})


# =========================
# HELPERS
# =========================

def extract_amount(text):

    nums = re.findall(r"\d+", text)

    if nums:
        try:
            return int(nums[0])
        except:
            return None

    return None


# =========================
# RULE ENGINE
# =========================

def detect_case_type_rule(complaint):

    text = complaint.lower()

    # phishing first

    if any(
        k in text
        for k in [
            "otp",
            "pin",
            "password",
            "fraud",
            "scam",
            "asking for otp",
            "called me",
            "verification code"
        ]
    ):
        return "phishing_or_social_engineering"

    if any(
        k in text
        for k in [
            "wrong number",
            "wrong recipient",
            "vul number",
            "bhul number",
            "ভুল নম্বর",
            "ভুল নাম্বার"
        ]
    ):
        return "wrong_transfer"

    if any(
        k in text
        for k in [
            "payment failed",
            "failed payment",
            "balance deducted",
            "transaction failed",
            "deducted"
        ]
    ):
        return "payment_failed"

    if any(
        k in text
        for k in [
            "refund",
            "money back",
            "return my money"
        ]
    ):
        return "refund_request"

    if any(
        k in text
        for k in [
            "duplicate payment",
            "paid twice",
            "charged twice"
        ]
    ):
        return "duplicate_payment"

    if any(
        k in text
        for k in [
            "merchant settlement",
            "settlement not received",
            "settlement"
        ]
    ):
        return "merchant_settlement_delay"

    if any(
        k in text
        for k in [
            "cash in",
            "cashin",
            "agent deposit"
        ]
    ):
        return "agent_cash_in_issue"

    return None


# =========================
# GEMINI FALLBACK
# =========================

def detect_case_type_ai(complaint):

    if not GEMINI_ENABLED:
        return "other"

    prompt = f"""
You are a fintech support classifier.

Understand:
- English
- Bangla
- Banglish

Complaint:
{complaint}

Choose exactly one:

wrong_transfer
payment_failed
refund_request
duplicate_payment
merchant_settlement_delay
agent_cash_in_issue
phishing_or_social_engineering
other

Return ONLY JSON:

{{"case_type":"value"}}
"""

    try:

        response = model.generate_content(prompt)

        text = response.text.strip()

        text = text.replace("```json", "")
        text = text.replace("```", "")

        result = json.loads(text)

        case_type = result.get("case_type", "other")

        allowed = [
            "wrong_transfer",
            "payment_failed",
            "refund_request",
            "duplicate_payment",
            "merchant_settlement_delay",
            "agent_cash_in_issue",
            "phishing_or_social_engineering",
            "other"
        ]

        if case_type not in allowed:
            return "other"

        return case_type

    except Exception:
        return "other"


# =========================
# MAPPING
# =========================

def get_department(case_type):

    mapping = {
        "wrong_transfer": "dispute_resolution",
        "payment_failed": "payments_ops",
        "refund_request": "dispute_resolution",
        "duplicate_payment": "payments_ops",
        "merchant_settlement_delay": "merchant_operations",
        "agent_cash_in_issue": "agent_operations",
        "phishing_or_social_engineering": "fraud_risk",
        "other": "customer_support"
    }

    return mapping.get(case_type, "customer_support")


def get_severity(case_type):

    mapping = {
        "wrong_transfer": "high",
        "payment_failed": "high",
        "refund_request": "medium",
        "duplicate_payment": "high",
        "merchant_settlement_delay": "medium",
        "agent_cash_in_issue": "high",
        "phishing_or_social_engineering": "critical",
        "other": "low"
    }

    return mapping.get(case_type, "low")


# =========================
# EVIDENCE ENGINE
# =========================

def investigate(case_type, complaint, transactions):

    confidence = 0.60
    verdict = "insufficient_data"
    txn_id = None
    reason_codes = [case_type]

    amount = extract_amount(complaint)

    if case_type == "wrong_transfer":

        for txn in transactions:

            if txn.get("type") == "transfer":

                if (
                    amount is None
                    or txn.get("amount") == amount
                ):
                    txn_id = txn.get("transaction_id")
                    verdict = "consistent"
                    confidence = 0.95
                    reason_codes.append("transaction_match")
                    break

    elif case_type == "payment_failed":

        for txn in transactions:

            if (
                txn.get("type") == "payment"
                and txn.get("status") == "failed"
            ):
                txn_id = txn.get("transaction_id")
                verdict = "consistent"
                confidence = 0.95
                reason_codes.append("failed_payment_found")
                break

    elif case_type == "refund_request":

        for txn in transactions:

            if txn.get("status") == "completed":

                txn_id = txn.get("transaction_id")
                verdict = "consistent"
                confidence = 0.90
                reason_codes.append(
                    "completed_transaction_found"
                )
                break

    elif case_type == "duplicate_payment":

        seen = {}

        for txn in transactions:

            key = (
                txn.get("amount"),
                txn.get("counterparty")
            )

            if key in seen:
                txn_id = txn.get("transaction_id")
                verdict = "consistent"
                confidence = 0.90
                reason_codes.append("duplicate_detected")
                break

            seen[key] = True

    return (
        txn_id,
        verdict,
        confidence,
        reason_codes
    )


# =========================
# CUSTOMER REPLY
# =========================

def generate_customer_reply(case_type, txn_id=None):

    if case_type == "wrong_transfer":

        if txn_id:
            return (
                f"We have noted your concern regarding transaction {txn_id}. "
                "The case will be reviewed by the dispute team. "
                "Please never share your PIN, OTP or password."
            )

        return (
            "We have noted your concern regarding a possible wrong transfer. "
            "The case will be reviewed by the dispute team."
        )

    if case_type == "payment_failed":

        return (
            "We understand your concern regarding the failed payment. "
            "Our team will review the transaction status."
        )

    if case_type == "refund_request":

        return (
            "We have received your refund request. "
            "Eligible adjustments will be processed after review."
        )

    if case_type == "phishing_or_social_engineering":

        return (
            "Thank you for reporting this incident. "
            "Never share your OTP, PIN or password with anyone."
        )

    return (
        "We have received your concern and our support team will review it."
    )


# =========================
# API
# =========================

@app.route("/analyze-ticket", methods=["POST"])
def analyze_ticket():

    try:

        data = request.get_json(silent=True)

        if data is None:
            return jsonify({
                "error": "Invalid JSON"
            }), 400

        if not isinstance(data, dict):
            return jsonify({
                "error": "JSON body must be object"
            }), 400

        ticket_id = data.get("ticket_id")

        if not ticket_id:
            return jsonify({
                "error": "ticket_id is required"
            }), 400

        complaint = data.get("complaint")

        if not isinstance(complaint, str):
            return jsonify({
                "error": "complaint must be string"
            }), 400

        if complaint.strip() == "":
            return jsonify({
                "error": "Complaint cannot be empty"
            }), 422

        transactions = data.get(
            "transaction_history",
            []
        )

        if not isinstance(transactions, list):
            transactions = []

        # Rule First

        case_type = detect_case_type_rule(
            complaint
        )

        # AI fallback

        if case_type is None:
            case_type = detect_case_type_ai(
                complaint
            )

        severity = get_severity(case_type)

        department = get_department(case_type)

        (
            txn_id,
            verdict,
            confidence,
            reason_codes
        ) = investigate(
            case_type,
            complaint,
            transactions
        )

        customer_reply = generate_customer_reply(
            case_type,
            txn_id
        )

        human_review_required = (
            severity in ["high", "critical"]
            or verdict == "insufficient_data"
        )

        return jsonify({

            "ticket_id": ticket_id,

            "relevant_transaction_id":
                txn_id,

            "evidence_verdict":
                verdict,

            "case_type":
                case_type,

            "severity":
                severity,

            "department":
                department,

            "agent_summary":
                complaint[:200],

            "recommended_next_action":
                "Review transaction details and follow standard operating procedure.",

            "customer_reply":
                customer_reply,

            "human_review_required":
                human_review_required,

            "confidence":
                round(confidence, 2),

            "reason_codes":
                reason_codes
        })

    except Exception:

        return jsonify({
            "error": "Internal server error"
        }), 500


if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=False
    )