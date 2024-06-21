using System;
using System.IO;
using System.Net.Http;
using System.Security.Cryptography.X509Certificates;
using System.Text;
using System.Threading.Tasks;
using Microsoft.Azure.WebJobs;
using Microsoft.Extensions.Logging;
using Newtonsoft.Json;

public static class MyHttpClientFunction
{
    private static HttpClient _httpClient;

    static MyHttpClientFunction()
    {
        InitializeHttpClient();
    }

    private static void InitializeHttpClient()
    {
        var certificatePath = Path.Combine(AppContext.BaseDirectory, "path/to/your/certificate.pfx");
        var certificatePassword = "your-certificate-password";

        // Load the PFX certificate from the local file system
        var certificate = new X509Certificate2(certificatePath, certificatePassword, X509KeyStorageFlags.MachineKeySet);

        // Create HttpClientHandler with the certificate
        var handler = new HttpClientHandler();
        handler.ClientCertificates.Add(certificate);

        _httpClient = new HttpClient(handler);
    }

    [FunctionName("MyHttpClientFunction")]
    public static async Task Run(
        [TimerTrigger("0 */5 * * * *")] TimerInfo myTimer,
        ILogger log)
    {
        var requestUrl = "https://api.example.com/endpoint";
        var payload = new
        {
            key1 = "value1",
            key2 = "value2"
        };

        var jsonPayload = JsonConvert.SerializeObject(payload);
        var content = new StringContent(jsonPayload, Encoding.UTF8, "application/json");

        var response = await _httpClient.PostAsync(requestUrl, content);

        if (response.IsSuccessStatusCode)
        {
            var responseContent = await response.Content.ReadAsStringAsync();
            log.LogInformation($"Response: {responseContent}");
        }
        else
        {
            log.LogError($"HTTP POST failed with status code: {response.StatusCode}");
        }
    }
}