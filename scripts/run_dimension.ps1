param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('13', '14', '15', '16', '17', '18', '20')]
    [string]$Dimension,
    [switch]$CheckOnly,
    [switch]$Force
)

$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Python = Join-Path $Root '.venv\Scripts\python.exe'
$Config = Join-Path $Root "configs\task_d${Dimension}_local.yaml"
$env:PATH = "$(Join-Path $Root '.runtime\ffmpeg\bin');$env:PATH"
if (-not (Test-Path $Python)) { throw 'Project Python environment missing. Run .\scripts\setup_environment.ps1 first.' }
if (-not (Test-Path $Config)) { throw "Task config not found: $Config" }

$EnvFile = Join-Path $Root '.env'
if (Test-Path $EnvFile) {
    foreach ($Line in Get-Content $EnvFile) {
        if ($Line -match '^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?)\s*$' -and $Matches[1] -notmatch '^#') {
            $Name = $Matches[1]
            $Value = $Matches[2].Trim()
            if ($Value.Length -ge 2 -and (($Value.StartsWith('"') -and $Value.EndsWith('"')) -or ($Value.StartsWith("'") -and $Value.EndsWith("'")))) {
                $Value = $Value.Substring(1, $Value.Length - 2)
            }
            [Environment]::SetEnvironmentVariable($Name, $Value, 'Process')
        }
    }
}

if (-not $CheckOnly) {
    if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue) -or -not (Get-Command ffprobe -ErrorAction SilentlyContinue)) {
        throw 'FFmpeg and ffprobe are required. Run .\scripts\setup_environment.ps1 -InstallFfmpeg.'
    }
    $VisionDims = @('13', '14', '17', '18')
    $AudioDims = @('15', '16', '20')
    $RequiredUrl = if ($VisionDims -contains $Dimension) { 'V_EVAL_VISION_JUDGE_URL' } else { 'V_EVAL_AUDIO_JUDGE_URL' }
    if (-not $env:V_EVAL_CHECKLIST_URL -and -not $env:V_EVAL_VISION_JUDGE_URL -and -not $env:V_EVAL_AUDIO_JUDGE_URL -and -not $env:V_EVAL_JUDGE_URL) {
        throw 'Checklist judge endpoint missing. Configure V_EVAL_CHECKLIST_URL or the applicable judge URL in .env.'
    }
    if (-not (Get-Item "Env:$RequiredUrl" -ErrorAction SilentlyContinue) -and -not $env:V_EVAL_JUDGE_URL) {
        throw "Answer judge endpoint missing. Configure $RequiredUrl or V_EVAL_JUDGE_URL in .env."
    }
    $RequiredPrefix = $RequiredUrl -replace '_URL$', ''
    foreach ($Name in @('V_EVAL_CHECKLIST_URL', 'V_EVAL_CHECKLIST_MODEL', 'V_EVAL_CHECKLIST_API_KEY',
                       $RequiredUrl, "${RequiredPrefix}_MODEL", "${RequiredPrefix}_API_KEY",
                       'V_EVAL_JUDGE_URL', 'V_EVAL_JUDGE_MODEL', 'V_EVAL_JUDGE_API_KEY')) {
        $Value = [Environment]::GetEnvironmentVariable($Name, 'Process')
        if ($Value -match 'example\.com|your-|replace-with') {
            throw "$Name still contains an example placeholder; set a real judge endpoint in .env."
        }
    }
}

$Arguments = @('--task-config', $Config)
if ($CheckOnly) { $Arguments += @('--stages', 'check') }
if ($Force) { $Arguments += '--force' }
& $Python (Join-Path $Root 'run.py') @Arguments
exit $LASTEXITCODE
