using System.Text.Json;
using System.Text.Json.Serialization;

namespace BeaconCtl.Core;

public class BeaconConfig
{
    [JsonPropertyName("comPort")]
    public string ComPort { get; set; } = "COM5";

    [JsonPropertyName("baudRate")]
    public int BaudRate { get; set; } = 9600;

    [JsonPropertyName("protocol")]
    public string Protocol { get; set; } = "lcus_a";

    [JsonPropertyName("exclusive")]
    public bool Exclusive { get; set; } = true;

    [JsonPropertyName("channels")]
    public Dictionary<string, int> Channels { get; set; } = new()
    {
        ["red"] = 1, ["yellow"] = 2, ["green"] = 3, ["buzzer"] = 4
    };

    [JsonPropertyName("statusEngine")]
    public StatusEngineConfig StatusEngine { get; set; } = new();

    public static BeaconConfig Load(string? path)
    {
        if (path == null || !File.Exists(path))
            return new BeaconConfig();

        using var stream = File.OpenRead(path);
        return JsonSerializer.Deserialize<BeaconConfig>(stream,
            new JsonSerializerOptions { PropertyNameCaseInsensitive = true })
               ?? new BeaconConfig();
    }

    public RelayProtocol ParseProtocol(string? overrideValue = null)
    {
        var raw = overrideValue ?? Protocol;
        return raw.ToLowerInvariant() switch
        {
            "lcus_b" or "b" => RelayProtocol.LcusB,
            _ => RelayProtocol.LcusA
        };
    }

    /// <summary>Resolves a logical name (e.g. "red") to a channel number, or null if unknown.</summary>
    public int? ResolveChannel(string name) =>
        Channels.TryGetValue(name.ToLowerInvariant(), out var ch) ? ch : null;

    public int MaxChannel => Channels.Count > 0 ? Channels.Values.Max() : 4;
}

public class StatusEngineConfig
{
    [JsonPropertyName("pollIntervalMinutes")]
    public int PollIntervalMinutes { get; set; } = 3;

    [JsonPropertyName("warningThresholdMinutes")]
    public int WarningThresholdMinutes { get; set; } = 60;

    [JsonPropertyName("criticalThresholdMinutes")]
    public int CriticalThresholdMinutes { get; set; } = 120;

    [JsonPropertyName("hysteresisPolls")]
    public int HysteresisPolls { get; set; } = 2;

    [JsonPropertyName("buzzerPulseMs")]
    public int BuzzerPulseMs { get; set; } = 750;
}
