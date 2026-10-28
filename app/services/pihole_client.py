import os
import requests

class PiHoleClient:
    def __init__(self):
        self.base_url = os.getenv('PIHOLE_URL')
        self.password = os.getenv('PIHOLE_PASSWORD')
        self.sid = None
        self.session = requests.Session()

    def login(self):
        """Authenticates with PiHole and gets the SID."""
        url = f"{self.base_url}/api/auth/"
        payload = {"password": self.password}
        try:
            response = self.session.post(url, json=payload)
            response.raise_for_status()
            data = response.json()
            if data.get("session", {}).get("valid"):
                self.sid = data["session"]["sid"]
                # Set X-FTL-SID header for future requests
                self.session.headers.update({"X-FTL-SID": self.sid})
                print(f"DEBUG: Login success. SID: {self.sid[:5]}...")
                return True
            else:
                print(f"Login failed: {data}")
                return False
        except Exception as e:
            print(f"Error logging in: {e}")
            return False

    def logout(self):
        """Terminates the Pi-hole session."""
        if not self.sid:
            return
            
        url = f"{self.base_url}/api/auth"
        try:
            print(f"DEBUG: Logging out from PiHole with SID: {self.sid[:5]}...")
            self.session.delete(url, params={"sid": self.sid})
        except Exception as e:
            print(f"Error logging out from PiHole: {e}")
        finally:
            self.sid = None
            if "X-FTL-SID" in self.session.headers:
                del self.session.headers["X-FTL-SID"]

    def _ensure_auth(self):
        if not self.sid:
            return self.login()
        return True

    def request(self, method, endpoint, **kwargs):
        """Sends an authenticated request, automatically re-authenticating if session expired (401)."""
        if not self._ensure_auth():
            return None

        url = f"{self.base_url}{endpoint}" if endpoint.startswith("/") else f"{self.base_url}/{endpoint}"
        try:
            response = self.session.request(method, url, **kwargs)
            if response.status_code == 401:
                print("DEBUG: Received 401 Unauthorized, session expired. Re-authenticating...")
                self.sid = None
                if "X-FTL-SID" in self.session.headers:
                    del self.session.headers["X-FTL-SID"]
                if self.login():
                    response = self.session.request(method, url, **kwargs)
                else:
                    print("DEBUG: Re-authentication failed.")
                    return None
            return response
        except Exception as e:
            print(f"Error making request to {url}: {e}")
            return None

    def toggle_group(self, group_name="Social", enable=True):
        """Enables or disables a group."""
        if enable:
            payload = {"enabled": True}
        else:
            payload = {
                "name": group_name,
                "comment": "Social Media", 
                "enabled": False
            }
            
        try:
            print(f"DEBUG: Toggling group {group_name} to {enable}. Payload: {payload}")
            response = self.request("PUT", f"/api/groups/{group_name}", json=payload)
            if response is not None and response.status_code in [200, 204]:
                return True
            else:
                status = response.status_code if response is not None else "No Response"
                text = response.text if response is not None else ""
                print(f"Failed to toggle group: {status} {text}")
                return False
        except Exception as e:
            print(f"Error toggling group: {e}")
            return False

    def get_group_id(self, group_name):
        """Fetches the numeric ID of a group by name."""
        try:
            response = self.request("GET", "/api/groups")
            if response is not None and response.status_code == 200:
                groups = response.json()
                if isinstance(groups, dict) and 'groups' in groups:
                     groups = groups['groups']
                
                if isinstance(groups, list):
                    for g in groups:
                         if g.get('name') == group_name:
                             return g.get('id')
                
                resp_spec = self.request("GET", f"/api/groups/{group_name}")
                if resp_spec is not None and resp_spec.status_code == 200:
                    data = resp_spec.json()
                    if isinstance(data, list) and len(data) > 0:
                        return data[0].get('id')
                    elif isinstance(data, dict):
                        return data.get('id')
                        
            print(f"DTO: Could not find ID for group {group_name}")
            return None
        except Exception as e:
            print(f"Error getting group ID: {e}")
            return None

    def add_client_to_group(self, client_ip, group_name="Social"):
        """Adds a client and assigns it to the group."""
        group_id = self.get_group_id(group_name)
        if group_id is None:
            print("Failed to resolve Group ID. Cannot add client.")
            return False
            
        payload = {
            "client": client_ip,
            "comment": "Social Media User",
            "groups": [group_id]
        }
        
        try:
            print(f"DEBUG: Adding client {client_ip} to group {group_id}")
            response = self.request("POST", "/api/clients/", json=payload)
            if response is not None and response.status_code in [200, 201]:
                return True
            else:
                return False
        except Exception as e:
            print(f"Error adding client: {e}")
            return False

    def remove_client(self, client_ip):
        """Removes the client."""
        try:
            print(f"DEBUG: Removing client {client_ip}")
            response = self.request("DELETE", f"/api/clients/{client_ip}")
            if response is not None and response.status_code in [200, 204, 404]:
                return True
            else:
                return False
        except Exception as e:
            print(f"Error removing client: {e}")
            return False

    def get_status(self, group_name="Social"):
        """Gets the status (Blocked/Unblocked)."""
        try:
            response = self.request("GET", f"/api/groups/{group_name}")
            if response is not None and response.status_code == 200:
                data = response.json()
                
                # Handle nested 'groups' key (PiHole v6 structure)
                if isinstance(data, dict) and 'groups' in data:
                    data = data['groups']

                # Handle potential list response
                if isinstance(data, list):
                    if len(data) > 0:
                        data = data[0]
                    else:
                        print("DEBUG: Empty groups list found")
                        return "Unblocked" 
                
                is_enabled = data.get("enabled")
                return "Blocked" if is_enabled else "Unblocked"
        except Exception as e:
            print(f"Error checking status: {e}")
            
        return "Unknown"

    def set_social_block(self, client_ip, enabled=True):
        """High-level method to block/unblock a client from social media."""
        if not self._ensure_auth():
            return "Error"

        group_name = "Social"
        
        if enabled:
            # Step 1: Enable the "Social" group
            if self.toggle_group(group_name, enable=True):
                # Step 2: Add the client to this group
                if self.add_client_to_group(client_ip, group_name):
                    return "Blocked"
        else:
            # Step 1: Disable the "Social" group
            if self.toggle_group(group_name, enable=False):
                # Step 2: Remove the client
                if self.remove_client(client_ip):
                    return "Unblocked"
        
        return "Error"
