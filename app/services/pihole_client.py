
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
            # User requested: /api/auth?sid=<sid>
            # We send DELETE to this URL.
            print(f"DEBUG: Logging out from PiHole with SID: {self.sid[:5]}...")
            response = self.session.delete(url, params={"sid": self.sid})
            print(f"DEBUG: Logout Response: {response.status_code}")
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

    def toggle_group(self, group_name="Social", enable=True):
        """Enables or disables a group."""
        if not self._ensure_auth():
            return False

        url = f"{self.base_url}/api/groups/{group_name}"
        # Based on user description:
        # Enable: body {"enabled": true}
        # Disable: body {"name": "Social", "comment": "Social Media", "enabled": false}
        
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
            response = self.session.put(url, json=payload)
            print(f"DEBUG: Response Status: {response.status_code}")
            print(f"DEBUG: Response Body: {response.text}")
            
            if response.status_code in [200, 204]:
                return True
            else:
                print(f"Failed to toggle group: {response.status_code} {response.text}")
                return False
        except Exception as e:
            print(f"Error toggling group: {e}")
            return False

    def get_group_id(self, group_name):
        """Fetches the numeric ID of a group by name."""
        try:
            # Try getting all groups or specific group to find ID
            # Assuming GET /api/groups returns list
            url = f"{self.base_url}/api/groups" 
            response = self.session.get(url)
            if response.status_code == 200:
                groups = response.json()
                if isinstance(groups, dict) and 'groups' in groups:
                     groups = groups['groups'] # Handle standard PiHole v5/v6 structure?
                
                # If groups is a list, search it
                if isinstance(groups, list):
                    for g in groups:
                         if g.get('name') == group_name:
                             return g.get('id')
                
                # If GET /api/groups/Social works and returns full obj
                url_specific = f"{self.base_url}/api/groups/{group_name}"
                resp_spec = self.session.get(url_specific)
                if resp_spec.status_code == 200:
                    data = resp_spec.json()
                    # Handle if it returns a list or dict
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
        if not self._ensure_auth():
            return False
        
        group_id = self.get_group_id(group_name)
        if group_id is None:
            # Fallback: User's example had 2, but relying on fetch is safer.
            # If fetch fails, we can't properly add to the correct group.
            print("Failed to resolve Group ID. Cannot add client.")
            return False
            
        url = f"{self.base_url}/api/clients/"
        payload = {
            "client": client_ip,
            "comment": "Social Media User",
            "groups": [group_id]
        }
        
        try:
            print(f"DEBUG: Adding client {client_ip} to group {group_id}")
            response = self.session.post(url, json=payload)
            print(f"DEBUG: Add Client Response: {response.status_code} {response.text}")
            
            if response.status_code in [200, 201]:
                return True
            else:
                return False
        except Exception as e:
            print(f"Error adding client: {e}")
            return False

    def remove_client(self, client_ip):
        """Removes the client."""
        if not self._ensure_auth():
            return False
            
        # According to user: DELETE "http://pihole/api/clients/<client>"
        # Assuming <client> is the IP.
        
        # User also mentioned "get all clients... and delete all clients".
        # But logical flow is to delete just the target one.
        # I will just call DELETE directly on the IP.
        
        url = f"{self.base_url}/api/clients/{client_ip}"
        
        try:
            print(f"DEBUG: Removing client {client_ip}")
            response = self.session.delete(url)
            print(f"DEBUG: Delete Client Response: {response.status_code} {response.text}")
            
            if response.status_code in [200, 204]:
                return True
            elif response.status_code == 404:
                # Client already gone, consider success
                return True
            else:
                return False
        except Exception as e:
            print(f"Error removing client: {e}")
            return False
        
    def get_status(self, group_name="Social"):
        """Gets the status (Blocked/Unblocked)."""
        if not self._ensure_auth():
            return "Unknown"
            
        # Check group status
        url = f"{self.base_url}/api/groups/{group_name}"
        try:
            response = self.session.get(url)
            print(f"DEBUG: Status Check {url} -> {response.status_code}")
            if response.status_code == 200:
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
                # print(f"DEBUG: Derived Enabled State: {is_enabled}")
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

