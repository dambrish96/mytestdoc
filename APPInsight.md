Step 1: Enable Application Insights for Logic Apps
Enable Application Insights:
Go to each Logic App in the Azure Portal.
Under Settings, select Diagnostics settings.
Click Add diagnostic setting.
Choose to send diagnostic logs to an Application Insights instance.
Select the relevant metrics and logs to be sent to Application Insights.
Save the settings.
Step 2: Set Up Application Insights
Create Application Insights Instance:

If you don’t have an Application Insights instance, create one.
Go to Create a resource > Application Insights > Create.
Fill in the required details and create the instance.
Link Logic Apps to Application Insights:

Ensure all Logic Apps are sending logs to the Application Insights instance.
Step 3: Create a Failure-Handling Logic App
Create the Logic App:
Create a new Logic App in the Azure Portal.
Add an HTTP trigger to receive failure details.
Add actions to handle failures (e.g., send notifications, log details).
Step 4: Create Log Alerts in Application Insights
Create Log Alerts:

Go to your Application Insights instance.
Under Monitoring, select Alerts > + New alert rule.
Define a condition based on your needs. For example, use a custom log search for failed runs:
kusto
Copy code
customEvents
| where name == "WorkflowFailed"
Set Up Action Groups:

Create an Action Group to invoke the failure-handling Logic App.
Add an action of type Logic App and select the failure-handling Logic App.
Link Alerts to Action Groups:

Configure the alert rule to use the Action Group for triggering the failure-handling Logic App.
Step 5: Customize Azure Dashboard
Create a New Dashboard:

In the Azure Portal, click on Dashboard > + New dashboard.
Add Application Insights Tiles:

Click + Add > Tile Gallery.
Choose Application Insights and configure tiles with relevant metrics and logs.
Example Queries for Application Insights
Query for Recent Failures:

kusto
Copy code
customEvents
| where name == "WorkflowFailed"
| project timestamp, customDimensions.WorkflowName, customDimensions.Status, customDimensions.CorrelationId
| order by timestamp desc
Query for Total Runs and Successes:

kusto
Copy code
customEvents
| summarize totalRuns = count(), totalSuccess = countif(customDimensions.Status == "Succeeded") by customDimensions.WorkflowName
Query for Average Duration of Runs:

kusto
Copy code
customMetrics
| where name == "WorkflowDuration"
| summarize avgDuration = avg(value) by customDimensions.WorkflowName
Step 6: Implement Failure Handling in Logic Apps
Send Failure Data:

In your Logic Apps workflows, add a step to send failure data to Application Insights. For example, using the HTTP action to send custom events:
json
Copy code
{
  "name": "WorkflowFailed",
  "customDimensions": {
    "WorkflowName": "YourLogicAppName",
    "Status": "Failed",
    "CorrelationId": "WorkflowCorrelationId"
  }
}
Handle Failures:

Configure your failure-handling Logic App to process the failure data. For example, send an email or log the failure details.
Step 7: Configure and Monitor the Dashboard
Configure Dashboard Tiles:

Add and configure tiles to show:
Recent failures.
Total runs and successes.
Average duration of runs.
Active alerts.
Monitor and Maintain:

Regularly review the dashboard.
Adjust queries and alerts as needed to ensure comprehensive monitoring and quick response to failures.
By following these steps, you will set up a comprehensive monitoring solution for your 100 Logic Apps, leveraging Application Insights for metrics and logs, and using an Azure Dashboard for visualization and proactive management.
