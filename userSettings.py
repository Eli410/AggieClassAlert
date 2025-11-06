import os
import json
from collections import defaultdict

class UserPreferences:
    def __init__(self, file_path="user_preferences.json"):
        self.file_path = file_path
        self._preferences = defaultdict(lambda: {"DM": False,
                                                 "reg_time": []})
        
        # Load existing preferences from file if it exists
        self._load_preferences()
    
    def _load_preferences(self):
        try:
            if os.path.exists(self.file_path):
                with open(self.file_path, 'r') as f:
                    data = json.load(f)
                    # Convert string keys (user IDs) back to integers
                    for user_id, prefs in data.items():
                        self._preferences[int(user_id)] = prefs
        except Exception as e:
            print(f"Error loading preferences: {e}")
    
    def _save_preferences(self):
        try:
            # Convert to regular dict with string keys for JSON
            data = {str(user_id): prefs for user_id, prefs in dict(self._preferences).items()}
            with open(self.file_path, 'w') as f:
                json.dump(data, f, indent=4)
        except Exception as e:
            print(f"Error saving preferences: {e}")
    
    def get_user_settings(self, user_id):
        return self._preferences[user_id]
    
    def update_user_setting(self, user_id, setting_name, value):
        self._preferences[user_id][setting_name] = value
        self._save_preferences()
        return self._preferences[user_id]
    
    def get_all_users(self):
        return dict(self._preferences)

USER_PREFERENCES = UserPreferences()