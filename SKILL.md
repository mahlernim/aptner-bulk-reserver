---
name: aptner-visitor-reservation
description: |
  Register visitor vehicle parking reservations on Aptner (아파트너) apartment management system.
  Use this skill when: user wants to register visitor cars, create recurring parking reservations,
  check existing reservations, or delete parking reservations for their apartment.
  Requires: APTNER_ID and APTNER_PW credentials (in .env file or provided by user).
---

# Aptner Visitor Vehicle Reservation Skill

Register and manage visitor vehicle parking reservations on Aptner-enabled Korean apartments.

## Prerequisites

- Python 3.8+
- Dependencies: `pip install python-dotenv pyyaml requests`
- Credentials: `.env` file with `APTNER_ID` and `APTNER_PW`, or get from user

---

## Raw HTTP API Reference

**Base URL:** `https://v2.aptner.com`

### Authentication

**Endpoint:** `POST /auth/token`

**Request:**
```json
{
  "id": "user_aptner_id",
  "password": "user_password"
}
```

**Response:**
```json
{
  "accessToken": "eyJhbGciOiJIUzI1NiIs..."
}
```

**Usage:** Include token in all subsequent requests:
```
Authorization: Bearer {accessToken}
```

---

### List Reservations

**Endpoint:** `GET /pc/reserves?pg={page_number}`

**Headers:**
```
Authorization: Bearer {token}
Content-Type: application/json
```

**Response:**
```json
{
  "totalPages": 1,
  "reserveList": [
    {
      "visitReserveIdx": 124209094,
      "carNo": "12가3456",
      "phone": "01012345678",
      "visitDate": "2026.02.10",
      "purpose": "과외/수업",
      "days": 1,
      "isValid": true
    }
  ]
}
```

---

### Create Reservation

**Endpoint:** `POST /pc/reserve/`

**Headers:**
```
Authorization: Bearer {token}
Content-Type: application/json
```

**Request:**
```json
{
  "carNo": "12가3456",
  "visitDate": "2026.02.10",
  "phone": "01012345678",
  "purpose": "지인/가족방문",
  "days": 1
}
```

**Parameters:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| carNo | string | Yes | License plate number (Korean format) |
| visitDate | string | Yes | Format: `YYYY.MM.DD` |
| phone | string | Yes | Phone number (no dashes) |
| purpose | string | Yes | One of: `지인/가족방문`, `과외/수업`, `돌봄도우미(청소)`, `기타` |
| days | int | No | Duration, 1-30 (default: 1) |

---

### Delete Reservation

**Endpoint:** `DELETE /pc/reserve/{visitReserveIdx}`

**Headers:**
```
Authorization: Bearer {token}
```

**Response:** Empty on success (HTTP 200)

---

## Python Client Usage

The repository includes a Python client (`aptner_api.py`) that wraps these endpoints:

### Initialize Client

```python
from aptner_api import create_client_from_env, AptnerClient

# From .env file (recommended)
client = create_client_from_env()
client.authenticate()

# Or with explicit credentials
client = AptnerClient(user_id="...", password="...")
client.authenticate()
```

### Get Reservations

```python
reservations = client.get_reservations()
# Returns: list of dicts with keys:
#   idx (int): visitReserveIdx for deletion
#   carNo (str): license plate
#   visitDate (date): Python date object
#   visitDateStr (str): "YYYY.MM.DD" format
#   purpose (str): visit purpose
#   phone (str): contact number
#   days (int): reservation duration
```

### Create Reservation

```python
from datetime import date

client.reserve_car(
    car_no="12가3456",
    visit_date=date(2026, 2, 10),
    phone="010-1234-5678",
    purpose="지인/가족방문",
    days=1
)
```

### Delete Reservation

```python
# Get idx from get_reservations() first
client.delete_reservation(idx=124209094)
```

### Check for Duplicates

```python
reserved = client.get_reserved_dates(car_no="12가3456")
# Returns: set of (carNo, date) tuples already reserved
```

---

## Example: Recurring Weekly Reservation

```python
from datetime import date, timedelta
from aptner_api import create_client_from_env

client = create_client_from_env()
client.authenticate()

# Reserve every Tuesday and Thursday for 4 weeks
car_no = "12가3456"
phone = "010-1234-5678"
target_weekdays = [1, 3]  # Monday=0, Tuesday=1, ..., Sunday=6

today = date.today()
end_date = today + timedelta(weeks=4)
reserved = client.get_reserved_dates(car_no)

current = today
while current <= end_date:
    if current.weekday() in target_weekdays:
        if (car_no, current) not in reserved:
            client.reserve_car(
                car_no=car_no,
                visit_date=current,
                phone=phone,
                purpose="과외/수업"
            )
            print(f"Reserved: {current}")
    current += timedelta(days=1)
```

---

## Error Handling

- **401 Unauthorized:** Token expired, re-authenticate
- **400 Bad Request:** Invalid parameters (check date format, purpose value)
- **AptnerAuthError:** Authentication failed (wrong credentials)
- **AptnerError:** General API error
