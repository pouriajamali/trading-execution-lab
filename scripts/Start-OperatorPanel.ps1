param(
    [string] $PublishedDirectory = $PSScriptRoot,
    [string] $Dotnet = 'dotnet'
)

$appDirectory = (Resolve-Path -LiteralPath $PublishedDirectory).Path
$dll = Join-Path $appDirectory 'ExecutionLab.Api.dll'
if (!(Test-Path -LiteralPath $dll -PathType Leaf)) {
    throw 'Pass the directory containing the published ExecutionLab.Api.dll.'
}
$runtime = (Get-Command $Dotnet -CommandType Application -ErrorAction Stop).Source
$secureCode = Read-Host 'Choose an operator code for this run (16–128 characters)' -AsSecureString
if ($secureCode.Length -lt 16 -or $secureCode.Length -gt 128) {
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
} finally {
    foreach ($variable in $variables) { [Environment]::SetEnvironmentVariable($variable, $saved[$variable], 'Process') }
    [Array]::Clear($key, 0, $key.Length)
    $secureCode.Dispose()
    Pop-Location
}
