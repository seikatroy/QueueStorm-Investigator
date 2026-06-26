# QueueStorm Investigator

## Overview

QueueStorm Investigator is an AI-assisted fintech ticket triage and investigation system.

It analyzes customer complaints, classifies ticket types, verifies transaction evidence, assigns severity, routes tickets to departments, and recommends human review when needed.

---

## Features

- GET /health
- POST /analyze-ticket
- Complaint classification
- Transaction evidence verification
- Department routing
- Severity assignment
- Human review recommendation
- Bangla, Banglish and English complaint support
- Error handling and safety validation

---

## Setup

Clone the repository:

```bash
git clone <repository-url>
cd QueueStorm-Investigator
```

Install dependencies:

```bash
pip install -r requirements.txt
```

---

## Run

```bash
python app.py
```

Server runs on:

```text
http://127.0.0.1:5000
```

---

## Health Check

Endpoint:

```http
GET /health
```

Response:

```json
{
  "status": "ok"
}
```

---

## Analyze Ticket

Endpoint:

```http
POST /analyze-ticket
```

Example Request:

```json
{
  "ticket_id":"TKT-001",
  "complaint":"ami vul number e 5000 taka pathaisi"
}
```

---

## AI Usage

The system uses a hybrid approach:

- Rule-based classification and validation
- Bangla/Banglish complaint understanding
- Transaction evidence verification
- Safety and escalation logic

---

## Safety Logic

- Invalid JSON validation
- Empty complaint validation
- Missing ticket_id validation
- Prompt injection resistance
- OTP/PIN safety messaging
- Human review escalation

---

## Limitations

- Demo system only
- No real banking integration
- No real customer data used