using Microsoft.Extensions.Logging;

namespace BeaconCtl.Cli;

/// <summary>Appends structured log lines to a file.</summary>
public sealed class FileLoggerProvider : ILoggerProvider
{
    private readonly StreamWriter _writer;

    public FileLoggerProvider(string path)
    {
        _writer = new StreamWriter(path, append: true) { AutoFlush = true };
    }

    public ILogger CreateLogger(string categoryName) => new FileLogger(_writer, categoryName);

    public void Dispose() => _writer.Dispose();
}

file sealed class FileLogger : ILogger
{
    private readonly StreamWriter _writer;
    private readonly string _category;

    public FileLogger(StreamWriter writer, string category)
    {
        _writer = writer;
        _category = category;
    }

    public IDisposable? BeginScope<TState>(TState state) where TState : notnull => null;

    public bool IsEnabled(LogLevel logLevel) => logLevel >= LogLevel.Debug;

    public void Log<TState>(LogLevel logLevel, EventId eventId, TState state,
        Exception? exception, Func<TState, Exception?, string> formatter)
    {
        _writer.WriteLine($"{DateTime.Now:yyyy-MM-dd HH:mm:ss.fff} [{logLevel,-11}] {_category}: {formatter(state, exception)}");
        if (exception != null)
            _writer.WriteLine(exception.ToString());
    }
}
