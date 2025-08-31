import json
import os
from datetime import datetime
from typing import List, Dict, Optional

class Database:
    def __init__(self):
        self.warnings_file = "data/warnings.json"
        self.logs_file = "data/logs.json"
        self.quarantine_file = "data/quarantine.json"
        self.backups_file = "data/backups.json"
        self.config_file = "data/config.json"
        self.ensure_data_files()
    
    def ensure_data_files(self):
        """Ensure data directory and files exist"""
        os.makedirs("data", exist_ok=True)
        
        if not os.path.exists(self.warnings_file):
            with open(self.warnings_file, 'w') as f:
                json.dump({"warnings": [], "next_id": 1}, f)
        
        if not os.path.exists(self.logs_file):
            with open(self.logs_file, 'w') as f:
                json.dump({"logs": []}, f)
        
        if not os.path.exists(self.quarantine_file):
            with open(self.quarantine_file, 'w') as f:
                json.dump({"quarantined": []}, f)
        
        if not os.path.exists(self.backups_file):
            with open(self.backups_file, 'w') as f:
                json.dump({"backups": [], "next_id": 1}, f)
        
        if not os.path.exists(self.config_file):
            with open(self.config_file, 'w') as f:
                json.dump({"settings": {}}, f)
    
    def load_warnings(self) -> Dict:
        """Load warnings from file"""
        try:
            with open(self.warnings_file, 'r') as f:
                return json.load(f)
        except:
            return {"warnings": [], "next_id": 1}
    
    def save_warnings(self, data: Dict):
        """Save warnings to file"""
        with open(self.warnings_file, 'w') as f:
            json.dump(data, f, indent=2)
    
    def load_logs(self) -> Dict:
        """Load logs from file"""
        try:
            with open(self.logs_file, 'r') as f:
                return json.load(f)
        except:
            return {"logs": []}
    
    def save_logs(self, data: Dict):
        """Save logs to file"""
        with open(self.logs_file, 'w') as f:
            json.dump(data, f, indent=2)
    
    def add_warning(self, user_id: int, moderator_id: int, reason: str) -> int:
        """Add a warning for a user"""
        data = self.load_warnings()
        warning_id = data["next_id"]
        
        warning = {
            "id": warning_id,
            "user_id": user_id,
            "moderator_id": moderator_id,
            "reason": reason,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        data["warnings"].append(warning)
        data["next_id"] += 1
        
        self.save_warnings(data)
        return warning_id
    
    def get_warnings(self, user_id: int) -> List[Dict]:
        """Get all warnings for a user"""
        data = self.load_warnings()
        return [w for w in data["warnings"] if w["user_id"] == user_id]
    
    def get_warning_count(self, user_id: int) -> int:
        """Get the number of warnings for a user"""
        return len(self.get_warnings(user_id))
    
    def remove_warning(self, warning_id: int) -> bool:
        """Remove a warning by ID"""
        data = self.load_warnings()
        original_count = len(data["warnings"])
        data["warnings"] = [w for w in data["warnings"] if w["id"] != warning_id]
        
        if len(data["warnings"]) < original_count:
            self.save_warnings(data)
            return True
        return False
    
    def log_action(self, action: str, moderator_id: Optional[int], target_id: Optional[int], reason: str):
        """Log a moderation action"""
        data = self.load_logs()
        
        log_entry = {
            "action": action,
            "moderator_id": moderator_id,
            "target_id": target_id,
            "reason": reason,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        data["logs"].append(log_entry)
        
        # Keep only last 1000 logs to prevent file from growing too large
        if len(data["logs"]) > 1000:
            data["logs"] = data["logs"][-1000:]
        
        self.save_logs(data)
    
    def get_recent_logs(self, limit: int = 10, user_id: Optional[int] = None) -> List[Dict]:
        """Get recent moderation logs"""
        data = self.load_logs()
        logs = data["logs"]
        
        if user_id:
            logs = [log for log in logs if log.get("target_id") == user_id]
        
        # Return most recent logs first
        return logs[-limit:][::-1]
    
    def get_user_stats(self, user_id: int) -> Dict:
        """Get statistics for a user"""
        warnings = self.get_warnings(user_id)
        
        # Count different types of actions
        data = self.load_logs()
        user_logs = [log for log in data["logs"] if log.get("target_id") == user_id]
        
        action_counts = {}
        for log in user_logs:
            action = log["action"]
            action_counts[action] = action_counts.get(action, 0) + 1
        
        return {
            "warnings": len(warnings),
            "actions": action_counts,
            "last_warning": warnings[-1]["timestamp"] if warnings else None
        }
    
    def clear_user_warnings(self, user_id: int) -> int:
        """Clear all warnings for a user and return count of removed warnings"""
        data = self.load_warnings()
        original_count = len(data["warnings"])
        data["warnings"] = [w for w in data["warnings"] if w["user_id"] != user_id]
        removed_count = original_count - len(data["warnings"])
        
        if removed_count > 0:
            self.save_warnings(data)
        
        return removed_count
    
    # Quarantine methods
    def load_quarantine(self) -> Dict:
        """Load quarantine data from file"""
        try:
            with open(self.quarantine_file, 'r') as f:
                return json.load(f)
        except:
            return {"quarantined": []}
    
    def save_quarantine(self, data: Dict):
        """Save quarantine data to file"""
        with open(self.quarantine_file, 'w') as f:
            json.dump(data, f, indent=2)
    
    def add_quarantine(self, quarantine_data: Dict):
        """Add a quarantine record"""
        data = self.load_quarantine()
        data["quarantined"].append(quarantine_data)
        self.save_quarantine(data)
    
    def get_quarantine(self, user_id: int, guild_id: int) -> Optional[Dict]:
        """Get quarantine data for a user"""
        data = self.load_quarantine()
        for record in data["quarantined"]:
            if record["user_id"] == user_id and record["guild_id"] == guild_id:
                return record
        return None
    
    def remove_quarantine(self, user_id: int, guild_id: int) -> bool:
        """Remove a quarantine record"""
        data = self.load_quarantine()
        original_count = len(data["quarantined"])
        data["quarantined"] = [
            record for record in data["quarantined"]
            if not (record["user_id"] == user_id and record["guild_id"] == guild_id)
        ]
        
        if len(data["quarantined"]) < original_count:
            self.save_quarantine(data)
            return True
        return False
    
    def get_all_quarantined(self, guild_id: int) -> List[Dict]:
        """Get all quarantined users in a guild"""
        data = self.load_quarantine()
        return [record for record in data["quarantined"] if record["guild_id"] == guild_id]
    
    # Backup methods
    def load_backups(self) -> Dict:
        """Load backup data from file"""
        try:
            with open(self.backups_file, 'r') as f:
                return json.load(f)
        except:
            return {"backups": [], "next_id": 1}
    
    def save_backups(self, data: Dict):
        """Save backup data to file"""
        with open(self.backups_file, 'w') as f:
            json.dump(data, f, indent=2)
    
    def store_backup(self, backup_data: Dict) -> str:
        """Store a backup and return its ID"""
        data = self.load_backups()
        backup_id = f"backup_{data['next_id']}"
        
        backup_record = {
            "id": backup_id,
            "guild_id": backup_data["guild_id"],
            "guild_name": backup_data["guild_name"],
            "timestamp": backup_data["timestamp"],
            "channels": backup_data["channels"],
            "roles": backup_data["roles"],
            "categories": backup_data["categories"]
        }
        
        data["backups"].append(backup_record)
        data["next_id"] += 1
        
        self.save_backups(data)
        return backup_id
    
    def get_backup(self, backup_id: str) -> Optional[Dict]:
        """Get a specific backup by ID"""
        data = self.load_backups()
        for backup in data["backups"]:
            if backup["id"] == backup_id:
                return backup
        return None
    
    def get_backups(self, guild_id: int) -> List[Dict]:
        """Get all backups for a guild"""
        data = self.load_backups()
        return [backup for backup in data["backups"] if backup["guild_id"] == guild_id]
    
    # Config methods
    def load_config(self) -> Dict:
        """Load configuration from file"""
        try:
            with open(self.config_file, 'r') as f:
                return json.load(f)
        except:
            return {"settings": {}}
    
    def save_config(self, data: Dict):
        """Save configuration to file"""
        with open(self.config_file, 'w') as f:
            json.dump(data, f, indent=2)
    
    def get_setting(self, key: str, default=None):
        """Get a configuration setting"""
        data = self.load_config()
        return data["settings"].get(key, default)
    
    def set_setting(self, key: str, value):
        """Set a configuration setting"""
        data = self.load_config()
        data["settings"][key] = value
        self.save_config(data)
