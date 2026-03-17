# -*- coding: utf-8 -*-
from __future__ import print_function
import os
import subprocess
import time

class GitHubManager(object):
    def __init__(self, repo_path, branch="main"):
        self.repo_path = repo_path
        self.branch = branch
        self.git_env = os.environ.copy()
    
    def set_pat(self, pat):
        """Set Personal Access Token in environment"""
        self.git_env["GIT_PAT"] = pat
    
    def _run_git_command(self, command):
        """Run git command and handle errors"""
        try:
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=self.git_env,
                cwd=self.repo_path,
                shell=True
            )
            output, error = process.communicate()
            
            if process.returncode != 0:
                print("Git command failed: {0}".format(error))
                return False
            return True
        except Exception as e:
            print("Error running git command: {0}".format(str(e)))
            return False
    
    def setup_repo(self, remote_url):
        """Initialize repo if needed and set remote"""
        if not os.path.exists(os.path.join(self.repo_path, '.git')):
            commands = [
                'git init',
                'git branch -M {0}'.format(self.branch),
                'git remote add origin {0}'.format(remote_url)
            ]
            
            for cmd in commands:
                if not self._run_git_command(cmd):
                    return False
        return True
    
    def commit_and_push_csv(self, csv_path, commit_message=None):
        """Commit and push CSV file to GitHub"""
        if not os.path.exists(csv_path):
            print("CSV file not found: {0}".format(csv_path))
            return False
        
        # Default commit message if none provided
        if commit_message is None:
            commit_message = "Update metadata CSV - {0}".format(
                time.strftime("%Y-%m-%d %H:%M:%S")
            )
        
        # Copy CSV to repo directory
        csv_name = os.path.basename(csv_path)
        repo_csv_path = os.path.join(self.repo_path, csv_name)
        
        try:
            with open(csv_path, 'rb') as src, open(repo_csv_path, 'wb') as dst:
                dst.write(src.read())
        except Exception as e:
            print("Error copying CSV file: {0}".format(str(e)))
            return False
        
        # Git commands
        commands = [
            'git pull origin {0}'.format(self.branch),
            'git add "{0}"'.format(csv_name),
            'git commit -m "{0}"'.format(commit_message),
            'git push origin {0}'.format(self.branch)
        ]
        
        for cmd in commands:
            if not self._run_git_command(cmd):
                return False
        
        return True 