# Docker MCP Servers Monitoring Scripts

This directory contains scripts to monitor and update information about Docker MCP servers listed in the main repository.

## Available Scripts

### 1. `update_pull_counts.py`

Updates the Docker Hub pull counts for all MCP servers listed in the README.md.

**Features:**
- Fetches current pull counts from Docker Hub API
- Updates the README.md with the latest numbers
- Can optionally commit and push changes to GitHub

**Usage:**
```bash
# Just update the README locally
python update_pull_counts.py

# Update and commit changes to GitHub
python update_pull_counts.py --commit
```

### 2. `check_mcp_servers.py`

Checks the availability and status of all Docker MCP servers listed in the README.md.

**Features:**
- Verifies if each server is available on Docker Hub
- Monitors server health, version, and pull count changes
- Generates a report in different formats (text, JSON, Markdown)
- Can send notifications when changes are detected

**Usage:**
```bash
# Generate report in markdown format
python check_mcp_servers.py --output markdown

# Generate report and send notifications if changes detected
python check_mcp_servers.py --notify
```

## GitHub Actions Workflows

These scripts are automatically run via GitHub Actions:

1. **Update Docker Hub Pull Counts** - Runs daily to update pull counts
2. **Check MCP Servers** - Runs every 6 hours to monitor server status

## Environment Variables

To enable notifications and GitHub integration, set these environment variables:

### For Email Notifications:
- `NOTIFICATION_EMAIL`: Email address to send notifications to
- `SMTP_SERVER`: SMTP server address (default: smtp.gmail.com)
- `SMTP_PORT`: SMTP port (default: 587)
- `SMTP_USERNAME`: SMTP username
- `SMTP_PASSWORD`: SMTP password

### For Slack Notifications:
- `SLACK_WEBHOOK`: Slack webhook URL

### For GitHub Integration:
- `GITHUB_TOKEN`: GitHub personal access token with repo permissions

## Adding to Repository

1. Place the scripts in the repository root or in a `scripts/` directory
2. Create the `.github/workflows/` directory and add the workflow files
3. Set up necessary secrets in the GitHub repository settings
4. Run the scripts manually first to initialize the status file