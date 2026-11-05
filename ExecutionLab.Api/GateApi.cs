using Microsoft.AspNetCore.Authentication.JwtBearer;
using Microsoft.IdentityModel.Tokens;
using ExecutionLab.Persistence;

namespace ExecutionLab.Api;

public sealed record ReserveRequest(string? OrderId, long Quantity);
public sealed record DecisionResponse(bool Accepted, string Reason, long Sequence, long Exposure, bool Replayed);

public static class GateApi
{
    public const string Issuer = "execution-lab-local";
    public const string Audience = "execution-lab-control";
    public static void Configure(WebApplicationBuilder builder, byte[] signingKey)
    {
        if (signingKey.Length < 32) throw new ArgumentException("Use at least 256 random key bits.", nameof(signingKey));
        builder.Services.AddAuthentication(JwtBearerDefaults.AuthenticationScheme).AddJwtBearer(options =>
        {
            options.MapInboundClaims = false;
            options.TokenValidationParameters = new()
            {
                ValidateIssuer = true, ValidIssuer = Issuer,
                ValidateAudience = true, ValidAudience = Audience,
                ValidateIssuerSigningKey = true, IssuerSigningKey = new SymmetricSecurityKey(signingKey),
                ValidateLifetime = true, RequireExpirationTime = true, RequireSignedTokens = true,
                ClockSkew = TimeSpan.Zero, RoleClaimType = "role",
                ValidAlgorithms = [SecurityAlgorithms.HmacSha256]
            };
        });
        builder.Services.AddAuthorization(options => options.AddPolicy("operator", policy =>
            policy.RequireAuthenticatedUser().RequireRole("operator").RequireAssertion(context =>
                context.User.FindAll("sub").Any(claim => !string.IsNullOrWhiteSpace(claim.Value)))));
    }

    public static void Map(WebApplication app, DurableGate store)
    {
        app.UseAuthentication(); app.UseAuthorization();
        app.MapPost("/reservations", (HttpContext context, ReserveRequest request) =>
        {
            var key = context.Request.Headers["Idempotency-Key"].ToString();
            if (string.IsNullOrWhiteSpace(key) || key.Length > 64 || key.Any(c => !char.IsAsciiLetterOrDigit(c) && c is not '-' and not '_') ||
                string.IsNullOrWhiteSpace(request.OrderId) || request.OrderId.Length > 64 || request.Quantity <= 0)
                return Results.BadRequest(new { error = "A bounded key, order ID and positive quantity are required." });
            try
            {
                // All operators share ONE fictitious gate; this is not tenant isolation.
                var result = store.Apply(key, new Reserve(key, 0, request.OrderId, request.Quantity));
                var d = result.Decision;
                return Results.Ok(new DecisionResponse(d.Accepted, d.Reason, d.State.Sequence, d.State.ReservedExposure, result.Replayed));
            }
            catch (IdempotencyConflictException) { return Results.Conflict(new { error = "Key already used for different content." }); }
        }).RequireAuthorization("operator");
    }
}
