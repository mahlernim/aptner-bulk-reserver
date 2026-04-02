---
name: aptner-visitor-reservation
description: "Register visitor vehicle parking reservations on Aptner (아파트너) apartment management system. Use this skill when: user wants to register visitor cars, create recurring parking reservations, check existing reservations, or delete parking reservations for their apartment. Requires: APTNER_ID and APTNER_PW credentials (in .env file or provided by user)."
---

# Aptner Visitor Vehicle Reservation Skill

Register and manage visitor vehicle parking reservations on Aptner-enabled Korean apartments.

## Workflow

1. **Authenticate** — obtain access token using `APTNER_ID` and `APTNER_PW`
2. **Check existing** — list current reservations to avoid duplicates
3. **Create or delete** — register new reservations or remove existing ones
4. **Verify** — confirm changes by re-listing reservations

## Prerequisites

- Python 3.8+
- Dependencies: `pip install python-dotenv pyyaml requests`
- Credentials: `.env` file with `APTNER_ID` and `APTNER_PW`, or get from user

## Python Client Usage

The repository includes a Python client (`aptner_api.py`) that wraps the Aptner v2 API. For the raw HTTP API details, see [references/raw-api.md](references/raw-api.md).

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

**Valid purpose values:** `지인/가족방문`, `과외/수업`, `돌봄도우미(청소)`, `기타`

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

## Example: Recurring Weekly Reservation

```python
from datetime import date, timedelta
from aptner_api import create_client_from_env, AptnerAuthError, AptnerError

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
            try:
                client.reserve_car(
                    car_no=car_no,
                    visit_date=current,
                    phone=phone,
                    purpose="과외/수업"
                )
                print(f"Reserved: {current}")
            except AptnerAuthError:
                # Token expired mid-batch — re-authenticate and retry
                client.authenticate()
                client.reserve_car(
                    car_no=car_no,
                    visit_date=current,
                    phone=phone,
                    purpose="과외/수업"
                )
                print(f"Reserved (after re-auth): {current}")
            except AptnerError as e:
                print(f"Failed to reserve {current}: {e}")
    current += timedelta(days=1)
```

## Error Handling

| Error | Cause | Recovery |
|-------|-------|----------|
| `AptnerAuthError` | Wrong credentials or expired token | Verify credentials; call `client.authenticate()` again |
| `AptnerError` | General API error | Check parameters (date format `YYYY.MM.DD`, valid purpose) |
| HTTP 401 | Token expired mid-session | Re-authenticate with `client.authenticate()` |
| HTTP 400 | Invalid request parameters | Verify date format, purpose value, phone format (no dashes) |
