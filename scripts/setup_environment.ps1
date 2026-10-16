param(
    [switch]$InstallFfmpeg
)

$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Runtime = Join-Path $Root '.runtime'
$Uv = (Get-Command uv -ErrorAction SilentlyContinue).Source

if (-not $Uv) {
    throw 'uv is required. Install it with: winget install --id astral-sh.uv --exact'
}

$env:UV_CACHE_DIR = Join-Path $Runtime 'uv-cache'
$env:UV_PYTHON_INSTALL_DIR = Join-Path $Runtime 'python'
New-Item -ItemType Directory -Force -Path $env:UV_CACHE_DIR, $env:UV_PYTHON_INSTALL_DIR | Out-Null

Write-Host 'Installing project-local Python 3.11...'
& $Uv python install --install-dir $env:UV_PYTHON_INSTALL_DIR 3.11
if ($LASTEXITCODE -ne 0) { throw 'Python installation failed.' }

Write-Host 'Creating .venv and installing base evaluator dependencies...'
$VenvPython = Join-Path $Root '.venv\Scripts\python.exe'
if (-not (Test-Path $VenvPython)) {
    & $Uv venv --python 3.11 (Join-Path $Root '.venv')
    if ($LASTEXITCODE -ne 0) { throw 'Virtual environment creation failed.' }
}
& $Uv pip install --python $VenvPython -r (Join-Path $Root 'requirements.txt')
if ($LASTEXITCODE -ne 0) { throw 'Base dependency installation failed.' }

$Dimensions = @(
    '13_style_visual_control',
    '14_edit_controllable_gen',
    '15_audio_quality_control',
    '16_audio_visual_sync',
    '17_failure_anomaly_control',
    '18_text_visual_consistency',
    '20_performance_emotion'
)
$Modes = @('t2va', 'f2va', 'l2va', 'fl2va', 'r2va')
foreach ($Dimension in $Dimensions) {
    foreach ($Mode in $Modes) {
        New-Item -ItemType Directory -Force -Path (Join-Path $Root "data\cases\$Dimension\$Mode") | Out-Null
    }
}
New-Item -ItemType Directory -Force -Path (Join-Path $Root 'outputs\logs') | Out-Null

$FfmpegBin = Join-Path $Runtime 'ffmpeg\bin'
$env:PATH = "$FfmpegBin;$env:PATH"
if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue) -or -not (Get-Command ffprobe -ErrorAction SilentlyContinue)) {
    if ($InstallFfmpeg) {
        New-Item -ItemType Directory -Force -Path $FfmpegBin | Out-Null
        $Npm = Get-Command npm.cmd -ErrorAction SilentlyContinue
        if ($Npm) {
            $PackageRoot = Join-Path $Runtime 'ffmpeg-npm'
            Write-Host 'Installing local FFmpeg and ffprobe binary packages...'
            & $Npm.Source install --prefix $PackageRoot --no-save --ignore-scripts '@ffmpeg-installer/win32-x64@4.1.0' '@ffprobe-installer/win32-x64@5.1.0'
            if ($LASTEXITCODE -ne 0) { throw 'FFmpeg npm package installation failed.' }
            $FfmpegExe = Get-ChildItem -LiteralPath (Join-Path $PackageRoot 'node_modules\@ffmpeg-installer\win32-x64') -Filter ffmpeg.exe -Recurse -File | Select-Object -First 1
            $FfprobeExe = Get-ChildItem -LiteralPath (Join-Path $PackageRoot 'node_modules\@ffprobe-installer\win32-x64') -Filter ffprobe.exe -Recurse -File | Select-Object -First 1
        } else {
            $Archive = Join-Path $Runtime 'ffmpeg-release-essentials.zip'
            $Download = Join-Path $Runtime 'ffmpeg-release-essentials.download'
            $Extract = Join-Path $Runtime 'ffmpeg-extracted'
            Write-Host 'Downloading the FFmpeg essentials build...'
            Invoke-WebRequest -Uri 'https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip' -OutFile $Download
            Move-Item -LiteralPath $Download -Destination $Archive -Force
            New-Item -ItemType Directory -Force -Path $Extract | Out-Null
            Expand-Archive -LiteralPath $Archive -DestinationPath $Extract -Force
            $FfmpegExe = Get-ChildItem -LiteralPath $Extract -Filter ffmpeg.exe -Recurse -File | Select-Object -First 1
            $FfprobeExe = Get-ChildItem -LiteralPath $Extract -Filter ffprobe.exe -Recurse -File | Select-Object -First 1
        }
        if (-not $FfmpegExe -or -not $FfprobeExe) { throw 'FFmpeg installation did not provide ffmpeg.exe and ffprobe.exe.' }
        Copy-Item -LiteralPath $FfmpegExe.FullName -Destination (Join-Path $FfmpegBin 'ffmpeg.exe') -Force
        Copy-Item -LiteralPath $FfprobeExe.FullName -Destination (Join-Path $FfmpegBin 'ffprobe.exe') -Force
        Write-Host "FFmpeg installed in $FfmpegBin"
    } else {
        Write-Warning 'FFmpeg/ffprobe are required for media evaluation. Run: .\scripts\setup_environment.ps1 -InstallFfmpeg'
    }
}

Write-Host ''
Write-Host 'Environment setup complete.'
Write-Host 'Next: add judge endpoint settings to .env, then place cases under data\cases.'
