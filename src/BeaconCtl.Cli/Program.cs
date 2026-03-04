using System.CommandLine;
using BeaconCtl.Core;
using Microsoft.Extensions.Logging;

namespace BeaconCtl.Cli;

// Exit codes
// 0  success
// 1  invalid arguments
// 2  COM port access denied
// 3  COM port not found / in use
// 4  serial write timeout
// 99 unexpected error

class Program
{
    static async Task<int> Main(string[] args)
    {
        // ── Options ──────────────────────────────────────────────────────────
        var portOption = new Option<string?>(
            "--port", "COM port (e.g. COM5). Overrides config.");

        var channelOption = new Option<int?>(
            "--ch", "Relay channel number 1–4.");

        var onOption = new Option<bool>(
            "--on", "Turn the channel on.");

        var offOption = new Option<bool>(
            "--off", "Turn the channel off.");

        var alloffOption = new Option<bool>(
            "--alloff", "Turn all relay channels off.");

        var pulseOption = new Option<int?>(
            "--pulse", "Pulse channel ON for N milliseconds, then off.");

        var protocolOption = new Option<string?>(
            "--protocol", "Protocol variant: lcus_a (default) | lcus_b.");

        var exclusiveOption = new Option<bool>(
            "--exclusive", "Turn off all other channels before turning one on (default: from config).");

        var nonexclusiveOption = new Option<bool>(
            "--nonexclusive", "Allow multiple channels on simultaneously.");

        var dryRunOption = new Option<bool>(
            "--dry-run", "Print what would be sent without opening the COM port.");

        var logFileOption = new Option<string?>(
            "--log-file", "Append timestamped log entries to this file.");

        var configOption = new Option<string?>(
            "--config", "Path to channels.json config (auto-detected if omitted).");

        // ── Root command ─────────────────────────────────────────────────────
        var root = new RootCommand("beaconctl — LCUS-4 relay control for 3-colour beacon lamp")
        {
            portOption, channelOption, onOption, offOption, alloffOption,
            pulseOption, protocolOption, exclusiveOption, nonexclusiveOption,
            dryRunOption, logFileOption, configOption
        };

        root.SetHandler(async context =>
        {
            var port         = context.ParseResult.GetValueForOption(portOption);
            var channel      = context.ParseResult.GetValueForOption(channelOption);
            var on           = context.ParseResult.GetValueForOption(onOption);
            var off          = context.ParseResult.GetValueForOption(offOption);
            var alloff       = context.ParseResult.GetValueForOption(alloffOption);
            var pulse        = context.ParseResult.GetValueForOption(pulseOption);
            var protocol     = context.ParseResult.GetValueForOption(protocolOption);
            var exclusive    = context.ParseResult.GetValueForOption(exclusiveOption);
            var nonexclusive = context.ParseResult.GetValueForOption(nonexclusiveOption);
            var dryRun       = context.ParseResult.GetValueForOption(dryRunOption);
            var logFile      = context.ParseResult.GetValueForOption(logFileOption);
            var configPath   = context.ParseResult.GetValueForOption(configOption);

            // ── Load config ──────────────────────────────────────────────────
            var cfg = BeaconConfig.Load(configPath ?? FindConfig());

            // ── Build logger ─────────────────────────────────────────────────
            using var logFactory = LoggerFactory.Create(b =>
            {
                b.AddSimpleConsole(o => { o.SingleLine = true; o.TimestampFormat = "HH:mm:ss "; });
                if (logFile != null) b.AddProvider(new FileLoggerProvider(logFile));
                b.SetMinimumLevel(LogLevel.Debug);
            });
            var log = logFactory.CreateLogger("beaconctl");

            // ── Resolve settings ─────────────────────────────────────────────
            var comPort     = port ?? cfg.ComPort;
            var baudRate    = cfg.BaudRate;
            var proto       = cfg.ParseProtocol(protocol);
            var isExclusive = nonexclusive ? false : (exclusive || cfg.Exclusive);
            var maxChannel  = cfg.MaxChannel;

            // ── Validate arguments ───────────────────────────────────────────
            if (!alloff && channel is null)
            {
                Console.Error.WriteLine("error: specify --ch N (1-4) or --alloff");
                context.ExitCode = 1;
                return;
            }
            if (!alloff && !on && !off && pulse is null)
            {
                Console.Error.WriteLine("error: specify --on, --off, or --pulse <ms>");
                context.ExitCode = 1;
                return;
            }
            if (on && off)
            {
                Console.Error.WriteLine("error: --on and --off are mutually exclusive");
                context.ExitCode = 1;
                return;
            }
            if (channel is < 1 or > 4)
            {
                Console.Error.WriteLine("error: --ch must be 1, 2, 3, or 4");
                context.ExitCode = 1;
                return;
            }

            // ── Build driver ─────────────────────────────────────────────────
            IRelayDriver driver = dryRun
                ? new DryRunRelayDriver(logFactory.CreateLogger<DryRunRelayDriver>())
                : new LcusRelayDriver(proto, logFactory.CreateLogger<LcusRelayDriver>());

            using (driver)
            {
                try
                {
                    await driver.OpenAsync(comPort, baudRate);

                    if (alloff)
                    {
                        log.LogInformation("alloff: turning channels 1–{Max} off", maxChannel);
                        await driver.AllOffAsync(maxChannel);
                    }
                    else if (pulse.HasValue)
                    {
                        log.LogInformation("CH{Ch} pulse {Ms}ms (exclusive={Ex})", channel, pulse, isExclusive);
                        if (isExclusive) await driver.AllOffAsync(maxChannel);
                        await driver.PulseAsync(channel!.Value, pulse.Value);
                    }
                    else if (on)
                    {
                        log.LogInformation("CH{Ch} ON (exclusive={Ex})", channel, isExclusive);
                        if (isExclusive) await driver.AllOffAsync(maxChannel);
                        await driver.SetChannelAsync(channel!.Value, true);
                    }
                    else // off
                    {
                        log.LogInformation("CH{Ch} OFF", channel);
                        await driver.SetChannelAsync(channel!.Value, false);
                    }

                    context.ExitCode = 0;
                }
                catch (UnauthorizedAccessException ex)
                {
                    Console.Error.WriteLine($"error: COM port access denied — {ex.Message}");
                    log.LogError(ex, "COM port access denied");
                    context.ExitCode = 2;
                }
                catch (IOException ex)
                {
                    Console.Error.WriteLine($"error: COM port not found or in use — {ex.Message}");
                    log.LogError(ex, "COM port IO error");
                    context.ExitCode = 3;
                }
                catch (TimeoutException ex)
                {
                    Console.Error.WriteLine($"error: serial write timeout — {ex.Message}");
                    log.LogError(ex, "Serial timeout");
                    context.ExitCode = 4;
                }
                catch (Exception ex)
                {
                    Console.Error.WriteLine($"error: {ex.Message}");
                    log.LogError(ex, "Unexpected error");
                    context.ExitCode = 99;
                }
            }
        });

        return await root.InvokeAsync(args);
    }

    /// <summary>
    /// Walks up from the executable location looking for config/channels.json,
    /// then falls back to the current working directory.
    /// </summary>
    private static string? FindConfig()
    {
        // CWD first (useful when running dotnet run from project root)
        var cwd = Path.Combine(Environment.CurrentDirectory, "config", "channels.json");
        if (File.Exists(cwd)) return cwd;

        // Walk up from AppContext.BaseDirectory (handles bin/Debug/net8.0 placement)
        var dir = AppContext.BaseDirectory;
        for (int i = 0; i < 6; i++)
        {
            var candidate = Path.Combine(dir, "config", "channels.json");
            if (File.Exists(candidate)) return candidate;
            var parent = Path.GetDirectoryName(dir);
            if (parent is null || parent == dir) break;
            dir = parent;
        }

        return null; // BeaconConfig.Load handles null gracefully (returns defaults)
    }
}
