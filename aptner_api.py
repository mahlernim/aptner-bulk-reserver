"""
Aptner API Client for visitor vehicle registration.
Based on https://github.com/af950833/aptner
"""

import os
import requests
from datetime import datetime, date, timedelta
from typing import Optional
from dotenv import load_dotenv

BASE_URL = "https://v2.aptner.com"

# Purpose options from Aptner
PURPOSE_OPTIONS = [
    "지인/가족방문",
    "과외/수업",
    "돌봄도우미(청소)",
    "기타"
]

# Maximum days per single reservation
MAX_DAYS_PER_RESERVATION = 30


class AptnerError(Exception):
    """Base exception for Aptner."""


class AptnerAuthError(AptnerError):
    """Raised when authentication fails."""


class AptnerClient:
    def __init__(self, user_id: str, password: str):
        self._id = user_id
        self._password = password
        self._token: Optional[str] = None
        self._session = requests.Session()
    
    def authenticate(self) -> bool:
        """Obtain a new access token."""
        payload = {"id": self._id, "password": self._password}
        headers = {"Content-Type": "application/json"}
        
        resp = self._session.post(
            f"{BASE_URL}/auth/token",
            json=payload,
            headers=headers
        )
        
        if resp.status_code >= 400:
            raise AptnerAuthError(f"Authentication failed: {resp.status_code} - {resp.text}")
        
        data = resp.json()
        token = data.get("accessToken")
        
        if not token:
            raise AptnerAuthError("Failed to obtain accessToken")
        
        self._token = token
        return True
    
    def _request(self, method: str, path: str, json_data: dict = None) -> dict:
        """Make an authenticated request."""
        if not self._token:
            self.authenticate()
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._token}"
        }
        
        url = f"{BASE_URL}{path}"
        
        resp = self._session.request(
            method,
            url,
            headers=headers,
            json=json_data
        )
        
        # Re-authenticate on 401
        if resp.status_code == 401:
            self.authenticate()
            headers["Authorization"] = f"Bearer {self._token}"
            resp = self._session.request(
                method,
                url,
                headers=headers,
                json=json_data
            )
        
        if resp.status_code >= 400:
            raise AptnerError(f"Request failed: {resp.status_code} - {resp.text}")
        
        try:
            return resp.json()
        except Exception:
            return {}
    
    def get_reservations(self) -> list[dict]:
        """Fetch all current and future reservations."""
        reservations = []
        current_page = 0
        total_pages = 1
        today = date.today()
        
        while current_page < total_pages:
            current_page += 1
            data = self._request("GET", f"/pc/reserves?pg={current_page}")
            
            if current_page == 1:
                total_pages = int(data.get("totalPages", 1) or 1)
            
            for item in data.get("reserveList", []):
                visit_date_str = item.get("visitDate")
                try:
                    visit_date = datetime.strptime(visit_date_str, "%Y.%m.%d").date()
                except Exception:
                    continue
                
                # Include today and future reservations
                if visit_date >= today:
                    reservations.append({
                        "idx": item.get("visitReserveIdx"),
                        "carNo": item.get("carNo"),
                        "visitDate": visit_date,
                        "visitDateStr": visit_date_str,
                        "purpose": item.get("purpose"),
                        "phone": item.get("phone"),
                        "days": item.get("days", 1)
                    })
            
            # Safety limit
            if current_page >= 50:
                break
        
        # Sort by date
        reservations.sort(key=lambda x: (x["visitDate"], x["carNo"]))
        return reservations
    
    def get_reserved_dates(self, car_no: str = None) -> set[tuple[str, date]]:
        """Get set of (carNo, date) tuples that are already reserved."""
        reservations = self.get_reservations()
        reserved = set()
        
        for r in reservations:
            if car_no and r["carNo"] != car_no:
                continue
            
            # Account for multi-day reservations
            base_date = r["visitDate"]
            days = r.get("days", 1) or 1
            
            for d in range(days):
                reserved.add((r["carNo"], base_date + timedelta(days=d)))
        
        return reserved
    
    def reserve_car(
        self,
        car_no: str,
        visit_date: date,
        phone: str,
        purpose: str = "지인/가족방문",
        days: int = 1
    ) -> dict:
        """Create a visitor vehicle reservation."""
        # Validate days
        if days < 1:
            days = 1
        elif days > MAX_DAYS_PER_RESERVATION:
            days = MAX_DAYS_PER_RESERVATION
        
        # Format date as yyyy.MM.dd
        date_str = visit_date.strftime("%Y.%m.%d")
        
        payload = {
            "visitDate": date_str,
            "purpose": purpose,
            "carNo": car_no,
            "days": days,
            "phone": phone
        }
        
        return self._request("POST", "/pc/reserve/", json_data=payload)
    
    def delete_reservation(self, idx: int) -> dict:
        """Delete a reservation by its visitReserveIdx."""
        return self._request("DELETE", f"/pc/reserve/{idx}")


def create_client_from_env(env_path: str = None) -> AptnerClient:
    """Create an AptnerClient from .env file."""
    if env_path:
        load_dotenv(env_path)
    else:
        load_dotenv()
    
    user_id = os.getenv("APTNER_ID")
    password = os.getenv("APTNER_PW")
    
    if not user_id or not password:
        raise AptnerError("APTNER_ID and APTNER_PW must be set in .env")
    
    return AptnerClient(user_id, password)


if __name__ == "__main__":
    # Quick test
    client = create_client_from_env()
    print("Authenticating...")
    client.authenticate()
    print("Authentication successful!")
    
    print("\nFetching reservations...")
    reservations = client.get_reservations()
    print(f"Found {len(reservations)} reservations")
    for r in reservations[:5]:
        print(f"  - {r['visitDateStr']}: {r['carNo']}")
