using System.IO.Ports;
using Microsoft.Extensions.Logging;

namespace BeaconCtl.Core;

/// <summary>
/// Sends 4-byte serial commands to an LCUS-4 (CH340) USB relay board.
///
/// LCUS-A (default): A0 CH STATE sum
///   sum = (0xA0 + CH + STATE) &amp; 0xFF
///
/// LCUS-B (alternate clone variant): A0 CH STATE xor
///   xor = (0xA0 ^ CH ^ STATE) &amp; 0xFF
///
/// Switch with --protocol lcus_b if the relay doesn't click on lcus_a.
/// </summary>
public sealed class LcusRelayDriver : IRelayDriver
{
    private readonly RelayProtocol _protocol;
    private readonly ILogger<LcusRelayDriver> _logger;
    private SerialPort? _port;

    public LcusRelayDriver(RelayProtocol protocol, ILogger<LcusRelayDriver> logger)
    {
        _protocol = protocol;
        _logger = logger;
    }

    public Task OpenAsync(string portName, int baudRate, CancellationToken ct = default)
    {
        _port = new SerialPort(portName, baudRate, Parity.None, 8, StopBits.One)
        {
            ReadTimeout  = 500,
            WriteTimeout = 500
        };
        _port.Open();
        _logger.LogInformation("Opened {Port} @ {Baud} baud, protocol={Proto}", portName, baudRate, _protocol);
        return Task.CompletedTask;
    }

    public Task SetChannelAsync(int channel, bool on, CancellationToken ct = default)
    {
        ThrowIfNotOpen();
        var cmd = BuildCommand(channel, on);
        _logger.LogDebug("CH{Ch} {State} → [{Bytes}]", channel, on ? "ON" : "OFF", BitConverter.ToString(cmd));
        _port!.Write(cmd, 0, cmd.Length);
        return Task.CompletedTask;
    }

    public async Task AllOffAsync(int channelCount, CancellationToken ct = default)
    {
        for (int i = 1; i <= channelCount; i++)
        {
            await SetChannelAsync(i, false, ct);
            await Task.Delay(20, ct); // brief inter-command gap
        }
    }

    public async Task PulseAsync(int channel, int milliseconds, CancellationToken ct = default)
    {
        await SetChannelAsync(channel, true, ct);
        await Task.Delay(milliseconds, ct);
        await SetChannelAsync(channel, false, ct);
    }

    private void ThrowIfNotOpen()
    {
        if (_port is not { IsOpen: true })
            throw new InvalidOperationException("Serial port is not open.");
    }

    private byte[] BuildCommand(int channel, bool on)
    {
        byte state = on ? (byte)0x01 : (byte)0x00;
        return _protocol switch
        {
            RelayProtocol.LcusB => BuildLcusB((byte)channel, state),
            _                   => BuildLcusA((byte)channel, state)
        };
    }

    // Standard protocol: checksum = sum of all prior bytes, masked to 8 bits
    private static byte[] BuildLcusA(byte ch, byte state)
    {
        byte header   = 0xA0;
        byte checksum = (byte)((header + ch + state) & 0xFF);
        return [header, ch, state, checksum];
    }

    // Alternate clone variant: checksum = XOR of all prior bytes
    private static byte[] BuildLcusB(byte ch, byte state)
    {
        byte header   = 0xA0;
        byte checksum = (byte)(header ^ ch ^ state);
        return [header, ch, state, checksum];
    }

    public void Dispose()
    {
        _port?.Close();
        _port?.Dispose();
    }
}
