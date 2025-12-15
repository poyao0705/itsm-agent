# Jira/Github Setup Guide

## 1. Get the site URL

1. Create Jira Cloud account
2. The site URL is given after account setup
3. Format: `https://<your-domain>.atlassian.net`

## 2. Get the API token

1. Go back to Atlassian Home
2. Click on your profile picture
3. Click on "Account Settings"
4. Click on "Security" tab
5. Go to "API tokens" section
6. Click on "Create and manage API tokens"

## 3. Check the API token availability

```bash
curl -u <registered-email>:<api-token> \
https://<your-domain>.atlassian.net/rest/api/3/issue/<issue-key>
```

## 4. Connect to Github Enterprise

Follow the below guide:
`https://support.atlassian.com/jira-cloud-administration/docs/integrate-with-github/`
