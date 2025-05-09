#!/usr/bin/env python3
"""
Script to check the availability and status of Docker MCP servers.
This script:
1. Reads the server list from README.md
2. Checks if each server is available on Docker Hub
3. Monitors server health, version, and updates
4. Generates a health report

Usage:
  python check_mcp_servers.py [--output FORMAT] [--notify]

Options:
  --output FORMAT    Output format (text, json, markdown) [default: markdown]
  --notify           Send notification on status changes
"""

import os
import re
import json
import time
import argparse
import requests
from datetime import datetime
import logging
from tabulate import tabulate

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    filename='server_check.log',
    filemode='a'
)
console = logging.StreamHandler()
console.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
console.setFormatter(formatter)
logging.getLogger('').addHandler(console)

# Constants
README_PATH = 'README.md'
DOCKER_HUB_API_URL = 'https://hub.docker.com/v2/repositories/mcp/'
SERVER_STATUS_FILE = 'server_status.json'
TABLE_PATTERN = r'\|\s*(\d+)\s*\|\s*([^\|]+)\s*\|\s*([^\|]+)\s*\|\s*([^\|]+)\s*\|\s*([^\|]+)\s*\|'
NOTIFICATION_EMAIL = os.environ.get('NOTIFICATION_EMAIL')
SLACK_WEBHOOK = os.environ.get('SLACK_WEBHOOK')

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
            'link': link
        })
    
    return servers

def check_server(server_name):
    """Check if a server is available on Docker Hub and get its details"""
    server_name = server_name.strip()
    result = {
        'name': server_name,
        'available': False,
        'last_updated': None,
        'status': 'unknown',
        'version': None,
        'pull_count': 0,
        'timestamp': datetime.now().isoformat()
    }
    
    try:
        # Check if server exists on Docker Hub
        url = f"{DOCKER_HUB_API_URL}{server_name}"
        logging.info(f"Checking server {server_name} at {url}")
        
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            result['available'] = True
            result['last_updated'] = data.get('last_updated')
            result['pull_count'] = data.get('pull_count', 0)
            result['status'] = 'online'
            
            # Get latest tag/version info
            tags_url = f"{DOCKER_HUB_API_URL}{server_name}/tags"
            tags_response = requests.get(tags_url, timeout=10)
            if tags_response.status_code == 200:
                tags_data = tags_response.json()
                if tags_data.get('results'):
                    result['version'] = tags_data['results'][0].get('name')
        else:
            result['status'] = 'offline'
            logging.warning(f"Server {server_name} returned status code {response.status_code}")
    except Exception as e:
        result['status'] = 'error'
        logging.error(f"Error checking server {server_name}: {e}")
    
    return result

def load_previous_status():
    """Load the previous server status from file"""
    try:
        if os.path.exists(SERVER_STATUS_FILE):
            with open(SERVER_STATUS_FILE, 'r', encoding='utf-8') as file:
                return json.load(file)
        return {}
    except Exception as e:
        logging.error(f"Error loading previous status: {e}")
        return {}

def save_status(status_data):
    """Save the current server status to file"""
    try:
        with open(SERVER_STATUS_FILE, 'w', encoding='utf-8') as file:
            json.dump(status_data, file, indent=2)
        logging.info(f"Server status saved to {SERVER_STATUS_FILE}")
    except Exception as e:
        logging.error(f"Error saving status: {e}")

def detect_changes(previous_status, current_status):
    """Detect changes in server status"""
    changes = []
    
    for server_name, current in current_status.items():
        if server_name in previous_status:
            prev = previous_status[server_name]
            
            # Check for status changes
            if current['status'] != prev['status']:
                changes.append({
                    'server': server_name,
                    'type': 'status',
                    'previous': prev['status'],
                    'current': current['status']
                })
            
            # Check for version changes
            if current['version'] != prev['version'] and current['version'] is not None:
                changes.append({
                    'server': server_name,
                    'type': 'version',
                    'previous': prev['version'],
                    'current': current['version']
                })
                
            # Check for significant pull count changes (>10%)
            if prev['pull_count'] > 0 and current['pull_count'] > 0:
                percentage_change = (current['pull_count'] - prev['pull_count']) / prev['pull_count'] * 100
                if abs(percentage_change) >= 10:
                    changes.append({
                        'server': server_name,
                        'type': 'pull_count',
                        'previous': prev['pull_count'],
                        'current': current['pull_count'],
                        'percentage': round(percentage_change, 2)
                    })
        else:
            # New server detected
            changes.append({
                'server': server_name,
                'type': 'new',
                'status': current['status']
            })
    
    # Check for removed servers
    for server_name in previous_status:
        if server_name not in current_status:
            changes.append({
                'server': server_name,
                'type': 'removed'
            })
    
    return changes

def format_output(servers_status, changes, output_format='markdown'):
    """Format the output based on the specified format"""
    if output_format == 'json':
        return json.dumps({
            'status': servers_status,
            'changes': changes,
            'timestamp': datetime.now().isoformat()
        }, indent=2)
    
    elif output_format == 'text':
        text_output = []
        text_output.append(f"SERVER CHECK REPORT - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        text_output.append("\nSERVER STATUS:")
        
        headers = ["Name", "Status", "Version", "Last Updated", "Pull Count"]
        rows = []
        
        for name, data in servers_status.items():
            rows.append([
                name,
                data['status'],
                data['version'] or 'N/A',
                data['last_updated'] or 'N/A',
                f"{data['pull_count']:,}" if data['pull_count'] else 'N/A'
            ])
        
        text_output.append(tabulate(rows, headers=headers))
        
        if changes:
            text_output.append("\nCHANGES DETECTED:")
            for change in changes:
                if change['type'] == 'status':
                    text_output.append(f"- {change['server']}: Status changed from {change['previous']} to {change['current']}")
                elif change['type'] == 'version':
                    text_output.append(f"- {change['server']}: Version updated from {change['previous']} to {change['current']}")
                elif change['type'] == 'pull_count':
                    text_output.append(f"- {change['server']}: Pull count changed by {change['percentage']}% ({change['previous']:,} ? {change['current']:,})")
                elif change['type'] == 'new':
                    text_output.append(f"- {change['server']}: New server detected (Status: {change['status']})")
                elif change['type'] == 'removed':
                    text_output.append(f"- {change['server']}: Server removed")
        
        return "\n".join(text_output)
    
    else:  # markdown
        md_output = []
        md_output.append(f"# MCP Server Check Report\n")
        md_output.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        
        md_output.append("## Server Status\n")
        md_output.append("| Server | Status | Version | Last Updated | Pull Count |")
        md_output.append("|--------|--------|---------|--------------|------------|")
        
        for name, data in servers_status.items():
            status_emoji = "?" if data['status'] == 'online' else "?" if data['status'] == 'offline' else "??"
            md_output.append(f"| {name} | {status_emoji} {data['status']} | {data['version'] or 'N/A'} | {data['last_updated'] or 'N/A'} | {data['pull_count']:,} |")
        
        if changes:
            md_output.append("\n## Changes Detected\n")
            for change in changes:
                if change['type'] == 'status':
                    md_output.append(f"- **{change['server']}**: Status changed from `{change['previous']}` to `{change['current']}`")
                elif change['type'] == 'version':
                    md_output.append(f"- **{change['server']}**: Version updated from `{change['previous']}` to `{change['current']}`")
                elif change['type'] == 'pull_count':
                    direction = "?" if change['percentage'] > 0 else "?"
                    md_output.append(f"- **{change['server']}**: Pull count changed by {direction} {abs(change['percentage'])}% ({change['previous']:,} ? {change['current']:,})")
                elif change['type'] == 'new':
                    md_output.append(f"- **{change['server']}**: New server detected (Status: `{change['status']}`)")
                elif change['type'] == 'removed':
                    md_output.append(f"- **{change['server']}**: Server removed")
        
        return "\n".join(md_output)

def send_notification(changes, servers_status, output_format='markdown'):
    """Send notification if there are changes"""
    if not changes:
        logging.info("No changes detected, skipping notification")
        return
    
    formatted_output = format_output(servers_status, changes, output_format)
    
    # Email notification
    if NOTIFICATION_EMAIL:
        try:
            import smtplib
            from email.mime.text import MIMEText
            from email.mime.multipart import MIMEMultipart
            
            # Setup email parameters
            smtp_server = os.environ.get('SMTP_SERVER', 'smtp.gmail.com')
            smtp_port = int(os.environ.get('SMTP_PORT', 587))
            smtp_username = os.environ.get('SMTP_USERNAME')
            smtp_password = os.environ.get('SMTP_PASSWORD')
            
            if smtp_username and smtp_password:
                msg = MIMEMultipart()
                msg['Subject'] = f"MCP Server Status Changes - {datetime.now().strftime('%Y-%m-%d')}"
                msg['From'] = smtp_username
                msg['To'] = NOTIFICATION_EMAIL
                
                if output_format == 'markdown':
                    # Convert markdown to HTML
                    import markdown
                    html_content = markdown.markdown(formatted_output)
                    msg.attach(MIMEText(html_content, 'html'))
                    msg.attach(MIMEText(formatted_output, 'plain'))
                else:
                    msg.attach(MIMEText(formatted_output, 'plain'))
                
                server = smtplib.SMTP(smtp_server, smtp_port)
                server.starttls()
                server.login(smtp_username, smtp_password)
                server.send_message(msg)
                server.quit()
                
                logging.info(f"Email notification sent to {NOTIFICATION_EMAIL}")
            else:
                logging.warning("Email notification enabled but SMTP credentials not provided")
        except Exception as e:
            logging.error(f"Failed to send email notification: {e}")
    
    # Slack notification
    if SLACK_WEBHOOK:
        try:
            slack_data = {
                "text": "MCP Server Status Update",
                "blocks": [
                    {
                        "type": "header",
                        "text": {
                            "type": "plain_text",
                            "text": f"MCP Server Status Changes - {datetime.now().strftime('%Y-%m-%d')}"
                        }
                    },
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": formatted_output if output_format == 'markdown' else f"```\n{formatted_output}\n```"
                        }
                    }
                ]
            }
            
            response = requests.post(
                SLACK_WEBHOOK,
                data=json.dumps(slack_data),
                headers={'Content-Type': 'application/json'}
            )
            
            if response.status_code != 200:
                logging.error(f"Failed to send Slack notification: {response.status_code} - {response.text}")
            else:
                logging.info("Slack notification sent successfully")
                
        except Exception as e:
            logging.error(f"Failed to send Slack notification: {e}")

def main():
    """Main function to check server status"""
    parser = argparse.ArgumentParser(description='Check Docker MCP servers status')
    parser.add_argument('--output', choices=['text', 'json', 'markdown'], default='markdown',
                        help='Output format (default: markdown)')
    parser.add_argument('--notify', action='store_true', help='Send notification on status changes')
    
    args = parser.parse_args()
    
    logging.info("Starting MCP server check process")
    
    try:
        # Read the README.md content
        readme_content = read_readme()
        
        # Extract server list
        servers = extract_server_list(readme_content)
        logging.info(f"Found {len(servers)} servers in README.md")
        
        # Load previous status
        previous_status = load_previous_status()
        
        # Check each server and build current status
        current_status = {}
        for server in servers:
            server_name = server['server_name']
            status = check_server(server_name)
            current_status[server_name] = status
            
            # Add a small delay to avoid rate limiting
            time.sleep(1)
        
        # Detect changes
        changes = detect_changes(previous_status, current_status)
        
        # Format and display output
        output = format_output(current_status, changes, args.output)
        print(output)
        
        # Save current status for future comparison
        save_status(current_status)
        
        # Send notification if needed and requested
        if args.notify and changes:
            send_notification(changes, current_status, args.output)
            
        logging.info("MCP server check completed")
        
    except Exception as e:
        logging.error(f"Error checking MCP servers: {e}")
        raise

if __name__ == "__main__":
    main()