# Aptner Raw HTTP API Reference

**Base URL:** `https://v2.aptner.com`

## Authentication

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

## List Reservations

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

## Create Reservation

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

## Delete Reservation

**Endpoint:** `DELETE /pc/reserve/{visitReserveIdx}`

**Headers:**
```
Authorization: Bearer {token}
```

**Response:** Empty on success (HTTP 200)
