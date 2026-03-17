# -*- coding: utf-8 -*-
import os
import json

DEFAULT_CONFIG = {
    "watch_mode_enabled": False,
    "watch_directory": "",
    "polling_interval": 60,  # seconds
    "processed_files_log": "processed_files.json",
    "cumulative_csv_path": "",
    "include_drift_files": False,
    "github_enabled": False,  # GitHub disabled by default
    "github_config": {
        "token": "",
        "repo_owner": "",
        "repo_name": "",
        "branch": "main",
        "repo_path": "",
        "remote_url": ""
    }
}

class WatchConfig(object):
    def __init__(self, config_path="watch_config.json"):
        self.config_path = config_path
        self.config = self._load_config()
    
    def _load_config(self):
        """Load configuration from JSON file or create default"""
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r') as f:
                    loaded_config = json.load(f)
                    # Merge with defaults to ensure all required fields exist
                    return self._merge_with_defaults(loaded_config)
            return DEFAULT_CONFIG.copy()
        except Exception as e:
            print("Error loading config: {0}".format(str(e)))
            return DEFAULT_CONFIG.copy()
    
    def _merge_with_defaults(self, loaded_config):
        """Merge loaded config with defaults to ensure all fields exist"""
        config = DEFAULT_CONFIG.copy()
        config.update(loaded_config)
        
        # Ensure github_config structure exists
        if 'github_config' in loaded_config:
            config['github_config'] = DEFAULT_CONFIG['github_config'].copy()
            config['github_config'].update(loaded_config['github_config'])
        
        return config
    
    def save_config(self):
        """Save current configuration to JSON file"""
        try:
            with open(self.config_path, 'w') as f:
                json.dump(self.config, f, indent=4)
            return True
        except Exception as e:
            print("Error saving config: {0}".format(str(e)))
            return False
    
    def update_config(self, **kwargs):
        """Update configuration with new values"""
        if 'github_config' in kwargs:
            self.config['github_config'].update(kwargs.pop('github_config'))
        self.config.update(kwargs)
        return self.save_config()
    
    def enable_github(self, token, repo_owner, repo_name, branch="main"):
        """Helper method to enable GitHub integration"""
        github_config = {
            "token": token,
            "repo_owner": repo_owner,
            "repo_name": repo_name,
            "branch": branch,
            "repo_path": os.path.join(os.getcwd(), "github_repo"),
            "remote_url": "https://github.com/{0}/{1}.git".format(repo_owner, repo_name)
        }
        return self.update_config(
            github_enabled=True,
            github_config=github_config
        )
    
    def disable_github(self):
        """Helper method to disable GitHub integration"""
        return self.update_config(github_enabled=False) 