using System.IdentityModel.Tokens.Jwt;
using System.Security.Claims;
using System.Security.Cryptography;
using System.Text;
using Microsoft.AspNetCore.RateLimiting;
using Microsoft.IdentityModel.Tokens;
using ExecutionLab.Persistence;

namespace ExecutionLab.Api;

public sealed record OperatorLogin(string? Code);

// Opt-in local synthetic interface. The original HTTP contract works with the
// panel disabled, and enabling it never exposes recovery, fills or venue commands.
public static class PanelApi
{
    public static void Configure(WebApplicationBuilder builder) =>
        builder.Services.AddRateLimiter(options =>
        {
            options.RejectionStatusCode = StatusCodes.Status429TooManyRequests;
            options.AddFixedWindowLimiter("operator-login", limiter =>
            {
                limiter.PermitLimit = 8;
                limiter.Window = TimeSpan.FromMinutes(1);
                limiter.QueueLimit = 0;
            });
        });

    public static void Map(WebApplication app, DurableGate store, int limit, byte[] signingKey, string code)
    {
        var expected = Digest(code);
        app.UseRateLimiter();
        app.MapPost("/panel/api/session", (HttpContext context, OperatorLogin request) =>
        {
            context.Response.Headers.CacheControl = "no-store";
            if (request.Code is not { Length: >= 16 and <= 128 } ||
                !CryptographicOperations.FixedTimeEquals(expected, Digest(request.Code)))
                return Results.Unauthorized();
            var now = DateTime.UtcNow;
            var token = new JwtSecurityToken(GateApi.Issuer, GateApi.Audience,
                [new Claim("sub", "local-panel"), new Claim("role", "operator")],
                now, now.AddMinutes(15),
                new SigningCredentials(new SymmetricSecurityKey(signingKey), SecurityAlgorithms.HmacSha256));
            return Results.Ok(new { token = new JwtSecurityTokenHandler().WriteToken(token) });
        }).RequireRateLimiting("operator-login");

        app.MapGet("/panel/api/state", (HttpContext context) =>
        {
            context.Response.Headers.CacheControl = "no-store";
            var state = store.ReadState();
            return Results.Ok(new
            {
                state.Sequence, state.Position, state.Pending, exposure = state.ReservedExposure,
                limit, state.Reconciled, state.Stopped,
                orders = state.Orders.OrderBy(order => order.Key, StringComparer.Ordinal)
                    .Select(order => new { id = order.Key, order.Value.Remaining, order.Value.CancelRequested })
            });
        }).RequireAuthorization("operator");
    }

    private static byte[] Digest(string value) => SHA256.HashData(Encoding.UTF8.GetBytes(value));
}
