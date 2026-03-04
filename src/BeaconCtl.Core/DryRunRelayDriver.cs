using Microsoft.Extensions.Logging;

namespace BeaconCtl.Core;

/// <summary>Logs relay commands to stdout without touching any serial port.</summary>
public sealed class DryRunRelayDriver : IRelayDriver
{
    private readonly ILogger<DryRunRelayDriver> _logger;

    public DryRunRelayDriver(ILogger<DryRunRelayDriver> logger) => _logger = logger;

    public Task OpenAsync(string port, int baudRate, CancellationToken ct = default)
    {
        Console.WriteLine($"[DRY-RUN] Would open {port} @ {baudRate} baud");
        return Task.CompletedTask;
    }

    public Task SetChannelAsync(int channel, bool on, CancellationToken ct = default)
    {
        Console.WriteLine($"[DRY-RUN] CH{channel} → {(on ? "ON" : "OFF")}");
        return Task.CompletedTask;
    }

    public async Task AllOffAsync(int channelCount, CancellationToken ct = default)
    {
        for (int i = 1; i <= channelCount; i++)
            await SetChannelAsync(i, false, ct);
    }

    public async Task PulseAsync(int channel, int milliseconds, CancellationToken ct = default)
    {
        Console.WriteLine($"[DRY-RUN] CH{channel} → ON  (pulse {milliseconds} ms)");
        await Task.Delay(milliseconds, ct);
        Console.WriteLine($"[DRY-RUN] CH{channel} → OFF");
    }

    public void Dispose() { }
}
