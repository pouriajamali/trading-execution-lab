param(
    [string] $PublishedDirectory = $PSScriptRoot,
    [string] $Dotnet = 'dotnet'
)

$appDirectory = (Resolve-Path -LiteralPath $PublishedDirectory).Path
$dll = Join-Path $appDirectory 'ExecutionLab.Api.dll'
if (!(Test-Path -LiteralPath $dll -PathType Leaf)) {
    throw 'Pass the directory containing the published ExecutionLab.Api.dll.'
}
# Inspect this exact host, not another installation discoverable on PATH.
# Keep the English CLI output local to these probes and restore the caller's value.
$prerequisite = 'This panel requires x64 ASP.NET Core Runtime 10.0.14 or a later 10.0 patch (including Microsoft.NETCore.App). See https://github.com/pouriajamali/trading-execution-lab/blob/main/docs/QUICKSTART.md#install-prerequisites . No runtime or system setting was changed.'
$savedLanguage = [Environment]::GetEnvironmentVariable('DOTNET_CLI_UI_LANGUAGE', 'Process')
try {
    $runtime = (Get-Command $Dotnet -CommandType Application -ErrorAction Stop).Source
    $env:DOTNET_CLI_UI_LANGUAGE = 'en-US'
    $hostInfo = @(& $runtime --info 2>&1)
    $infoExit = $LASTEXITCODE
    $frameworks = @(& $runtime --list-runtimes 2>&1)
    $listExit = $LASTEXITCODE
    if ($infoExit -ne 0 -or $listExit -ne 0) { throw 'Selected host inspection failed.' }
    $hostSection = [regex]::Match(($hostInfo -join "`n") + "`n", '(?m)^Host:\s*\r?\n(?<details>(?:[ \t]+[^\r\n]*\r?\n|[ \t]*\r?\n)*)')
    if (!$hostSection.Success -or $hostSection.Groups['details'].Value -notmatch '(?m)^[ \t]+Architecture:[ \t]+x64[ \t]*\r?$') {
        throw 'The selected host is not x64 or its architecture could not be determined.'
    }
    foreach ($framework in @('Microsoft.NETCore.App', 'Microsoft.AspNetCore.App')) {
        $compatible = @($frameworks | Where-Object {
            $_ -match ('^' + [regex]::Escape($framework) + ' 10\.0\.(?<patch>[0-9]+) \[[^\r\n]+\]$') -and
            [int]$Matches['patch'] -ge 14
        })
        if ($compatible.Count -eq 0) { throw "The selected host lacks a compatible $framework framework." }
    }
} catch {
    throw "$prerequisite Selected host: '$Dotnet'. $($_.Exception.Message)"
} finally {
    [Environment]::SetEnvironmentVariable('DOTNET_CLI_UI_LANGUAGE', $savedLanguage, 'Process')
}
$secureCode = Read-Host 'Choose an operator code for this run (16–128 characters)' -AsSecureString
if ($secureCode.Length -lt 16 -or $secureCode.Length -gt 128) {
    $secureCode.Dispose()
    throw 'The local operator code must be 16–128 characters.'
}
$demoDirectory = Join-Path ([System.IO.Path]::GetTempPath()) ('execution-lab-' + [Guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $demoDirectory -ErrorAction Stop | Out-Null
$key = [byte[]]::new(32)
$random = [Security.Cryptography.RandomNumberGenerator]::Create()
$random.GetBytes($key)
$random.Dispose()
$variables = @('EXECUTION_LAB_PANEL', 'EXECUTION_LAB_PANEL_SEED_NEW', 'EXECUTION_LAB_DB', 'EXECUTION_LAB_KEY_BASE64', 'EXECUTION_LAB_OPERATOR_CODE')
$saved = @{}
foreach ($variable in $variables) { $saved[$variable] = [Environment]::GetEnvironmentVariable($variable, 'Process') }
$backendExit = 1
Push-Location -LiteralPath $appDirectory
try {
    $env:EXECUTION_LAB_PANEL = '1'
    $env:EXECUTION_LAB_PANEL_SEED_NEW = '1'
    $env:EXECUTION_LAB_DB = Join-Path $demoDirectory 'synthetic.sqlite'
    $env:EXECUTION_LAB_KEY_BASE64 = [Convert]::ToBase64String($key)
    $env:EXECUTION_LAB_OPERATOR_CODE = [Net.NetworkCredential]::new('', $secureCode).Password
    Write-Host 'Open http://127.0.0.1:5087/panel/ and enter the operator code for this run.'
    Write-Host "Disposable synthetic database: $env:EXECUTION_LAB_DB"
    & $runtime $dll
    $backendExit = $LASTEXITCODE
} finally {
    foreach ($variable in $variables) { [Environment]::SetEnvironmentVariable($variable, $saved[$variable], 'Process') }
    [Array]::Clear($key, 0, $key.Length)
    $secureCode.Dispose()
    Pop-Location
    # Delete only this launcher's freshly created, generated directory. A caller's
    # supplied database is never accepted by this launcher or removed here.
    $temporaryRoot = [System.IO.Path]::GetFullPath([System.IO.Path]::GetTempPath())
    $resolvedDemo = (Resolve-Path -LiteralPath $demoDirectory -ErrorAction Stop).Path
    if ([System.IO.Path]::GetDirectoryName($resolvedDemo).TrimEnd([System.IO.Path]::DirectorySeparatorChar) -ne $temporaryRoot.TrimEnd([System.IO.Path]::DirectorySeparatorChar) -or
        [System.IO.Path]::GetFileName($resolvedDemo) -notmatch '^execution-lab-[0-9a-f]{32}$') {
        throw 'Refusing cleanup outside the owned temporary demo directory.'
    }
    Remove-Item -LiteralPath $resolvedDemo -Recurse -Force -ErrorAction Stop
}
exit $backendExit
