// Headless PicoGK driver for OpenClaw Engineering — reads job.json, writes STL (mm).
// Run: dotnet run --project picogk_driver -- <job.json> <out.stl>
// On Linux Brev: xvfb-run -a dotnet run ...  (or build PicoGKRuntime from source if NuGet runtime fails)

using System.Numerics;
using System.Text.Json;
using PicoGK;

if (args.Length < 2)
{
    Console.Error.WriteLine("Usage: OpenClawEngineering.PicoGK <job.json> <out.stl>");
    Environment.Exit(2);
}

var jobPath = args[0];
var outStl = args[1];
var json = File.ReadAllText(jobPath);
var job = JsonSerializer.Deserialize<JobSpec>(json, JsonOpts()) ?? throw new Exception("Invalid job.json");

var done = false;
var error = "";

void Task()
{
    try
    {
        Voxels? acc = null;
        foreach (var op in job.operations ?? [])
            acc = Apply(acc, op);

        if (acc is null)
            acc = Voxels.voxSphere(Vector3.Zero, 10f);

        Mesh msh = new(acc);
        msh.SaveToStlFile(outStl, Mesh.EStlUnit.MM);
        done = true;
    }
    catch (Exception ex)
    {
        error = ex.ToString();
    }
}

Library.Go(job.voxel_size_mm, Task);

if (!done)
{
    Console.Error.WriteLine(error);
    Environment.Exit(1);
}

Console.WriteLine($"{{\"status\":\"ok\",\"stl\":\"{outStl}\"}}");

static Voxels Apply(Voxels? acc, Operation op)
{
    Voxels? piece = op.type switch
    {
        "sphere" => Voxels.voxSphere(ToVec(op.center), op.radius ?? 10f),
        "beam" => BeamVoxels(op),
        "stl_import" => StlVoxels(op),
        "cube" => Voxels.voxSphere(ToVec(op.center), (op.size ?? 20f) * 0.5f),
        _ => throw new Exception($"Unknown op type: {op.type}"),
    };

    if (piece is null)
        throw new Exception($"Failed op {op.type}");

    if (acc is null)
        return piece;

    var mode = (op.boolean ?? "add").ToLowerInvariant();
    return mode switch
    {
        "add" or "union" or "+" => acc + piece,
        "subtract" or "sub" or "-" => acc - piece,
        "intersect" or "&" => acc & piece,
        _ => acc + piece,
    };
}

static Voxels BeamVoxels(Operation op)
{
    var a = ToVec(op.a ?? [0, 0, 0]);
    var b = ToVec(op.b ?? [10, 0, 0]);
    float r = op.radius ?? 3f;
    Lattice lat = new();
    lat.AddBeam(a, b, r, r, true);
    return new Voxels(lat);
}

static Voxels StlVoxels(Operation op)
{
    if (string.IsNullOrEmpty(op.path) || !File.Exists(op.path))
        throw new FileNotFoundException(op.path ?? "stl_import path missing");
    Mesh m = Mesh.mshFromStlFile(op.path, Mesh.EStlUnit.MM, op.scale ?? 1f);
    return new Voxels(m);
}

static Vector3 ToVec(float[]? c) =>
    c is { Length: >= 3 } ? new Vector3(c[0], c[1], c[2]) : Vector3.Zero;

static JsonSerializerOptions JsonOpts() => new() { PropertyNameCaseInsensitive = true };

sealed class JobSpec
{
    public float voxel_size_mm { get; set; } = 0.5f;
    public List<Operation>? operations { get; set; }
}

sealed class Operation
{
    public string type { get; set; } = "sphere";
    public string? boolean { get; set; }
    public float[]? center { get; set; }
    public float[]? a { get; set; }
    public float[]? b { get; set; }
    public float? radius { get; set; }
    public float? size { get; set; }
    public float? scale { get; set; }
    public string? path { get; set; }
}
