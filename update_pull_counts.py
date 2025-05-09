#!/usr/bin/env python3
"""
Script to update Docker Hub pull counts for MCP servers listed in the README.md file.
This script:
1. Fetches the current list of servers from README.md
2. Queries Docker Hub API to get the current pull count for each server
3. Updates the README.md with the latest pull counts
4. Optionally commits and pushes the changes to GitHub

Usage:
  python update_pull_counts.py [--commit]

Options:
  --commit    Commit and push changes to GitHub
"""

import os
import re
import time
import base64
import argparse
import requests
from datetime import datetime
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Constants
README_PATH = 'README.md'
DOCKER_HUB_API_URL = 'https://hub.docker.com/v2/repositories/mcp/'
GITHUB_REPO_URL = 'https://api.github.com/repos/ajeetraina/awesome-docker-mcp-servers'
TABLE_PATTERN = r'\|\s*(\d+)\s*\|\s*([^\|]+)\s*\|\s*([^\|]+)\s*\|\s*([^\|]+)\s*\|\s*([^\|]+)\s*\|'
GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN')

def read_readme():
    """Read the README.md file"""
    try:
        with open(README_PATH, 'r', encoding='utf-8') as file:
            return file.read()
    except FileNotFoundError:
        logging.error(f"README file not found at {README_PATH}")
        raise

def extract_server_list(readme_content):
    """Extract the server list from the README.md content"""
    servers = []
    
    # First check how many servers are listed in the README
    match = re.search(r'There are currently (\d+) MCP servers available:', readme_content)
    expected_count = int(match.group(1)) if match else 0
    
    if expected_count > 0:
        logging.info(f"README mentions {expected_count} MCP servers")
    
    # Find all table rows using regex pattern
    matches = re.finditer(TABLE_PATTERN, readme_content)
    
    for match in matches:
        index = match.group(1)
        server_name = match.group(2).strip()
        description = match.group(3).strip()
        pull_count = match.group(4).strip()
        link = match.group(5).strip()
        
        servers.append({
            'index': index,
            'server_name': server_name,
            'description': description,
            'pull_count': pull_count,
            'link': link,
            'line': match.group(0)
        })
    
    # Verify if we found all servers
    found_count = len(servers)
    logging.info(f"Found {found_count} servers in README.md table")
    
    if expected_count > 0 and found_count < expected_count:
        logging.warning(f"Expected {expected_count} servers but only found {found_count}")
        logging.warning("Some servers might be missing from the table or in a different format")
    
    return servers

def get_docker_hub_pull_count(server_name):
    """Query Docker Hub API to get the pull count for a server"""
    # Remove any leading/trailing whitespace
    server_name = server_name.strip()
    
    try:
        # Some server names might contain characters that need to be handled
        url = f"{DOCKER_HUB_API_URL}{server_name}"
        logging.info(f"Querying Docker Hub for {server_name} at URL: {url}")
        
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            pull_count = data.get('pull_count', 0)
            logging.info(f"Pull count for {server_name}: {pull_count}")
            return f"{pull_count:,}"  # Format with comma separators
        else:
            logging.warning(f"Failed to get pull count for {server_name}: HTTP {response.status_code}")
            return "TBD"
    except Exception as e:
        logging.error(f"Error getting pull count for {server_name}: {e}")
        return "TBD"
    
    # Sleep to avoid rate limiting
    time.sleep(1)

def update_readme_with_pull_counts(readme_content, servers):
    """Update the README.md with the latest pull counts"""
    updated_content = readme_content
    
    for server in servers:
        if server['pull_count'] != server.get('new_pull_count', server['pull_count']):
            # Create the new line with updated pull count
            old_line = server['line']
            new_line = f"| {server['index']} | {server['server_name']} | {server['description']} | {server['new_pull_count']} | {server['link']} |"
            
            # Replace the old line with the new line
            updated_content = updated_content.replace(old_line, new_line)
            logging.info(f"Updated pull count for {server['server_name']}: {server['pull_count']} ? {server['new_pull_count']}")
    
    return updated_content

def write_readme(content):
    """Write the updated content back to README.md"""
    try:
        with open(README_PATH, 'w', encoding='utf-8') as file:
            file.write(content)
        logging.info(f"Successfully updated {README_PATH}")
    except Exception as e:
        logging.error(f"Failed to write to {README_PATH}: {e}")
        raise

def commit_and_push_changes():
    """Commit and push the changes to GitHub"""
    if not GITHUB_TOKEN:
        logging.error("GITHUB_TOKEN environment variable not set. Cannot commit changes.")
        return False
    
    date_str = datetime.now().strftime('%Y-%m-%d')
    commit_message = f"Update Docker Hub pull counts - {date_str}"
    
    try:
        # Using GitHub API to commit changes
        headers = {
            'Authorization': f'token {GITHUB_TOKEN}',
            'Accept': 'application/vnd.github.v3+json'
        }
        
        # 1. Get the current README content from GitHub
        readme_response = requests.get(f"{GITHUB_REPO_URL}/contents/{README_PATH}", headers=headers)
        readme_data = readme_response.json()
        sha = readme_data['sha']
        
        # 2. Read the locally updated README
        with open(README_PATH, 'r', encoding='utf-8') as file:
            updated_content = file.read()
        
        # 3. Update the file on GitHub
        update_data = {
            'message': commit_message,
            'content': base64.b64encode(updated_content.encode()).decode(),
            'sha': sha,
            'branch': 'main'
        }
        
        update_response = requests.put(
            f"{GITHUB_REPO_URL}/contents/{README_PATH}",
            json=update_data,
            headers=headers
        )
        
        if update_response.status_code in (200, 201):
            logging.info("Successfully committed and pushed changes to GitHub")
            return True
        else:
            logging.error(f"Failed to push changes to GitHub: {update_response.status_code} - {update_response.text}")
            return False
            
    except Exception as e:
        logging.error(f"Error committing changes: {e}")
        return False

def check_server_availability(servers):
    """Check if the servers in the list are available"""
    logging.info("Checking server availability...")
    
    for server in servers:
        server_name = server['server_name'].strip()
        try:
            url = f"https://hub.docker.com/r/mcp/{server_name}"
            response = requests.head(url)
            if response.status_code == 200:
                server['available'] = True
                logging.info(f"Server {server_name} is available")
            else:
                server['available'] = False
                logging.warning(f"Server {server_name} returned status code {response.status_code}")
        except Exception as e:
            server['available'] = False
            logging.error(f"Error checking server {server_name}: {e}")
        
        # Sleep to avoid rate limiting
        time.sleep(1)
    
    return servers

def find_all_mcp_servers(readme_content):
    """Find all MCP servers mentioned in the README, even those not in the main table"""
    # First, get the servers from the main table
    table_servers = extract_server_list(readme_content)
    
    # Then look for other MCP servers in the document
    # This would need to be customized based on how the other servers are listed
    
    # Get additional servers from the README using a different pattern if needed
    # For example, scanning for links to MCP server pages:
    additional_servers = []
    
    # Combine and deduplicate the lists
    all_servers = table_servers + additional_servers
    
    # Remove duplicates if any
    server_names = set()
    unique_servers = []
    
    for server in all_servers:
        if server['server_name'] not in server_names:
            server_names.add(server['server_name'])
            unique_servers.append(server)
    
    logging.info(f"Found a total of {len(unique_servers)} unique MCP servers")
    return unique_servers

def main():
    """Main function to update pull counts"""
    parser = argparse.ArgumentParser(description='Update Docker Hub pull counts for MCP servers')
    parser.add_argument('--commit', action='store_true', help='Commit and push changes to GitHub')
    parser.add_argument('--full-scan', action='store_true', help='Scan the entire README for servers, not just the table')
    
    args = parser.parse_args()
    
    logging.info("Starting Docker Hub pull count update process")
    
    try:
        # Read the README.md content
        readme_content = read_readme()
        
        # Extract server list
        if args.full_scan:
            servers = find_all_mcp_servers(readme_content)
        else:
            servers = extract_server_list(readme_content)
        
        logging.info(f"Found {len(servers)} servers in README.md")
        
        # Check server availability
        servers = check_server_availability(servers)
        
        # Update pull counts
        for server in servers:
            if server.get('available', False):
                server['new_pull_count'] = get_docker_hub_pull_count(server['server_name'])
            else:
                server['new_pull_count'] = "TBD (unavailable)"
        
        # Update README.md with new pull counts
        updated_content = update_readme_with_pull_counts(readme_content, servers)
        
        # Write the updated content back to README.md
        write_readme(updated_content)
        
        # Commit and push changes if --commit flag is provided
        if args.commit:
            success = commit_and_push_changes()
            if success:
                logging.info("Changes committed and pushed to GitHub")
            else:
                logging.warning("Failed to commit changes to GitHub")
                
        logging.info("Docker Hub pull count update completed")
        
    except Exception as e:
        logging.error(f"Error updating pull counts: {e}")
        raise

if __name__ == "__main__":
    main()