---
name: aptner-visitor-reservation
description: |
  Register visitor vehicle parking reservations on Aptner (아파트너) apartment management system.
  Use this skill when: user wants to register visitor cars, create recurring parking reservations,
  check existing reservations, or delete parking reservations for their apartment.
  Requires: APTNER_ID and APTNER_PW environment variables set in .env file.
---

# Aptner Visitor Vehicle Reservation Skill

Register and manage visitor vehicle parking reservations on Aptner-enabled apartments.

## Prerequisites

- Python 3.8+
- Dependencies: `pip install python-dotenv pyyaml requests`
- `.env` file with credentials:
  ```
  APTNER_ID=your_id
  APTNER_PW=your_password
  ```

## API Reference

### Initialize Client

```python
from aptner_api import create_client_from_env, AptnerClient

# From .env file
client = create_client_from_env()
client.authenticate()

# Or manually
client = AptnerClient(user_id="...", password="...")
client.authenticate()
```

### Get Current Reservations

```python
reservations = client.get_reservations()
# Returns: list of dicts with keys: idx, carNo, visitDate, visitDateStr, purpose, phone, days
```

### Create Reservation

```python
from datetime import date

client.reserve_car(
    car_no="12가3456",
    visit_date=date(2026, 2, 10),
    phone="010-1234-5678",
    purpose="지인/가족방문",  # Options: 지인/가족방문, 과외/수업, 돌봄도우미(청소), 기타
    days=1  # Max 30 days per reservation
)
```

### Delete Reservation

```python
# Get the idx from get_reservations()
client.delete_reservation(idx=124209094)
```

### Check for Duplicates

```python
reserved = client.get_reserved_dates(car_no="12가3456")
# Returns: set of (carNo, date) tuples
```

## Example: Recurring Weekly Reservation

```python
from datetime import date, timedelta
from aptner_api import create_client_from_env

client = create_client_from_env()
client.authenticate()

# Reserve every Tuesday and Thursday for 4 weeks
car_no = "12가3456"
phone = "010-1234-5678"
target_weekdays = [1, 3]  # Tuesday=1, Thursday=3

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
