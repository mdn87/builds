namespace BeaconCtl.Core;

public enum RelayProtocol
{
    /// <summary>Standard LCUS-4 command: A0 CH STATE (A0+CH+STATE)&0xFF</summary>
    LcusA,

    /// <summary>Alternate clone variant: A0 CH STATE (A0^CH^STATE)&0xFF</summary>
    LcusB
}
