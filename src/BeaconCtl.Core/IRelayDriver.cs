namespace BeaconCtl.Core;

public interface IRelayDriver : IDisposable
{
    Task OpenAsync(string port, int baudRate, CancellationToken ct = default);
    Task SetChannelAsync(int channel, bool on, CancellationToken ct = default);
    Task AllOffAsync(int channelCount, CancellationToken ct = default);
    Task PulseAsync(int channel, int milliseconds, CancellationToken ct = default);
}
